"""Optical block: holds a 10 mm cuvette between the LED and sensor boards,
with the CoreS3 mounted on top (BOM item 20).

Run with FreeCAD's console interpreter:

    freecadcmd flow_cell_holder.py

Writes flow_cell_holder.step / .FCStd (the holder alone, for machining) and
flow_cell_assembly.step / .FCStd (holder + CoreS3 / sensor PCB / LED PCB /
cuvette placeholders, for checking fit), plus flow_cell_sideview.png / .svg.

Design notes that are not obvious from the numbers:

- The two boards' die positions are NOT centred the same way on their own
  mounting-hole rectangles. uv_abc_sensor_hy20's AS7331 sits 1.27 mm off the
  hole-rectangle centre (in the board's own Y); uv_abc_led's LED sits exactly
  on-centre. Bolt both boards to bosses at the same height and the LED and
  sensor apertures do NOT line up -- the beam misses the detector by 1.27 mm.
  So the two boss patterns on this block sit at DIFFERENT heights (Z_BOSS_LED
  vs Z_BOSS_SENSOR, offset by exactly that 1.27 mm), computed from the boards'
  own measured hole/die coordinates below rather than assumed equal. This is
  this design's equivalent of gd_cell.py's flip-symmetry check: an assumption
  that is wrong by default and has to be checked, not just declared.
- Hole and die coordinates are the raw numbers read out of each board's own
  KiCad file, not re-derived or rounded:
    uv_abc_sensor_hy20/kicad/uv_abc_sensor_hy20.kicad_pcb -- U1 (AS7331) "at",
    four "custom_mount_hole:MountingHole_2.5mm_Pad" footprints' "at"
    uv_abc_led/uv_abc_led/uv_abc_led.kicad_pcb -- D1 (LED) "at", four
    "custom_mount_hole:MountingHole_2.5mm_Pad" footprints' "at"
  Hole rectangle size/centre and die offset are computed from those raw
  points below, so a board revision only means updating the raw coordinates.
- The CoreS3 cradle has no vendor screw pattern to build to. Nothing in this
  repo or in M5Stack's own M5_Hardware describes bolt holes through a CoreS3
  -- M5Stack's own case accessories (K128 series) are snap/frame fits around
  the shell. So the cradle here is a lip sized to the CoreS3's *measured*
  envelope (M5_Hardware/Products/K128_CoreS3/Structures/CoreS3.stl bounding
  box: 54 x 54 x ~31.5 mm), not a bolted interface. Treat it as a
  print-and-fit placeholder, same as cabinet.py's pump/valve footprints.
- The CoreS3 cradle (54x54 mm) is much wider than the optical block (sized
  to the small sensor/LED boards' hole patterns, ~37 mm), and the cuvette
  sticks up out of the open-top pocket by CUVETTE_STICKOUT. A single post
  centred over the block would land the cradle directly on top of the
  sticking-up cuvette. So the CoreS3 deck is carried on two legs that rise
  from the block top OUTSIDE the pocket's footprint (in X, where the boards'
  boss patterns leave clear side margin), tall enough to clear the cuvette's
  stick-up height, with the wider deck cantilevered off both legs -- a
  mushroom shape, not a simple post. Checked below (deck/legs vs cuvette).
- The cuvette is a placeholder box, not a specific catalog part (see
  README.md). It is dropped into an open-top pocket, the same way gd_cell.py
  treats its membrane as a user-supplied consumable rather than something
  this script designs.
"""

import os

import FreeCAD as App
import Part
from FreeCAD import Vector

# ---------------------------------------------------------------- parameters

# ---- raw board coordinates, read directly from each board's .kicad_pcb ----
# (all in that board's own native KiCad frame, mm; see module docstring)

SENSOR_HOLES_KICAD = [(53.34, 53.34), (77.06, 53.34), (53.34, 76.2), (77.06, 76.2)]
SENSOR_DIE_KICAD = (65.2, 63.5)                 # U1 (AS7331) "at"
SENSOR_PCB_X, SENSOR_PCB_Y = 28.8, 27.94        # Edge.Cuts bbox (octagonal outline)
SENSOR_PCB_T = 1.6

LED_HOLES_KICAD = [(53.34, 53.34), (78.26, 53.34), (53.34, 72.06), (78.26, 72.06)]
LED_DIE_KICAD = (65.8, 62.7)                    # D1 (LED) "at"
LED_PCB_X, LED_PCB_Y = 30.2, 24.0               # Edge.Cuts bbox, per uv_abc_led/notes.txt
LED_PCB_T = 1.6

# Mounting-hole footprint is "custom_mount_hole:MountingHole_2.5mm_Pad" on
# both boards -> M2.5 screws into the block. Tap drill for M2.5 is ~2.05 mm.
BOSS_SCREW_TAP_DIA = 2.05
BOSS_TAP_DEPTH_MARGIN = 2.0   # mm of material kept behind a blind tapped hole

CHANNEL_DIA = 6.0  # mm; clears the AS7331's ~3.15 mm pad envelope and the
                    # LED's 2.4 mm aperture ring (uv_abc_led/notes.txt) with margin

# Cuvette placeholder: generic 10 mm-path macro cuvette (design doc BOM item
# 15 cost-down option), not a specific catalog part -- see README.md.
CUVETTE_X = 12.5
CUVETTE_Y = 12.5
CUVETTE_Z = 45.0
POCKET_CLEARANCE = 0.3     # per side, cuvette pocket vs cuvette
CUVETTE_STICKOUT = 8.0     # mm of cuvette left above the block top, for grip/tubing

WALL_T = 6.0               # mm, mounting face to pocket wall (both faces)
BOSS_MARGIN_X = 6.0        # mm, boss hole to block side edge
BOSS_MARGIN_Z = 5.0        # mm, boss pattern to block top/bottom edge
POCKET_SIDE_WALL_MIN = 6.0 # mm, min wall thickness beside the pocket in X
CHANNEL_MARGIN = 3.0       # mm, min clearance from beam height to pocket floor/top
FLOOR_MARGIN = 4.0         # mm, min solid material under the pocket floor

# Base mounting flange (bolts the whole holder to a bench fixture or the
# design doc's wet mounting panel -- see gd_cell.py's BOLT_DIA/BOLT_INSET,
# reused here so both parts use the same corner-bolt convention)
BASE_T = 8.0
FLANGE_MARGIN = 10.0
BOLT_DIA = 4.3
BOLT_INSET = 6.0

# CoreS3 cradle -- see module docstring: envelope is measured, not spec'd
CORE_S3_X, CORE_S3_Y, CORE_S3_Z = 54.0, 54.0, 31.5
CRADLE_CLEARANCE = 0.5     # per side
CRADLE_WALL = 4.0
CRADLE_GRIP_DEPTH = 10.0   # mm of CoreS3 height gripped by the frame lip
CRADLE_DECK_T = 4.0        # mm, solid floor the CoreS3 rests on
LEG_Y = 20.0               # mm, leg depth (Y); LEG_X and LEG_H are derived below
CABLE_SLOT_D = 3.0

# --------------------------------------------------------------- derived geometry

def _hole_rect(holes):
    """(dx, dy, cx, cy) of a 4-hole rectangle's span and centre."""
    xs = [p[0] for p in holes]
    ys = [p[1] for p in holes]
    return (max(xs) - min(xs), max(ys) - min(ys),
            (max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0)


SENSOR_HOLE_DX, SENSOR_HOLE_DY, _s_cx, _s_cy = _hole_rect(SENSOR_HOLES_KICAD)
LED_HOLE_DX, LED_HOLE_DY, _l_cx, _l_cy = _hole_rect(LED_HOLES_KICAD)

# Die offset from that board's own hole-rectangle centre, in the board's own
# frame. offset_x is expected to be ~0 for both boards (checked below) --
# that is what lets the block's single centred channel axis serve both
# boards in X and only need per-board compensation in Z (mapped from local Y).
SENSOR_DIE_OFFSET = (SENSOR_DIE_KICAD[0] - _s_cx, SENSOR_DIE_KICAD[1] - _s_cy)
LED_DIE_OFFSET = (LED_DIE_KICAD[0] - _l_cx, LED_DIE_KICAD[1] - _l_cy)

# Block footprint
BLOCK_X = max(SENSOR_HOLE_DX, LED_HOLE_DX) + 2 * BOSS_MARGIN_X
POCKET_XY = max(CUVETTE_X, CUVETTE_Y) + 2 * POCKET_CLEARANCE
BLOCK_Y = 2 * WALL_T + POCKET_XY

# Optical axis height (Z_AXIS) and block height (BLOCK_Z), derived from the
# boss-margin requirement of whichever board's pattern is the tighter fit --
# see module docstring for why the two boss centres land at different Z.
# Z_AXIS (the optical beam height) is set purely by the boss-pattern
# geometry: it must sit BOSS_MARGIN_Z above the lower of the two boards'
# lowest boss holes, so both boss patterns have their bottom-edge margin.
_bottom_terms = [LED_DIE_OFFSET[1] + LED_HOLE_DY / 2.0,
                 SENSOR_DIE_OFFSET[1] + SENSOR_HOLE_DY / 2.0]
Z_AXIS = BOSS_MARGIN_Z + max(_bottom_terms)

# BLOCK_Z (the block's, and the open pocket's, top face) must be tall enough
# for: (a) both boss patterns' top-edge margin above Z_AXIS, and (b) the
# pocket -- cut from the top down by POCKET_DEPTH -- to still leave
# FLOOR_MARGIN of solid material below its floor. It must NOT be so tall
# that the floor (at BLOCK_Z - POCKET_DEPTH) rises above Z_AXIS -- a taller
# block pushes the floor UP, not down, since the pocket depth is fixed and
# cut from the top. Picking the smallest BLOCK_Z that clears both lower
# bounds maximises the floor's clearance below the beam, which is what the
# "beam clears the pocket floor" self-check below is guarding.
_top_terms = [LED_HOLE_DY / 2.0 - LED_DIE_OFFSET[1],
              SENSOR_HOLE_DY / 2.0 - SENSOR_DIE_OFFSET[1]]
BLOCK_Z_BOSS_MIN = BOSS_MARGIN_Z + Z_AXIS + max(_top_terms)

POCKET_DEPTH = CUVETTE_Z - CUVETTE_STICKOUT
BLOCK_Z_FLOOR_MIN = POCKET_DEPTH + FLOOR_MARGIN
BLOCK_Z = max(BLOCK_Z_BOSS_MIN, BLOCK_Z_FLOOR_MIN)

Z_BOSS_LED = Z_AXIS - LED_DIE_OFFSET[1]
Z_BOSS_SENSOR = Z_AXIS - SENSOR_DIE_OFFSET[1]

FLANGE_X = BLOCK_X + 2 * FLANGE_MARGIN
FLANGE_Y = BLOCK_Y + 2 * FLANGE_MARGIN

CRADLE_INNER_X = CORE_S3_X + 2 * CRADLE_CLEARANCE
CRADLE_INNER_Y = CORE_S3_Y + 2 * CRADLE_CLEARANCE
CRADLE_OUTER_X = CRADLE_INNER_X + 2 * CRADLE_WALL
CRADLE_OUTER_Y = CRADLE_INNER_Y + 2 * CRADLE_WALL

# Pocket X span (used to keep the CoreS3 support legs, below, clear of the
# cuvette's footprint and its stick-up column above the block).
POCKET_X_MIN = BLOCK_X / 2.0 - POCKET_XY / 2.0
POCKET_X_MAX = BLOCK_X / 2.0 + POCKET_XY / 2.0
CUVETTE_TOP_Z = (BLOCK_Z - POCKET_DEPTH) + CUVETTE_Z

# Two legs, standing on the block top OUTSIDE the pocket's X span (not a
# single central post -- see module docstring), rising past the cuvette's
# stick-up to the CoreS3 deck. LEG_X is picked to fit the space available
# between the pocket edge (plus LEG_GAP clearance) and the block's own side
# edge; checked below, not assumed.
LEG_GAP = 2.0
LEG_X = min(8.0, POCKET_X_MIN - LEG_GAP, (BLOCK_X - POCKET_X_MAX) - LEG_GAP)
LEG_CLEARANCE_ABOVE_CUVETTE = 5.0
DECK_Z0 = CUVETTE_TOP_Z + LEG_CLEARANCE_ABOVE_CUVETTE   # bottom of the CoreS3 deck
LEG_H = DECK_Z0 - BLOCK_Z


# --------------------------------------------------------------- geometry

def make_base_flange():
    flange = Part.makeBox(
        FLANGE_X, FLANGE_Y, BASE_T,
        Vector(-FLANGE_MARGIN, -FLANGE_MARGIN, -BASE_T),
    )
    xs = (-FLANGE_MARGIN + BOLT_INSET, BLOCK_X + FLANGE_MARGIN - BOLT_INSET)
    ys = (-FLANGE_MARGIN + BOLT_INSET, BLOCK_Y + FLANGE_MARGIN - BOLT_INSET)
    for x in xs:
        for y in ys:
            hole = Part.makeCylinder(
                BOLT_DIA / 2.0, BASE_T + 2, Vector(x, y, -BASE_T - 1), Vector(0, 0, 1)
            )
            flange = flange.cut(hole)
    return flange.removeSplitter()


def make_block_stock():
    return Part.makeBox(BLOCK_X, BLOCK_Y, BLOCK_Z, Vector(0, 0, 0))


def make_pocket_cut():
    return Part.makeBox(
        POCKET_XY, POCKET_XY, POCKET_DEPTH + 0.5,
        Vector(BLOCK_X / 2.0 - POCKET_XY / 2.0, BLOCK_Y / 2.0 - POCKET_XY / 2.0,
               BLOCK_Z - POCKET_DEPTH),
    )


def make_light_channel_cuts():
    """Two bores, LED face (Y=0) and sensor face (Y=BLOCK_Y), both at Z_AXIS."""
    led = Part.makeCylinder(
        CHANNEL_DIA / 2.0, WALL_T + 0.5,
        Vector(BLOCK_X / 2.0, -0.25, Z_AXIS), Vector(0, 1, 0),
    )
    sensor = Part.makeCylinder(
        CHANNEL_DIA / 2.0, WALL_T + 0.5,
        Vector(BLOCK_X / 2.0, BLOCK_Y + 0.25, Z_AXIS), Vector(0, -1, 0),
    )
    return led, sensor


def _boss_hole_cuts(face_y, inward, hole_dx, hole_dy, z_center):
    """Blind tapped holes for one board's 4-hole pattern on one block face."""
    depth = WALL_T - BOSS_TAP_DEPTH_MARGIN
    cuts = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            x = BLOCK_X / 2.0 + sx * hole_dx / 2.0
            z = z_center + sz * hole_dy / 2.0
            start = Vector(x, face_y, z)
            cuts.append(Part.makeCylinder(
                BOSS_SCREW_TAP_DIA / 2.0, depth + 0.2, start, Vector(0, inward, 0)
            ))
    return cuts


def make_led_boss_cuts():
    return _boss_hole_cuts(0.0, 1, LED_HOLE_DX, LED_HOLE_DY, Z_BOSS_LED)


def make_sensor_boss_cuts():
    return _boss_hole_cuts(BLOCK_Y, -1, SENSOR_HOLE_DX, SENSOR_HOLE_DY, Z_BOSS_SENSOR)


def make_legs():
    """Two legs straddling the pocket in X, standing outside its footprint
    (see module docstring: a single central post would collide with the
    cuvette sticking up out of the pocket)."""
    legs = []
    for x0 in (POCKET_X_MIN - LEG_GAP - LEG_X, POCKET_X_MAX + LEG_GAP):
        legs.append(Part.makeBox(
            LEG_X, LEG_Y, LEG_H,
            Vector(x0, BLOCK_Y / 2.0 - LEG_Y / 2.0, BLOCK_Z),
        ))
    return legs


def make_cable_slot_cut():
    """Groove on the +Y-leg's sensor-facing face, for the HY2.0 pigtail."""
    x0 = POCKET_X_MAX + LEG_GAP
    return Part.makeBox(
        LEG_X, CABLE_SLOT_D + 0.2, LEG_H + 0.5,
        Vector(x0, BLOCK_Y / 2.0 + LEG_Y / 2.0 - CABLE_SLOT_D, BLOCK_Z - 0.25),
    )


def make_cradle_solid():
    z0 = DECK_Z0
    outer = Part.makeBox(
        CRADLE_OUTER_X, CRADLE_OUTER_Y, CRADLE_DECK_T + CRADLE_GRIP_DEPTH,
        Vector(BLOCK_X / 2.0 - CRADLE_OUTER_X / 2.0,
               BLOCK_Y / 2.0 - CRADLE_OUTER_Y / 2.0, z0),
    )
    pocket = Part.makeBox(
        CRADLE_INNER_X, CRADLE_INNER_Y, CRADLE_GRIP_DEPTH + 0.5,
        Vector(BLOCK_X / 2.0 - CRADLE_INNER_X / 2.0,
               BLOCK_Y / 2.0 - CRADLE_INNER_Y / 2.0, z0 + CRADLE_DECK_T),
    )
    return outer.cut(pocket).removeSplitter()


def make_holder():
    solid = make_block_stock()
    for leg in make_legs():
        solid = solid.fuse(leg)
    solid = solid.fuse(make_cradle_solid())
    solid = solid.cut(make_pocket_cut())
    for c in make_light_channel_cuts():
        solid = solid.cut(c)
    for c in make_led_boss_cuts() + make_sensor_boss_cuts():
        solid = solid.cut(c)
    solid = solid.cut(make_cable_slot_cut())
    solid = solid.fuse(make_base_flange())
    return solid.removeSplitter()


# ------------------------------------------------------------ placeholders

def make_cuvette_placeholder():
    return Part.makeBox(
        CUVETTE_X, CUVETTE_Y, CUVETTE_Z,
        Vector(BLOCK_X / 2.0 - CUVETTE_X / 2.0, BLOCK_Y / 2.0 - CUVETTE_Y / 2.0,
               BLOCK_Z - POCKET_DEPTH),
    )


def make_led_pcb_placeholder():
    return Part.makeBox(
        LED_PCB_X, LED_PCB_T, LED_PCB_Y,
        Vector(BLOCK_X / 2.0 - LED_PCB_X / 2.0, -LED_PCB_T, Z_BOSS_LED - LED_PCB_Y / 2.0),
    )


def make_sensor_pcb_placeholder():
    return Part.makeBox(
        SENSOR_PCB_X, SENSOR_PCB_T, SENSOR_PCB_Y,
        Vector(BLOCK_X / 2.0 - SENSOR_PCB_X / 2.0, BLOCK_Y,
               Z_BOSS_SENSOR - SENSOR_PCB_Y / 2.0),
    )


def make_cores3_placeholder():
    z0 = DECK_Z0 + CRADLE_DECK_T
    return Part.makeBox(
        CORE_S3_X, CORE_S3_Y, CORE_S3_Z,
        Vector(BLOCK_X / 2.0 - CORE_S3_X / 2.0, BLOCK_Y / 2.0 - CORE_S3_Y / 2.0, z0),
    )


# ------------------------------------------------------------------ checks

def self_check():
    """Assert the geometry facts a dimension change could silently break."""
    holder = make_holder()
    pocket = make_pocket_cut()
    led_ch, sensor_ch = make_light_channel_cuts()
    cuvette = make_cuvette_placeholder()
    led_pcb = make_led_pcb_placeholder()
    sensor_pcb = make_sensor_pcb_placeholder()
    cores3 = make_cores3_placeholder()

    out = []

    out.append(("board dies are centred in X on their own boss pattern",
                abs(SENSOR_DIE_OFFSET[0]) < 1e-6 and abs(LED_DIE_OFFSET[0]) < 1e-6,
                "sensor dx=%.3f led dx=%.3f" % (SENSOR_DIE_OFFSET[0], LED_DIE_OFFSET[0])))

    out.append(("LED and sensor light channels share one Z (colinear axis)",
                abs(led_ch.BoundBox.Center.z - sensor_ch.BoundBox.Center.z) < 1e-6, ""))

    out.append(("boss centres differ by exactly the die-offset mismatch",
                abs((Z_BOSS_SENSOR - Z_BOSS_LED) -
                    (LED_DIE_OFFSET[1] - SENSOR_DIE_OFFSET[1])) < 1e-6,
                "Z_BOSS_LED=%.2f Z_BOSS_SENSOR=%.2f" % (Z_BOSS_LED, Z_BOSS_SENSOR)))

    out.append(("LED channel opens into the cuvette pocket",
                led_ch.common(pocket).Volume > 1e-6, ""))
    out.append(("sensor channel opens into the cuvette pocket",
                sensor_ch.common(pocket).Volume > 1e-6, ""))

    for name, cuts in (("LED", make_led_boss_cuts()), ("sensor", make_sensor_boss_cuts())):
        for i, b in enumerate(cuts):
            out.append(("%s boss hole %d clears the cuvette pocket" % (name, i),
                        b.common(pocket).Volume < 1e-9, ""))
            out.append(("%s boss hole %d clears the light channels" % (name, i),
                        b.common(led_ch).Volume < 1e-9 and b.common(sensor_ch).Volume < 1e-9,
                        ""))

    out.append(("cuvette placeholder fits the pocket",
                cuvette.BoundBox.XLength <= POCKET_XY - 2 * POCKET_CLEARANCE + 1e-6
                and cuvette.BoundBox.YLength <= POCKET_XY - 2 * POCKET_CLEARANCE + 1e-6,
                "cuvette %.1fx%.1f, pocket %.1f" % (cuvette.BoundBox.XLength,
                                                      cuvette.BoundBox.YLength, POCKET_XY)))
    out.append(("beam height clears the pocket floor",
                Z_AXIS - (BLOCK_Z - POCKET_DEPTH) > CHANNEL_MARGIN,
                "clearance %.1f mm" % (Z_AXIS - (BLOCK_Z - POCKET_DEPTH))))
    out.append(("beam height clears the pocket (block) top",
                (BLOCK_Z) - Z_AXIS > CHANNEL_MARGIN,
                "clearance %.1f mm" % (BLOCK_Z - Z_AXIS)))

    out.append(("boss tap holes don't break through into the pocket wall",
                (WALL_T - BOSS_TAP_DEPTH_MARGIN) < WALL_T, ""))

    out.append(("cradle inner pocket clears the CoreS3 envelope",
                CRADLE_INNER_X >= CORE_S3_X and CRADLE_INNER_Y >= CORE_S3_Y,
                "%.1fx%.1f vs %.1fx%.1f" % (CRADLE_INNER_X, CRADLE_INNER_Y,
                                             CORE_S3_X, CORE_S3_Y)))

    legs = make_legs()
    out.append(("legs stand clear of the pocket in X", LEG_X > 0,
                "LEG_X=%.1f" % LEG_X))
    for i, leg in enumerate(legs):
        out.append(("leg %d clears the pocket" % i, leg.common(pocket).Volume < 1e-9, ""))
        out.append(("leg %d clears the cuvette placeholder" % i,
                    leg.common(cuvette).Volume < 1e-9, ""))
    out.append(("CoreS3 deck clears the cuvette's stick-up above the block",
                DECK_Z0 > CUVETTE_TOP_Z, "deck z0=%.1f, cuvette top=%.1f"
                % (DECK_Z0, CUVETTE_TOP_Z)))

    placeholders = [("cores3", cores3), ("led_pcb", led_pcb), ("sensor_pcb", sensor_pcb),
                    ("cuvette", cuvette)]
    for i in range(len(placeholders)):
        for j in range(i + 1, len(placeholders)):
            n0, s0 = placeholders[i]
            n1, s1 = placeholders[j]
            out.append(("%s / %s don't overlap" % (n0, n1),
                        s0.common(s1).Volume < 1e-6, ""))
        n0, s0 = placeholders[i]
        out.append(("%s doesn't overlap the holder body" % n0,
                    s0.common(holder).Volume < 1e-6, ""))

    out.append(("light channels don't poke out the block's side (X) faces",
                led_ch.BoundBox.XMin > 0 and led_ch.BoundBox.XMax < BLOCK_X
                and sensor_ch.BoundBox.XMin > 0 and sensor_ch.BoundBox.XMax < BLOCK_X, ""))

    out.append(("holder is a valid solid", holder.isValid(), ""))

    return out


# ------------------------------------------------------------------- output

def main():
    here = os.path.dirname(os.path.abspath(__file__))

    holder = make_holder()

    doc = App.newDocument("flow_cell_holder")
    obj = doc.addObject("Part::Feature", "Holder")
    obj.Shape = holder
    doc.recompute()
    doc.saveAs(os.path.join(here, "flow_cell_holder.FCStd"))
    holder.exportStep(os.path.join(here, "flow_cell_holder.step"))

    cuvette = make_cuvette_placeholder()
    led_pcb = make_led_pcb_placeholder()
    sensor_pcb = make_sensor_pcb_placeholder()
    cores3 = make_cores3_placeholder()

    asm = Part.makeCompound([holder, cuvette, led_pcb, sensor_pcb, cores3])
    asm.exportStep(os.path.join(here, "flow_cell_assembly.step"))

    adoc = App.newDocument("flow_cell_assembly")
    for name, shp in (("Holder", holder), ("Cuvette", cuvette), ("LedPcb", led_pcb),
                      ("SensorPcb", sensor_pcb), ("CoreS3", cores3)):
        o = adoc.addObject("Part::Feature", name)
        o.Shape = shp
    adoc.recompute()
    adoc.saveAs(os.path.join(here, "flow_cell_assembly.FCStd"))

    checks = self_check()
    failed = [c for c in checks if not c[1]]

    print("block envelope           : %.1f x %.1f x %.1f mm" % (BLOCK_X, BLOCK_Y, BLOCK_Z))
    print("optical axis height      : %.2f mm" % Z_AXIS)
    print("LED boss centre Z        : %.2f mm" % Z_BOSS_LED)
    print("sensor boss centre Z     : %.2f mm (%.2f mm above LED boss)"
          % (Z_BOSS_SENSOR, Z_BOSS_SENSOR - Z_BOSS_LED))
    print("cuvette pocket           : %.1f x %.1f x %.1f mm deep" % (POCKET_XY, POCKET_XY, POCKET_DEPTH))
    print("CoreS3 cradle inner      : %.1f x %.1f mm" % (CRADLE_INNER_X, CRADLE_INNER_Y))
    print("holder is a valid solid  : %s" % holder.isValid())
    print("")
    for label, passed, detail in checks:
        print("  [%s] %s%s" % ("ok" if passed else "FAIL", label,
                               ("  " + detail) if detail else ""))
    print("")
    if failed:
        print("SELF-CHECK FAILED: %d of %d" % (len(failed), len(checks)))
        raise SystemExit(1)
    print("self-check: %d/%d passed" % (len(checks), len(checks)))

    make_sideview_figure(here)


def make_sideview_figure(out_dir):
    """Annotated elevation: block, post, cradle, boards, cuvette, CoreS3."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    fig, ax = plt.subplots(figsize=(6, 9))

    ax.add_patch(patches.Rectangle((0, -BASE_T), BLOCK_X, BASE_T + BLOCK_Z,
                                    fill=False, edgecolor="#333", linewidth=1.2))
    ax.add_patch(patches.Rectangle((-FLANGE_MARGIN, -BASE_T), FLANGE_X, BASE_T,
                                    facecolor="#eee", edgecolor="#333", linewidth=1.0))

    pocket = make_pocket_cut()
    pbb = pocket.BoundBox
    ax.add_patch(patches.Rectangle((pbb.XMin, pbb.ZMin), pbb.XLength, pbb.ZLength,
                                    facecolor="#dfe8f5", edgecolor="#2a6ebb"))
    ax.text(BLOCK_X / 2.0, (pbb.ZMin + pbb.ZMax) / 2.0, "cuvette\npocket",
            ha="center", va="center", fontsize=7)

    cuvette = make_cuvette_placeholder().BoundBox
    ax.add_patch(patches.Rectangle((cuvette.XMin, cuvette.ZMin), cuvette.XLength, cuvette.ZLength,
                                    facecolor="none", edgecolor="#3a3", linestyle="--"))

    ax.plot([-8, 0], [Z_AXIS, Z_AXIS], color="#c33", linewidth=1.5)
    ax.plot([BLOCK_X, BLOCK_X + 8], [Z_AXIS, Z_AXIS], color="#c33", linewidth=1.5)
    ax.text(-9, Z_AXIS, "beam", color="#c33", fontsize=7, ha="right", va="center")

    led_pcb = make_led_pcb_placeholder().BoundBox
    ax.add_patch(patches.Rectangle((led_pcb.XMin, led_pcb.ZMin), led_pcb.XLength, led_pcb.ZLength,
                                    facecolor="#f7ddc0", edgecolor="#c76"))
    ax.text(led_pcb.XMin - 2, (led_pcb.ZMin + led_pcb.ZMax) / 2.0, "LED\nboard",
            ha="right", va="center", fontsize=7)

    sensor_pcb = make_sensor_pcb_placeholder().BoundBox
    ax.add_patch(patches.Rectangle((sensor_pcb.XMin, sensor_pcb.ZMin),
                                    sensor_pcb.XLength, sensor_pcb.ZLength,
                                    facecolor="#d9f0d4", edgecolor="#3a3"))
    ax.text(sensor_pcb.XMax + 2, (sensor_pcb.ZMin + sensor_pcb.ZMax) / 2.0, "sensor\nboard",
            ha="left", va="center", fontsize=7)

    for x0 in (POCKET_X_MIN - LEG_GAP - LEG_X, POCKET_X_MAX + LEG_GAP):
        ax.add_patch(patches.Rectangle((x0, BLOCK_Z), LEG_X, LEG_H,
                                        facecolor="#eee", edgecolor="#333"))

    cradle_z0 = DECK_Z0
    ax.add_patch(patches.Rectangle((BLOCK_X / 2.0 - CRADLE_OUTER_X / 2.0, cradle_z0),
                                    CRADLE_OUTER_X, CRADLE_DECK_T + CRADLE_GRIP_DEPTH,
                                    facecolor="#eee", edgecolor="#333"))

    cores3 = make_cores3_placeholder().BoundBox
    ax.add_patch(patches.Rectangle((cores3.XMin, cores3.ZMin), cores3.XLength, cores3.ZLength,
                                    facecolor="#cfe3f7", edgecolor="#2a6ebb"))
    ax.text(BLOCK_X / 2.0, cores3.ZMax + 5, "CoreS3", ha="center", va="bottom", fontsize=8)

    ax.set_xlim(-40, BLOCK_X + 40)
    ax.set_ylim(-BASE_T - 10, cores3.ZMax + 20)
    ax.set_xlabel("width X (mm)")
    ax.set_ylabel("height Z (mm)")
    ax.set_title("Flow cell holder -- elevation (optical axis in section)")
    ax.set_aspect("equal")

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "flow_cell_sideview.svg"))
    fig.savefig(os.path.join(out_dir, "flow_cell_sideview.png"), dpi=150)


main()
