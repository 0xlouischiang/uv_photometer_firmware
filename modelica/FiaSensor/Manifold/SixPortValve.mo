within FiaSensor.Manifold;
model SixPortValve
  "Injection valve: captures the mole content of the 100 uL sample loop at
  the instant it switches into the carrier stream (design doc section 3,
  BOM item 4).

  This block is purely algebraic -- it has no continuous state of its own.
  The actual mass injection (a reinit() jump, since the injection event has
  zero duration in continuous time) happens in TransportCoil, which is the
  model that owns the state being perturbed; see TransportCoil.mo's
  docstring for why. injectMoles here just holds the most recently loaded
  amount, updated once per injection and constant in between --
  TransportCoil is what decides *when* to apply it, by watching
  change(injectionCount) itself.

  Driven by injectionCount (from FiaSequencer) rather than a Boolean
  derived from comparing to the transient INJECT state: see
  FiaSequencer.mo's injectionCount output docstring for why that
  comparison pattern breaks OMC 1.25.4's backend, and
  modelica/FiaSensor/README.md for how that was found. sampleConc does not
  change between LOAD (when the loop fills) and the INJECT instant, so
  sampling it exactly on change(injectionCount) is equivalent to sampling
  it at the end of LOAD."

  parameter Real loopVolume_uL = 100.0 "injection loop volume, uL (design doc section 3)";
  input Real sampleConc "concentration on the sample line while loading, mol/uL";
  input Integer injectionCount "from FiaSequencer -- increments once per injection";
  output Real injectMoles "moles loaded at the most recent injection, mol; constant between injections";

protected
  discrete Real injectMoles_(start=0);

equation
  when change(injectionCount) then
    injectMoles_ = loopVolume_uL*sampleConc;
  end when;
  injectMoles = injectMoles_;
end SixPortValve;
