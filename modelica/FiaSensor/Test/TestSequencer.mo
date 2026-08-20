within FiaSensor.Test;
model TestSequencer
  "Checks FiaSequencer's state dwell times against
  src/fia_settings.py::FiaSettings.DEFAULTS -- cyclePeriodS=900,
  primeS=60, baselineS=10, loadS=15, acquireS=70 -- cross-checked against
  tools/fia_sim.py's printed trace for the same defaults, since that tool
  already exercises the reference Python implementation.

  absorbanceIn is held at 0 (well under wash_threshold=0.002), so WASH
  should exit on its first check rather than timing out at
  wash_timeout_s=120 -- this model does not exercise that timeout path,
  see run_tests.mos for expected assertions."

  FiaSensor.Sequencer.FiaSequencer seq;
equation
  seq.absorbanceIn = 0.0;
end TestSequencer;
