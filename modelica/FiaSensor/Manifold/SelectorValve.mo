within FiaSensor.Manifold;
model SelectorValve
  "Sample/standard/wash selector: picks which reservoir the sample pump
  draws from (design doc section 3, BOM item 5). Purely algebraic --
  routes one of three fixed concentrations through to the sample line."

  parameter Real sampleConc "process sample concentration, mol/uL";
  parameter Real standardConc "calibration standard concentration, mol/uL";
  input Boolean drawStandard "true when the sequencer's interleave picks the standard";
  output Real outConc "concentration presented to the sample pump / injection loop, mol/uL";
equation
  // WASH position (deionized water, zero NH3/NH4+) is the implicit
  // "neither" case -- the sequencer only ever asks this model to
  // distinguish sample from standard during LOAD; wash flow is represented
  // upstream by the sequencer simply not loading a value into the loop.
  outConc = if drawStandard then standardConc else sampleConc;
end SelectorValve;
