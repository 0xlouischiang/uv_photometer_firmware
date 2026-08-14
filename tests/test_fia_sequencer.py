"""
Tests for the FIA cycle state machine.

The important one is test_transition_times_independent_of_call_rate. Timing
determinism is the whole method (design doc section 3.2), so transitions must
land at the same elapsed times whether update() is called every 5 ms or every
200 ms. A loop-count implementation fails that test outright.
"""

import pytest

import fia_actuators
import fia_sequencer
from fia_constants import Actuator
from fia_constants import Fault
from fia_constants import InjectPos
from fia_constants import Mode
from fia_constants import Reject
from fia_constants import SelectPos
from fia_constants import State
from fia_constants import Switch
from fia_settings import FiaSettings

from fake_clock import FakeClock
from synthetic_peak import Noise
from synthetic_peak import ScriptedReader


NS_PER_S = 1000000000


class Trace(list):
    """
    Records (t_s, state) on every state entry, via the sequencer's callback.

    A callback rather than polling update()'s return value: INJECT and ANALYZE
    are drained inside a single update() call, so polling cannot see them, and a
    baseline retry re-enters the same state and is not a state *change* at all.
    Timestamps come from the sequencer, so they are the times transitions
    actually happened, not when a tick noticed them.
    """

    def record(self, state, t_ns):
        self.append((t_ns/NS_PER_S, state))

    @property
    def states(self):
        return [s for (_, s) in self]

    def first_time(self, state):
        for t, s in self:
            if s == state:
                return t
        return None


def build(settings=None, reader_kwargs=None, mode=Mode.CONTINUOUS,
          trace=None, **overrides):
    """A sequencer wired to a fake clock, logging actuators and a scripted sensor."""
    if settings is None:
        settings = FiaSettings(mode=mode, **overrides)
    clock = FakeClock()
    backend = fia_actuators.LoggingBackend(now_ns=clock.now_ns)
    actuators = fia_actuators.ActuatorSet(backend)
    reader = ScriptedReader(clock, **(reader_kwargs or {}))
    seq = fia_sequencer.FiaSequencer(
            reader, actuators, settings, now_ns=clock.now_ns,
            on_transition=(trace.record if trace is not None else None))
    reader.sequencer = seq
    return seq, clock, backend, reader


def run_cycle(seq, clock, step_s=0.01, limit_s=1200.0):
    """Tick the sequencer until it returns to IDLE or faults."""
    seq.start()
    t_limit = clock.now_s + limit_s
    left_idle = False
    while clock.now_s < t_limit:
        clock.advance(step_s)
        state = seq.update()
        if state != State.IDLE:
            left_idle = True
        elif left_idle:
            return State.IDLE
        if state == State.FAULT:
            return State.FAULT
    return None


# --------------------------------------------------------------- happy path

def test_full_cycle_state_sequence():
    trace = Trace()
    seq, clock, backend, reader = build(trace=trace)
    end = run_cycle(seq, clock)
    assert end == State.IDLE
    assert trace.states == [
            State.IDLE,
            State.PRIME,
            State.BASELINE,
            State.LOAD,
            State.INJECT,
            State.ACQUIRE,
            State.ANALYZE,
            State.WASH,
            State.IDLE,
            ]


def test_transition_times_match_design_doc():
    trace = Trace()
    seq, clock, backend, reader = build(trace=trace)
    run_cycle(seq, clock)

    # 60 s prime, then 10 s baseline, then 15 s load, then inject at t=85 s.
    assert trace.first_time(State.PRIME) == pytest.approx(0.0, abs=0.05)
    assert trace.first_time(State.BASELINE) == pytest.approx(60.0, abs=0.05)
    assert trace.first_time(State.LOAD) == pytest.approx(70.0, abs=0.05)
    assert trace.first_time(State.INJECT) == pytest.approx(85.0, abs=0.05)
    # 70 s acquisition after injection.
    assert trace.first_time(State.ANALYZE) == pytest.approx(155.0, abs=0.05)


def test_result_is_quantifiable_and_populated():
    seq, clock, backend, reader = build()
    run_cycle(seq, clock)
    result = seq.last_result
    assert result is not None
    assert result.reject == Reject.NONE
    assert result.is_ok
    assert result.height == pytest.approx(0.30, rel=0.02)
    assert result.t_peak == pytest.approx(32.0, abs=0.1)
    assert result.area > 0.0
    assert result.ratio == pytest.approx(result.height/result.area)
    assert result.n_samples == pytest.approx(1400, abs=5)


def test_blank_is_established_from_flowing_baseline():
    seq, clock, backend, reader = build()
    run_cycle(seq, clock)
    # Baseline absorbance is zero, so the blank is the raw reagent counts.
    assert seq.blank_value == pytest.approx(reader.blank, rel=1e-3)
    assert seq.baseline_rsd == pytest.approx(0.0, abs=1e-6)


# ------------------------------------------------- the timing-determinism test

def test_transition_times_independent_of_call_rate():
    """
    The load-bearing test: transitions are elapsed-time driven, not loop-count
    driven. A 40x difference in tick rate must not move the transition times.
    """
    fine = Trace()
    seq_a, clock_a, _, _ = build(trace=fine)
    run_cycle(seq_a, clock_a, step_s=0.005)

    coarse = Trace()
    seq_b, clock_b, _, _ = build(trace=coarse)
    run_cycle(seq_b, clock_b, step_s=0.2)

    assert fine.states == coarse.states

    # Each transition is *noticed* up to one tick late, but the time it is
    # deemed to have happened carries over, so the lag never accumulates.
    for (t_fine, state), (t_coarse, _) in zip(fine, coarse):
        assert t_coarse == pytest.approx(t_fine, abs=0.42), state

    # The strong claim: for every deadline-driven transition the offset is one
    # tick and no more, even 155 s into the cycle. A per-state delay would
    # compound to seconds by ANALYZE.
    for state in (State.BASELINE, State.LOAD, State.INJECT, State.ACQUIRE,
                  State.ANALYZE, State.WASH):
        lag = coarse.first_time(state) - fine.first_time(state)
        assert lag == pytest.approx(0.195, abs=0.01), state


def test_wash_exit_is_sensor_driven_not_deadline_driven():
    # WASH leaves when absorbance falls below threshold, so unlike every other
    # transition it cannot resolve faster than the caller ticks. One extra tick
    # of lag here is inherent, not drift.
    fine = Trace()
    seq_a, clock_a, _, _ = build(trace=fine)
    run_cycle(seq_a, clock_a, step_s=0.005)

    coarse = Trace()
    seq_b, clock_b, _, _ = build(trace=coarse)
    run_cycle(seq_b, clock_b, step_s=0.2)

    def wash_to_idle(trace):
        t_wash = trace.first_time(State.WASH)
        t_idle = [t for (t, s) in trace if s == State.IDLE][-1]
        return t_idle - t_wash

    assert wash_to_idle(fine) == pytest.approx(0.005, abs=0.001)
    assert wash_to_idle(coarse) == pytest.approx(0.2, abs=0.001)


def test_peak_time_stable_across_call_rates():
    # Same point, expressed in the quantity that actually matters.
    seq_a, clock_a, _, _ = build()
    run_cycle(seq_a, clock_a, step_s=0.005)
    seq_b, clock_b, _, _ = build()
    run_cycle(seq_b, clock_b, step_s=0.2)
    assert seq_a.last_result.t_peak == pytest.approx(
            seq_b.last_result.t_peak, abs=0.25)
    assert seq_a.last_result.height == pytest.approx(
            seq_b.last_result.height, rel=0.02)


def test_t0_coincides_with_injection_valve_actuation():
    seq, clock, backend, reader = build()
    run_cycle(seq, clock)
    injects = [(t, s) for (t, s) in backend.entries_for(Actuator.INJECT_VALVE)
               if s == InjectPos.INJECT]
    assert len(injects) == 1
    t_valve, _ = injects[0]
    # Not merely close: the valve write and the timing origin are one event.
    assert t_valve == seq.t0_ns


def test_sample_count_matches_configured_rate():
    seq, clock, backend, reader = build()
    run_cycle(seq, clock, step_s=0.01)
    # 70 s at 20 Hz.
    assert seq.n_samples == pytest.approx(1400, abs=5)
    assert seq.late_samples == 0


def test_coarse_ticks_are_counted_as_late_samples():
    # Ticking slower than the sample period cannot magically produce 20 Hz;
    # the shortfall must be reported, not hidden.
    seq, clock, backend, reader = build()
    run_cycle(seq, clock, step_s=0.2)
    assert seq.n_samples < 1400
    assert seq.late_samples > 0
    assert seq.last_result.late_samples == seq.late_samples


# ----------------------------------------------------------- window rejection

def test_late_peak_is_flagged_but_cycle_completes():
    seq, clock, backend, reader = build(
            reader_kwargs={'t_peak': 60.0, 'shape': 0.2})
    end = run_cycle(seq, clock)
    # A rejected injection is not a fault -- the instrument is fine.
    assert end == State.IDLE
    assert seq.fault_reason == Fault.NONE
    assert seq.last_result.reject == Reject.WINDOW_LATE
    assert not seq.last_result.is_ok


def test_early_peak_is_flagged():
    seq, clock, backend, reader = build(
            reader_kwargs={'t_peak': 8.0, 'shape': 0.2})
    end = run_cycle(seq, clock)
    assert end == State.IDLE
    assert seq.last_result.reject == Reject.WINDOW_EARLY


def test_overflow_flags_the_result_without_faulting():
    seq, clock, backend, reader = build()
    reader.overflow = True
    end = run_cycle(seq, clock)
    assert end == State.IDLE
    assert seq.fault_reason == Fault.NONE
    assert seq.last_result.reject == Reject.OVERFLOW


def test_overflow_flag_does_not_leak_into_the_next_injection():
    seq, clock, backend, reader = build()
    reader.overflow = True
    run_cycle(seq, clock)
    assert seq.last_result.reject == Reject.OVERFLOW
    reader.overflow = False
    run_cycle(seq, clock)
    assert seq.last_result.reject == Reject.NONE


# --------------------------------------------------------- baseline rsd gate

def test_quiet_baseline_proceeds_to_load():
    seq, clock, backend, reader = build(
            reader_kwargs={'noise': Noise(rsd=0.0005, seed=7)})
    end = run_cycle(seq, clock)
    assert end == State.IDLE
    assert seq.baseline_rsd < 0.003
    assert seq.baseline_attempts == 1       # accepted first time, no retry


def test_unstable_baseline_retries_then_faults():
    # 3 % noise against a 0.3 % threshold: two retries, then give up. A
    # transient bubble clears on a retry; a dead pump does not.
    trace = Trace()
    seq, clock, backend, reader = build(
            trace=trace, reader_kwargs={'noise': Noise(rsd=0.03, seed=11)})
    end = run_cycle(seq, clock)
    assert end == State.FAULT
    assert seq.fault_reason == Fault.BASELINE_RSD
    # Re-entering BASELINE is not a state *change*, so count attempts.
    assert seq.baseline_attempts == 3              # initial + 2 retries
    assert trace.states.count(State.BASELINE) == 3
    # Never injected: an unstable baseline must not be quantified against.
    assert State.INJECT not in trace.states


def test_fault_leaves_actuators_safe():
    seq, clock, backend, reader = build(
            reader_kwargs={'noise': Noise(rsd=0.03, seed=11)})
    run_cycle(seq, clock)
    assert seq.state == State.FAULT
    assert backend.last_state(Actuator.LED) == Switch.OFF
    for pump in (Actuator.SAMPLE_PUMP, Actuator.CARRIER_PUMP,
                 Actuator.ACCEPTOR_PUMP):
        assert backend.last_state(pump) == Switch.OFF


def test_start_clears_a_fault():
    seq, clock, backend, reader = build(
            reader_kwargs={'noise': Noise(rsd=0.03, seed=11)})
    run_cycle(seq, clock)
    assert seq.state == State.FAULT
    reader.noise = Noise(0.0)
    seq.start()
    assert seq.state == State.IDLE
    assert seq.fault_reason == Fault.NONE


# --------------------------------------------------------------- fault paths

def test_wash_timeout_faults():
    # Absorbance never falls below the wash threshold: a leak, a blockage or
    # exhausted reagent.
    seq, clock, backend, reader = build(reader_kwargs={'wash_tail_a': 0.05})
    end = run_cycle(seq, clock)
    assert end == State.FAULT
    assert seq.fault_reason == Fault.WASH_TIMEOUT
    assert backend.last_state(Actuator.LED) == Switch.OFF


def test_wash_exits_when_absorbance_falls_below_threshold():
    trace = Trace()
    seq, clock, backend, reader = build(
            trace=trace, reader_kwargs={'wash_tail_a': 0.0})
    end = run_cycle(seq, clock)
    assert end == State.IDLE
    t_wash = trace.first_time(State.WASH)
    t_idle = [t for (t, s) in trace if s == State.IDLE][-1]
    # WASH is prompt when the trace is already clean, nothing like the 120 s
    # timeout.
    assert t_idle - t_wash < 1.0


def test_sensor_io_error_faults():
    seq, clock, backend, reader = build()
    seq.start()
    clock.advance(0.01)
    seq.update()
    reader.raise_error = fia_sequencer.SensorError('sensor gone')
    # Into BASELINE, where the sequencer actually reads the sensor. Two ticks:
    # one to enter the state, one to reach a sample deadline.
    clock.advance(61.0)
    seq.update()
    clock.advance(0.1)
    state = seq.update()
    assert state == State.FAULT
    assert seq.fault_reason == Fault.SENSOR_IO
    assert backend.last_state(Actuator.LED) == Switch.OFF


def test_abort_stops_immediately():
    seq, clock, backend, reader = build()
    seq.start()
    clock.advance(10.0)
    seq.update()
    seq.abort()
    assert seq.state == State.FAULT
    assert seq.fault_reason == Fault.ABORTED
    assert backend.last_state(Actuator.LED) == Switch.OFF


# ------------------------------------------------------------- actuator log

def test_led_and_pumps_driven_at_prime():
    seq, clock, backend, reader = build()
    seq.start()
    clock.advance(0.01)
    seq.update()
    assert seq.state == State.PRIME
    assert backend.last_state(Actuator.LED) == Switch.ON
    for pump in (Actuator.SAMPLE_PUMP, Actuator.CARRIER_PUMP,
                 Actuator.ACCEPTOR_PUMP):
        assert backend.last_state(pump) == Switch.ON


def test_injection_valve_sequence_is_load_then_inject():
    seq, clock, backend, reader = build()
    run_cycle(seq, clock)
    positions = [s for (_, s) in backend.entries_for(Actuator.INJECT_VALVE)]
    # LOAD (safe/prime), INJECT, then back to LOAD when IDLE resets.
    assert positions[0] == InjectPos.LOAD
    assert InjectPos.INJECT in positions
    assert positions.index(InjectPos.INJECT) > 0


def test_no_duplicate_consecutive_writes():
    # Entry actions set actuators unconditionally; the shadow dict must absorb
    # the redundancy so the log stays readable and the bus stays quiet.
    seq, clock, backend, reader = build()
    run_cycle(seq, clock)
    last = {}
    for t, name, state in backend.log:
        assert last.get(name, None) != state, (name, state, t)
        last[name] = state


def test_led_off_when_cycle_returns_to_idle():
    seq, clock, backend, reader = build(mode=Mode.DUTY_CYCLE)
    run_cycle(seq, clock)
    assert seq.state == State.IDLE
    assert backend.last_state(Actuator.LED) == Switch.OFF


# -------------------------------------------------------- standard interleave

def test_standard_interleaved_every_tenth_injection():
    seq, clock, backend, reader = build(standard_every=3)
    selections = []
    for _ in range(6):
        run_cycle(seq, clock)
        selections.append(seq.last_result.is_standard)
    # Injections 3 and 6 read the standard, the rest read sample.
    assert selections == [False, False, True, False, False, True]


def test_standard_selection_reaches_the_valve():
    seq, clock, backend, reader = build(standard_every=2)
    run_cycle(seq, clock)
    run_cycle(seq, clock)
    positions = [s for (_, s) in backend.entries_for(Actuator.SELECT_VALVE)]
    assert SelectPos.STANDARD in positions
    assert SelectPos.SAMPLE in positions


def test_standard_every_zero_disables_interleave():
    seq, clock, backend, reader = build(standard_every=0)
    for _ in range(3):
        run_cycle(seq, clock)
        assert seq.last_result.is_standard is False


def test_injection_count_increments():
    seq, clock, backend, reader = build()
    assert seq.injection_count == 0
    run_cycle(seq, clock)
    assert seq.injection_count == 1
    run_cycle(seq, clock)
    assert seq.injection_count == 2


# ----------------------------------------------------------------- duty cycle

def test_duty_cycle_waits_for_the_scheduled_period():
    seq, clock, backend, reader = build(mode=Mode.DUTY_CYCLE,
                                        cycle_period_s=900.0)
    run_cycle(seq, clock)
    assert seq.state == State.IDLE
    t_idle = clock.now_s

    # Well inside the period: still idle, LED still off.
    clock.advance(600.0)
    assert seq.update() == State.IDLE
    assert backend.last_state(Actuator.LED) == Switch.OFF

    # Past it: the next cycle primes.
    clock.advance(310.0)
    assert seq.update() == State.PRIME
    assert clock.now_s - t_idle >= 900.0
    assert backend.last_state(Actuator.LED) == Switch.ON


def test_continuous_mode_starts_next_cycle_immediately():
    seq, clock, backend, reader = build(mode=Mode.CONTINUOUS)
    run_cycle(seq, clock)
    assert seq.state == State.IDLE
    clock.advance(0.01)
    assert seq.update() == State.PRIME


def test_led_on_time_is_measured_not_assumed():
    # The design doc quotes 130 s on per 15 min cycle, but its own state
    # timings sum to 155 s before WASH. Report what actually happened.
    seq, clock, backend, reader = build(mode=Mode.DUTY_CYCLE)
    run_cycle(seq, clock)
    assert seq.led_on_s is not None
    assert seq.led_on_s > 155.0
    assert seq.led_on_s < 160.0


# ------------------------------------------------------- buffers and hygiene

def test_buffers_are_allocated_once_and_reused():
    seq, clock, backend, reader = build()
    t_buf = seq._t_buf
    a_buf = seq._a_buf
    for _ in range(3):
        run_cycle(seq, clock)
    assert seq._t_buf is t_buf
    assert seq._a_buf is a_buf
    assert len(t_buf) == seq.settings.sample_capacity


def test_samples_accessor_returns_the_acquired_trace():
    seq, clock, backend, reader = build()
    run_cycle(seq, clock)
    samples = seq.samples()
    assert len(samples) == seq.n_samples
    t_first, _ = samples[0]
    t_last, _ = samples[-1]
    assert t_first == pytest.approx(0.0, abs=0.05)
    assert t_last == pytest.approx(70.0, abs=0.2)


def test_on_result_callback_fires_once_per_injection():
    seen = []
    settings = FiaSettings(mode=Mode.CONTINUOUS)
    clock = FakeClock()
    backend = fia_actuators.LoggingBackend(now_ns=clock.now_ns)
    actuators = fia_actuators.ActuatorSet(backend)
    reader = ScriptedReader(clock)
    seq = fia_sequencer.FiaSequencer(
            reader, actuators, settings, now_ns=clock.now_ns,
            on_result=seen.append)
    reader.sequencer = seq
    run_cycle(seq, clock)
    run_cycle(seq, clock)
    assert len(seen) == 2
    assert all(r.is_ok for r in seen)


# --------------------------------------------------- dual-beam reference path

def test_reference_channel_cancels_lamp_drift():
    """
    With a reference channel, a lamp that dims between baseline and acquisition
    must not appear as absorbance. This is why dual-beam is mandatory in the
    wide-range acceptor configuration (design doc section 3.1).
    """
    settings = FiaSettings(mode=Mode.CONTINUOUS)
    clock = FakeClock()
    backend = fia_actuators.LoggingBackend(now_ns=clock.now_ns)
    actuators = fia_actuators.ActuatorSet(backend)

    class DriftingReader(ScriptedReader):
        """Signal and reference both fall 20 % once acquisition starts."""

        def __call__(self):
            import fia_constants
            state = self.sequencer.state
            drift = 0.8 if state in (fia_constants.State.ACQUIRE,
                                     fia_constants.State.ANALYZE) else 1.0
            raw, _, overflow = ScriptedReader.__call__(self)
            return raw*drift, 10000.0*drift, overflow

    reader = DriftingReader(clock, reference=10000.0, height=0.0)
    seq = fia_sequencer.FiaSequencer(
            reader, actuators, settings, now_ns=clock.now_ns)
    reader.sequencer = seq
    run_cycle(seq, clock)

    # A flat sample with a dimming lamp: the reference divides the drift out,
    # so measured absorbance stays at zero rather than reading 0.097 AU.
    assert seq.last_result.height == pytest.approx(0.0, abs=0.005)


def test_without_reference_lamp_drift_shows_up_as_signal():
    # The contrapositive, which is the reason the reference channel exists.
    settings = FiaSettings(mode=Mode.CONTINUOUS)
    clock = FakeClock()
    backend = fia_actuators.LoggingBackend(now_ns=clock.now_ns)
    actuators = fia_actuators.ActuatorSet(backend)

    class DriftingReader(ScriptedReader):
        def __call__(self):
            import fia_constants
            state = self.sequencer.state
            drift = 0.8 if state in (fia_constants.State.ACQUIRE,
                                     fia_constants.State.ANALYZE) else 1.0
            raw, ref, overflow = ScriptedReader.__call__(self)
            return raw*drift, ref, overflow

    reader = DriftingReader(clock, reference=None, height=0.0)
    seq = fia_sequencer.FiaSequencer(
            reader, actuators, settings, now_ns=clock.now_ns)
    reader.sequencer = seq
    run_cycle(seq, clock)
    # -log10(0.8) = 0.097 AU of pure artefact.
    assert seq.last_result.height == pytest.approx(0.0969, abs=0.002)
