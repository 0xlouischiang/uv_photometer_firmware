"""
Run the FIA cycle on a host, against a fake clock and a synthetic peak.

No fluidics hardware exists yet, so this is how the state machine gets
demonstrated: a full 15-minute cycle completes in well under a second of wall
time because the clock is advanced rather than slept on.

    python tools/fia_sim.py                 # one nominal cycle
    python tools/fia_sim.py --reject-late   # peak outside the window
    python tools/fia_sim.py --cycles 3      # standard interleave
    python tools/fia_sim.py --help

Prints the state transition trace with timestamps, the actuator log, the peak
result, and the measured LED on-time.
"""

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Appended, not prepended: src/code.py would shadow the stdlib `code` module.
for _path in (os.path.join(REPO_ROOT, 'src'), os.path.join(REPO_ROOT, 'tests')):
    if _path not in sys.path:
        sys.path.append(_path)

import fia_actuators                                            # noqa: E402
import fia_sequencer                                            # noqa: E402
from fia_constants import FAULT_TO_STR                          # noqa: E402
from fia_constants import Fault                                 # noqa: E402
from fia_constants import Mode                                  # noqa: E402
from fia_constants import REJECT_TO_STR                         # noqa: E402
from fia_constants import STATE_TO_STR                          # noqa: E402
from fia_constants import State                                 # noqa: E402
from fia_settings import FiaSettings                             # noqa: E402

from fake_clock import FakeClock                                 # noqa: E402
from synthetic_peak import Noise                                # noqa: E402
from synthetic_peak import ScriptedReader                        # noqa: E402

NS_PER_S = 1000000000


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
            description='Run the FIA cycle on a host with a synthetic peak.')
    parser.add_argument('--cycles', type=int, default=1,
                        help='number of injections to run (default 1)')
    parser.add_argument('--reject-late', action='store_true',
                        help='put the peak at 60 s, outside the window')
    parser.add_argument('--reject-early', action='store_true',
                        help='put the peak at 8 s, before the window')
    parser.add_argument('--unstable-baseline', action='store_true',
                        help='3%% baseline noise, to exercise the rsd gate')
    parser.add_argument('--wash-stuck', action='store_true',
                        help='absorbance never clears, to exercise the timeout')
    parser.add_argument('--reference', action='store_true',
                        help='enable the dual-beam reference channel')
    parser.add_argument('--duty-cycle', action='store_true',
                        help='schedule cycles 15 min apart instead of back to back')
    parser.add_argument('--height', type=float, default=0.30,
                        help='peak absorbance (default 0.30)')
    parser.add_argument('--tick-ms', type=float, default=10.0,
                        help='update() interval in ms (default 10)')
    parser.add_argument('--standard-every', type=int, default=10,
                        help='interleave a standard every N injections')
    parser.add_argument('--quiet-log', action='store_true',
                        help='omit the actuator log')
    return parser.parse_args(argv)


def build(args):
    settings = FiaSettings(
            mode=Mode.DUTY_CYCLE if args.duty_cycle else Mode.CONTINUOUS,
            standard_every=args.standard_every,
            )
    clock = FakeClock()
    backend = fia_actuators.LoggingBackend(now_ns=clock.now_ns)
    actuators = fia_actuators.ActuatorSet(backend)

    t_peak = 32.0
    if args.reject_late:
        t_peak = 60.0
    elif args.reject_early:
        t_peak = 8.0

    reader = ScriptedReader(
            clock,
            height=args.height,
            t_peak=t_peak,
            shape=0.2 if (args.reject_late or args.reject_early) else 0.35,
            noise=Noise(rsd=0.03, seed=11) if args.unstable_baseline
                    else Noise(rsd=0.0005, seed=3),
            reference=10000.0 if args.reference else None,
            wash_tail_a=0.05 if args.wash_stuck else 0.0,
            )

    trace = []
    seq = fia_sequencer.FiaSequencer(
            reader, actuators, settings, now_ns=clock.now_ns,
            on_transition=lambda s, t: trace.append((t/NS_PER_S, s)))
    reader.sequencer = seq
    return seq, clock, backend, reader, trace


def run_one(seq, clock, tick_s, limit_s=2400.0):
    """Tick until the cycle returns to IDLE or faults."""
    seq.start()
    t_limit = clock.now_s + limit_s
    left_idle = False
    while clock.now_s < t_limit:
        clock.advance(tick_s)
        state = seq.update()
        if state == State.FAULT:
            return State.FAULT
        if state != State.IDLE:
            left_idle = True
        elif left_idle:
            return State.IDLE
    return None


def print_trace(trace, t_offset=0.0):
    print('  {:>10}  {:<9}  {}'.format('t (s)', 'state', 'elapsed'))
    print('  ' + '-'*40)
    previous = None
    for t, state in trace:
        elapsed = '' if previous is None else '+{:.2f}'.format(t - previous)
        print('  {:>10.3f}  {:<9}  {}'.format(
            t - t_offset, STATE_TO_STR[state], elapsed))
        previous = t


def print_actuator_log(backend, t_offset=0.0):
    print('  {:>10}  {:<14}  {}'.format('t (s)', 'actuator', 'state'))
    print('  ' + '-'*44)
    for t_ns, name, state in backend.log:
        t = (t_ns/NS_PER_S) - t_offset if t_ns is not None else 0.0
        print('  {:>10.3f}  {:<14}  {}'.format(t, name, state))


def print_result(seq):
    result = seq.last_result
    if result is None:
        print('  no result: the cycle did not reach ANALYZE')
        return

    def fmt(value, spec='{:.4f}'):
        return 'n/a' if value is None else spec.format(value)

    print('  peak height    {}  AU'.format(fmt(result.height)))
    print('  peak time      {}  s'.format(fmt(result.t_peak, '{:.2f}')))
    print('  peak area      {}  AU*s'.format(fmt(result.area)))
    print('  height/area    {}  (health metric)'.format(fmt(result.ratio)))
    print('  samples        {} ({} late)'.format(
        result.n_samples, result.late_samples))
    print('  acceptance     {}'.format(REJECT_TO_STR[result.reject]))
    print('  is standard    {}'.format(result.is_standard))
    if not result.is_ok:
        print('  -> flagged, not reported as a concentration')


def print_health(seq):
    print('  blank (counts) {}'.format(
        'n/a' if seq.blank_value is None else '{:.1f}'.format(seq.blank_value)))
    print('  baseline rsd   {}'.format(
        'n/a' if seq.baseline_rsd is None
        else '{:.4f} %'.format(seq.baseline_rsd*100.0)))
    print('  baseline tries {}'.format(seq.baseline_attempts))
    print('  led on time    {}'.format(
        'still on' if seq.led_on_s is None
        else '{:.1f} s per cycle'.format(seq.led_on_s)))
    print('  fault          {}'.format(FAULT_TO_STR[seq.fault_reason]))


def main(argv=None):
    args = parse_args(argv)
    seq, clock, backend, reader, trace = build(args)
    tick_s = args.tick_ms/1000.0

    print('=== FIA cycle simulation ===')
    print('mode {}, tick {:.0f} ms, sample {:.0f} Hz, window [{:.0f}, {:.0f}] s'
          .format(seq.settings.mode, args.tick_ms, seq.settings.sample_hz,
                  seq.settings.window_min_s, seq.settings.window_max_s))
    if reader.reference is not None:
        print('dual-beam reference channel enabled')

    for cycle in range(args.cycles):
        mark = len(trace)
        log_mark = len(backend.log)
        t_start = clock.now_s

        outcome = run_one(seq, clock, tick_s)

        print('')
        print('--- cycle {} of {} ---'.format(cycle + 1, args.cycles))
        print_trace(trace[mark:])
        if not args.quiet_log:
            print('')
            print('actuator log')
            print_actuator_log(_slice_backend(backend, log_mark))
        print('')
        print('result')
        print_result(seq)
        print('')
        print('health')
        print_health(seq)
        print('')
        print('wall-clock cycle span {:.1f} s of simulated time'.format(
            clock.now_s - t_start))

        if outcome == State.FAULT:
            print('')
            print('cycle ended in FAULT: {}'.format(
                FAULT_TO_STR[seq.fault_reason]))
            return 1
        if outcome is None:
            print('')
            print('cycle did not complete within the simulation limit')
            return 1

    return 0


class _SlicedBackend:
    """A view of the tail of an actuator log, for per-cycle printing."""

    def __init__(self, log):
        self.log = log


def _slice_backend(backend, mark):
    return _SlicedBackend(backend.log[mark:])


if __name__ == '__main__':
    sys.exit(main())
