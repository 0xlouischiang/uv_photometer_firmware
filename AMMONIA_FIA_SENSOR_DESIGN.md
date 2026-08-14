# Ammonia Nitrogen Sensor — Flow Injection Analysis Design

Design study for an automated NH₃-N analyser built on the existing UV photometer
hardware (AS7331 + CircuitPython Feather).

Status: design only, nothing built or measured. Performance figures are
projections from molar absorptivity and path length, not measurements.

**Recommendation for a wastewater treatment plant: Option A** (gas diffusion →
chloramine UV at 245 nm), as a process-control instrument rather than a
compliance-reporting one. Full comparison in §5. Enclosure, chassis material and
plant siting are in §8 — the short version is a bought NEMA 4X cabinet over a
non-metallic wet panel, with aluminum kept out of the caustic zone entirely.

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

Note that a 255 nm LED sitting off a 245 nm λmax costs roughly 15 % of ε — use
it, but don't expect the textbook 460.

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
   1-10 mM NaOCl in 20 mM borate, pH 9.2  └────────────────────────────────────┘
   (size to range — see §3.1)                                            │
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

### What the gas diffusion cell does

The selectivity element of the whole design, and the component that makes 245 nm
detection viable in wastewater at all. Without it Option A does not work.

```
   donor groove  (sample + 0.2 M NaOH, pH > 12)
   ═══════════════════════════════════════════►  to waste
        NH₄⁺ + OH⁻ → NH₃(aq)  ──┐
                                ▼  diffuses to membrane surface
   ┌──────────────────────────────────────────┐
   │  NH₃(aq) → NH₃(g)      evaporates        │ ← liquid/gas interface pinned
   │  ░░░ PTFE, 0.2 µm, AIR-FILLED pores ░░░  │   at the pore mouths
   │  NH₃(g) → NH₃(aq)      redissolves       │   (hydrophobic: water can't enter)
   └──────────────────────────────────────────┘
                                │
   ═══════════════════════════════════════════►  to flow cell
   acceptor groove  (1–10 mM OCl⁻, pH 9.2)
        NH₃ + OCl⁻ → NH₂Cl   ← trapped, non-volatile
```

The membrane is hydrophobic PTFE, so water cannot wet the 0.2 µm pores — surface
tension keeps them **gas-filled**. The result is a barrier transparent to volatile
neutral species and completely opaque to liquid and to anything dissolved in it.
Ammonia crosses as a gas through an air gap on the order of 100 µm; everything
ionic or particulate stays on the donor side.

The pH split drives it. NH₄⁺/NH₃ has pKa 9.25, so at pH 12+ over 99 % of the
ammonia is the free volatile base and it evaporates readily. On the far side,
pH 9.2 plus hypochlorite converts arriving NH₃ to monochloramine — non-volatile,
so it cannot cross back. The gradient stays steep and transfer is effectively
one-way.

**Four functions, in order of importance:**

1. **Matrix separation** — the real payoff. At 245 nm the raw sample is hopeless:
   nitrate absorbs strongly below 250 nm, humics and dissolved organics absorb
   broadly across the UV, and MLSS at 2,000–4,000 mg/L scatters everything. None
   of it is volatile, so none of it crosses. The acceptor arriving at the flow cell
   is optically clean water containing only hypochlorite and chloramine. An
   impossible measurement becomes an easy one.
2. **Replaces the filtration module** — particulates cannot pass a gas-filled pore.
   Analyzers that detect in the sample stream need online ultrafiltration or a
   filtration probe, invariably the highest-maintenance part of the instrument.
   Gas diffusion gets this free as a side effect (see §5.2).
3. **Preconcentration** — acceptor slower than donor (0.6 vs 1.2 mL/min) collects
   ammonia from a larger donor volume into a smaller acceptor volume. ~2×
   enrichment for no added hardware.
4. **Reagent isolation** — the strong caustic needed to liberate NH₃ never reaches
   the flow cell or the detection chemistry. Donor and acceptor conditions are
   optimized independently: pH 12 for volatilization, pH 9.2 for clean
   monochloramine formation. In a single stream those requirements contradict.

**What crosses and what doesn't** — this is also the interference list:

| Crosses the membrane | Stays behind |
|---|---|
| NH₃ ✓ (the analyte) | NO₃⁻, NO₂⁻, PO₄³⁻ — all ions |
| CO₂ (acidifies acceptor — risk #3) | Humics, dissolved organics, color |
| H₂S, SO₂ | Metals, hardness ions |
| **Volatile amines (risk #2)** | TSS, MLSS, all particulates |
| Volatile organics | Surfactants (but they foul the membrane) |

Anything volatile is a potential interferent precisely because the membrane cannot
distinguish it from ammonia — which is why methylamines are the dominant accuracy
risk for Option A (§5.3) and why CO₂ demands a buffered acceptor.

**Why ~25 % transfer is acceptable.** Three transport resistances in series — donor
boundary layer, gas-filled pore, acceptor boundary layer — and the plug is moving
past at 1.2 mL/min rather than equilibrating. That would be fatal in a batch
method. In FIA it does not matter, for the same reason the chapter files FIA under
*Kinetic Methods*: **transfer must be reproducible, not complete.** Fixed flow
rates and fixed geometry give a fixed 25 %, and the calibration absorbs it as a
constant.

The corollary: anything that changes that fraction — worn pump tubing, a fouling
membrane, temperature drift — appears directly as a calibration shift. Hence
membrane replacement is scheduled maintenance rather than repair, and the
height/area ratio is worth logging as a health signal.

### Why each choice

- **EDTA in the carrier** — without it, 0.2 M NaOH precipitates Ca/Mg hydroxides
  in hard samples and blinds the membrane within hours.
- **Acceptor flow < donor flow** (0.6 vs 1.2 mL/min) — preconcentrates NH₃ into a
  smaller acceptor volume. Free sensitivity.
- **Hypochlorite *in* the acceptor** — consumes NH₃ on arrival to non-volatile
  NH₂Cl, so the trap can't leak back. Also drops a third reagent channel. Keep
  OCl⁻:N above 1 but modest; large excess at low pH drives breakpoint oxidation
  to N₂ and signal is lost. **Concentration sets the upper range — see §3.1.**
- **pH 9.2 borate** — monochloramine is the dominant species here. Below pH 7 you
  get dichloramine, which has a different spectrum and wrecks the calibration.
- **Hypochlorite absorbs in the UVC** too, setting a constant elevated baseline.
  Compatible with FIA — the analytical signal is peak height *above* the flowing
  baseline, and the existing blank mechanism handles exactly this.
- **50 cm coil, ambient** — targets D ≈ 4–6 (medium dispersion). Residence to
  peak ≈ 30–35 s, baseline return ≈ 60 s → **~50–60 samples/h**.

### 3.1 Acceptor hypochlorite sets the upper range

Chloramination is 1:1 molar, so the acceptor OCl⁻ concentration — not the optics —
is what caps the top of the curve. At 40 mg/L N (2.86 mM), with ~25 % membrane
transfer into a 0.5× acceptor volume, you deliver ~1.4 mM NH₃ into the acceptor.
Against 1 mM OCl⁻ that is stoichiometrically saturated, and the calibration rolls
over well below the optical limit with no obvious symptom.

Size the acceptor to the sampling point:

| Range needed | Acceptor OCl⁻ | Baseline A @245 nm (ε≈50–80, 10 mm) |
|---|---|---|
| 0–5 mg/L N | 1 mM | 0.05–0.08 |
| 0–20 mg/L N | 3 mM | 0.15–0.24 |
| 0–50 mg/L N | 5 mM | 0.25–0.40 |
| 0–90 mg/L N | 10 mM | 0.50–0.80 |

The consequence: at the wide-range end, OCl⁻ alone eats half the usable
absorbance window. **Dual-beam referencing becomes mandatory, not merely
advisable**, and baseline absorbance doubles as the reagent-health indicator
(it falls as OCl⁻ decays).

### 3.2 Pulse the UVC LED

A 255 nm LED is L50 ≈ 1,000–10,000 h. Run it continuously and it needs replacing
two to eight times a year, drifting the whole time. Gate it instead:

```
60 s LED on, thermal equilibration (no data)
70 s acquisition
─────────────────────────────────────────────
130 s on per 15 min cycle = 14 % duty → years of wall time
```

The warm-up is **mandatory**, not optional — junction temperature drift during
the first minute is larger than the analytical signal at low concentrations. A
660 nm LED (>50,000 h, negligible drift) is genuinely more robust here; this is
the one axis on which Option B wins outright.

### Firmware state machine

The current firmware is a single-point cuvette photometer. The FIA version is a
timed cycle:

```
IDLE               LED off (see §3.2)
 └─► PRIME          pumps on + LED on, 60 s, purge air / LED thermal settle
      └─► BASELINE  acquire flowing reagent reference, 10 s
           │        accept only if RSD < 0.3 %  → store as blank_values
           └─► LOAD          valve = LOAD, sample through loop, 15 s (≥3 loop volumes)
                └─► INJECT   valve = INJECT, t := 0   ◄── timing origin
                     └─► ACQUIRE   sample UVC at 20 Hz until t = 70 s
                          └─► ANALYZE   h = max A(t) in window [20 s, 50 s]
                               │        area = ∫A dt over same window
                               │        c = calibration_poly(h)
                               └─► WASH  hold until A < 0.002, then LOAD next
                                    └─► LED off until next cycle
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
  10 samples *and* split the beam to a second AS7331 as a reference channel. With
  wide-range acceptor chemistry (§3.1) the reference channel is mandatory, since
  OCl⁻ baseline absorbance already consumes much of the dynamic range.
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
| 6 | Gas diffusion cell | PTFE/**PVDF or PP** sandwich, 0.5×1×80 mm grooves — not PMMA, §8.1 | Global FIA GD cell, $620 | machined PVDF, 2 blocks + gasket, $110 |
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
| 32 | Enclosure | **NEMA 4X / IP66 FRP, 600×500×300** — see §8.4 | $450 | $250 |
| 32b | Wet mounting panel | 10 mm PVC Type 1 or HDPE, drilled/tapped | $60 | $40 |
| 32c | Bunded drip tray | folded 316 or molded PP, sloped to item 29 | $70 | $40 |

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

**Rough totals:** lab-grade ≈ $9,400 (≈ $12,800 with the long-path waveguide);
cost-down ≈ $1,750. Option A over Option B saves the heater, one pump channel,
and the nitroprusside handling burden. Totals include the revised enclosure of
§8.4; the earlier IP54 300×250×150 box was both undersized and under-rated.

## 5. Option A vs Option B for a wastewater treatment plant

**Conclusion: Option A, for the opposite of the obvious reason.** Wastewater is a
high-ammonia matrix, so Option B's 30–40× sensitivity is a liability rather than
an advantage.

### 5.1 Range is the decisive factor

Single-configuration linear range, 10 mm cell, usable absorbance window
0.003–1.5 AU:

| | Option A (245 nm, ε≈460) | Option B (660 nm, ε≈1.4×10⁴) |
|---|---|---|
| A per mg/L N (ideal) | 0.033 | 1.0 |
| Linear range, ideal | 0.09 – 45 mg/L | 0.003 – 1.5 mg/L |
| With GD (~25 % transfer, 2× preconc.) | **0.2 – 90 mg/L** | **0.006 – 3 mg/L** |

Against the points you'd actually instrument:

| Point | NH₄-N | Option A | Option B |
|---|---|---|---|
| Raw influent | 25–50 mg/L | in range | needs ~30× dilution |
| Primary effluent | 25–45 mg/L | in range | needs ~20× dilution |
| Aeration basin (control point) | 0.5–10 mg/L | in range | needs ~5× dilution |
| Final effluent | 0.05–3 mg/L | in range | in range |
| Centrate / digester supernatant | 600–1,500 mg/L | needs ~20× | needs ~600× |

Option B covers one of five points without dilution. Every dilution stage is
another pump channel, another confluence point, another calibration factor and
another failure mode — in a device meant to run unattended next to an aeration
basin. Option A spans the plant on one configuration.

Option B *can* be detuned in FIA by shrinking the injection volume and raising
dispersion to D = 20–50. That works, but you then pay for a heater, a fourth
reagent channel and nitroprusside in order to throw the sensitivity away.

### 5.2 Gas diffusion is required either way

WWTP samples run 200–400 mg/L TSS at the influent and 2,000–4,000 mg/L MLSS in
the basin. Neither chemistry tolerates that optically. Commercial analyzers that
skip gas diffusion need an online ultrafiltration module, which is the most
maintenance-hungry part of the instrument.

The GD cell and membrane therefore stay in the BOM regardless, which collapses
the decision to the detection module alone — LED, driver, flow cell, plus (for B)
the heated coil and two extra reagents. Option A's marginal simplicity is the
whole difference:

- **2 reagents vs 4.** Option B adds salicylate (stable) and sodium nitroprusside
  (cyanogenic, light-sensitive, degrades in days). Both options need hypochlorite,
  so B inherits that weakness and adds more.
- **No heated coil.** Chloramination is seconds at pH 9 — no 55 °C block, no PID,
  no RTD, no thermal settling before a valid reading.
- **No cyanide-containing reagent** in a plant operated by operators rather than
  analysts. A procurement and chemical-inventory consideration, not a theoretical
  one.
- **Reuses the AS7331.** No optics redesign, no new driver code path.

### 5.3 Where Option A genuinely loses

**Volatile amines cause positive bias — the one that should worry you.** At pH 12+
in the donor stream, methylamine, dimethylamine and trimethylamine volatilize and
cross the PTFE membrane alongside NH₃, then react with hypochlorite to form
organic chloramines absorbing in the same 240–260 nm region. This cannot be
separated at a single wavelength.

Indophenol is far more selective — primary amines give a weak response and the
660 nm dye is a specific product — so B is effectively immune. If the plant
receives septage haulings, food processing, rendering or fish processing waste,
the bias is significant and variable. For a plain municipal plant it is usually
small. **Check the industrial pretreatment permits before deciding.**

**Not a regulatory-approved method.** Chloramine UV at 245 nm appears on no
approved method list. 40 CFR Part 136 for ammonia means EPA 350.1 or SM 4500-NH₃
— the automated phenate/indophenol family, i.e. Option B's chemistry. For NPDES
permit reporting, Option A is disqualified outright.

This matters less than it sounds, since a homemade analyzer won't be used for
compliance reporting either way, but it fixes the boundary: **Option A is a
process-control and trending instrument.** That is where the value is anyway —
real-time aeration control against basin ammonia is a documented double-digit
energy saving, and it needs fast and reliable far more than accurate.

**Less specific to reaction conditions.** Dichloramine (λmax 295, ε≈260) forms if
acceptor pH sags below ~7, and excess OCl⁻ contributes its own UVC absorbance.
Both shift calibration with no obvious symptom. The dye method is closer to a
digital endpoint. Buffer the acceptor hard and track baseline absorbance.

### 5.4 Recommendation

Build Option A for process control, with three non-negotiables: dual-beam
referencing, a bracketing standard every 10 samples, and a pulsed LED with
enforced warm-up (§3.2). Size acceptor hypochlorite per sampling point (§3.1).

Design the optical block so LED, driver and detector form one swappable module.
If the plant later needs effluent compliance-grade numbers, or the influent turns
out to carry volatile amines, you change the detection module and add the heated
coil rather than rebuilding the fluidics — which is where the cost and the
engineering both live.

**Check first, because it can flip the answer:** the plant's industrial
pretreatment permits and its NPDES ammonia limit. Heavy amine-bearing industrial
load, or a permit at 0.5 mg/L or tighter, argues for B despite everything above.

## 6. Expected performance

Option A, 10 mm cell, dual-beam referencing, 100 µL injection. **Projected from
ε and path length — not measured.**

| Metric | Expected |
|---|---|
| Range | 0.2–90 mg/L NH₃-N, acceptor-dependent (§3.1); dilute above |
| LOD (3σ) | 0.05–0.1 mg/L N (at 1 mM acceptor) |
| Precision | 1.5–3 % RSD at 5 mg/L |
| Throughput | 50–60 samples/h |
| Reagent use | ~2 mL/injection |

LOD and top-of-range trade against each other through the acceptor OCl⁻
concentration — you cannot have both ends at once in a single configuration. For
a WWTP, 3–5 mM (0–20 to 0–50 mg/L) covers influent through basin; drop to 1 mM
for final effluent work.

## 7. Ranked risks

1. **UVC LED thermal/aging drift** — biggest error source. Dual-beam referencing
   (item 19) plus a bracketing standard every 10 samples, plus pulsed operation
   with enforced warm-up (§3.2). Do not skip.
2. **Volatile amine positive bias** (WWTP-specific, §5.3) — methylamines cross the
   membrane and form organic chloramines absorbing at the same wavelength.
   Unresolvable at a single wavelength; check industrial pretreatment permits.
   This is the risk that would send you to Option B.
3. **CO₂ crossing the membrane** — it also permeates PTFE and acidifies the
   acceptor, suppressing chloramine yield. Buffer the acceptor adequately (20 mM
   borate is chosen for this) and check for negative bias on high-alkalinity
   samples.
4. **Membrane fouling** — surfactants wet the PTFE and kill gas transfer
   irreversibly. Inline 20 µm filter; treat the membrane as a scheduled
   consumable (weekly on wastewater).
5. **Hypochlorite decay** — NaOCl loses titer over weeks. Date the stock, prepare
   the working acceptor daily, track baseline absorbance as the health indicator
   (it falls as OCl⁻ decays).
6. **Acceptor OCl⁻ under-sized for the sampling point** (§3.1) — the curve rolls
   over stoichiometrically with no obvious symptom. Verify the top standard reads
   on-curve after any range change.
7. **Pump tubing wear** — changes flow rate, shifting peak time and dispersion.
   The height/area ratio is the early-warning signal.
8. **Ammonia in lab air and DI water** — a classic; the blank will creep. Keep
   reagents capped and vented through an acid trap.

### Safety and waste

The carrier is 0.2 M NaOH (caustic) and the acceptor generates chloramine. Never
let the waste line meet acid — that liberates Cl₂/NHCl₂. Quench waste with
thiosulfate before disposal, and vent the waste container.

## 8. Mechanical construction and plant installation

**Conclusion: sheet metal for the deployed instrument, aluminum profile only for
the bench prototype, and neither for the panel the wet components bolt to.**

### 8.1 Aluminum is disqualified from the wet zone by the chemistry

The carrier is 0.2 M NaOH. Aluminum is amphoteric and dissolves in alkali:

```
2 Al + 2 NaOH + 6 H₂O → 2 Na[Al(OH)₄] + 3 H₂
```

Anodizing protects only roughly pH 4–9, so the oxide layer goes first. A weeping
pump fitting over a T-slot extrusion etches and stains it within days. That
single point rules aluminum out of anywhere a caustic leak can reach,
independent of any structural argument.

Two related material notes:

- **No polycarbonate enclosures.** Alkali hydrolyses PC and causes stress
  cracking. FRP (fiberglass polyester) or 316L only.
- **The GD cell blocks should not be PMMA** (BOM item 6). PMMA is attacked by
  0.2 M NaOH over months; PVDF or PP is the safer machining stock for a part
  that sees caustic continuously.

### 8.2 Material by zone

| Zone | Material | Why |
|---|---|---|
| Outer enclosure | bought FRP or 316L, NEMA 4X / IP66 | don't fabricate the pressure boundary — buying it gets a certified gasket, hinges and latches for less than one-off bending |
| Wet mounting panel | 10 mm PVC Type 1 or HDPE | NaOH + NaOCl proof, tappable, cheap to re-drill when the manifold layout changes |
| Optical block | machined aluminum (as BOM item 20) | needs thermal mass for the LED and dimensional stability; sits above the drip zone, never wetted |
| Electronics subpanel | steel or aluminum DIN plate, upper compartment | bonded to ground, shields the analog front end |
| Bund / drip tray | folded 316 or molded PP, sloped to the leak sensor | gives BOM item 29 something to detect into |

### 8.3 Profile vs sheet, on the criteria that decide it

| | Aluminum profile (T-slot) | Folded sheet |
|---|---|---|
| Ingress protection | none — needs a second enclosure anyway | *is* the enclosure; gasket surfaces come free with the flanges |
| Layout changes | move a bracket, no drilling — big win while the manifold is unproven | every hole committed at fab time |
| Volume cost | 25–30 mm sections eat interior space | 1.5 mm wall, negligible |
| Washdown | slots trap spilled reagent and grime | wipes clean |
| Vibration (blower buildings) | T-nut joints creep loose without threadlocker | monolithic once welded or riveted |
| Corrosion in plant air | pits in chloride, dissolves in caustic, and stainless hardware makes the aluminum the anode | 316L passivates; painted mild steel rusts from every scratch, so don't |
| Optical stability | good stiffness | thin panels flex; needs a local thick pad under the optical block |
| One-off cost | ~$150–200 in profile, brackets and panels | ~$200–350 laser-and-bend in 316, or $180–400 off-shelf IP66 |

**Optical stability deserves emphasis** given the 0.002 AU wash threshold in the
firmware state machine (§3). Micrometre-scale shifts between LED, cell and detector read
as baseline drift. Bolt the optical block at three points to a 6 mm plate or a
boss, never to a 1.5 mm sheet wall that breathes with temperature.

### 8.4 The hybrid that commercial process analysers converge on

Buy a NEMA 4X cabinet, roughly 600 × 500 × 300, wall- or 316-stand-mounted.
Inside, a hinged non-metallic panel:

```
 ┌──────────── NEMA 4X / IP66 cabinet, 600×500×300 ────────────┐
 │  UPPER   MCU · drivers · LED driver · optical module        │  ← dry
 │  ────────────────────────────────────────────────────────   │
 │  MIDDLE  pumps · valves · GD cell · coils · flow cell       │  ← wet
 │  ────────────────────────────────────────────────────────   │
 │  LOWER   reagent bottles · standard · waste, in a bund      │  ← wettest
 │          ▼ leak pad (item 29) at the low corner of the tray │
 └──────────────────────────────────────────────────────────────┘
```

Everything wet lives below everything electrical, because leaks go down.

That reduces the original question to the internal chassis, where a flat plate
plus small brackets beats extrusion on space alone. Keep ~2 m of 2020 profile for
the bench prototype, then transfer the proven layout to a drilled PVC panel once
the manifold stops moving.

### 8.5 Siting it at the plant

End-of-aeration, or the basin control point, is where Option A earns its keep —
that is what aeration control trims (§5.3). Practical constraints:

- **Keep the sample path short.** At 1.2 mL/min through 5 m of 3 mm tubing you
  carry ~35 mL of dead volume, roughly 30 minutes of transport lag — which
  destroys a control loop. Run a fast recirculating sample loop into a
  constant-head overflow cup next to the analyser and let the sample pump draw
  from the cup at atmospheric pressure. Lag drops under a minute.
- **Plumb the waste.** ~2 mL/injection at 50/h is ~2.9 L/day, so a carboy is a
  daily chore. Thiosulfate-quenched waste returned to the plant head is normally
  acceptable and needs plant sign-off, not new hardware.
- **Enclosure heat and sun.** Sealed means no venting, so heat leaves by
  conduction — metal helps, dark metal in direct sun hurts more. Light colour plus
  a sunshade either way. If winter reaches freezing, a thermostatic heater and
  insulation, which argues again for a sealed box over an open frame.
- **The environment varies by sampling point.** Headworks and influent carry H₂S,
  which becomes biogenic sulfuric acid on damp surfaces and eats metals and
  concrete alike — FRP or PVC is the plant-standard answer there. An open aeration
  basin walkway is mild enough for 316.
- **Grounding and EMI.** A metal cabinet bonded to plant ground shields the UVC
  front end from nearby VFD-driven blowers. FRP gives no shielding, so rely on
  shielded cable and a ground bar, and keep the AS7331 I²C runs short.
- **Hardware.** 316 fasteners and anchors throughout. Never mix 316 hardware into
  aluminum in wet plant air — galvanic coupling puts the aluminum on the losing
  side.

## 9. Next step

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
