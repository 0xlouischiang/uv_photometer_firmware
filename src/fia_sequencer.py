"""
The FIA cycle state machine.

    IDLE -> PRIME -> BASELINE -> LOAD -> INJECT -> ACQUIRE -> ANALYZE -> WASH

See AMMONIA_FIA_SENSOR_DESIGN.md section 3.2. Timing determinism is the whole
method, so two rules are non-negotiable here:

  - Every transition is driven by elapsed time, never by loop iteration count.
    update() is non-blocking and may be called at any rate; the transition
    timestamps come out the same either way.
  - t=0 for the acquisition is stamped in the same breath as the injection valve
    write, so peak time is measured from the actual actuation.

Sample buffers are preallocated once in __init__ and written by index, and
gc.collect() is confined to IDLE and PRIME. An allocation during ACQUIRE invites
a GC pause, and GC pauses are the jitter the design doc names as the dominant
method risk.

Imports `array`, `math` and `time` only -- no board, no ulab -- so the whole
state machine is testable on a host with an injected clock.
"""

import array
import gc
import time

import fia_peak
from fia_constants import Actuator
from fia_constants import Fault
from fia_constants import InjectPos
from fia_constants import Mode
from fia_constants import NS_PER_S
from fia_constants import Reject
from fia_constants import SelectPos
from fia_constants import State
from fia_constants import STATE_TO_STR
from fia_constants import Switch


# States whose entry action is the whole state: they have no wait condition, so
# they must not consume an update() call. See _update.
TRANSIENT_STATES = (State.INJECT, State.ANALYZE)


class SensorError(Exception):
    """Raised by a reader when the sensor is unreachable."""
    pass


class FiaSequencer:
    """
    Runs the FIA cycle.

    reader     -- callable returning (raw_signal, raw_reference, overflow).
                  raw_reference is None on a single-beam build. Raises
                  SensorError if the sensor is gone.
    actuators  -- an ActuatorSet.
    settings   -- a FiaSettings.
    now_ns     -- monotonic nanosecond clock. Injected so tests can drive it.
    on_result  -- optional callable(PeakResult) invoked at ANALYZE.
    """

    def __init__(self, reader, actuators, settings,
                 now_ns=time.monotonic_ns, on_result=None, on_transition=None):
        self.reader = reader
        self.actuators = actuators
        self.settings = settings
        self.now_ns = now_ns
        self.on_result = on_result
        # on_transition(state, t_ns) fires on every _enter, including transients
        # that update() drains internally and re-entry into the same state.
        # Without it a caller cannot observe INJECT or a baseline retry.
        self.on_transition = on_transition

        cap = settings.sample_capacity
        self._t_buf = array.array('f', bytes(4*cap))
        self._a_buf = array.array('f', bytes(4*cap))
        self._cap = cap

        bcap = settings.baseline_capacity
        self._b_buf = array.array('f', bytes(4*bcap))
        self._bcap = bcap

        # Reused so ANALYZE allocates nothing.
        self._result = fia_peak.PeakResult()

        self._state = State.IDLE
        self._t_entry = 0
        self._t0 = 0
        self._next_sample_ns = 0
        self._sample_dt_ns = int(settings.sample_dt_s*NS_PER_S)
        # Cap on how much lateness a transition may carry over. Generous enough
        # to absorb a slow call rate, small enough that a long stall
        # resynchronises rather than compounding. See _enter.
        self._max_carry_ns = int(2.0*NS_PER_S)

        self._n = 0
        self._bn = 0
        self._baseline_attempt = 0

        self.blank_value = None
        self.blank_reference = None
        self.injection_count = 0
        self.late_samples = 0
        self.fault_reason = Fault.NONE
        self.last_result = None
        self.last_absorbance = None
        self.baseline_rsd = None
        self.baseline_attempts = 0

        self._next_cycle_ns = None
        self._led_on_ns = None
        self.led_on_s = None
        self._is_standard = False

        # Increments on every _enter, including re-entry into the same state, so
        # a baseline retry is observable to a caller watching transitions.
        self.transition_count = 0

    # ------------------------------------------------------------------ state

    @property
    def state(self):
        return self._state

    @property
    def t0_ns(self):
        """Timing origin of the current or most recent injection."""
        return self._t0

    @property
    def n_samples(self):
        return self._n

    @property
    def elapsed_s(self):
        """Seconds since entering the current state."""
        return (self.now_ns() - self._t_entry)/NS_PER_S

    @property
    def acquire_elapsed_s(self):
        """Seconds since the injection valve fired."""
        return (self.now_ns() - self._t0)/NS_PER_S

    def samples(self):
        """(t, absorbance) pairs of the last acquisition. For plotting/logging."""
        return [(self._t_buf[i], self._a_buf[i]) for i in range(self._n)]

    # ------------------------------------------------------------- public api

    def start(self):
        """Reset to IDLE and arm the cycle. Also clears a fault."""
        self.fault_reason = Fault.NONE
        self._baseline_attempt = 0
        self.baseline_attempts = 0
        self._enter(State.IDLE)
        return self._state

    def abort(self, reason=Fault.ABORTED):
        """Stop immediately, actuators safe."""
        self.fault_reason = reason
        self._enter(State.FAULT)
        return self._state

    def update(self):
        """
        Advance the state machine. Non-blocking; returns the current state.

        Call as often as convenient. Transitions fire on elapsed time, so the
        call rate affects only how promptly they are noticed, never when they
        are deemed to have happened.
        """
        try:
            return self._update()
        except SensorError:
            self.fault_reason = Fault.SENSOR_IO
            self._enter(State.FAULT)
            return self._state

    # ------------------------------------------------------------- internals

    def _update(self):
        """
        Dispatch, then settle through any transient states.

        INJECT and ANALYZE have no wait condition -- their entry action is the
        whole state. Letting each consume an update() call would make every
        downstream transition land one tick late, which is precisely the
        loop-rate dependence this design exists to avoid. So they are drained
        within the same call.
        """
        for _ in range(len(STATE_TO_STR)):
            before = self._state
            self._dispatch()
            if self._state == before:
                break
            if self._state not in TRANSIENT_STATES:
                break
        return self._state

    def _dispatch(self):
        state = self._state
        now = self.now_ns()

        if state == State.IDLE:
            if self.settings.mode == Mode.CONTINUOUS:
                self._enter(State.PRIME)
            elif self._next_cycle_ns is None or now >= self._next_cycle_ns:
                self._enter(State.PRIME)

        elif state == State.PRIME:
            # Pumps purge air while the LED reaches thermal equilibrium. The
            # warm-up is mandatory: junction temperature drift in the first
            # minute exceeds the analytical signal at low concentrations.
            if self._due(now, self.settings.prime_s):
                self._enter(State.BASELINE,
                            self._deadline(self.settings.prime_s))

        elif state == State.BASELINE:
            self._sample_baseline(now)
            if self._due(now, self.settings.baseline_s):
                self._finish_baseline(self._deadline(self.settings.baseline_s))

        elif state == State.LOAD:
            if self._due(now, self.settings.load_s):
                self._enter(State.INJECT, self._deadline(self.settings.load_s))

        elif state == State.INJECT:
            # Entry action fired the valve and stamped t0; nothing to wait for.
            self._enter(State.ACQUIRE)

        elif state == State.ACQUIRE:
            self._sample_acquire(now)
            if self._n >= self._cap:
                self._enter(State.ANALYZE)
            elif (now - self._t0) >= int(self.settings.acquire_s*NS_PER_S):
                # Measured from t0, the actuation, not from state entry.
                self._enter(
                        State.ANALYZE,
                        self._t0 + int(self.settings.acquire_s*NS_PER_S))

        elif state == State.ANALYZE:
            # Entry action did the work.
            self._enter(State.WASH)

        elif state == State.WASH:
            absorbance = self._read_absorbance()
            if absorbance is not None and absorbance < self.settings.wash_threshold:
                self._enter(State.IDLE)
            elif self._due(now, self.settings.wash_timeout_s):
                self.fault_reason = Fault.WASH_TIMEOUT
                self._enter(State.FAULT,
                            self._deadline(self.settings.wash_timeout_s))

        # FAULT is terminal until start() is called.
        return self._state

    def _due(self, now, duration_s):
        return (now - self._t_entry) >= int(duration_s*NS_PER_S)

    def _deadline(self, duration_s):
        """When the current state was *due* to end, ignoring tick granularity."""
        return self._t_entry + int(duration_s*NS_PER_S)

    def _enter(self, state, t_entry=None):
        """
        Set state and run its entry action, stamping the entry time first.

        t_entry defaults to now, but a timed transition passes the deadline it
        just met instead. Otherwise each state would start late by up to one
        tick and the error would compound across the cycle, stretching it at
        slow call rates -- the same drift the sample deadline avoids by
        advancing a fixed period rather than measuring from now.

        Carry-over is capped at one state duration so a genuinely stalled caller
        resynchronises instead of trying to catch up through a burst.
        """
        now = self.now_ns()
        if t_entry is None or t_entry > now:
            t_entry = now
        elif (now - t_entry) > self._max_carry_ns:
            t_entry = now

        self._state = state
        self._t_entry = t_entry
        self.transition_count += 1
        if self.on_transition is not None:
            self.on_transition(state, now)

        if state == State.IDLE:
            self._stop_led(now)
            self.actuators.all_off()
            if self.settings.mode == Mode.DUTY_CYCLE:
                self._next_cycle_ns = now + int(
                        self.settings.cycle_period_s*NS_PER_S)
            else:
                self._next_cycle_ns = None
            # Safe to collect: no acquisition in flight.
            gc.collect()

        elif state == State.PRIME:
            gc.collect()
            self._start_led(now)
            self.actuators.set(Actuator.LED, Switch.ON)
            self.actuators.set_pumps(Switch.ON)
            self.actuators.set(Actuator.SELECT_VALVE, SelectPos.SAMPLE)
            self.actuators.set(Actuator.INJECT_VALVE, InjectPos.LOAD)
            self.actuators.set(Actuator.WASTE_VALVE, Switch.ON)

        elif state == State.BASELINE:
            self._bn = 0
            self.baseline_rsd = None
            self.baseline_attempts += 1
            self._next_sample_ns = now

        elif state == State.LOAD:
            # Every tenth injection reads a mid-range standard instead of
            # sample, for drift correction (design doc section 3.2).
            every = self.settings.standard_every
            self._is_standard = bool(
                    every and (self.injection_count + 1) % every == 0)
            position = SelectPos.STANDARD if self._is_standard else SelectPos.SAMPLE
            self.actuators.set(Actuator.SELECT_VALVE, position)
            self.actuators.set(Actuator.INJECT_VALVE, InjectPos.LOAD)

        elif state == State.INJECT:
            self.actuators.set(Actuator.INJECT_VALVE, InjectPos.INJECT)
            self._t0 = self.now_ns()   # timing origin, at the actuation
            self._n = 0
            self.late_samples = 0
            # The result object is reused, so clear the sticky overflow flag
            # from the previous injection.
            self._result.reject = Reject.NONE
            self._next_sample_ns = self._t0
            self.injection_count += 1

        elif state == State.ANALYZE:
            self._analyze()

        elif state == State.WASH:
            self.actuators.set(Actuator.SELECT_VALVE, SelectPos.WASH)

        elif state == State.FAULT:
            self._stop_led(now)
            self.actuators.all_off()

    # ---------------------------------------------------------------- the led

    def _start_led(self, now):
        if self._led_on_ns is None:
            self._led_on_ns = now

    def _stop_led(self, now):
        if self._led_on_ns is not None:
            self.led_on_s = (now - self._led_on_ns)/NS_PER_S
            self._led_on_ns = None

    # ------------------------------------------------------------- baselining

    def _sample_baseline(self, now):
        """
        Accumulate raw counts of the flowing reagent.

        Raw counts, not absorbance -- there is no blank yet; establishing it is
        the point of this state.
        """
        if now < self._next_sample_ns:
            return
        if self._bn >= self._bcap:
            return
        raw, reference, overflow = self.reader()
        self._b_buf[self._bn] = raw
        self._bn += 1
        self._advance_sample_deadline(now)
        # Reference channel blank is a running mean; it needs no rsd gate of
        # its own since it tracks the same lamp.
        if reference is not None:
            if self.blank_reference is None or self._bn == 1:
                self.blank_reference = float(reference)
            else:
                k = 1.0/self._bn
                self.blank_reference += k*(float(reference) - self.blank_reference)

    def _finish_baseline(self, t_deadline=None):
        """
        Gate the baseline on stability, then adopt it as the blank.

        Accept only if RSD < 0.3 % (design doc). Mean rather than median: the
        rsd check has already established the trace is stable, so a median buys
        nothing and would cost a sort. Colorimeter.blank_sensor uses a median
        because it has no such gate.
        """
        self.baseline_rsd = fia_peak.rsd(self._b_buf, self._bn)
        avg = fia_peak.mean(self._b_buf, self._bn)

        ok = (self.baseline_rsd is not None
              and avg is not None
              and avg > 0.0
              and self.baseline_rsd < self.settings.baseline_rsd_max)

        if ok:
            self.blank_value = avg
            self._baseline_attempt = 0
            self._enter(State.LOAD, t_deadline)
            return

        # A transient bubble clears on a retry; a dead pump does not.
        self._baseline_attempt += 1
        if self._baseline_attempt > self.settings.baseline_retries:
            self.fault_reason = Fault.BASELINE_RSD
            self._enter(State.FAULT, t_deadline)
        else:
            self._enter(State.BASELINE, t_deadline)

    # ------------------------------------------------------------ acquisition

    def _sample_acquire(self, now):
        """
        One sample into the preallocated buffers. Allocation-free by design.

        The deadline advances by a fixed period rather than from `now`, so a
        late tick does not push every later sample late.
        """
        if now < self._next_sample_ns:
            return
        if self._n >= self._cap:
            return

        raw, reference, overflow = self.reader()
        value = self._absorbance_from(raw, reference)

        if overflow:
            self._result.reject = Reject.OVERFLOW

        self._t_buf[self._n] = (now - self._t0)/NS_PER_S
        self._a_buf[self._n] = value if value is not None else 0.0
        self._n += 1
        self.last_absorbance = value
        self._advance_sample_deadline(now)

    def _advance_sample_deadline(self, now):
        self._next_sample_ns += self._sample_dt_ns
        if self._next_sample_ns <= now:
            # Fell behind by a whole period. Resynchronise rather than sample in
            # a tight burst trying to catch up, and count it as a health signal.
            self.late_samples += 1
            self._next_sample_ns = now + self._sample_dt_ns

    def _absorbance_from(self, raw, reference):
        """
        Absorbance, ratio-corrected against the reference channel when present.

        Dual-beam referencing is mandatory in the wide-range acceptor
        configuration, where hypochlorite baseline absorbance already consumes
        much of the dynamic range (design doc section 3.1).
        """
        if reference is None or self.blank_reference is None:
            return fia_peak.absorbance(raw, self.blank_value)
        if reference <= 0.0 or self.blank_reference <= 0.0:
            return None
        drift = float(reference)/self.blank_reference
        if drift <= 0.0:
            return None
        return fia_peak.absorbance(raw, self.blank_value*drift)

    def _read_absorbance(self):
        raw, reference, overflow = self.reader()
        value = self._absorbance_from(raw, reference)
        self.last_absorbance = value
        return value

    # --------------------------------------------------------------- analysis

    def _analyze(self):
        """
        Height, area, peak time and acceptance. Quantification is the caller's.

        Deliberately does not compute concentration: fia_hardware passes height
        to the existing Calibrations.apply, which keeps ulab off this side of
        the boundary.
        """
        overflowed = self._result.reject == Reject.OVERFLOW
        result = fia_peak.analyze(
                self._t_buf,
                self._a_buf,
                self._n,
                self.settings.window_min_s,
                self.settings.window_max_s,
                result=self._result,
                )
        if overflowed:
            result.reject = Reject.OVERFLOW
        result.is_standard = self._is_standard
        result.late_samples = self.late_samples

        if self._n >= self._cap and self.acquire_elapsed_s < self.settings.acquire_s:
            # Cannot happen with correct sizing; cheap insurance against a
            # misconfigured sample_hz.
            self.fault_reason = Fault.BUFFER_FULL

        self.last_result = result
        if self.on_result is not None:
            self.on_result(result)
