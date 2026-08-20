within FiaSensor.Manifold;
model Pump
  "Gated volumetric flow-rate source. No head/pressure -- see package doc.

  Mirrors ActuatorSet: a pump is just Switch.ON/OFF in fia_actuators.py;
  the actual flow rate is a design constant (design doc section 3/4), not
  a measured or controlled quantity, so ratedFlow_mLmin is a parameter and
  `on` is the only input."

  parameter Real ratedFlow_mLmin "flow rate while on, mL/min (design doc section 3)";
  input Boolean on;
  output Real flowRate "volumetric flow, uL/s (package-internal unit, see Units.mo)";
equation
  flowRate = if on then ratedFlow_mLmin*FiaSensor.Units.mLmin else 0.0;
end Pump;
