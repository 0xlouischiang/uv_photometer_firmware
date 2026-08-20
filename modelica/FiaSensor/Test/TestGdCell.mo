within FiaSensor.Test;
model TestGdCell
  "Steps the donor inlet concentration and checks the GD cell's
  donor->acceptor steady-state transfer fraction converges to
  targetTransferFraction=0.25, at the design doc's own flow rates
  (carrier 1.2, acceptor 0.6 mL/min) -- verifying kMem's derivation in
  GdCell.mo actually delivers the doc-given outcome it was solved for,
  not just that the formula parses."

  FiaSensor.GasDiffusion.GdCell gd(flowDonor=1.2*FiaSensor.Units.mLmin,
      flowAcceptor=0.6*FiaSensor.Units.mLmin);
equation
  gd.cInDonor = 1.0*FiaSensor.Units.mM;
end TestGdCell;
