#!/usr/bin/env python3
"""Simplified 3D model (STEP) of the HMILU BGA64-1.0-TP21NS BGA-64 socket.

No vendor model is published, so this is built from the HMILU drawing
007-BGA-1.0-64-10X13-B-01 rev A:
  * body 26.0 x 30.0, overall height 17.5 (cover up), base 10.8
  * black PEI base and cover on 4 springs, 10 x 13 mm IC nest (13 mm along X)
  * 64 BeCu double-sided spring contacts (t0.1 x w0.17), 0.25 below the base
    onto the solid PCB pads
  * 4 locator pins (1 x dia 1.75 at the A1 corner, 3 x dia 1.45), 3.4 long
  * 4 x dia 2.0 fixing holes
Contact / pin positions come from design.py, so they line up exactly with
the footprint.  Needs CadQuery (run with the build/cqenv venv, python 3.12):

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

BW, BH = D.SOCKET_BODY          # 26.0 x 30.0
BASE_TOP = 7.5                  # top of the base block
Z_SEAT = 3.3                    # IC seating plane (nest floor)
Z_TOP = 17.5                    # cover top (cover up)
COVER_T = 6.7                   # cover from 10.8 to 17.5


def fp2m(p):
    """Footprint coords (y down) -> model coords (y up)."""
    return (p[0], -p[1])


def box(x, y, z, cx=0, cy=0, z0=0):
    return cq.Workplane("XY").box(x, y, z, centered=(True, True, False)).translate((cx, cy, z0))


def build():
    gx, gy = fp2m((D.GRID_X0 + 3.5, D.GRID_Y0 - 3.5))   # grid / IC centre

    # ---- base: full footprint, nest pocket, fixing holes
    base = box(BW, BH, BASE_TOP)
    base = base.cut(box(17.0, 14.0, BASE_TOP - Z_SEAT, gx, gy, Z_SEAT))
    for p in D.SOCKET_FIX_HOLES:
        x, y = fp2m(p)
        base = base.cut(cq.Workplane("XY").circle(1.0).extrude(BASE_TOP).translate((x, y, 0)))
        base = base.cut(cq.Workplane("XY").circle(1.9).extrude(1.0).translate((x, y, BASE_TOP - 1.0)))
    # pin-1 chamfer on the A1 corner (bottom-left in the footprint frame)
    base = base.cut(cq.Workplane("XY").polyline([(-BW / 2, -BH / 2 + 3), (-BW / 2, -BH / 2),
                                                 (-BW / 2 + 3, -BH / 2)]).close().extrude(BASE_TOP))

    # ---- IC nest (10 x 13 mm, 13 mm along X) with the contact window
    nest = box(16.0, 13.0, 1.2, gx, gy, Z_SEAT - 1.2)
    nest = nest.cut(box(9.0, 9.0, 1.2, gx, gy, Z_SEAT - 1.2))
    guide = box(15.0, 12.0, 0.8, gx, gy, Z_SEAT).cut(box(13.2, 10.2, 0.8, gx, gy, Z_SEAT))

    # ---- cover: 26 x 30 frame with a window over the nest, on 4 springs
    cover = box(BW, BH, COVER_T, 0, 0, Z_TOP - COVER_T)
    cover = cover.cut(box(17.0, 14.0, COVER_T, gx, gy, Z_TOP - COVER_T))
    # springs sit in the counterbores of the 4 corner holes (cover guide posts)
    springs = None
    for p in D.SOCKET_FIX_HOLES:
        x, y = fp2m(p)
        s = (cq.Workplane("XY").circle(1.4).circle(1.0).extrude(Z_TOP - COVER_T - BASE_TOP + 1.0)
             .translate((x, y, BASE_TOP - 1.0)))
        springs = s if springs is None else springs.union(s)

    # ---- contacts: 0.17 x 0.10 blades from the PCB pad (0.25 below the base) up to the seat
    contacts = None
    for ball in D.P30_BALLS:
        x, y = fp2m(D.socket_pad_xy(ball))
        c = box(0.17, 0.10, Z_SEAT + 0.25, x, y, -0.25)
        contacts = c if contacts is None else contacts.union(c)

    # ---- locator pins, 3.4 below the base
    pins = None
    for x, y, d in D.SOCKET_LOCATORS:
        x, y = fp2m((x, y))
        c = cq.Workplane("XY").circle(d / 2 - 0.03).extrude(3.4 + 0.5).translate((x, y, -3.4))
        c = c.faces("<Z").chamfer(0.2)
        pins = c if pins is None else pins.union(c)

    black = cq.Color(0.10, 0.10, 0.10)
    asm = cq.Assembly(name="HMILU_BGA64-1.0-TP21NS")
    asm.add(base.union(pins), name="base", color=black)
    asm.add(nest.union(guide), name="ic_holder", color=black)
    asm.add(cover, name="cover", color=black)
    asm.add(springs, name="springs", color=cq.Color(0.75, 0.75, 0.78))
    asm.add(contacts, name="contacts", color=cq.Color(0.86, 0.70, 0.25))
    return asm


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for f in os.listdir(os.path.dirname(OUT)):
        if f != os.path.basename(OUT):
            os.remove(os.path.join(os.path.dirname(OUT), f))
    build().export(OUT)
    print("wrote", os.path.normpath(OUT), os.path.getsize(OUT), "bytes")
