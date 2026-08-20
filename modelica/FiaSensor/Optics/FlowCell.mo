within FiaSensor.Optics;
model FlowCell
  "Beer-Lambert absorbance readout at the flow cell (design doc section 2/4:
  10 mm path, 8-20 uL volume; BOM item 15/16).

  epsEff_M_cm is monochloramine's molar absorptivity at its 245 nm lambda-max
  (460 M^-1 cm^-1, design doc section 2) discounted by the ~15% efficiency
  the doc quotes for a 255 nm LED sitting off that peak ('costs roughly
  15% of eps -- use it, but don't expect the textbook 460'), i.e.
  460*0.85 = 391, both numbers doc-derived, not fitted.

  Absorbance formula matches src/fia_peak.py::absorbance and
  src/colorimeter.py:242 (A = -log10(raw/blank), clamped at 0) in form;
  here it is computed directly from concentration via Beer-Lambert rather
  than from a raw/blank photon-count ratio, since this model has no photon
  shot noise or detector nonlinearity to simulate -- see
  modelica/FiaSensor/README.md."

  parameter Real epsEff_M_cm = 460.0*0.85 "effective molar absorptivity, M^-1 cm^-1 (design doc section 2/4)";
  parameter Real pathLength_cm = 1.0 "10 mm path length (design doc section 4, BOM item 15)";
  input Real cNh2cl "monochloramine concentration, mol/uL (package-internal unit)";
  output Real absorbance "AU, clamped at zero";

protected
  Real cNh2cl_M = cNh2cl/FiaSensor.Units.molPerL "concentration converted to mol/L for the eps in M^-1 cm^-1";
  Real raw = epsEff_M_cm*pathLength_cm*cNh2cl_M;

equation
  absorbance = max(raw, 0.0);
end FlowCell;
