"""Gas diffusion cell for the ammonia FIA analyser (BOM item 6).

Two identical plates clamp a 47 mm hydrophobic PTFE membrane between mirrored
serpentine grooves. Run with FreeCAD's console interpreter:

    freecadcmd gd_cell.py

Writes gd_cell_plate.step / .FCStd (one plate) and gd_cell_assembly.step
(both plates plus the membrane, exploded by the membrane thickness).

Design notes that are not obvious from the numbers:

- The groove is serpentine, not straight. A straight 80 mm channel needs a
  strip membrane; the whole point of a 47 mm disc is that it is a stock
  filtration consumable (Millipore FGLP, BOM item 7). Folding the path into
  three legs fits 82 mm of channel inside the disc's sealed area.
- One part number, two pieces. The serpentine is symmetric about the X axis,
  so flipping the second plate over lands its groove exactly on the first.
  That also makes the streams counter-current, which holds the NH3 gradient
  up along the whole path instead of letting it collapse at the outlet.
- Ports enter from the back face and turn into the groove ends. Drilling
  straight down into a 0.5 mm deep groove would blow through the sealing
  land, so each port lands in a short riser well inside the O-ring.
"""

import os

import FreeCAD as App
import Part
from FreeCAD import Vector

# ---------------------------------------------------------------- parameters

# Plate envelope
PLATE_X = 70.0          # mm, long axis
PLATE_Y = 60.0
PLATE_Z = 15.0          # thick enough for 1/4-28 threads (needs >= 8 mm)

# Groove: 0.5 x 1.0 mm cross-section, 80.0 mm developed length
# N_LEGS must be EVEN. An even leg count puts a mirror plane on y=0, which is
# what lets the second plate be the same part flipped over. An odd count only
# has point symmetry about Z, and its end turns land on the wrong sides when
# flipped -- verified by check_flip_symmetry() below.
GROOVE_W = 1.0
GROOVE_D = 0.5
LEG_LEN = 14.11         # straight portion of each leg -> 80.0 mm developed
LEG_PITCH = 5.0         # centre-to-centre spacing between legs
N_LEGS = 4

# Membrane
MEMBRANE_DIA = 47.0
MEMBRANE_T = 0.15       # Millipore FGLP nominal, informational only

# O-ring groove, outside the flow path, inside the membrane rim
ORING_MEAN_DIA = 40.0
ORING_CORD = 1.5        # nominal cord of a 1.5 mm section O-ring
ORING_W = ORING_CORD + 0.2
ORING_D = ORING_CORD * 0.75   # 75 % squeeze depth per half -> compressed seal

# 1/4-28 UNF flat-bottom ports for 1/16" OD PTFE tubing
PORT_TAP_DIA = 5.6      # tap drill for 1/4-28 (0.2188" ~ 5.56 mm)
PORT_TAP_DEPTH = 8.0
PORT_SEAT_DIA = 2.4     # flat-bottom seat the ferrule stops against
PORT_RISER_DIA = 0.8    # through-hole into the groove end
PORT_X = 30.0           # port centres, symmetric about origin
PORT_Y_OFF = 12.0

# Corner clamp bolts, M4
BOLT_DIA = 4.3          # clearance
BOLT_INSET = 6.0

# --------------------------------------------------------------- geometry

def _leg_centres():
    """Y centres of the serpentine legs, symmetric about Y=0."""
    span = (N_LEGS - 1) * LEG_PITCH
    return [(-span / 2.0) + i * LEG_PITCH for i in range(N_LEGS)]


def groove_path_length():
    """Developed centreline length of the serpentine."""
    turns = (N_LEGS - 1) * 3.14159265358979 * (LEG_PITCH / 2.0)
    return N_LEGS * LEG_LEN + turns


def make_groove_solid():
    """Serpentine groove as a solid to cut: legs plus 180 deg end turns."""
    solids = []
    ys = _leg_centres()

    # straight legs
    for y in ys:
        box = Part.makeBox(
            LEG_LEN, GROOVE_W, GROOVE_D,
            Vector(-LEG_LEN / 2.0, y - GROOVE_W / 2.0, PLATE_Z - GROOVE_D),
        )
        solids.append(box)

    # 180 deg turns, alternating ends, joining consecutive legs
    for i in range(N_LEGS - 1):
        y0, y1 = ys[i], ys[i + 1]
        yc = (y0 + y1) / 2.0
        r_out = abs(y1 - y0) / 2.0 + GROOVE_W / 2.0
        r_in = abs(y1 - y0) / 2.0 - GROOVE_W / 2.0
        # right end for even i, left end for odd i
        x_end = (LEG_LEN / 2.0) if (i % 2 == 0) else (-LEG_LEN / 2.0)

        outer = Part.makeCylinder(
            r_out, GROOVE_D, Vector(x_end, yc, PLATE_Z - GROOVE_D), Vector(0, 0, 1)
        )
        ring = outer
        if r_in > 0.01:
            inner = Part.makeCylinder(
                r_in, GROOVE_D, Vector(x_end, yc, PLATE_Z - GROOVE_D), Vector(0, 0, 1)
            )
            ring = outer.cut(inner)

        # keep only the half-annulus pointing away from the legs
        half = Part.makeBox(
            r_out + 1, 2 * r_out + 2, GROOVE_D + 0.2,
            Vector(
                x_end if x_end > 0 else x_end - (r_out + 1),
                yc - (r_out + 1),
                PLATE_Z - GROOVE_D - 0.1,
            ),
        )
        solids.append(ring.common(half))

    fused = solids[0]
    for s in solids[1:]:
        fused = fused.fuse(s)
    return fused.removeSplitter()


def make_oring_solid():
    r_mean = ORING_MEAN_DIA / 2.0
    z0 = PLATE_Z - ORING_D
    outer = Part.makeCylinder(
        r_mean + ORING_W / 2.0, ORING_D, Vector(0, 0, z0), Vector(0, 0, 1)
    )
    inner = Part.makeCylinder(
        r_mean - ORING_W / 2.0, ORING_D, Vector(0, 0, z0), Vector(0, 0, 1)
    )
    return outer.cut(inner)


def _groove_end_points():
    """(x, y) of the two open groove ends: first leg and last leg."""
    ys = _leg_centres()
    # leg 0 starts at -X (first turn is at +X), so its free end is at -X
    start = (-LEG_LEN / 2.0 + GROOVE_W, ys[0])
    # last leg's free end is at the opposite side of its incoming turn
    last_turn_at_right = ((N_LEGS - 2) % 2 == 0)
    x_end = (-LEG_LEN / 2.0 + GROOVE_W) if last_turn_at_right else (LEG_LEN / 2.0 - GROOVE_W)
    end = (x_end, ys[-1])
    return [start, end]


def make_port_solids():
    """Two ports: tapped bore from the back, riser into the groove end."""
    solids = []
    for (gx, gy) in _groove_end_points():
        # tapped bore, from z=0 (back face) upward
        tap = Part.makeCylinder(
            PORT_TAP_DIA / 2.0, PORT_TAP_DEPTH, Vector(gx, gy, 0), Vector(0, 0, 1)
        )
        # flat-bottom seat above the thread
        seat = Part.makeCylinder(
            PORT_SEAT_DIA / 2.0,
            PLATE_Z - PORT_TAP_DEPTH - GROOVE_D,
            Vector(gx, gy, PORT_TAP_DEPTH),
            Vector(0, 0, 1),
        )
        # riser breaking into the groove floor
        riser = Part.makeCylinder(
            PORT_RISER_DIA / 2.0,
            GROOVE_D + 0.2,
            Vector(gx, gy, PLATE_Z - GROOVE_D - 0.1),
            Vector(0, 0, 1),
        )
        solids.append(tap.fuse(seat).fuse(riser))
    return solids


def make_bolt_solids():
    xs = (PLATE_X / 2.0 - BOLT_INSET, -(PLATE_X / 2.0 - BOLT_INSET))
    ys = (PLATE_Y / 2.0 - BOLT_INSET, -(PLATE_Y / 2.0 - BOLT_INSET))
    return [
        Part.makeCylinder(BOLT_DIA / 2.0, PLATE_Z + 2, Vector(x, y, -1), Vector(0, 0, 1))
        for x in xs
        for y in ys
    ]


def make_plate():
    plate = Part.makeBox(
        PLATE_X, PLATE_Y, PLATE_Z, Vector(-PLATE_X / 2.0, -PLATE_Y / 2.0, 0)
    )
    plate = plate.cut(make_groove_solid())
    plate = plate.cut(make_oring_solid())
    for s in make_port_solids():
        plate = plate.cut(s)
    for s in make_bolt_solids():
        plate = plate.cut(s)
    return plate.removeSplitter()


def make_membrane():
    return Part.makeCylinder(
        MEMBRANE_DIA / 2.0, MEMBRANE_T, Vector(0, 0, PLATE_Z), Vector(0, 0, 1)
    )


def check_flip_symmetry(tol=1e-6):
    """Verify the groove maps onto itself when the plate is flipped about X.

    This is what makes both plates the same part number. If it fails, the two
    grooves do not register and the cell has no contact area.
    """
    gr = make_groove_solid()
    flipped = gr.copy()
    # rotating 180 deg about X maps y -> -y and z -> -z; shift the groove back
    # into its original Z band so any XY mismatch shows up as lost overlap
    flipped.rotate(Vector(0, 0, 0), Vector(1, 0, 0), 180)
    flipped.translate(Vector(0, 0, 2 * PLATE_Z - GROOVE_D))
    common = gr.common(flipped)
    overlap = common.Volume / gr.Volume if gr.Volume else 0.0
    return overlap, abs(overlap - 1.0) < 1e-3


def self_check():
    """Assert the geometry facts that a dimension change could silently break.

    Returns a list of (label, passed, detail). Everything here was a real
    failure mode during design: an odd leg count broke registration, and a
    riser drilled at the groove centreline broke through the sealing land.
    """
    import math

    gr = make_groove_solid()
    og = make_oring_solid()
    ports = make_port_solids()
    oring_ir = (ORING_MEAN_DIA - ORING_W) / 2.0
    oring_or = (ORING_MEAN_DIA + ORING_W) / 2.0
    memb_r = MEMBRANE_DIA / 2.0
    r_groove = max(math.hypot(v.Point.x, v.Point.y) for v in gr.Vertexes)

    out = []
    out.append(("even leg count", N_LEGS % 2 == 0, "N_LEGS=%d" % N_LEGS))
    for i, p in enumerate(ports):
        out.append(("port %d opens into groove" % i,
                    p.common(gr).Volume > 1e-6, ""))
        out.append(("port %d clears O-ring" % i,
                    p.common(og).Volume < 1e-9, ""))
    out.append(("groove inside O-ring", gr.common(og).Volume < 1e-9,
                "land %.2f mm" % (oring_ir - r_groove)))
    out.append(("O-ring inside membrane", oring_or < memb_r,
                "rim %.2f mm" % (memb_r - oring_or)))
    for i, b in enumerate(make_bolt_solids()):
        c = b.BoundBox.Center
        r = math.hypot(c.x, c.y)
        out.append(("bolt %d clears membrane" % i,
                    r - BOLT_DIA / 2.0 > memb_r, "r=%.1f" % r))
    out.append(("thread fits plate", PORT_TAP_DEPTH < PLATE_Z - GROOVE_D,
                "%.1f < %.1f" % (PORT_TAP_DEPTH, PLATE_Z - GROOVE_D)))
    return out


# ------------------------------------------------------------------- output

def main():
    here = os.path.dirname(os.path.abspath(__file__))

    plate = make_plate()

    doc = App.newDocument("gd_cell")
    obj = doc.addObject("Part::Feature", "Plate")
    obj.Shape = plate
    doc.recompute()
    doc.saveAs(os.path.join(here, "gd_cell_plate.FCStd"))
    plate.exportStep(os.path.join(here, "gd_cell_plate.step"))

    # assembly: lower plate as-is, upper plate flipped about X and lifted
    upper = plate.copy()
    upper.rotate(Vector(0, 0, 0), Vector(1, 0, 0), 180)
    upper.translate(Vector(0, 0, 2 * PLATE_Z + MEMBRANE_T))

    asm = Part.makeCompound([plate, make_membrane(), upper])
    asm.exportStep(os.path.join(here, "gd_cell_assembly.step"))

    adoc = App.newDocument("gd_cell_assembly")
    for name, shp in (("Lower", plate), ("Membrane", make_membrane()), ("Upper", upper)):
        o = adoc.addObject("Part::Feature", name)
        o.Shape = shp
    adoc.recompute()
    adoc.saveAs(os.path.join(here, "gd_cell_assembly.FCStd"))

    length = groove_path_length()
    volume = length * GROOVE_W * GROOVE_D
    overlap, ok = check_flip_symmetry()
    checks = self_check()
    print("groove developed length : %.1f mm" % length)
    print("groove swept volume     : %.1f uL per side" % volume)
    print("plate volume            : %.0f mm^3" % plate.Volume)
    print("plate is a valid solid  : %s" % plate.isValid())
    print("flip registration       : %.4f  -> %s"
          % (overlap, "same part both sides" if ok else "MISMATCH, grooves do not register"))
    print("membrane sealed dia     : %.0f mm (O-ring mean %.0f mm)"
          % (MEMBRANE_DIA, ORING_MEAN_DIA))
    print("")
    failed = [c for c in checks if not c[1]]
    for label, passed, detail in checks:
        print("  [%s] %s%s" % ("ok" if passed else "FAIL", label,
                               ("  " + detail) if detail else ""))
    print("")
    if failed:
        print("SELF-CHECK FAILED: %d of %d" % (len(failed), len(checks)))
        raise SystemExit(1)
    print("self-check: %d/%d passed" % (len(checks), len(checks)))


main()
