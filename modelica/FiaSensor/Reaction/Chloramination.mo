within FiaSensor.Reaction;
model Chloramination
  "NH3 + OCl- -> NH2Cl (monochloramine) in the acceptor stream (design doc
  section 3: pH 9.2 borate-buffered NaOCl, 'fast, seconds, no heater').

  OCl- is carried at 1-10 mM (design doc section 3.1) while the NH3
  crossing the membrane is at most low-hundreds-of uM even at the top of
  the calibration range (examples/calibrations.json's NH3-N max 1.4 AU
  corresponds to roughly 45 mg/L N =~ 3.2 mM NH3-N, and typical process
  samples are far below that) -- OCl- is always in large stoichiometric
  excess, so this is modeled as pseudo-first-order in NH3 (1 mole NH2Cl
  per mole NH3 consumed) without tracking OCl- depletion. The rate
  constant k, like Volatilization's, is a modeling choice (not in the
  design doc) sized to finish within a few seconds; see
  modelica/FiaSensor/README.md."

  parameter Real k = 2.0 "first-order rate constant, 1/s -- modeling choice, see docstring";
  input Real cNh3 "NH3 concentration delivered by the GD cell's acceptor side, mol/uL";
  output Real cNh2cl "monochloramine concentration, mol/uL";

equation
  der(cNh2cl) = k*(cNh3 - cNh2cl);
end Chloramination;
