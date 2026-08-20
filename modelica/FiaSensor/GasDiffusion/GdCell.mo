within FiaSensor.GasDiffusion;
model GdCell
  "Two-compartment membrane mass transfer, donor groove <-> acceptor
  groove across the PTFE membrane (design doc section 3; BOM item 6).

  Both compartment volumes are pinned to mech/gd_cell/gd_cell.py's swept
  groove volume (40.0 uL/side, PLATE_X/Y/Z + serpentine groove geometry),
  not re-derived, so the two models cannot silently drift apart.

  The membrane transfer rate kMem is not an independent guess: it is
  solved (see the protected parameter equation below) so that the
  donor->acceptor steady-state flux equals targetTransferFraction of the
  donor's incoming NH3 mass rate, at the given through-flows. 0.25 is the
  design doc's own number (section 3, 'why ~25% transfer is acceptable'),
  so this calibrates the model's one free parameter to a doc-given
  *outcome* rather than inventing a permeability constant from nothing --
  see modelica/FiaSensor/README.md.

  Derivation (steady state, cInAcceptor = 0):
    J = kMem*(cDonor - cAcceptor)                    (membrane flux)
    0 = flowDonor*(cInDonor - cDonor) - J             (donor balance)
    0 = flowAcceptor*(0 - cAcceptor) + J              (acceptor balance)
  Solving for kMem at J = f*flowDonor*cInDonor (f = targetTransferFraction)
  gives the formula below; it depends only on the two flow rates and f,
  not on cInDonor, because membrane permeation here is linear (no
  saturation) -- consistent with the doc's flow-based transfer-fraction
  framing, not a concentration-based one.

  The formula is rearranged to divide by
  ((1-f)*flowAcceptor - f*flowDonor) rather than by flowAcceptor directly
  (algebraically identical away from flowAcceptor=0), and that denominator
  is floored at a tiny epsilon rather than gated with an if-condition.
  An if-condition on flowDonor>0 and flowAcceptor>0 was tried first and
  compiled fine, but Plant.mo's simulation aborted on a division-by-zero
  assert at a discrete event boundary anyway (both pumps switch on/off in
  lockstep with FiaSequencer's `when` blocks, and OMC 1.25.4's event
  iteration evaluates the un-taken branch's subexpressions while probing
  trial values near the switch) -- see modelica/FiaSensor/README.md. The
  epsilon floor sidesteps that by making the expression finite for every
  trial value a solver could evaluate, not just at the converged solution."

  parameter Real donorVolume_uL = 40.0 "donor groove swept volume, uL (gd_cell.py)";
  parameter Real acceptorVolume_uL = 40.0 "acceptor groove swept volume, uL (gd_cell.py)";
  parameter Real targetTransferFraction = 0.25 "design doc section 3's ~25% transfer";
  input Real flowDonor "donor (carrier) through-flow, uL/s";
  input Real flowAcceptor "acceptor through-flow, uL/s";
  input Real cInDonor "free NH3 concentration entering the donor groove, mol/uL";
  output Real cAcceptorOut "NH3 concentration leaving the acceptor groove, mol/uL";

protected
  Real cDonor(start=0) "donor groove concentration, mol/uL";
  Real cAcceptor(start=0) "acceptor groove concentration, mol/uL";
  Real kMem "membrane mass-transfer rate constant, uL/s -- solved, not guessed, see docstring";

equation
  kMem = targetTransferFraction*flowDonor*flowAcceptor
      /max((1 - targetTransferFraction)*flowAcceptor - targetTransferFraction*flowDonor, 1e-12);

  donorVolume_uL*der(cDonor) = flowDonor*(cInDonor - cDonor) - kMem*(cDonor - cAcceptor);
  acceptorVolume_uL*der(cAcceptor) = flowAcceptor*(0.0 - cAcceptor) + kMem*(cDonor - cAcceptor);
  cAcceptorOut = cAcceptor;
end GdCell;
