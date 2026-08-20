within FiaSensor;
package Units
  "Unit conventions shared by every model in this package.

  Internal state is kept in volume = uL, flow = uL/s, concentration =
  mol/uL, time = s. Concentration times volume is then a plain product
  with no scale factor (mol/uL * uL = mol), which keeps every mass-balance
  ODE in the package free of embedded unit-conversion constants -- only
  the *parameterization* boundary (writing a rate constant or an initial
  concentration in familiar mM/mL-per-min units) needs a conversion, via
  the constants below.

  Concentration conversion derivation: 1 mM = 1e-3 mol/L = 1e-3 mol /
  (1e6 uL) = 1e-9 mol/uL. So `3*Units.mM` inside a parameter declaration
  means '3 mM', stored internally as 3e-9 mol/uL.
  Flow conversion: 1 mL/min = 1000 uL / 60 s = (1000/60) uL/s."

  constant Real mM = 1.0e-9 "mol/uL per mM (millimolar)";
  constant Real uM = 1.0e-12 "mol/uL per uM (micromolar)";
  constant Real molPerL = 1.0e-6 "mol/uL per mol/L (1 L = 1e6 uL)";
  constant Real mLmin = 1000.0/60.0 "uL/s per mL/min";
end Units;
