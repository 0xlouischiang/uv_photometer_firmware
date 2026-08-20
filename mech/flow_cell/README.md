# Optical block — flow cell / cuvette holder

`AMMONIA_FIA_SENSOR_DESIGN.md` BOM item 20 ("optical block... LED/cell/detector
alignment, light-tight"). Holds a 10 mm cuvette between the LED source board
(`../../uv_abc_led`) and the AS7331 sensor board (`../../uv_abc_sensor_hy20`),
with the CoreS3 (this repo's firmware host) cradled on top.

## Files

| File | Purpose |
|---|---|
| `flow_cell_holder.py` | Parametric modeling script, 44-item geometry self-check |
| `flow_cell_holder.step` | Holder alone — this is what goes to a machinist |
| `flow_cell_assembly.step` | Assembly (holder + CoreS3 / sensor PCB / LED PCB / cuvette placeholders), for checking fit |
| `flow_cell_holder.FCStd` / `flow_cell_assembly.FCStd` | Native FreeCAD files |
| `flow_cell_sideview.png` / `.svg` | Annotated elevation through the optical axis |

Regenerate:

```bash
"/c/Program Files/FreeCAD 1.0/bin/freecadcmd.exe" flow_cell_holder.py
```

Any dimension change re-runs the self-check; a geometry conflict exits
non-zero (`SELF-CHECK FAILED` + `SystemExit(1)`) instead of silently writing
bad STEP files.

## The one fact that drives this design

`uv_abc_sensor_hy20`'s AS7331 die sits **1.27 mm off-centre** from its own
board's 4-hole mounting pattern (in the board's local Y). `uv_abc_led`'s LED
die sits **exactly on-centre** of its own mounting pattern. Bolt both boards
to bosses at the same height on one block and the beam misses the detector
by 1.27 mm — silently, since nothing about the boards themselves signals the
mismatch.

So the block's two boss patterns sit at *different* heights:

```
LED boss centre Z     15.16 mm
sensor boss centre Z  16.43 mm   (1.27 mm above the LED boss — exactly the die-offset gap)
optical axis (beam) Z 15.16 mm
```

Both heights are computed from the raw coordinates read out of each board's
own `.kicad_pcb` (see the constants at the top of `flow_cell_holder.py`), not
assumed equal and not hand-tuned. This is this design's equivalent of
`gd_cell.py`'s flip-symmetry check — a default assumption (die = pattern
centre) that is wrong for one of the two boards, checked explicitly rather
than trusted.

## Key dimensions

```
block envelope        36.9 x 25.1 x 41.0 mm
optical axis height   15.16 mm
cuvette pocket        13.1 x 13.1 mm, 37.0 mm deep, open top
light channels        Ø6.0 mm, one per mounting face, colinear
boss patterns         sensor 23.72 x 22.86 mm (M2.5 tap), LED 24.92 x 18.72 mm (M2.5 tap)
CoreS3 cradle inner   55.0 x 55.0 mm (54 x 54 mm envelope + 0.5 mm/side)
base flange           4x M4 clearance corner bolts, same convention as gd_cell.py
```

The cuvette pocket sits directly under the CoreS3 cradle in plan view, so the
cradle deck can't be carried on a single central post — it would land on top
of the cuvette sticking up out of the open pocket. It's carried on **two legs
that stand outside the pocket's footprint in X**, tall enough to clear the
cuvette's stick-up, with the deck cantilevered off both legs.

## Board inputs (read from KiCad, not re-derived)

| | `uv_abc_sensor_hy20` | `uv_abc_led` |
|---|---|---|
| Board outline | 28.8 x 27.94 mm | 30.2 x 24.0 mm |
| Mount holes (M2.5) | 23.72 x 22.86 mm rect, centred on outline | 24.92 x 18.72 mm rect |
| Die offset from hole-rect centre | (0, −1.27) mm | (0, 0) mm |
| Connector | HY2.0 4-pin, Grove pinout | HY2.0 4-pin, Grove pinout |

## Material

**Machined aluminum** — `AMMONIA_FIA_SENSOR_DESIGN.md` §8.2: "needs thermal
mass for the LED and dimensional stability; sits above the drip zone, never
wetted." This is the opposite of `gd_cell.py`'s PVDF/PP-only rule — do not
carry that rule over. The GD cell sees 0.2 M NaOH continuously; this block
never contacts the carrier or acceptor stream at all, so aluminum's normal
disqualification (§8.1) doesn't apply here.

## Open decisions (placeholders, not selected parts)

- **CoreS3 cradle geometry is unvalidated.** No screw/snap spec for a CoreS3
  exists anywhere in this repo or in M5Stack's own `M5_Hardware` — their own
  case accessories (K128 series) are snap/frame fits around the shell, not
  bolted interfaces. The cradle here is sized to the *measured* STL envelope
  (`M5_Hardware/Products/K128_CoreS3/Structures/CoreS3.stl`, 54 x 54 x
  ~31.5 mm) with a flat frame lip, same placeholder treatment `cabinet.py`
  gives its pump/valve footprints. Needs a print-and-fit pass before trusting
  the retention feature.
- **Cuvette is generic, not a catalog part.** 12.5 x 12.5 x 45 mm is a
  representative 10 mm-path macro cuvette footprint (matches the design
  doc's BOM item 15 cost-down option: "quartz cuvette + PTFE flow insert"),
  not a specific vendor's dimensions. The flow insert itself (how liquid
  actually enters/exits a dropped-in cuvette) is not modeled at all.
- **Beam height within the pocket is a placeholder.** Z_AXIS is set purely
  by the boss patterns' own margin requirements, not by any specified fill
  level or beam-to-liquid-surface requirement.
- **No reference channel / dual-beam provision.** Design doc §7 risk #1
  calls dual-beam referencing a non-negotiable for LED drift — this model is
  single-beam only (BOM item 19, the reference detector, is out of scope
  here).
- **`../../cuvette_holder`** (the Open Colorimeter's TSL2591 holder) was
  checked as a size reference only, not reused — different sensor, and built
  with PartDesign sketches rather than this repo's scripted-boolean
  convention.
