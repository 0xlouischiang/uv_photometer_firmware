within FiaSensor.Manifold;
model TransportCoil
  "Reaction coil as a cascade of nTanks equal well-mixed volumes.

  Approximates axial dispersion in a knitted PTFE coil without solving a
  transport PDE. This is a real approximation, not a doc-derived model:
  AMMONIA_FIA_SENSOR_DESIGN.md only gives a target dispersion coefficient
  range (D = c0/cmax approx 4-6, section 3) and the coil's physical length
  and i.d.; it does not specify a tanks-in-series count. nTanks=4 is an
  engineering choice within the literature's usual range for 'medium
  dispersion' FIA coils, not a fitted or measured value -- see
  modelica/FiaSensor/README.md.

  totalVolume_uL should be the coil's own swept volume (cross-section area
  x length), computed from the design doc's stated tube i.d. and coil
  length, not guessed independently."

  parameter Integer nTanks(min=1) = 4 "tanks-in-series count, see docstring";
  parameter Real totalVolume_uL "coil swept volume, uL (i.d. and length from the design doc)";
  input Real flowRate "carrier volumetric flow through the coil, uL/s";
  input Real cIn "continuous inlet concentration (e.g. 0 for plain carrier), mol/uL";
  input Real injectMoles "moles delivered by an injected plug, mol -- see docstring below";
  input Integer injectionCount "from FiaSequencer/SixPortValve -- change() marks the injection instant";
  output Real cOut "outlet concentration after dispersion, mol/uL";

protected
  parameter Real tankVolume_uL = totalVolume_uL/nTanks;
  Real c[nTanks](each start=0);

equation
  tankVolume_uL*der(c[1]) = flowRate*(cIn - c[1]);
  for i in 2:nTanks loop
    tankVolume_uL*der(c[i]) = flowRate*(c[i-1] - c[i]);
  end for;
  cOut = c[nTanks];

  // Loop injection as an instantaneous mass addition to the first tank,
  // not as a finite-duration flow of concentrated fluid: the INJECT state
  // that fires this is transient (zero span in continuous time -- see
  // FiaSequencer.mo), so integrating cIn*flowRate over it would deliver
  // zero mass regardless of cIn. reinit()-ing c[1] by
  // injectMoles/tankVolume_uL instead adds the sample loop's full mole
  // content (loopVolume_uL*sampleConc, computed in SixPortValve) in one
  // jump. This is the standard way tanks-in-series dispersion models
  // represent a pulse input (an impulse of mass into the first stage), not
  // a design-doc-derived approximation -- flagged in
  // modelica/FiaSensor/README.md.
  //
  // Triggered by change(injectionCount) rather than a Boolean compared
  // against the transient INJECT state directly: see
  // FiaSequencer.mo's injectionCount output docstring and
  // modelica/FiaSensor/README.md for why that comparison pattern breaks
  // OMC 1.25.4's backend.
  when change(injectionCount) then
    reinit(c[1], c[1] + injectMoles/tankVolume_uL);
  end when;
end TransportCoil;
