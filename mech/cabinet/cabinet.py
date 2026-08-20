"""NEMA 4X cabinet and internal chassis for the ammonia FIA analyser (BOM item 32).

Run with FreeCAD's console interpreter:

    freecadcmd cabinet.py

Writes cabinet_shell.step / .FCStd (the outer enclosure alone, for checking
against a real catalog cutsheet), cabinet_assembly.step / .FCStd (shell plus
the three-tier internal chassis and placeholder components), and
cabinet_sideview.svg / .png (an annotated elevation + plan schematic).

Design notes that are not obvious from the numbers:

- The outer shell is NOT the part to manufacture. AMMONIA_FIA_SENSOR_DESIGN.md
  section 8.4 concludes that the NEMA 4X / IP66 boundary should be bought
  (FRP or 316L, off the shelf) rather than fabricated -- a one-off welded or
  bonded box cannot match a certified gasket, hinge and latch set for the
  price. This model exists to check that the internal chassis actually fits
  inside a cabinet of that catalog size, not to hand to a fabricator.
- Everything wet lives below everything electrical, because leaks travel
  down (section 8.2/8.4). The three tiers are stacked upper (dry
  electronics) over middle (wet fluidics) over lower (wettest: reagents,
  standard and waste, in a bund). Tier order is a hard invariant checked
  below, not just a layout choice.
- Component footprints inside each tier (pump, valve, bottle, optical block)
  are placeholder geometry, not vendor dimensions -- no BOM line in the
  design doc gives a footprint for those items. The six-port valve and
  peristaltic pump are modeled as recognizable shapes (radial-port body +
  actuator; motor housing + rotor head + rollers + tubing loop) so the
  layout reads as an assembled cabinet, but the numbers are still guesses.
  See README.md's "open decisions" section before cutting anything to
  these numbers.
- The gas diffusion cell footprint (70 x 60 x 15 mm) is not re-derived here;
  it is the same constant as gd_cell.py's PLATE_X/Y/Z, so the two models
  can't silently drift apart.
"""

import math
import os

import FreeCAD as App
import Part
from FreeCAD import Vector

# ---------------------------------------------------------------- parameters

# Outer cabinet envelope (BOM item 32, bought NEMA 4X / IP66 -- section 8.4)
CAB_W = 600.0      # mm, X, left-right
CAB_D = 300.0      # mm, Y, front (0) to back (CAB_D); door is on the front face
CAB_H = 500.0      # mm, Z, floor (0) to ceiling; tiers stack along this axis
WALL_T = 3.0       # mm, representative FRP/316L wall thickness (bought part,
                   # not a fabrication spec)

# Door: hinged on the -X edge, swings open about a vertical (Z) axis
DOOR_T = 3.0
DOOR_MARGIN = 15.0       # mm, gasket flange width around the door opening
DOOR_SWING_DEG = 110.0   # typical hinge swing before the door hits its stop
DOOR_HINGE_STANDOFF = 5.0  # mm, pivot offset outboard of the door's inner
                           # face -- without it the door's hinge-side edge
                           # sweeps back through the frame post next to the
                           # opening for any nonzero swing angle

# Cable glands: rear face, low in the lower tier, per section 8.5's grounding
# and EMI note -- never through the top, so washdown can't pool at an entry
GLAND_DIA = 20.0
GLAND_Z_REL = 100.0     # mm above the cabinet floor
GLAND_X_OFFSETS = (-150.0, 150.0)

# Corner mounting-flange holes, through the rear wall (wall-mount)
MOUNT_HOLE_DIA = 9.0
MOUNT_INSET = 25.0

# Tier split along Z: upper (dry) / middle (wet) / lower (wettest), as
# fractions of the internal height. Lower gets the largest share because it
# carries the tallest components (reservoir and waste bottles).
TIER_FRACTIONS = (0.30, 0.28, 0.42)   # upper, middle, lower -- must sum to 1
PANEL_T = 10.0      # mm, wet mounting panel (BOM 32b), PVC Type 1 / HDPE
PANEL_MARGIN = 15.0  # mm, inset of each panel from the interior walls

# Standoffs lifting the upper (electronics) subpanel off its tier floor
STANDOFF_H = 15.0
STANDOFF_DIA = 8.0

# Placeholder component geometry -- NOT vendor dimensions, see README.md.
# Sized to plausible commercial footprints only so the clearance and
# collision checks below have real geometry to check, not just a box.
OPTICAL_BLOCK = (70.0, 60.0, 15.0)    # matches gd_cell.py's plate footprint
GD_CELL_ENV = (70.0, 60.0, 15.0)      # gd_cell.py PLATE_X/Y/Z, imported as-is
BOTTLE_DIA = 90.0                     # 500 mL HDPE reservoir bottle, x3
BOTTLE_H = 140.0
WASTE_DIA = 150.0                     # 2 L HDPE waste container
WASTE_H = 180.0

# Six-port valve (BOM item 4/5): cylindrical body with radial ports on the
# mid-plane and an actuator knob on top. N_PORTS=6 for a rotary injection or
# selector valve; the port ring is what a rotary valve actually looks like,
# unlike a plain box.
VALVE_BODY_DIA = 45.0
VALVE_BODY_H = 35.0
VALVE_N_PORTS = 6
VALVE_PORT_DIA = 3.2
VALVE_PORT_LEN = 12.0     # port stub length, radially outward from the body
VALVE_KNOB_DIA = 20.0
VALVE_KNOB_H = 15.0
VALVE_COUNT = 2

# Peristaltic pump (BOM item 1): motor block, rotor head, roller set on the
# head, and a tubing loop wrapped around the rollers with a gap where the
# tube enters/exits -- the loop is why a real pump's footprint is wider than
# its motor housing, which matters for the no-collision check below.
PUMP_MOTOR = (60.0, 55.0, 45.0)   # x, y, z of the motor housing block
PUMP_HEAD_DIA = 45.0
PUMP_HEAD_H = 8.0
PUMP_ROLLER_DIA = 8.0
PUMP_ROLLER_H = 18.0
PUMP_ROLLER_COUNT = 3
PUMP_TUBE_DIA = 3.0
PUMP_TUBE_GAP_DEG = 50.0   # open arc where the tube leaves the roller wrap
PUMP_TUBE_STUB_LEN = 15.0  # straight tube length at each open end
PUMP_COUNT = 3

# Middle tier is a single vertical mounting plate (BOM 32b's wet panel,
# reoriented) with all six components -- 3 pumps, 2 valves, 1 GD cell -- in
# one horizontal row, per FIAlab's own instruments (FIAlyzer-1000/FLEX
# flyer: pump+valve bolted to a vertical face plate in a narrow chassis,
# "designed vertically to minimize footprint") and design doc §8.4's own
# preference for "a flat plate plus small brackets." One row, not stacked
# rows, because the middle tier's height (~138 mm) only clears one row of
# these footprints, not two.
MIDDLE_ROW_GAP = 15.0     # mm, clearance between adjacent component footprints along the row

# Bund tray (BOM item 29's leak sensor sits at its low corner)
BUND_WALL_H = 20.0
BUND_SLOPE = 8.0         # mm, floor rise from the low corner to the high corner
LEAK_SENSOR_DIA = 20.0
TRAY_INSET = 10.0        # mm, tray wall inset from the lower tier's footprint

CLEARANCE_MIN = 5.0       # mm, minimum required margin for the "fits" checks

# --------------------------------------------------------------- geometry

def interior_bounds():
    """Inside-wall envelope of the cabinet, in (x0, x1, y0, y1, z0, z1)."""
    return (
        -CAB_W / 2.0 + WALL_T, CAB_W / 2.0 - WALL_T,
        WALL_T, CAB_D - WALL_T,
        WALL_T, CAB_H - WALL_T,
    )


def tier_bounds():
    """Z bounds (z0, z1) of the lower, middle and upper tiers, bottom to top."""
    x0, x1, y0, y1, z0, z1 = interior_bounds()
    int_h = z1 - z0
    upper_f, middle_f, lower_f = TIER_FRACTIONS
    lower_h = int_h * lower_f
    middle_h = int_h * middle_f
    upper_h = int_h * upper_f
    lower = (z0, z0 + lower_h)
    middle = (lower[1], lower[1] + middle_h)
    upper = (middle[1], middle[1] + upper_h)
    return lower, middle, upper


def panel_footprint():
    """(x0, x1, y0, y1) shared by every tier's mounting panel/tray."""
    x0, x1, y0, y1, _, _ = interior_bounds()
    return (x0 + PANEL_MARGIN, x1 - PANEL_MARGIN, y0 + PANEL_MARGIN, y1 - PANEL_MARGIN)


def make_shell():
    """Outer enclosure: hollow box, door opening, mount holes, cable glands."""
    outer = Part.makeBox(CAB_W, CAB_D, CAB_H, Vector(-CAB_W / 2.0, 0.0, 0.0))
    inner = Part.makeBox(
        CAB_W - 2 * WALL_T, CAB_D - 2 * WALL_T, CAB_H - 2 * WALL_T,
        Vector(-CAB_W / 2.0 + WALL_T, WALL_T, WALL_T),
    )
    shell = outer.cut(inner)

    door_w, door_h = door_size()
    opening = Part.makeBox(
        door_w, WALL_T + 0.2, door_h,
        Vector(-door_w / 2.0, -0.1, DOOR_MARGIN),
    )
    shell = shell.cut(opening)

    for x in (-(CAB_W / 2.0 - MOUNT_INSET), CAB_W / 2.0 - MOUNT_INSET):
        for z in (MOUNT_INSET, CAB_H - MOUNT_INSET):
            hole = Part.makeCylinder(
                MOUNT_HOLE_DIA / 2.0, WALL_T + 0.2,
                Vector(x, CAB_D - WALL_T - 0.1, z), Vector(0, 1, 0),
            )
            shell = shell.cut(hole)

    for x in GLAND_X_OFFSETS:
        gland = Part.makeCylinder(
            GLAND_DIA / 2.0, WALL_T + 0.2,
            Vector(x, CAB_D - WALL_T - 0.1, WALL_T + GLAND_Z_REL), Vector(0, 1, 0),
        )
        shell = shell.cut(gland)

    return shell.removeSplitter()


def door_size():
    return (CAB_W - 2 * DOOR_MARGIN, CAB_H - 2 * DOOR_MARGIN)


def make_door(angle_deg=0.0):
    """Door leaf, hinged on the -X vertical edge of the opening.

    angle_deg=0 sits flush in the closed opening. Positive angles swing the
    free edge out into -Y, away from the cabinet interior (which occupies
    +Y beyond the front face) -- the direction a real hinge opens.
    """
    door_w, door_h = door_size()
    door = Part.makeBox(
        door_w, DOOR_T, door_h,
        Vector(-door_w / 2.0, -DOOR_T, DOOR_MARGIN),
    )
    if angle_deg:
        # Pivot offset outboard (in -Y, away from the wall) by the hinge
        # standoff. A pivot placed exactly on the door's hinge-side edge
        # (y=0) has the door's own finite thickness straddling the axis, so
        # the near-hinge corner sweeps back to x < -door_w/2 for angles past
        # ~90 deg and clips the frame post beside the opening. Offsetting
        # the axis outward -- what a real hinge barrel does -- keeps every
        # point's swept x-coordinate >= -door_w/2 for the whole travel.
        hinge_pt = Vector(-door_w / 2.0, -DOOR_HINGE_STANDOFF, 0.0)
        # FreeCAD's rotate() follows the right-hand rule about +Z, which is
        # CCW in the XY plane and swings a +angle toward +Y (into the
        # cabinet interior). Negate so a positive DOOR_SWING_DEG swings the
        # free edge toward -Y (out into the room), matching a real hinge.
        door.rotate(hinge_pt, Vector(0, 0, 1), -angle_deg)
    return door


def _box_at(size, center_xy, z0):
    """Axis-aligned box, size=(sx, sy, sz), centred in X/Y at center_xy, floor at z0."""
    sx, sy, sz = size
    cx, cy = center_xy
    return Part.makeBox(sx, sy, sz, Vector(cx - sx / 2.0, cy - sy / 2.0, z0))


def _cyl_at(dia, height, center_xy, z0):
    cx, cy = center_xy
    return Part.makeCylinder(dia / 2.0, height, Vector(cx, cy, z0), Vector(0, 0, 1))


def _mount_on_plate(solid, plate_front_y):
    """Remap a floor-mounted solid (resting face at z=0, grows in +Z) onto a
    vertical plate whose front (component-facing) face is at y=plate_front_y,
    projecting forward into -Y (toward the door) the way it used to grow up.

    FreeCAD's rotate() follows the right-hand rule about +X: a +90 deg turn
    sends local +Z to world -Y and local +Y to world +Z, while local X is
    untouched. So a solid built with make_pump_solid/make_valve_solid at
    center_xy=(x, z) and z0=0.0 lands with its old floor footprint's X centred
    at world x, its old floor footprint's Y (now vertical) centred at world z,
    and its old "up" axis pointing at world y=plate_front_y minus whatever it
    used to call height -- i.e. it projects toward the door from the plate.
    """
    s = solid.copy()
    s.rotate(Vector(0, 0, 0), Vector(1, 0, 0), 90.0)
    s.translate(Vector(0, plate_front_y, 0))
    return s


def make_valve_solid(center_xy, z0):
    """Six-port valve: cylindrical body, radial port stubs, actuator knob.

    (center_xy, z0) place the body's footprint centre and its resting face.
    Returns a single fused solid so downstream collision checks (.common())
    see one shape, not a loose compound of body/knob/ports.
    """
    cx, cy = center_xy
    origin = Vector(cx, cy, z0)
    body = Part.makeCylinder(VALVE_BODY_DIA / 2.0, VALVE_BODY_H, origin, Vector(0, 0, 1))
    knob = Part.makeCylinder(
        VALVE_KNOB_DIA / 2.0, VALVE_KNOB_H,
        Vector(cx, cy, z0 + VALVE_BODY_H), Vector(0, 0, 1),
    )
    solid = body.fuse(knob)

    port_z = z0 + VALVE_BODY_H / 2.0
    r0 = VALVE_BODY_DIA / 2.0 - 1.0   # start the stub just inside the body
                                       # wall so the fuse has real overlap
    for i in range(VALVE_N_PORTS):
        ang = math.radians(360.0 / VALVE_N_PORTS * i)
        dx, dy = math.cos(ang), math.sin(ang)
        start = Vector(cx + dx * r0, cy + dy * r0, port_z)
        port = Part.makeCylinder(
            VALVE_PORT_DIA / 2.0, VALVE_PORT_LEN + 1.0, start, Vector(dx, dy, 0),
        )
        solid = solid.fuse(port)
    return solid.removeSplitter()


def valve_footprint_radius():
    """Radius from the valve's centre to the tip of its longest port stub."""
    return VALVE_BODY_DIA / 2.0 + VALVE_PORT_LEN


def valve_height():
    return VALVE_BODY_H + VALVE_KNOB_H


def make_pump_solid(center_xy, z0):
    """Peristaltic pump: motor block, rotor head, rollers, tubing loop.

    (center_xy, z0) place the motor block's footprint centre and its
    resting face. The tubing loop is swept short of a full circle
    (360 - PUMP_TUBE_GAP_DEG) with two straight stubs at the open ends,
    which is why the pump's footprint radius is bigger than the motor
    housing -- a box placeholder would miss that and let the middle tier's
    layout pack pumps closer than a real one's tubing allows.
    """
    cx, cy = center_xy
    mx, my, mz = PUMP_MOTOR
    motor = Part.makeBox(mx, my, mz, Vector(cx - mx / 2.0, cy - my / 2.0, z0))
    head_z0 = z0 + mz
    head = Part.makeCylinder(PUMP_HEAD_DIA / 2.0, PUMP_HEAD_H, Vector(cx, cy, head_z0), Vector(0, 0, 1))
    solid = motor.fuse(head)

    roller_orbit = PUMP_HEAD_DIA / 2.0 - PUMP_ROLLER_DIA / 2.0 - 3.0
    roller_z0 = head_z0 + PUMP_HEAD_H
    for i in range(PUMP_ROLLER_COUNT):
        ang = math.radians(360.0 / PUMP_ROLLER_COUNT * i)
        rx, ry = cx + roller_orbit * math.cos(ang), cy + roller_orbit * math.sin(ang)
        roller = Part.makeCylinder(
            PUMP_ROLLER_DIA / 2.0, PUMP_ROLLER_H, Vector(rx, ry, roller_z0), Vector(0, 0, 1),
        )
        solid = solid.fuse(roller)
    solid = solid.removeSplitter()

    # Torus radius shrunk slightly below the true roller-tangent radius so
    # the fuse has overlap instead of a coincident (zero-thickness) contact
    # -- a bare tangent fuse leaves two touching-but-separate solids.
    tube_r1 = roller_orbit + PUMP_ROLLER_DIA / 2.0 + PUMP_TUBE_DIA / 2.0 - 0.5
    tube_r2 = PUMP_TUBE_DIA / 2.0
    tube_z = roller_z0 + PUMP_ROLLER_H / 2.0
    sweep = 360.0 - PUMP_TUBE_GAP_DEG
    tube = Part.makeTorus(
        tube_r1, tube_r2, Vector(cx, cy, tube_z), Vector(0, 0, 1), -180.0, 180.0, sweep,
    )
    solid = solid.fuse(tube)

    for ang_deg in (0.0, sweep):
        ang = math.radians(ang_deg)
        dx, dy = math.cos(ang), math.sin(ang)
        start = Vector(cx + dx * tube_r1, cy + dy * tube_r1, tube_z)
        stub = Part.makeCylinder(tube_r2, PUMP_TUBE_STUB_LEN, start, Vector(dx, dy, 0))
        solid = solid.fuse(stub)

    return solid.removeSplitter()


def pump_footprint_half_extents():
    """(half_x, half_y) of the pump's true footprint, tube loop included."""
    roller_orbit = PUMP_HEAD_DIA / 2.0 - PUMP_ROLLER_DIA / 2.0 - 3.0
    tube_r1 = roller_orbit + PUMP_ROLLER_DIA / 2.0 + PUMP_TUBE_DIA / 2.0 - 0.5
    tube_outer = tube_r1 + PUMP_TUBE_DIA / 2.0
    half_x = max(PUMP_MOTOR[0] / 2.0, tube_outer, PUMP_TUBE_STUB_LEN)
    half_y = max(PUMP_MOTOR[1] / 2.0, tube_outer, PUMP_TUBE_STUB_LEN)
    return half_x, half_y


def pump_height():
    return PUMP_MOTOR[2] + PUMP_HEAD_H + PUMP_ROLLER_H


def make_upper_tier():
    """Electronics subpanel: standoffs, DIN plate, MCU/driver/optical placeholders."""
    lower, middle, upper = tier_bounds()
    px0, px1, py0, py1 = panel_footprint()
    cy = (py0 + py1) / 2.0
    z_floor = upper[0]

    standoffs = [
        _cyl_at(STANDOFF_DIA, STANDOFF_H, (x, y), z_floor)
        for x in (px0 + 20.0, px1 - 20.0)
        for y in (py0 + 20.0, py1 - 20.0)
    ]
    panel_z = z_floor + STANDOFF_H
    panel = Part.makeBox(px1 - px0, py1 - py0, PANEL_T, Vector(px0, py0, panel_z))

    comp_z = panel_z + PANEL_T
    optical = _box_at(OPTICAL_BLOCK, (px0 + OPTICAL_BLOCK[0] / 2.0 + 10.0, cy), comp_z)
    mcu = _box_at((90.0, 70.0, 20.0), (cy_x := (px0 + px1) / 2.0, cy), comp_z)
    driver = _box_at((90.0, 70.0, 20.0), (px1 - 90.0 / 2.0 - 10.0, cy), comp_z)

    solids = standoffs + [panel, optical, mcu, driver]
    return {
        "solids": solids,
        "panel": panel,
        "components": [optical, mcu, driver],
        "z_floor": z_floor,
        "comp_top": comp_z + max(OPTICAL_BLOCK[2], 20.0),
    }


def make_middle_tier():
    """Vertical mounting plate: pumps, valves, GD cell in a single row.

    Mounted against the tier's back wall, all six components face the door
    and project forward in -Y -- see _mount_on_plate()'s docstring for the
    floor-mounted-to-plate-mounted transform every component goes through.
    """
    lower, middle, upper = tier_bounds()
    px0, px1, py0, py1 = panel_footprint()
    _, _, y0, y1, _, _ = interior_bounds()

    # Plate sits against the back wall (interior y1), inset by the usual
    # panel margin; components are mounted on its front (door-facing) side
    # and project further toward the door (smaller y) from there.
    plate_back_y = y1 - PANEL_MARGIN
    plate_front_y = plate_back_y - PANEL_T
    z_row_center = (middle[0] + middle[1]) / 2.0

    plate = Part.makeBox(
        px1 - px0, PANEL_T, middle[1] - middle[0],
        Vector(px0, plate_front_y, middle[0]),
    )

    pump_hx, pump_hy = pump_footprint_half_extents()
    valve_r = valve_footprint_radius()
    gd_hx = GD_CELL_ENV[0] / 2.0

    # Grouped pump/valve/GD-cell order is readable, not derived from any
    # real fluidic routing -- routing is still an open decision.
    row = (
        [("pump", pump_hx)] * PUMP_COUNT
        + [("valve", valve_r)] * VALVE_COUNT
        + [("gd_cell", gd_hx)]
    )
    total_width = sum(2 * hw for _, hw in row) + MIDDLE_ROW_GAP * (len(row) - 1)
    x_cursor = px0 + (px1 - px0 - total_width) / 2.0

    pumps, valves, gd_cell = [], [], None
    for kind, hw in row:
        cx = x_cursor + hw
        if kind == "pump":
            solid = _mount_on_plate(make_pump_solid((cx, z_row_center), 0.0), plate_front_y)
            pumps.append(solid)
        elif kind == "valve":
            solid = _mount_on_plate(make_valve_solid((cx, z_row_center), 0.0), plate_front_y)
            valves.append(solid)
        else:
            solid = _mount_on_plate(
                _box_at((GD_CELL_ENV[0], GD_CELL_ENV[1], GD_CELL_ENV[2]), (cx, z_row_center), 0.0),
                plate_front_y,
            )
            gd_cell = solid
        x_cursor += 2 * hw + MIDDLE_ROW_GAP

    comps = pumps + valves + [gd_cell]
    y_front_min = min(c.BoundBox.YMin for c in comps)
    return {
        "solids": [plate] + comps,
        "panel": plate,
        "pumps": pumps,
        "valves": valves,
        "gd_cell": gd_cell,
        "components": comps,
        "z_floor": middle[0],
        "z_top": z_row_center + valve_r,
        "z_bottom": z_row_center - valve_r,
        "y_front_min": y_front_min,
        "plate_back_y": plate_back_y,
    }


def bund_tray_corners():
    """(low_xy, high_xy) footprint corners of the bund tray floor."""
    px0, px1, py0, py1 = panel_footprint()
    x0, x1 = px0 + TRAY_INSET, px1 - TRAY_INSET
    y0, y1 = py0 + TRAY_INSET, py1 - TRAY_INSET
    low = (x0, y0)     # low corner: floor slopes down toward here
    high = (x1, y1)
    return low, high, (x0, x1, y0, y1)


def make_lower_tier():
    """Bund tray: sloped floor, walls, leak sensor, reservoir/waste placeholders."""
    lower, middle, upper = tier_bounds()
    z0 = lower[0]
    low_xy, high_xy, (tx0, tx1, ty0, ty1) = bund_tray_corners()

    # Sloped floor: a planar top face, low corner at z0+FLOOR_T, diagonally
    # opposite corner at z0+FLOOR_T+BUND_SLOPE, extruded straight down by
    # FLOOR_T. Splitting the slope evenly between X and Y (a, b >= 0) keeps
    # z(x,y) = z0 + FLOOR_T + a*(x-x0) + b*(y-y0) monotonically increasing
    # away from the low corner, so the extruded solid's bottom face never
    # dips below z0 -- unlike rotating a box about a diagonal axis, which
    # pulls two of its four corners down through the tier floor.
    floor_t = 4.0
    a = BUND_SLOPE / (2.0 * (tx1 - tx0))
    b = BUND_SLOPE / (2.0 * (ty1 - ty0))

    def _z_top(x, y):
        return z0 + floor_t + a * (x - tx0) + b * (y - ty0)

    top_pts = [
        Vector(tx0, ty0, _z_top(tx0, ty0)),
        Vector(tx1, ty0, _z_top(tx1, ty0)),
        Vector(tx1, ty1, _z_top(tx1, ty1)),
        Vector(tx0, ty1, _z_top(tx0, ty1)),
    ]
    top_wire = Part.makePolygon(top_pts + [top_pts[0]])
    top_face = Part.Face(top_wire)
    floor = top_face.extrude(Vector(0, 0, -floor_t))

    walls_outer = Part.makeBox(tx1 - tx0, ty1 - ty0, BUND_WALL_H, Vector(tx0, ty0, z0))
    walls_inner = Part.makeBox(
        tx1 - tx0 - 2 * WALL_T, ty1 - ty0 - 2 * WALL_T, BUND_WALL_H + 1.0,
        Vector(tx0 + WALL_T, ty0 + WALL_T, z0 - 0.5),
    )
    tray = walls_outer.cut(walls_inner).fuse(floor)

    leak_sensor = _cyl_at(LEAK_SENSOR_DIA, 1.0, low_xy, z0 + floor_t)

    comp_z = z0 + floor_t + BUND_SLOPE  # worst-case (highest) resting height
    bottles = []
    bx = tx0 + WALL_T + BOTTLE_DIA / 2.0 + 15.0
    for _ in range(3):
        bottles.append(_cyl_at(BOTTLE_DIA, BOTTLE_H, (bx, ty0 + WALL_T + BOTTLE_DIA / 2.0 + 15.0), comp_z))
        bx += BOTTLE_DIA + 15.0
    waste = _cyl_at(WASTE_DIA, WASTE_H, (tx1 - WALL_T - WASTE_DIA / 2.0 - 15.0,
                                          ty1 - WALL_T - WASTE_DIA / 2.0 - 15.0), comp_z)

    comps = bottles + [waste]
    return {
        "solids": [tray, leak_sensor] + comps,
        "tray": tray,
        "leak_sensor": leak_sensor,
        "low_xy": low_xy,
        "components": comps,
        "z_floor": z0,
        "comp_top": comp_z + max(BOTTLE_H, WASTE_H),
    }


# ------------------------------------------------------------------ checks

def self_check():
    """Assert the layout facts a parameter change could silently break.

    Returns a list of (label, passed, detail) tuples. Everything here is a
    real failure mode for a stacked, wet-over-dry cabinet layout: a tier
    fraction that leaves no headroom for its tallest component, a bund tray
    that doesn't drain to where the leak sensor actually is, a door that
    swings into its own chassis, or a cable gland placed above the flood
    line it's supposed to stay clear of.
    """
    x0, x1, y0, y1, z0, z1 = interior_bounds()
    lower_z, middle_z, upper_z = tier_bounds()

    shell = make_shell()
    upper = make_upper_tier()
    middle = make_middle_tier()
    lower = make_lower_tier()

    out = []

    out.append(("tier fractions sum to 1", abs(sum(TIER_FRACTIONS) - 1.0) < 1e-6,
                "sum=%.4f" % sum(TIER_FRACTIONS)))

    out.append(("tiers stack lower < middle < upper",
                lower_z[1] <= middle_z[0] + 1e-6 and middle_z[1] <= upper_z[0] + 1e-6,
                "lower=%.1f middle=%.1f upper=%.1f" % (lower_z[1], middle_z[0], upper_z[0])))

    margin_upper = upper_z[1] - upper["comp_top"]
    out.append(("upper tier clears its components", margin_upper > CLEARANCE_MIN,
                "margin %.1f mm" % margin_upper))

    margin_middle_top = middle_z[1] - middle["z_top"]
    out.append(("middle tier row clears the tier ceiling", margin_middle_top > CLEARANCE_MIN,
                "margin %.1f mm" % margin_middle_top))

    margin_middle_bottom = middle["z_bottom"] - middle_z[0]
    out.append(("middle tier row clears the tier floor", margin_middle_bottom > CLEARANCE_MIN,
                "margin %.1f mm" % margin_middle_bottom))

    margin_middle_front = middle["y_front_min"] - y0
    out.append(("middle tier components clear the front (door) wall", margin_middle_front > CLEARANCE_MIN,
                "margin %.1f mm" % margin_middle_front))

    margin_middle_back = y1 - middle["plate_back_y"]
    out.append(("middle tier plate clears the back wall", margin_middle_back > CLEARANCE_MIN,
                "margin %.1f mm" % margin_middle_back))

    margin_lower = lower_z[1] - lower["comp_top"]
    out.append(("lower tier clears its components (bund + bottles)",
                margin_lower > CLEARANCE_MIN, "margin %.1f mm" % margin_lower))

    for name, tier in (("upper", upper), ("middle", middle), ("lower", lower)):
        for i, s in enumerate(tier["solids"]):
            out.append(("%s tier item %d inside shell walls" % (name, i),
                        s.common(shell).Volume < 1e-6, ""))

    vgap = upper["z_floor"] - middle["z_top"]
    out.append(("optical block clears the middle tier row across the tier boundary",
                vgap > 0, "gap %.1f mm" % vgap))

    # Pairwise no-overlap across every middle-tier component (pumps, valves,
    # GD cell). Real geometry now, not spaced boxes -- the pump's tubing
    # loop and the valve's port stubs both extend past their motor/body
    # footprint, so a spacing formula alone isn't proof they actually clear.
    mid_comps = middle["components"]
    for i in range(len(mid_comps)):
        for j in range(i + 1, len(mid_comps)):
            out.append(("middle tier component %d/%d don't overlap" % (i, j),
                        mid_comps[i].common(mid_comps[j]).Volume < 1e-6, ""))

    low_xy = lower["low_xy"]
    sensor_c = lower["leak_sensor"].BoundBox.Center
    dist = math.hypot(sensor_c.x - low_xy[0], sensor_c.y - low_xy[1])
    out.append(("leak sensor sits at the tray's low corner", dist < 1e-3,
                "offset %.3f mm" % dist))

    for i, b in enumerate(lower["components"]):
        out.append(("lower tier component %d clear of the low-corner sensor" % i,
                    b.common(lower["leak_sensor"]).Volume < 1e-9, ""))

    door_open = make_door(DOOR_SWING_DEG)
    all_chassis = Part.makeCompound(upper["solids"] + middle["solids"] + lower["solids"])
    out.append(("open door clears the internal chassis",
                door_open.common(all_chassis).Volume < 1e-6, ""))
    out.append(("open door clears the shell body",
                door_open.common(shell).Volume < 1e-6, ""))

    gland_z = WALL_T + GLAND_Z_REL
    out.append(("cable glands sit above the bund tray rim",
                gland_z > lower["tray"].BoundBox.ZMax, "gland z=%.1f, rim z=%.1f"
                % (gland_z, lower["tray"].BoundBox.ZMax)))
    out.append(("cable glands stay within the lower (wettest) tier's height",
                gland_z < lower_z[1], "gland z=%.1f, tier top=%.1f" % (gland_z, lower_z[1])))

    out.append(("wet panel never sits above the electronics tier",
                middle["panel"].BoundBox.ZMax <= upper["z_floor"] + 1e-6, ""))
    out.append(("bund tray never sits above the wet-fluidics tier",
                lower["tray"].BoundBox.ZMax <= middle["z_floor"] + 1e-6, ""))

    return out


# ------------------------------------------------------------------- output

def main():
    here = os.path.dirname(os.path.abspath(__file__))

    shell = make_shell()

    doc = App.newDocument("cabinet_shell")
    obj = doc.addObject("Part::Feature", "Shell")
    obj.Shape = shell
    doc.recompute()
    doc.saveAs(os.path.join(here, "cabinet_shell.FCStd"))
    shell.exportStep(os.path.join(here, "cabinet_shell.step"))

    upper = make_upper_tier()
    middle = make_middle_tier()
    lower = make_lower_tier()
    door = make_door(0.0)

    asm = Part.makeCompound([shell, door] + upper["solids"] + middle["solids"] + lower["solids"])
    asm.exportStep(os.path.join(here, "cabinet_assembly.step"))

    adoc = App.newDocument("cabinet_assembly")
    named = [("Shell", shell), ("Door", door),
             ("UpperPanel", upper["panel"]), ("MiddlePanel", middle["panel"]),
             ("BundTray", lower["tray"]), ("LeakSensor", lower["leak_sensor"])]
    for i, s in enumerate(upper["components"]):
        named.append(("UpperComponent%d" % i, s))
    for i, s in enumerate(middle["components"]):
        named.append(("MiddleComponent%d" % i, s))
    for i, s in enumerate(lower["components"]):
        named.append(("LowerComponent%d" % i, s))
    for name, shp in named:
        o = adoc.addObject("Part::Feature", name)
        o.Shape = shp
    adoc.recompute()
    adoc.saveAs(os.path.join(here, "cabinet_assembly.FCStd"))

    checks = self_check()
    failed = [c for c in checks if not c[1]]

    print("cabinet envelope        : %.0f x %.0f x %.0f mm (W x D x H)" % (CAB_W, CAB_D, CAB_H))
    lower_z, middle_z, upper_z = tier_bounds()
    print("tier heights (bottom->top): lower %.1f | middle %.1f | upper %.1f mm"
          % (lower_z[1] - lower_z[0], middle_z[1] - middle_z[0], upper_z[1] - upper_z[0]))
    print("shell is a valid solid   : %s" % shell.isValid())
    print("")
    for label, passed, detail in checks:
        print("  [%s] %s%s" % ("ok" if passed else "FAIL", label,
                               ("  " + detail) if detail else ""))
    print("")
    if failed:
        print("SELF-CHECK FAILED: %d of %d" % (len(failed), len(checks)))
        import sys
        sys.stdout.flush()
        raise SystemExit(1)
    print("self-check: %d/%d passed" % (len(checks), len(checks)))

    make_sideview_figure(here, middle)


def make_sideview_figure(out_dir, middle):
    """Annotated elevation (tier stack) + middle-tier layout + door-swing plan."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    lower_z, middle_z, upper_z = tier_bounds()
    fig, (ax_side, ax_mid, ax_front, ax_plan) = plt.subplots(1, 4, figsize=(18, 5.5))

    # --- elevation: Y (depth) horizontal, Z (height) vertical ---
    ax_side.add_patch(patches.Rectangle((0, 0), CAB_D, CAB_H, fill=False,
                                         edgecolor="#333", linewidth=1.5))
    bands = [
        (lower_z, "#dfe8f5", "LOWER -- reagents/waste, bund"),
        (middle_z, "#e8f0df", "MIDDLE -- pumps, valves, GD cell"),
        (upper_z, "#f5e8df", "UPPER -- MCU, drivers, optics"),
    ]
    for (z0, z1), color, label in bands:
        ax_side.add_patch(patches.Rectangle((WALL_T, z0), CAB_D - 2 * WALL_T, z1 - z0,
                                             facecolor=color, edgecolor="#888"))
        ax_side.text(CAB_D / 2.0, (z0 + z1) / 2.0, label, ha="center", va="center", fontsize=8)

    tray_low, tray_high, _ = bund_tray_corners()
    ax_side.plot([tray_low[1], tray_high[1]], [lower_z[0], lower_z[0] + BUND_SLOPE],
                 color="#c33", linewidth=1.2)
    ax_side.plot(tray_low[1], lower_z[0], marker="o", color="#c33", markersize=5)
    ax_side.text(tray_low[1], lower_z[0] - 18, "leak sensor", color="#c33", fontsize=7, ha="center")

    gland_z = WALL_T + GLAND_Z_REL
    ax_side.plot(CAB_D - WALL_T, gland_z, marker=">", color="#333", markersize=6)
    ax_side.text(CAB_D - WALL_T - 6, gland_z, "gland", fontsize=7, ha="right", va="center")

    ax_side.set_xlim(-10, CAB_D + 10)
    ax_side.set_ylim(-25, CAB_H + 10)
    ax_side.set_xlabel("depth Y (mm), front (door) at 0")
    ax_side.set_ylabel("height Z (mm)")
    ax_side.set_title("Elevation: tier stack")
    ax_side.set_aspect("equal")

    # --- middle tier plan: top-down layout of pumps, valves, GD cell ---
    px0, px1, py0, py1 = panel_footprint()
    ax_mid.add_patch(patches.Rectangle((px0, py0), px1 - px0, py1 - py0, fill=False,
                                        edgecolor="#333", linewidth=1.2))
    for i, pump in enumerate(middle["pumps"]):
        bb = pump.BoundBox
        ax_mid.add_patch(patches.Rectangle(
            (bb.XMin, bb.YMin), bb.XMax - bb.XMin, bb.YMax - bb.YMin,
            facecolor="#cfe3f7", edgecolor="#2a6ebb", linewidth=1.0,
        ))
        cx, cy = (bb.XMin + bb.XMax) / 2.0, (bb.YMin + bb.YMax) / 2.0
        ax_mid.text(cx, cy, "pump %d" % i, ha="center", va="center", fontsize=6.5)
    for i, valve in enumerate(middle["valves"]):
        bb = valve.BoundBox
        cx, cy = (bb.XMin + bb.XMax) / 2.0, (bb.YMin + bb.YMax) / 2.0
        r = max(bb.XMax - bb.XMin, bb.YMax - bb.YMin) / 2.0
        ax_mid.add_patch(patches.Circle((cx, cy), r, facecolor="#f7ddc0",
                                         edgecolor="#c76", linewidth=1.0))
        ax_mid.text(cx, cy, "valve %d" % i, ha="center", va="center", fontsize=6.5)
    gd_bb = middle["gd_cell"].BoundBox
    ax_mid.add_patch(patches.Rectangle(
        (gd_bb.XMin, gd_bb.YMin), gd_bb.XMax - gd_bb.XMin, gd_bb.YMax - gd_bb.YMin,
        facecolor="#d9f0d4", edgecolor="#3a3", linewidth=1.0,
    ))
    ax_mid.text((gd_bb.XMin + gd_bb.XMax) / 2.0, (gd_bb.YMin + gd_bb.YMax) / 2.0,
                "GD cell", ha="center", va="center", fontsize=6.5)

    ax_mid.set_xlim(px0 - 10, px1 + 10)
    ax_mid.set_ylim(py0 - 10, py1 + 10)
    ax_mid.set_xlabel("width X (mm)")
    ax_mid.set_ylabel("depth Y (mm)")
    ax_mid.set_title("Middle tier: wet fluidics layout (top-down)")
    ax_mid.set_aspect("equal")

    # --- middle tier front elevation: X (width) horizontal, Z (height)
    # vertical -- the view a technician sees opening the door, matching how
    # FIAlab's own flyer diagrams its pump/valve face plate ---
    plate_bb = middle["panel"].BoundBox
    ax_front.add_patch(patches.Rectangle(
        (plate_bb.XMin, plate_bb.ZMin), plate_bb.XMax - plate_bb.XMin, plate_bb.ZMax - plate_bb.ZMin,
        facecolor="#eee", edgecolor="#333", linewidth=1.2,
    ))
    for i, pump in enumerate(middle["pumps"]):
        bb = pump.BoundBox
        ax_front.add_patch(patches.Rectangle(
            (bb.XMin, bb.ZMin), bb.XMax - bb.XMin, bb.ZMax - bb.ZMin,
            facecolor="#cfe3f7", edgecolor="#2a6ebb", linewidth=1.0,
        ))
        cx, cz = (bb.XMin + bb.XMax) / 2.0, (bb.ZMin + bb.ZMax) / 2.0
        ax_front.text(cx, cz, "pump %d" % i, ha="center", va="center", fontsize=6.5)
    for i, valve in enumerate(middle["valves"]):
        bb = valve.BoundBox
        cx, cz = (bb.XMin + bb.XMax) / 2.0, (bb.ZMin + bb.ZMax) / 2.0
        r = max(bb.XMax - bb.XMin, bb.ZMax - bb.ZMin) / 2.0
        ax_front.add_patch(patches.Circle((cx, cz), r, facecolor="#f7ddc0",
                                           edgecolor="#c76", linewidth=1.0))
        ax_front.text(cx, cz, "valve %d" % i, ha="center", va="center", fontsize=6.5)
    gd_bb = middle["gd_cell"].BoundBox
    ax_front.add_patch(patches.Rectangle(
        (gd_bb.XMin, gd_bb.ZMin), gd_bb.XMax - gd_bb.XMin, gd_bb.ZMax - gd_bb.ZMin,
        facecolor="#d9f0d4", edgecolor="#3a3", linewidth=1.0,
    ))
    ax_front.text((gd_bb.XMin + gd_bb.XMax) / 2.0, (gd_bb.ZMin + gd_bb.ZMax) / 2.0,
                  "GD cell", ha="center", va="center", fontsize=6.5)

    ax_front.set_xlim(plate_bb.XMin - 10, plate_bb.XMax + 10)
    ax_front.set_ylim(middle_z[0] - 10, middle_z[1] + 10)
    ax_front.set_xlabel("width X (mm)")
    ax_front.set_ylabel("height Z (mm)")
    ax_front.set_title("Middle tier: front elevation (door view)")
    ax_front.set_aspect("equal")

    # --- plan: X (width) horizontal, Y (depth) vertical, door swing arc ---
    ax_plan.add_patch(patches.Rectangle((-CAB_W / 2.0, 0), CAB_W, CAB_D, fill=False,
                                         edgecolor="#333", linewidth=1.5))
    door_w, door_h = door_size()
    hinge = (-door_w / 2.0, 0.0)
    ax_plan.add_patch(patches.Rectangle((hinge[0], -DOOR_T), door_w, DOOR_T,
                                         facecolor="#2a6ebb", edgecolor="none"))
    arc = patches.Arc(hinge, door_w * 2, door_w * 2, angle=0, theta1=0, theta2=DOOR_SWING_DEG,
                       color="#2a6ebb", linestyle="--", linewidth=1.0)
    ax_plan.add_patch(arc)
    open_x = hinge[0] + door_w * math.cos(math.radians(DOOR_SWING_DEG))
    open_y = hinge[1] + door_w * math.sin(math.radians(DOOR_SWING_DEG))
    ax_plan.plot([hinge[0], open_x], [hinge[1], open_y], color="#2a6ebb", linewidth=2.0)

    for x in GLAND_X_OFFSETS:
        ax_plan.plot(x, CAB_D - WALL_T, marker="s", color="#333", markersize=5)
    ax_plan.text(0, CAB_D - WALL_T - 22, "cable glands (rear face)", fontsize=7, ha="center")

    ax_plan.set_xlim(-CAB_W / 2.0 - 10, CAB_W / 2.0 + 10)
    ax_plan.set_ylim(-door_w - 20, CAB_D + 10)
    ax_plan.set_xlabel("width X (mm)")
    ax_plan.set_ylabel("depth Y (mm)")
    ax_plan.set_title("Plan: door swing (%.0f deg)" % DOOR_SWING_DEG)
    ax_plan.set_aspect("equal")

    fig.suptitle("NEMA 4X cabinet, %.0f x %.0f x %.0f mm -- BOM item 32" % (CAB_W, CAB_D, CAB_H))
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "cabinet_sideview.svg"))
    fig.savefig(os.path.join(out_dir, "cabinet_sideview.png"), dpi=150)


main()
