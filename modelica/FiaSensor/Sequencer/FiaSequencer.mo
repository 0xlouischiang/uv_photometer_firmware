within FiaSensor.Sequencer;
model FiaSequencer
  "Port of src/fia_sequencer.py::FiaSequencer -- the FIA cycle timing layer.

  IDLE -> PRIME -> BASELINE -> LOAD -> INJECT -> ACQUIRE -> ANALYZE -> WASH -> IDLE

  Faithful to the Python state machine's transition *timing* (every
  duration below is copied from src/fia_settings.py::FiaSettings.DEFAULTS,
  not re-guessed), but not to its signal-quality machinery: the Python
  version gates BASELINE on a measured RSD and WASH on a measured
  absorbance because it is reading a real, noisy sensor. This model reads
  its own noiseless simulated absorbance (absorbanceIn), so BASELINE always
  accepts on the first pass and WASH's exit condition is the same threshold
  compare but never needs a retry. baselineRsdMax/baselineRetries are kept
  as parameters (for symmetry with FiaSettings and in case a future version
  adds simulated sensor noise) but are not wired to any decision here.

  Three OpenModelica 1.25.4 constraints shaped how this is written -- each
  found with a minimal probe model, see modelica/FiaSensor/README.md for
  all three:
    1. The graphical initialState/transition syntax fails at C code
       generation on this version, so this uses a plain `discrete
       FiaStates` variable instead.
    2. An equation-section `when ... elsewhen` chain on that variable fails
       backend sorting (analyseStrongComponentBlock). The fix is one
       `algorithm`-section `when` block per transition (no elsewhen),
       which is also what makes each block read as one `elif` branch of
       fia_sequencer.py::_dispatch, in order.
    3. ANY Boolean or Integer defined by an equation-section alias of a
       `state_ == FiaStates.X` comparison ALSO breaks the backend the same
       way, the instant that alias is reused inside a later `when`-guard
       or read by another component -- this is not limited to comparisons
       against the transient states. The fix is the same shape as #2:
       every output derived from state_ (samplePumpOn, ledOn,
       injectionCount, etc.) is a `discrete` variable written only inside
       `algorithm`-section `when` blocks, holding its value between
       events like a level, never an `equation`-section `x = state_ ==
       FiaStates.Y` alias. This is why every output below is set
       explicitly in every transition that changes it, rather than derived
       once from `state`.
  A transient state (INJECT, ANALYZE -- see TRANSIENT_STATES in
  fia_sequencer.py) is entered and left by two `when` blocks that both
  fire within the same discrete event, so it never occupies a nonzero span
  of simulated time. Downstream models must not detect the injection
  instant by comparing `state` to FiaStates.INJECT (that hits constraint 3
  above); they watch change(injectionCount) instead -- see this model's
  injectionCount output."

  import FiaSensor.Sequencer.FiaStates;

  parameter Real primeS = 60.0 "PRIME duration, s (FiaSettings.DEFAULTS['prime_s'])";
  parameter Real baselineS = 10.0 "BASELINE duration, s (['baseline_s'])";
  parameter Real loadS = 15.0 "LOAD duration, s (['load_s'])";
  parameter Real acquireS = 70.0 "ACQUIRE duration measured from t0, s (['acquire_s'])";
  parameter Real washThreshold = 0.002 "WASH exit absorbance, AU (['wash_threshold'])";
  parameter Real washTimeoutS = 120.0 "WASH -> FAULT timeout, s (['wash_timeout_s'])";
  parameter Real cyclePeriodS = 900.0 "IDLE dwell before the next PRIME, s (['cycle_period_s'])";
  parameter Integer standardEvery = 10 "interleave a standard every N injections (['standard_every'])";
  parameter Real baselineRsdMax = 0.003 "kept for parity with FiaSettings; unused, see model docstring";
  parameter Integer baselineRetries = 2 "kept for parity with FiaSettings; unused, see model docstring";

  input Real absorbanceIn "simulated absorbance at the flow cell, AU";

  output Boolean samplePumpOn(start=false);
  output Boolean carrierPumpOn(start=false);
  output Boolean acceptorPumpOn(start=false);
  output Boolean ledOn(start=false);
  output Boolean sampleIsStandard(start=false) "true if the current/most recent injection drew the mid-range standard";
  output Real t0(start=0) "timing origin of the current/most recent injection, s (like fia_sequencer.py's t0_ns/NS_PER_S)";
  output FiaStates state(start=FiaStates.IDLE);
  output Integer injectionCount(start=0)
    "increments once per completed injection. Downstream models detect the
    injection instant with change(injectionCount) rather than comparing
    `state` to FiaStates.INJECT -- see constraint 3 in the model
    docstring above.";

protected
  discrete Real tEntry(start=0);

equation
  // state, injectionCount, t0, sampleIsStandard and every pump/LED output
  // above are declared as top-level `output` variables (not aliased from
  // a protected copy) and are written directly inside the algorithm
  // section below, in every transition that changes them. There is
  // deliberately no equation-section derivation of any of them from
  // `state` -- see constraint 3 in the docstring.

algorithm
  // IDLE -> PRIME, after cyclePeriodS. Continuous mode (fia_sequencer's
  // Mode.CONTINUOUS) would re-enter PRIME immediately; this model only
  // implements the duty-cycle timing since that is FiaSettings' default
  // and the doc's headline number (900 s cycle).
  when state == FiaStates.IDLE and (time - tEntry) >= cyclePeriodS then
    state := FiaStates.PRIME;
    tEntry := time;
    // fia_sequencer.py's PRIME entry action: LED on, all pumps on,
    // selector at SAMPLE, injection valve at LOAD.
    samplePumpOn := true;
    carrierPumpOn := true;
    acceptorPumpOn := true;
    ledOn := true;
  end when;

  when state == FiaStates.PRIME and (time - tEntry) >= primeS then
    state := FiaStates.BASELINE;
    tEntry := time;
  end when;

  // BASELINE always accepts here -- see the model docstring on why the
  // Python version's RSD gate has nothing to gate in a noiseless plant.
  when state == FiaStates.BASELINE and (time - tEntry) >= baselineS then
    state := FiaStates.LOAD;
    tEntry := time;
  end when;

  when state == FiaStates.LOAD and (time - tEntry) >= loadS then
    state := FiaStates.INJECT;
    tEntry := time;
    // Every standardEvery-th injection draws the mid-range standard
    // instead of sample (design doc section 3.2) -- ported from
    // fia_sequencer.py's `(self.injection_count + 1) % every == 0`.
    sampleIsStandard := standardEvery > 0 and mod(injectionCount + 1, standardEvery) == 0;
  end when;

  // INJECT is transient (TRANSIENT_STATES in fia_sequencer.py): its whole
  // job is to fire the valve and stamp t0, then fall straight through to
  // ACQUIRE in the same event. injectionCount increments here so
  // downstream models can detect this instant via change(injectionCount).
  when state == FiaStates.INJECT then
    t0 := time;
    injectionCount := injectionCount + 1;
    state := FiaStates.ACQUIRE;
    tEntry := time;
  end when;

  // Measured from t0 (the actuation), not from tEntry -- matches
  // fia_sequencer.py's comment "Measured from t0, the actuation, not from
  // state entry."
  when state == FiaStates.ACQUIRE and (time - t0) >= acquireS then
    state := FiaStates.ANALYZE;
    tEntry := time;
  end when;

  // ANALYZE is transient -- the Python entry action does the peak-fit work
  // and falls straight through; there is nothing to wait for.
  when state == FiaStates.ANALYZE then
    state := FiaStates.WASH;
    tEntry := time;
  end when;

  when state == FiaStates.WASH and absorbanceIn < washThreshold then
    state := FiaStates.IDLE;
    tEntry := time;
    samplePumpOn := false;
    carrierPumpOn := false;
    acceptorPumpOn := false;
    ledOn := false;
  end when;

  when state == FiaStates.WASH and (time - tEntry) >= washTimeoutS then
    state := FiaStates.FAULT;
    tEntry := time;
    samplePumpOn := false;
    carrierPumpOn := false;
    acceptorPumpOn := false;
    ledOn := false;
  end when;

  annotation(Documentation(info="<html>
<p>See fia_sequencer.py::FiaSequencer for the reference implementation and
AMMONIA_FIA_SENSOR_DESIGN.md section 3.2 for the state diagram this
mirrors.</p>
</html>"));
end FiaSequencer;
