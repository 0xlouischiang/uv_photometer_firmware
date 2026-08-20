within ;
package FiaSensor
  "Physical plant model of the ammonia FIA analyser (see AMMONIA_FIA_SENSOR_DESIGN.md and src/fia_sequencer.py)."

  annotation(
    Documentation(info="<html>
<p>Lumped-parameter simulation of the flow-injection-analysis ammonia
sensor: pumps and valves as gated signal sources/routers, the reaction
coil as a tanks-in-series dispersion cascade, the gas diffusion cell as a
two-compartment membrane mass-transfer pair, the flow cell as a
Beer-Lambert absorbance readout, and a port of the firmware's
<code>FiaSequencer</code> state machine driving all of it. See
<code>modelica/FiaSensor/README.md</code> for which numbers come from
<code>AMMONIA_FIA_SENSOR_DESIGN.md</code> / <code>src/fia_settings.py</code>
/ <code>mech/gd_cell/gd_cell.py</code> verbatim, and which are modeling
choices flagged as such.</p>
</html>"));
end FiaSensor;
