within FiaSensor.Reaction;
model Volatilization
  "NH4+ -> NH3 in the carrier stream, driven to high pH by 0.2 M NaOH
  (design doc section 3: 'NH4+ -> NH3' at the coil, pKa 9.25).

  cIn is the *total* ammoniacal nitrogen concentration (NH4+ + NH3) coming
  out of the reaction coil; cOut is the free-NH3 fraction of it, the
  species that actually crosses the GD cell membrane. The Henderson-
  Hasselbalch equilibrium fraction at the given pH is doc-derived (pKa
  9.25 is stated in section 3); the first-order rate constant k driving
  the approach to that equilibrium is NOT -- the doc only says the
  conversion is fast ('seconds'), so k is chosen to reach >95% of
  equilibrium well inside the coil's residence time. See
  modelica/FiaSensor/README.md."

  parameter Real pKa = 9.25 "NH4+/NH3 pKa (design doc section 3)";
  parameter Real pH = 12.5 "carrier pH after 0.2 M NaOH addition (design doc section 3)";
  parameter Real k = 2.0 "first-order rate constant, 1/s -- modeling choice, see docstring";
  input Real cIn "total ammoniacal N concentration (NH4+ + NH3), mol/uL";
  output Real cOut "free NH3 concentration, mol/uL";

protected
  parameter Real nh3Fraction = 1.0/(1.0 + 10.0^(pKa - pH))
    "equilibrium free-NH3 fraction of total ammoniacal N, Henderson-Hasselbalch";

equation
  der(cOut) = k*(nh3Fraction*cIn - cOut);
end Volatilization;
