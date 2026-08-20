within FiaSensor;
model Plant
  "Top-level plant: wires FiaSequencer's actuator outputs through the
  Manifold, Reaction, GasDiffusion and Optics packages, matching the
  fluidic manifold diagram in AMMONIA_FIA_SENSOR_DESIGN.md section 3
  exactly (sample -> injection loop -> merge with carrier -> 30 cm coil
  (NH4+ -> NH3) -> donor groove || acceptor groove (membrane transfer) ->
  50 cm knitted coil (NH3 + OCl- -> NH2Cl) -> flow cell -> absorbance,
  fed back into the sequencer's WASH-exit decision).

  Every sub-model is wired by plain equations (no connect()/connectors),
  matching every other model in this package -- see
  modelica/FiaSensor/README.md.

  Coil swept volumes are computed from BOM items 8 and 11's stated tubing
  i.d. and the diagram's stated coil lengths, not guessed independently:
    donor coil:    30 cm x 0.8 mm i.d. (item 8, general manifold tubing --
                   the diagram gives no separate spec for this coil)
                   -> pi*(0.4mm)^2*300mm = 150.8 uL
    acceptor coil: 50 cm x 0.8 mm i.d. (item 11, 'knitted reaction coil')
                   -> pi*(0.4mm)^2*500mm = 251.3 uL
  The acceptor coil sits between the GD cell and Chloramination in the
  diagram (section 3: '...acceptor groove...50 cm knitted coil, ambient
  (NH3 + OCl- -> NH2Cl)'), so it is wired on gd.cAcceptorOut's continuous,
  time-varying breakthrough signal (TransportCoil's cIn accepts any
  time-varying forcing, not just a constant baseline -- see its
  docstring), not fed an injection pulse of its own: this coil disperses
  the plug the GD cell already shaped, it does not receive a fresh
  100 uL loop injection, so its injectionCount/injectMoles inputs are
  wired to 0 and never fire the pulse-reinit event.
  sampleConc/standardConc use the design doc's own 71.4 uM-per-mg/L-N
  conversion (section 2, 'Sensitivity check'). standardConc's 10 mg/L N is
  the design doc's own mid-range calibration standard (section 3.2's
  5-standard list: 0, 0.5, 2, 10, 40 mg/L N). sampleConc's 8 mg/L N has no
  doc source -- it is an arbitrary, plausible process-sample value picked
  only so this model has something to simulate standalone; a real
  deployment's sample concentration is whatever the process actually is."

  Sequencer.FiaSequencer seq;
  Manifold.SelectorValve selVal(sampleConc=sampleConc, standardConc=standardConc);
  Manifold.SixPortValve sixPort(loopVolume_uL=100.0);
  Manifold.Pump samplePump(ratedFlow_mLmin=1.2)
    "3 loop volumes in load_s=15 s (design doc section 3's LOAD state) =
    300 uL/15 s = 1.2 mL/min minimum; flowRate is otherwise unused since
    SixPortValve treats the loop as fully loaded by injection time.";
  Manifold.Pump carrierPump(ratedFlow_mLmin=1.2);
  Manifold.Pump acceptorPump(ratedFlow_mLmin=0.6);
  Manifold.TransportCoil donorCoil(nTanks=4, totalVolume_uL=150.8, cIn=0.0);
  Reaction.Volatilization volat;
  GasDiffusion.GdCell gd;
  Manifold.TransportCoil acceptorCoil(nTanks=4, totalVolume_uL=251.3, injectMoles=0.0, injectionCount=0);
  Reaction.Chloramination chlor;
  Optics.FlowCell flowCell;

  parameter Real sampleConc = 8.0*71.4*Units.uM "process sample, ~8 mg/L NH3-N -- test default, see docstring";
  parameter Real standardConc = 10.0*71.4*Units.uM "10 mg/L NH3-N standard, design doc section 3.2";

  output Real absorbance = flowCell.absorbance;
  output FiaSensor.Sequencer.FiaStates state = seq.state;
  output Integer injectionCount = seq.injectionCount;

equation
  selVal.drawStandard = seq.sampleIsStandard;

  sixPort.sampleConc = selVal.outConc;
  sixPort.injectionCount = seq.injectionCount;

  samplePump.on = seq.samplePumpOn;
  carrierPump.on = seq.carrierPumpOn;
  acceptorPump.on = seq.acceptorPumpOn;

  donorCoil.flowRate = carrierPump.flowRate;
  donorCoil.injectMoles = sixPort.injectMoles;
  donorCoil.injectionCount = seq.injectionCount;

  volat.cIn = donorCoil.cOut;

  gd.flowDonor = carrierPump.flowRate;
  gd.flowAcceptor = acceptorPump.flowRate;
  gd.cInDonor = volat.cOut;

  acceptorCoil.flowRate = acceptorPump.flowRate;
  acceptorCoil.cIn = gd.cAcceptorOut;

  chlor.cNh3 = acceptorCoil.cOut;

  flowCell.cNh2cl = chlor.cNh2cl;

  seq.absorbanceIn = flowCell.absorbance;

  annotation(Documentation(info="<html>
<p>See AMMONIA_FIA_SENSOR_DESIGN.md section 3 for the manifold diagram this
mirrors, and each sub-model's own docstring for which of its parameters are
doc-derived vs. flagged modeling choices.</p>
</html>"));
end Plant;
