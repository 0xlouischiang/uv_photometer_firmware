within FiaSensor.Sequencer;
type FiaStates = enumeration(
    IDLE,
    PRIME,
    BASELINE,
    LOAD,
    INJECT,
    ACQUIRE,
    ANALYZE,
    WASH,
    FAULT)
  "Mirrors src/fia_constants.py::State. Order and names must match exactly
  -- FiaSequencer.mo's transition comments cite fia_sequencer.py by state
  name, and a renumbering there with no matching rename here would silently
  desync the two.";
