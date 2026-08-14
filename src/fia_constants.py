"""
Constants for the flow injection analysis (FIA) cycle.

Deliberately has no imports. This module and the rest of the FIA core
(fia_peak, fia_actuators, fia_settings, fia_sequencer) must stay importable on
a host so the state machine can be tested without hardware. Importing
`constants` here would pull in `board` and `iorodeo_as7331` and break that.
"""

# Mirrors constants.CHANNEL_UVC. Duplicated rather than imported, see above.
# fia_hardware asserts the two agree at import time on device.
CHANNEL_UVC = 2


class State:
    """States of the FIA cycle. See AMMONIA_FIA_SENSOR_DESIGN.md section 3.2."""
    IDLE     = 0
    PRIME    = 1
    BASELINE = 2
    LOAD     = 3
    INJECT   = 4
    ACQUIRE  = 5
    ANALYZE  = 6
    WASH     = 7
    FAULT    = 8


STATE_TO_STR = {
        State.IDLE     : 'IDLE',
        State.PRIME    : 'PRIME',
        State.BASELINE : 'BASELINE',
        State.LOAD     : 'LOAD',
        State.INJECT   : 'INJECT',
        State.ACQUIRE  : 'ACQUIRE',
        State.ANALYZE  : 'ANALYZE',
        State.WASH     : 'WASH',
        State.FAULT    : 'FAULT',
        }


class Actuator:
    """The six actuators of the manifold, plus the UVC LED."""
    SAMPLE_PUMP   = 'sample_pump'
    CARRIER_PUMP  = 'carrier_pump'
    ACCEPTOR_PUMP = 'acceptor_pump'
    INJECT_VALVE  = 'inject_valve'
    SELECT_VALVE  = 'select_valve'
    WASTE_VALVE   = 'waste_valve'
    LED           = 'led'


PUMPS = (Actuator.SAMPLE_PUMP, Actuator.CARRIER_PUMP, Actuator.ACCEPTOR_PUMP)


class Switch:
    """States of an on/off actuator (pumps, LED, waste valve)."""
    OFF = 'OFF'
    ON  = 'ON'


class InjectPos:
    """Injection valve positions."""
    LOAD   = 'LOAD'
    INJECT = 'INJECT'


class SelectPos:
    """Sample/standard selector valve positions."""
    SAMPLE   = 'SAMPLE'
    STANDARD = 'STANDARD'
    WASH     = 'WASH'


class Reject:
    """Why a result is not quantifiable. NONE means the result is good."""
    NONE         = 0
    WINDOW_EARLY = 1
    WINDOW_LATE  = 2
    OVERFLOW     = 3
    NO_PEAK      = 4


REJECT_TO_STR = {
        Reject.NONE         : 'ok',
        Reject.WINDOW_EARLY : 'peak before window',
        Reject.WINDOW_LATE  : 'peak after window',
        Reject.OVERFLOW     : 'sensor overflow',
        Reject.NO_PEAK      : 'no peak',
        }


class Fault:
    """Why the sequencer stopped. NONE means it is running normally."""
    NONE          = 0
    BASELINE_RSD  = 1
    WASH_TIMEOUT  = 2
    SENSOR_IO     = 3
    BUFFER_FULL   = 4
    ABORTED       = 5


FAULT_TO_STR = {
        Fault.NONE         : 'none',
        Fault.BASELINE_RSD : 'baseline unstable',
        Fault.WASH_TIMEOUT : 'wash did not return to baseline',
        Fault.SENSOR_IO    : 'sensor io error',
        Fault.BUFFER_FULL  : 'sample buffer full',
        Fault.ABORTED      : 'aborted',
        }


class Mode:
    """Cycle scheduling. See the IDLE discussion in the plan."""
    CONTINUOUS = 'continuous'
    DUTY_CYCLE = 'duty_cycle'


NS_PER_S = 1000000000
