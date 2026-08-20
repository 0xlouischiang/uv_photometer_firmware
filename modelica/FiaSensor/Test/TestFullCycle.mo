within FiaSensor.Test;
model TestFullCycle
  "Runs Plant.mo through one full injection-to-baseline cycle and checks
  the absorbance peak lands inside the design doc's acceptance window
  (AMMONIA_FIA_SENSOR_DESIGN.md section 3.2 / src/fia_settings.py's
  peak_window_s = [20, 50] s after t0) and that A/30.3 (the NH3-N
  calibration's fit_coef[1], examples/calibrations.json) gives a
  plausible mg/L-N recovery given the sampleConc this model injects.

  Uses shortened prime/baseline/load/cycle durations (see the extends
  clause) purely to keep the simulated span short -- acquireS is left at
  its real 70 s default since the peak timing being checked is measured
  from t0 (the injection instant), which acquireS does not affect."

  extends FiaSensor.Plant(seq(primeS=5, baselineS=2, loadS=3, cyclePeriodS=1));
end TestFullCycle;
