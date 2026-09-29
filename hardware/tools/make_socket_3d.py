#!/usr/bin/env python3
"""Simplified 3D model (STEP) of the Sensata CBG064-087G BGA-64 burn-in socket.

No vendor model exists (SnapEDA / TraceParts / Sensata), so this is built
from the Sensata sales drawing CBG064-087G-3 rev A:
  * body 28.00 x 24.60, overall height 16.50 (cover up)
  * base / lead guide (black PEI), IC seating plane at 9.20
  * beige adapter nest for an 11 x 13 mm package
  * cover (black) 2.9 mm thick on 4 springs, open centre
  * 64 BeCu contacts 0.12 x 0.20, tails 2.80 below the seating plane
  * 4 x dia 2.00 registration posts, 3.00 below the seating plane
Contact / post positions come from design.py, so they line up exactly with
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

OUT = os.path.join(HERE, "..", "lib", "flashcat_p30.3dshapes", "Sensata_CBG064-087G.step")

BW, BH = D.SOCKET_BODY          # 28.0 x 24.6
Z_SEAT = 9.2                    # IC seating plane
Z_TOP = 16.5                    # cover top (full height)
COVER_T = 2.9
BASE_TOP = 9.5
GRID_C = (0.09, 0.09)           # grid centre offset (model frame, y up)


def fp2m(p):
    """Footprint coords (y down) -> model coords (y up)."""
    return (p[0], -p[1])


def box(x, y, z, cx=0, cy=0, z0=0):
    return cq.Workplane("XY").box(x, y, z, centered=(True, True, False)).translate((cx, cy, z0))


def build():
    kx, ky = D.SOCKET_KEEPOUT
    # ---- base: full footprint, central window, corner cut-outs (latch travel)
    base = box(BW, BH, BASE_TOP)
    base = base.cut(box(16.0, 16.0, BASE_TOP, *GRID_C, 0))
    for sx in (-1, 1):
        for sy in (-1, 1):
            base = base.cut(box(kx, ky, BASE_TOP, sx * (BW - kx) / 2, sy * (BH - ky) / 2, 0))
    # pin-1 chamfer mark on the A1 corner of the base
    ax, ay = fp2m(D.socket_pad_xy("A1"))
    base = base.cut(cq.Workplane("XY").polyline([(-BW / 2, -BH / 2 + 3), (-BW / 2, -BH / 2),
                                                 (-BW / 2 + 3, -BH / 2)]).close()
                    .extrude(BASE_TOP).translate((0, 0, 0)).translate((0, 0, 0)))

    # ---- lead guide under the grid (sits in the window, flush with the PCB)
    guide = box(15.0, 15.0, 2.0, *GRID_C, 0)
    for ball in D.P30_BALLS:
        x, y = fp2m(D.socket_pad_xy(ball))
        guide = guide.cut(box(0.45, 0.45, 2.0, x, y, 0))

    # ---- adapter nest (beige): 13.2 x 12.8 block, 11 x 13 pocket, seat at 9.2
    nest = box(14.8, 14.8, Z_SEAT + 1.0 - 2.0, *GRID_C, 2.0)
    nest = nest.cut(box(13.0, 11.0, 1.0, *GRID_C, Z_SEAT))
    nest = nest.edges("|Z").fillet(0.8)
    # funnel chamfer around the pocket
    nest = nest.cut(box(13.8, 11.8, 0.4, *GRID_C, Z_SEAT + 0.6))

    # ---- latches (2), either side of the nest along Y
    latches = None
    for sy in (-1, 1):
        l = box(6.0, 2.0, 1.6, GRID_C[0], GRID_C[1] + sy * 7.0, Z_SEAT)
        latches = l if latches is None else latches.union(l)

    # ---- cover: 28 x 24.6 frame, octagonal opening
    cover = box(BW, BH, COVER_T, 0, 0, Z_TOP - COVER_T)
    hole = (cq.Workplane("XY").rect(16.4, 16.4).extrude(COVER_T)
            .edges("|Z").chamfer(2.5).translate((GRID_C[0], GRID_C[1], Z_TOP - COVER_T)))
    cover = cover.cut(hole)

    # ---- springs (4) between base and cover
    springs = None
    for sx in (-1, 1):
        for sy in (-1, 1):
            s = (cq.Workplane("XY").circle(1.4).circle(1.0).extrude(Z_TOP - COVER_T - BASE_TOP)
                 .translate((sx * 11.0, sy * 9.5, BASE_TOP)))
            springs = s if springs is None else springs.union(s)

    # ---- contacts: 0.20 x 0.12 blades from 2.8 below the PCB top up into the nest
    contacts = None
    for ball in D.P30_BALLS:
        x, y = fp2m(D.socket_pad_xy(ball))
        c = box(0.20, 0.12, 2.8 + 2.4, x, y, -2.8)
        contacts = c if contacts is None else contacts.union(c)

    # ---- registration posts: dia 2.0, 3.0 below the seating plane
    posts = None
    for p in D.SOCKET_REG_HOLES:
        x, y = fp2m(p)
        c = cq.Workplane("XY").circle(1.0).extrude(3.0 + 0.5).translate((x, y, -3.0))
        c = c.faces("<Z").chamfer(0.3)
        posts = c if posts is None else posts.union(c)

    black = cq.Color(0.10, 0.10, 0.10)
    asm = cq.Assembly(name="Sensata_CBG064-087G")
    asm.add(base.union(posts), name="base", color=black)
    asm.add(guide, name="lead_guide", color=black)
    asm.add(nest, name="adapter", color=cq.Color(0.87, 0.80, 0.62))
    asm.add(latches, name="latches", color=black)
    asm.add(cover, name="cover", color=black)
    asm.add(springs, name="springs", color=cq.Color(0.75, 0.75, 0.78))
    asm.add(contacts, name="contacts", color=cq.Color(0.86, 0.70, 0.25))
    return asm


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    build().export(OUT)
    print("wrote", os.path.normpath(OUT), os.path.getsize(OUT), "bytes")
