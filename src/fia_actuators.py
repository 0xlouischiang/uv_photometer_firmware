"""
Actuator abstraction for the FIA manifold.

Six actuators plus the UVC LED. No fluidics hardware exists yet, so the only
backend here is LoggingBackend, which records what would have happened. A real
backend implements one method, `apply`.

Imports nothing platform-specific, so this runs on a host under pytest.
"""

from fia_constants import Actuator
from fia_constants import InjectPos
from fia_constants import PUMPS
from fia_constants import SelectPos
from fia_constants import Switch


class ActuatorBackend:
    """
    Where actuator writes actually go.

    A real implementation would drive an I2C expander -- see BOM item 26 in
    AMMONIA_FIA_SENSOR_DESIGN.md, and ../uv_photometer_micropython/src/aw9523.py
    for a working AW9523 driver to crib from. Two gotchas documented there: 0
    means OUTPUT in the direction register, and both LED-mode registers need
    0xFF written or the outputs appear dead.
    """

    def apply(self, name, state):
        raise NotImplementedError

    def close(self):
        """Release the hardware. Default is a no-op."""
        pass


class LoggingBackend(ActuatorBackend):
    """
    Records actuator writes instead of performing them.

    The log is a list of (t_ns, name, state) tuples. Tests assert against it,
    and tools/fia_sim.py prints it.
    """

    def __init__(self, now_ns=None):
        self._now_ns = now_ns
        self.log = []

    def apply(self, name, state):
        t_ns = self._now_ns() if self._now_ns is not None else None
        self.log.append((t_ns, name, state))

    def clear(self):
        self.log = []

    def entries_for(self, name):
        """Every (t_ns, state) written to one actuator, in order."""
        return [(t, s) for (t, n, s) in self.log if n == name]

    def last_state(self, name):
        for t, n, s in reversed(self.log):
            if n == name:
                return s
        return None


class ActuatorSet:
    """
    The actuators, with redundant writes suppressed.

    A shadow copy of the last written state means a state's entry action can set
    every actuator unconditionally without generating duplicate backend writes.
    That keeps the log readable and, on real hardware, keeps I2C traffic off the
    bus during the acquisition window.
    """

    SAFE_STATES = {
            Actuator.SAMPLE_PUMP   : Switch.OFF,
            Actuator.CARRIER_PUMP  : Switch.OFF,
            Actuator.ACCEPTOR_PUMP : Switch.OFF,
            Actuator.LED           : Switch.OFF,
            # Waste valve energised means open. Left open so the manifold drains
            # rather than holding pressure behind a closed valve.
            Actuator.WASTE_VALVE   : Switch.ON,
            Actuator.INJECT_VALVE  : InjectPos.LOAD,
            Actuator.SELECT_VALVE  : SelectPos.WASH,
            }

    # Explicit order: LED and pumps stop before the valves move, and dict
    # iteration order is not guaranteed on CircuitPython.
    SAFE_ORDER = (
            Actuator.LED,
            Actuator.SAMPLE_PUMP,
            Actuator.CARRIER_PUMP,
            Actuator.ACCEPTOR_PUMP,
            Actuator.INJECT_VALVE,
            Actuator.SELECT_VALVE,
            Actuator.WASTE_VALVE,
            )

    def __init__(self, backend):
        self.backend = backend
        self._shadow = {}

    def set(self, name, state):
        """Write an actuator. Returns True if the backend was touched."""
        if self._shadow.get(name, None) == state:
            return False
        self._shadow[name] = state
        self.backend.apply(name, state)
        return True

    def get(self, name):
        return self._shadow.get(name, None)

    def set_pumps(self, state):
        for name in PUMPS:
            self.set(name, state)

    def all_off(self):
        """Pumps and LED off, valves to safe positions."""
        for name in self.SAFE_ORDER:
            self.set(name, self.SAFE_STATES[name])
