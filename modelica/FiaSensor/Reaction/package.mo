within FiaSensor;
package Reaction
  "The two 'fast' chemistry steps (design doc section 3): NH4+ -> NH3 at
  high pH in the carrier, and NH3 + OCl- -> NH2Cl in the acceptor. Both
  modeled as first-order approach-to-completion ODEs with a rate constant
  chosen to finish within a few seconds, matching the doc's qualitative
  description ('fast, seconds at pH 9, no heater'). The rate constants
  themselves are NOT in the design doc -- see
  modelica/FiaSensor/README.md's 'not doc-derived' section."
end Reaction;
