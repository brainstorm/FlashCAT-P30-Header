#!/usr/bin/env python3
"""Simplified 3D model (STEP) of the HMILU BGA64-1.0-TP21NS BGA-64 socket.

No vendor model is published, so this is built from the HMILU drawing
007-BGA-1.0-64-10X13-B-01 rev A (top, front section and isometric views):
  * base (black): 3.3 mm slab with four corner towers up to 7.5 mm, lower
    channels between them, IC holder / nest (10 x 13 mm, 13 mm along X) in
    the middle; 4 x dia 2.0 fixing holes through the towers
  * cover (black): 26 x 30 mm top plate from 10.8 to 17.5 mm (cover up) with
    an 18 x 14 mm funnel window, countersunk corner holes and edge slots; a
    skirt in the middle of each side drops between the towers (into the base
    channels on the 26 mm faces, outside the base with a guide slot and pin
    on the 30 mm faces)
  * 4 coil springs on the towers, around the corner screw posts
  * 2 clamp arms (levers on pins beside the IC holder) whose hook tips press
    on the top of the chip along its 13 mm edges
  * 64 BeCu double-sided spring contacts (t0.1 x w0.17), 0.25 below the base
    onto the solid PCB pads
  * 4 locator pins (1 x dia 1.75 at the A1 corner, 3 x dia 1.45), 3.4 long
Contact / pin / hole positions come from design.py, so they line up exactly
with the footprint.  Proportions not dimensioned on the drawing were
measured from it.  Needs CadQuery (run with the build/cqenv venv, python 3.12):

  uv venv --python 3.12 build/cqenv && uv pip install --python build/cqenv/bin/python cadquery
  build/cqenv/bin/python tools/make_socket_3d.py
"""
import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design as D  # noqa: E402

OUT = os.path.join(HERE, "..", "lib", "flashcat_p30.3dshapes", "HMILU_BGA64-1.0-TP21NS.step")

BW, BH = D.SOCKET_BODY          # 26.0 x 30.0 (cover outline)
SLAB = 3.3                      # base slab height
TOWER = 7.5                     # top of the corner towers (spring seats)
NEST = 4.8                      # top of the IC holder
COVER_LO = 10.8                 # cover underside at the corners (springs' top)
COVER_TOP = 17.5                # cover top (cover up)
BX, BY = 12.5, 14.5             # base half-sizes
TX, TY = 6.2, 6.0               # corner tower size (from the base corner)
SKIRT_A_Z = 4.8                 # 26 mm faces: skirt bottom (into the channel)
SKIRT_B_Z = 3.5                 # 30 mm faces: skirt bottom (outside the base)


def fp2m(p):
    """Footprint coords (y down) -> model coords (y up)."""
    return (p[0], -p[1])


def box(x0, y0, z0, x1, y1, z1):
    """Axis-aligned box from two corners."""
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def cyl(x, y, z0, z1, r):
    return cq.Workplane("XY").circle(r).extrude(z1 - z0).translate((x, y, z0))


def spring(x, y, z0, z1, r_coil=1.3, r_wire=0.2, turns=4.0):
    h = z1 - z0 - 2 * r_wire
    path = cq.Wire.makeHelix(pitch=h / turns, height=h, radius=r_coil)
    prof = (cq.Workplane("XZ").center(r_coil, 0).circle(r_wire))
    coil = prof.sweep(cq.Workplane(obj=path), isFrenet=True)
    return coil.translate((x, y, z0 + r_wire))


def build():
    gx, gy = fp2m((D.GRID_X0 + 3.5, D.GRID_Y0 - 3.5))   # grid / IC centre
    holes = [fp2m(p) for p in D.SOCKET_FIX_HOLES]

    # ---- base: slab + 4 corner towers + IC holder, fixing holes, A1 chamfer
    base = box(-BX, -BY, 0, BX, BY, SLAB)
    for sx in (-1, 1):
        for sy in (-1, 1):
            x0, x1 = sorted((sx * BX, sx * (BX - TX)))
            y0, y1 = sorted((sy * BY, sy * (BY - TY)))
            base = base.union(box(x0, y0, SLAB, x1, y1, TOWER))
    holder = box(gx - 8.0, gy - 6.5, SLAB, gx + 8.0, gy + 6.5, NEST)
    holder = holder.cut(box(gx - 6.6, gy - 5.1, NEST - 1.2, gx + 6.6, gy + 5.1, NEST))   # IC pocket
    holder = holder.cut(box(gx - 4.0, gy - 4.0, SLAB, gx + 4.0, gy + 4.0, NEST))         # contact window
    base = base.union(holder)
    for x, y in holes:
        base = base.cut(cyl(x, y, 0, TOWER, 1.0))
        base = base.cut(cyl(x, y, TOWER - 0.4, TOWER, 1.6))      # spring seat
    base = base.cut(cq.Workplane("XY").polyline([(-BX, -BY + 2.5), (-BX, -BY), (-BX + 2.5, -BY)])
                    .close().extrude(TOWER))                       # A1 corner (footprint frame)

    # ---- clamp arms: two levers that pivot on pins beside the IC holder; the
    #      cover (via its slots) swings them open, the springs close them so
    #      the hook tips press on the top of the chip along its long edges
    arms = None
    arm_pins = None
    ic_top = NEST                                   # IC seated in the pocket, top flush with the holder
    for sy in (-1, 1):
        yc = lambda d: gy + sy * d                  # distance from the IC centre line
        hook = box(gx - 4.5, min(yc(3.7), yc(6.0)), ic_top + 0.05, gx + 4.5, max(yc(3.7), yc(6.0)), ic_top + 0.75)
        hook = hook.edges("|X").edges(">Z").chamfer(0.3)
        riser = box(gx - 4.5, min(yc(6.0), yc(7.0)), ic_top + 0.05, gx + 4.5, max(yc(6.0), yc(7.0)), ic_top + 3.4)
        boss = (cq.Workplane("YZ").circle(0.9).extrude(9.0).translate((gx - 4.5, yc(7.6), ic_top + 1.6)))
        cam = box(gx - 1.5, min(yc(6.8), yc(8.8)), ic_top + 2.6, gx + 1.5, max(yc(6.8), yc(8.8)), ic_top + 3.4)
        arm = hook.union(riser).union(boss).union(cam)
        arm = arm.cut(cq.Workplane("YZ").circle(0.45).extrude(9.0).translate((gx - 4.5, yc(7.6), ic_top + 1.6)))
        arms = arm if arms is None else arms.union(arm)
        pin = cq.Workplane("YZ").circle(0.42).extrude(11.0).translate((gx - 5.5, yc(7.6), ic_top + 1.6))
        arm_pins = pin if arm_pins is None else arm_pins.union(pin)

    # ---- cover: top plate + side skirts
    cover = box(-BW / 2, -BH / 2, COVER_LO, BW / 2, BH / 2, COVER_TOP)
    # skirts on the 26 mm faces (y = +/-15): drop into the channel between towers
    for sy in (-1, 1):
        y0, y1 = sorted((sy * BH / 2, sy * (BH / 2 - 2.5)))
        cover = cover.union(box(-(BX - TX) + 0.15, y0, SKIRT_A_Z, (BX - TX) - 0.15, y1, COVER_LO))
    # skirts on the 30 mm faces (x = +/-13): hang just outside the base
    pins = None
    for sx in (-1, 1):
        x0, x1 = sorted((sx * BW / 2, sx * (BX - 0.6)))
        sk = box(x0, -(BY - TY) + 0.15, SKIRT_B_Z, x1, (BY - TY) - 0.15, COVER_LO)
        # vertical guide slot with the latch pin at its lower end
        slot = (cq.Workplane("YZ").slot2D(3.2, 1.0, angle=90).extrude(2.0)
                .translate((sx * BW / 2 - 1.0, 4.0, 7.2)))
        sk = sk.cut(slot)
        cover = cover.union(sk)
        p = cq.Workplane("YZ").circle(0.45).extrude(1.6).translate((sx * BX - 0.9, 4.0, 6.0))
        pins = p if pins is None else pins.union(p)
    # funnel window over the nest
    win = (cq.Workplane("XY").workplane(offset=COVER_LO).center(gx, gy).rect(14.6, 11.6)
           .workplane(offset=COVER_TOP - COVER_LO).rect(18.0, 14.0).loft())
    cover = cover.cut(win)
    # countersunk corner holes, edge slots
    for x, y in holes:
        cover = cover.cut(cyl(x, y, COVER_LO, COVER_TOP, 1.0))
        cover = cover.cut(cq.Workplane("XY").workplane(offset=COVER_TOP - 0.8).center(x, y)
                          .circle(1.0).workplane(offset=0.8).circle(1.8).loft())
    for sy in (-1, 1):
        cover = cover.cut(box(-4.5, sy * 13.6 - 0.4, COVER_TOP - 0.3, 4.5, sy * 13.6 + 0.4, COVER_TOP))
    for sx in (-1, 1):
        for sy in (-1, 1):
            cover = cover.cut(box(sx * 11.3 - 0.4, sy * 6.5 - 2.0, COVER_TOP - 0.3,
                                  sx * 11.3 + 0.4, sy * 6.5 + 2.0, COVER_TOP))

    # ---- springs and screw posts at the corners
    springs = None
    posts = None
    for x, y in holes:
        s = spring(x, y, TOWER - 0.4, COVER_LO)
        springs = s if springs is None else springs.union(s)
        p = cyl(x, y, TOWER - 0.4, COVER_LO, 0.75)
        posts = p if posts is None else posts.union(p)

    # ---- contacts: 0.17 x 0.10 blades from the PCB pad (0.25 below the base) up into the nest
    contacts = None
    for ball in D.P30_BALLS:
        x, y = fp2m(D.socket_pad_xy(ball))
        c = box(x - 0.085, y - 0.05, -0.25, x + 0.085, y + 0.05, NEST - 1.2)
        contacts = c if contacts is None else contacts.union(c)

    # ---- locator pins, 3.4 below the base
    locs = None
    for x, y, d in D.SOCKET_LOCATORS:
        x, y = fp2m((x, y))
        c = cyl(x, y, -3.4, 0.5, d / 2 - 0.03).faces("<Z").chamfer(0.2)
        locs = c if locs is None else locs.union(c)

    black = cq.Color(0.10, 0.10, 0.10)
    asm = cq.Assembly(name="HMILU_BGA64-1.0-TP21NS")
    asm.add(base.union(locs), name="base", color=black)
    asm.add(arms, name="clamp_arms", color=cq.Color(0.20, 0.20, 0.20))
    asm.add(arm_pins, name="arm_pins", color=cq.Color(0.75, 0.75, 0.78))
    asm.add(cover, name="cover", color=cq.Color(0.13, 0.13, 0.13))
    asm.add(pins, name="guide_pins", color=cq.Color(0.75, 0.75, 0.78))
    asm.add(springs, name="springs", color=cq.Color(0.80, 0.80, 0.83))
    asm.add(posts, name="screw_posts", color=cq.Color(0.55, 0.55, 0.58))
    asm.add(contacts, name="contacts", color=cq.Color(0.86, 0.70, 0.25))
    return asm


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for f in os.listdir(os.path.dirname(OUT)):
        if f != os.path.basename(OUT):
            os.remove(os.path.join(os.path.dirname(OUT), f))
    build().export(OUT)
    print("wrote", os.path.normpath(OUT), os.path.getsize(OUT), "bytes")
