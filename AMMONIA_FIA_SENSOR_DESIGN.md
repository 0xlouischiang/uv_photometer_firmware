# Ammonia Nitrogen Sensor — Flow Injection Analysis Design

Design study for an automated NH₃-N analyser built on the existing UV photometer
hardware (AS7331 + CircuitPython Feather).

Status: design only, nothing built or measured. Performance figures are
projections from molar absorptivity and path length, not measurements.

## 0. Source caveat

The reference chapter — [Harvey, *Analytical Chemistry 2.1*, §13.4 Flow Injection
Analysis](https://chem.libretexts.org/Bookshelves/Analytical_Chemistry/Analytical_Chemistry_2.1_(Harvey)/13:_Kinetic_Methods/13.04:_Flow_Injection_Analysis)
— could not be fetched directly; `chem.libretexts.org` is blocked from this
environment (three URL variants attempted). Section 1 below was reconstructed
from search snippets plus standard FIA references (Ruzicka & Hansen;
Trojanowicz). The principles are well established, but **verify the specific
numbers against a copy of Harvey before quoting them.**

## 1. What §13.4 establishes

FIA sits in the *Kinetic Methods* chapter because it is deliberately a
**non-equilibrium** measurement. A discrete sample plug is injected into a
flowing carrier, reacts partially en route to the detector, and produces a
transient peak. The reaction never has to reach completion — reproducible
*timing* gives a reproducible *extent* of reaction, and that is enough for
quantitation. This is the most important idea to carry into the sensor design.

### Four components

| Component | Role | Typical spec |
|---|---|---|
| Propelling unit | constant carrier flow | peristaltic pump, 0.5–2.5 mL/min |
| Injector | reproducible sample plug | rotary loop valve, 5–200 µL |
| Transport/reaction zone | controlled mixing + reaction time | 0.5–0.8 mm i.d. tubing, coils/packed reactors |
| Detector | flow-through, transient signal | absorbance, fluorescence, potentiometry |

### Dispersion

Immediately after injection, convection dominates — the parabolic laminar
velocity profile smears the plug into a paraboloid. Downstream, radial diffusion
takes over and partly re-homogenizes it. The net result is the characteristic
asymmetric peak: sharp rise, long tail.

Quantified by the **dispersion coefficient**:

```
D = c⁰ / c_max
```

where `c⁰` is the injected concentration and `c_max` the concentration at peak
maximum.

- **Limited dispersion**, D = 1–3 — sample reaches the detector nearly undiluted;
  used when you want the sample itself (ion-selective electrodes, AAS, pH)
- **Medium dispersion**, D = 3–10 — the working range when you need
  sample/reagent mixing and reaction time
- **Large dispersion**, D > 10 — in-line dilution, titrations

D rises with coil length (roughly as √L) and falls as injection volume
increases. Injecting a large enough plug drives D → 1.

### Peak parameters

Travel time `t_a` (injection → signal first appears), residence time / peak time
`T` (injection → peak maximum), return-to-baseline time, and peak height `h`
(the analytical signal; area also usable). Throughput runs 20–120 samples/h.

**The trade-off to design against:** more reaction time buys sensitivity from the
chemistry but loses it to dispersion. There is an optimum coil length, not a
monotonic improvement.

## 2. Wavelength constraint — read before the design

The existing firmware drives an **AS7331**, a three-channel filtered UV sensor:
UVA (~315–400 nm), UVB (~280–315 nm), UVC (~220–280 nm). See
`src/light_sensor.py:1` and the channel constants at `src/constants.py:78`.

The default ammonia chemistry — **indophenol blue** (Berthelot: NH₃ + OCl⁻ →
monochloramine, then salicylate + nitroprusside catalyst → blue dye) — is read at
**660 nm**. The AS7331 cannot see it. Nessler's is 420 nm (also invisible, and
mercury-based — don't).

Ammonium itself has no usable UV absorbance, so a reagent-free UV method is off
the table too.

Two honest paths remain.

### Option A — chloramine UV at 245 nm (recommended; reuses existing hardware)

Stop the Berthelot sequence at the first step. Monochloramine has λmax 245 nm,
ε ≈ 460 M⁻¹cm⁻¹, landing in the AS7331's UVC channel.

Normally 245 nm detection in real water is hopeless — nitrate and dissolved
organics swamp it — but **gas diffusion upstream removes them entirely**, because
only NH₃ crosses the membrane. The acceptor stream is optically clean.
Chloramination is also fast (seconds at pH 9), so no heater and only a short coil.

Sensitivity check: 1 mg/L NH₃-N = 71.4 µM → A = 0.033 in a 10 mm cell. With a
10 mm flow cell, roughly 0.05–0.1 mg/L LOD; a 50 mm cell pushes it to
~0.02 mg/L. Adequate for wastewater, aquaculture, digestate, soil extracts.

### Option B — indophenol blue at 660 nm (30–40× more sensitive; needs new optics)

ε₆₆₀ ≈ 1.4×10⁴, so ~1.0 AU per mg/L N at 10 mm. Costs a 660 nm LED plus a
visible photodiode or TSL2591/OPT4001, a heated coil at 45–60 °C, and sodium
nitroprusside (cyanide-containing — real handling burden). Take this only if
sub-10 µg/L is required.

The BOM below builds Option A; the Option B delta is listed separately.

## 3. Sensor workflow

### Fluidic manifold (gas-diffusion FIA)

```
                    ┌─────────── 6-port injection valve ───────────┐
                    │      100 µL loop        LOAD ⇄ INJECT        │
 sample ──pump──────┘                                             │
                                                                   ▼
 NaOH carrier ──pump─────────────────────────────────────► merge ──► 30 cm coil
   0.2 M NaOH + 5 mM EDTA                                            (NH4+ → NH3)
   1.2 mL/min                                                            │
                                                                         ▼
                                          ┌──────── GAS DIFFUSION CELL ────────┐
                                          │  donor groove  ═══════════════►  waste
                                          │  ─── PTFE membrane, 0.2 µm ───     │
 acceptor ──pump──────────────────────────►  acceptor groove ═══════════►      │
   1 mM NaOCl in 20 mM borate, pH 9.2     └────────────────────────────────────┘
   0.6 mL/min                                                            │
                                                                         ▼
                                                        50 cm knitted coil, ambient
                                                             (NH3 + OCl- → NH2Cl)
                                                                         │
                                                                         ▼
                                                   ┌──── FLOW CELL, 10 mm quartz ────┐
                                        255 nm LED ──►  ═══════════  ──► AS7331 UVC  │
                                                   └─────────────────────────────────┘
                                                                         │
                                                                         ▼
                                                                       waste
```

### Why each choice

- **EDTA in the carrier** — without it, 0.2 M NaOH precipitates Ca/Mg hydroxides
  in hard samples and blinds the membrane within hours.
- **Acceptor flow < donor flow** (0.6 vs 1.2 mL/min) — preconcentrates NH₃ into a
  smaller acceptor volume. Free sensitivity.
- **Hypochlorite *in* the acceptor** — consumes NH₃ on arrival to non-volatile
  NH₂Cl, so the trap can't leak back. Also drops a third reagent channel. Keep
  OCl⁻:N above 1 but modest; large excess at low pH drives breakpoint oxidation
  to N₂ and signal is lost.
- **pH 9.2 borate** — monochloramine is the dominant species here. Below pH 7 you
  get dichloramine, which has a different spectrum and wrecks the calibration.
- **Hypochlorite absorbs in the UVC** too, setting a constant elevated baseline.
  Compatible with FIA — the analytical signal is peak height *above* the flowing
  baseline, and the existing blank mechanism handles exactly this.
- **50 cm coil, ambient** — targets D ≈ 4–6 (medium dispersion). Residence to
  peak ≈ 30–35 s, baseline return ≈ 60 s → **~50–60 samples/h**.

### Firmware state machine

The current firmware is a single-point cuvette photometer. The FIA version is a
timed cycle:

```
IDLE
 └─► PRIME          pumps on, 60 s, purge air
      └─► BASELINE  acquire flowing reagent reference, 10 s
           │        accept only if RSD < 0.3 %  → store as blank_values
           └─► LOAD          valve = LOAD, sample through loop, 15 s (≥3 loop volumes)
                └─► INJECT   valve = INJECT, t := 0   ◄── timing origin
                     └─► ACQUIRE   sample UVC at 20 Hz until t = 70 s
                          └─► ANALYZE   h = max A(t) in window [20 s, 50 s]
                               │        area = ∫A dt over same window
                               │        c = calibration_poly(h)
                               └─► WASH  hold until A < 0.002, then LOAD next
```

Implementation notes that matter:

- **`is_blanked` / `blank_values` map directly onto the flowing baseline.** That
  machinery in `src/colorimeter.py:52` is already the right abstraction — it just
  references flowing reagent instead of a blank cuvette. Re-baseline every cycle,
  not once at startup.
- **Timing determinism is the whole method.** Every reading needs a
  `time.monotonic_ns()` stamp, and valve actuation must be driven off elapsed
  time, not loop iteration count. CircuitPython GC pauses will otherwise jitter
  peak time and shift the extent of reaction. Consider pinning the acquisition
  loop and pre-allocating the `ulab` sample array.
- **AS7331 integration time** — 32 or 64 ms keeps 15–30 Hz, plenty for a peak
  with a 10 s rise. Avoid the long integration times; they alias the peak.
- **Record peak height *and* area.** Height is faster and more precise; area
  tolerates pump flow drift better. Log both, quantify on height, use the
  height/area ratio as a health metric — if it moves, pump tubing is worn or the
  membrane is fouling.
- **Reject on window violation.** If the peak maximum lands outside [20 s, 50 s],
  flag the result rather than reporting it. That single check catches air bubbles,
  valve failures, and pump slip.
- **Drift correction.** UVC LEDs drift hard with junction temperature — the
  dominant accuracy risk in the whole build. Interleave a mid-range standard every
  10 samples *and* split the beam to a second AS7331 as a reference channel.
- **Calibration** — 5 standards (0, 0.5, 2, 10, 40 mg/L N), quadratic fit. The
  `calibrations.json` schema at `examples/calibrations.json` should extend cleanly.

### Sequence control

Six actuators: sample pump, carrier pump, acceptor pump, injection valve,
sample/standard selector valve, waste. To avoid a rotary valve, replace loop
injection with two 3-way solenoids doing **time-based injection**
(sequential-injection style) — cheaper, no moving seals, at the cost of somewhat
worse plug reproducibility.

## 4. Bill of materials

Indicative USD, single-unit, mid-2026. Two columns: a lab-grade build and a
cost-down build that still works.

### Fluidics

| # | Item | Spec | Lab-grade | Cost-down |
|---|---|---|---|---|
| 1 | Peristaltic pump | 3-channel, 0.1–3 mL/min, low pulsation | Ismatec Reglo ICC 3-ch, $2,600 | 3× Kamoer KDS/F02 stepper, $150 |
| 2 | Pump tubing | PharMed BPT, 1.02 mm + 0.76 mm i.d., 12-stop | $60 / 12-pack | Tygon LMT-55, $30 |
| 3 | Pulse damper | inline, 2× (carrier + acceptor) | Global FIA, $180 | coiled 1 m PTFE + air bubble trap, $15 |
| 4 | Injection valve | 6-port 2-position, PEEK, 100 µL loop | VICI Cheminert C22, $850 | 2× Bio-Chem 075T 3-way solenoid, $130 |
| 5 | Selector valve | 6-position, sample/std/wash | VICI C25, $1,100 | 4× 2-way solenoid pinch, $160 |
| 6 | Gas diffusion cell | PTFE/PMMA sandwich, 0.5×1×80 mm grooves | Global FIA GD cell, $620 | machined PMMA, 2 blocks + gasket, $90 |
| 7 | GD membrane | PTFE hydrophobic, 0.2 µm, 47 mm | Millipore Fluoropore FGLP, $210/100 | PTFE plumber's tape (2 layers), $5 |
| 8 | Manifold tubing | PTFE 0.8 mm i.d. × 1/16" o.d., 10 m | $45 | $45 |
| 9 | Fittings | 1/4-28 flangeless, PEEK ferrules, ~30 | IDEX, $110 | generic, $35 |
| 10 | Tees / connectors | PEEK low-dead-volume tee ×3 | $75 | PMMA/PP tee, $12 |
| 11 | Knitted reaction coil | 50 cm × 0.8 mm i.d. PTFE, knitted | $40 | hand-knit from item 8, $0 |
| 12 | Reservoirs | 500 mL HDPE ×3 + caps with ports | $60 | lab bottles + drilled caps, $25 |
| 13 | Waste container | 2 L HDPE, vented | $20 | $20 |
| 14 | Inline filter | 20 µm, sample line | $55 | syringe filter holder, $18 |

### Optics and detection

| # | Item | Spec | Lab-grade | Cost-down |
|---|---|---|---|---|
| 15 | Flow cell | 10 mm path, Z-flow, quartz, 8–20 µL | Starna 583.65-Q-10, $480 | quartz cuvette + PTFE flow insert, $120 |
| 15b | *(upgrade)* long-path cell | 50 mm liquid waveguide | WPI LWCC-3050, $3,400 | — |
| 16 | UVC LED | 255 nm, TO-39 ball lens, ≥1 mW | Bolb S6255-01, $95 | generic 255 nm TO-39, $22 |
| 17 | LED driver | constant current 20–100 mA, ±0.1 % | Thorlabs LEDD1B, $360 | LM334 / TLC5940 + sense R, $8 |
| 18 | Detector | AS7331 breakout (UVC channel) | SparkFun/IO Rodeo AS7331, $25 | same, $25 |
| 19 | Reference detector | 2nd AS7331 + fused-silica beamsplitter | $25 + $180 | 2nd AS7331 + quartz slide pickoff, $32 |
| 20 | Optical block | machined Al, LED/cell/detector alignment, light-tight | $250 machined | 3D-print (opaque PETG) + Al foil liner, $10 |
| 21 | Thermistor | 10 kΩ NTC on LED heatsink | $4 | $4 |
| 22 | LED heatsink | TO-39 clip-on + thermal pad | $12 | $12 |

### Electronics and control

| # | Item | Spec | Lab-grade | Cost-down |
|---|---|---|---|---|
| 23 | MCU | existing Feather (CircuitPython) — reuse | $0 | $0 |
| 24 | Motor drivers | 3× stepper driver (TMC2209) for pumps | $30 | $30 |
| 25 | Valve driver | 8-ch high-side / ULN2803 + flyback | $12 | $12 |
| 26 | I²C expander | for valve/pump enables | $8 | $8 |
| 27 | PSU | 12 V 3 A + 5 V rail | $30 | $30 |
| 28 | Liquid level sensors | 4× optical/capacitive, reagent + waste | $60 | float switches, $20 |
| 29 | Leak sensor | conductive pad under manifold | $15 | $15 |
| 30 | Ambient T/RH | for drift logging | $10 | $10 |
| 31 | SD card + RTC | result logging, timestamps | $20 | $20 |
| 32 | Enclosure | IP54, 300×250×150, DIN plate | $180 | $70 |

### Reagents and consumables (per ~2,000 injections)

| # | Item | Spec | Cost |
|---|---|---|---|
| 33 | NaOH | pellets, ACS, 500 g | $35 |
| 34 | EDTA disodium | ACS, 250 g | $40 |
| 35 | NaOCl | 10–15 % w/v, 500 mL — **stabilized, dated** | $25 |
| 36 | Boric acid + NaOH | borate buffer pH 9.2, 500 g | $30 |
| 37 | NH₄Cl | primary standard grade, 100 g | $45 |
| 38 | DI water | 18 MΩ, ammonia-free — **critical** | in-house |
| 39 | Volumetric glassware | Class A flasks 100/1000 mL for standards | $150 |
| 40 | Sodium thiosulfate | waste quench (destroys chloramine) | $20 |

### Option B delta (indophenol blue, 660 nm)

Add if sub-10 µg/L is required:

| # | Item | Cost |
|---|---|---|
| B1 | 660 nm LED + visible photodiode/TSL2591 (replaces items 16–17) | $30 |
| B2 | 4th pump channel + reagent line (salicylate/nitroprusside merge) | $50 |
| B3 | Heated coil, 200 cm @ 55 °C — Al block + cartridge heater + PID + RTD | $110 |
| B4 | Sodium salicylate 250 g | $40 |
| B5 | Sodium nitroprusside 25 g — **toxic, cyanogenic** | $60 |
| B6 | Trisodium citrate 500 g | $30 |

**Rough totals:** lab-grade ≈ $8,900 (≈ $12,300 with the long-path waveguide);
cost-down ≈ $1,400. Option A over Option B saves the heater, one pump channel,
and the nitroprusside handling burden.

## 5. Expected performance

Option A, 10 mm cell, dual-beam referencing, 100 µL injection. **Projected from
ε and path length — not measured.**

| Metric | Expected |
|---|---|
| Range | 0.1–50 mg/L NH₃-N (dilute above) |
| LOD (3σ) | 0.05–0.1 mg/L N |
| Precision | 1.5–3 % RSD at 5 mg/L |
| Throughput | 50–60 samples/h |
| Reagent use | ~2 mL/injection |

## 6. Ranked risks

1. **UVC LED thermal/aging drift** — biggest error source. Dual-beam referencing
   (item 19) plus a bracketing standard every 10 samples. Do not skip.
2. **CO₂ crossing the membrane** — it also permeates PTFE and acidifies the
   acceptor, suppressing chloramine yield. Buffer the acceptor adequately (20 mM
   borate is chosen for this) and check for negative bias on high-alkalinity
   samples.
3. **Membrane fouling** — surfactants wet the PTFE and kill gas transfer
   irreversibly. Inline 20 µm filter; treat the membrane as a scheduled
   consumable (weekly on wastewater).
4. **Hypochlorite decay** — NaOCl loses titer over weeks. Date the stock, prepare
   the working acceptor daily, track baseline absorbance as the health indicator
   (it falls as OCl⁻ decays).
5. **Pump tubing wear** — changes flow rate, shifting peak time and dispersion.
   The height/area ratio is the early-warning signal.
6. **Ammonia in lab air and DI water** — a classic; the blank will creep. Keep
   reagents capped and vented through an acid trap.

### Safety and waste

The carrier is 0.2 M NaOH (caustic) and the acceptor generates chloramine. Never
let the waste line meet acid — that liberates Cl₂/NHCl₂. Quench waste with
thiosulfate before disposal, and vent the waste container.

## 7. Next step

Sketch the CircuitPython FIA state machine against the existing `Colorimeter`
class. The peak-detection and timing layer is the part with real design content,
and it would slot in alongside `measure_screen.py` rather than replacing it.

## References

- [13.4 Flow Injection Analysis (Harvey)](https://chem.libretexts.org/Bookshelves/Analytical_Chemistry/Analytical_Chemistry_2.1_(Harvey)/13:_Kinetic_Methods/13.04:_Flow_Injection_Analysis) — primary source, not directly fetchable from this environment
- [13.7 Chapter Summary and Key Terms](https://chem.libretexts.org/Bookshelves/Analytical_Chemistry/Book:_Analytical_Chemistry_2.1_(Harvey)/13:_Kinetic_Methods/13.07:_Chapter_Summary_and_Key_Terms)
- [Principles of Flow Injection Analysis](https://www.researchgate.net/publication/338435099_Principles_of_Flow_Injection_Analysis)
- [FIA with indophenol blue — application notes](https://www.benchchem.com/pdf/Application_Notes_and_Protocols_for_Flow_Injection_Analysis_with_the_Indophenol_Blue_Method.pdf)
- [Gas-diffusion FIA for ammonium in Kjeldahl digests](https://pubmed.ncbi.nlm.nih.gov/18966961/)
- [FIA indophenol with Mn(II) catalysis](https://link.springer.com/article/10.2116/analsci.18.1141)
- [NEMI salicylate-hypochlorite method summary](https://www.nemi.gov/methods/method_summary/8899/)
- [FIA ammonium in water, 660 nm](https://anlaborders-test.ucdavis.edu/analysis/Water/847)
- [Trace ammonium in seawater by FIA-fluorescence](https://pubs.rsc.org/en/content/articlehtml/2005/em/b405924g)
