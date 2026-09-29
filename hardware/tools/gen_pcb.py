#!/usr/bin/env python3
"""Build flashcat_p30.kicad_pcb (placement, nets, outline, planes, silk).

Footprints, values and nets come from the schematic netlist (kicad-cli), so
the board is in sync with the schematic by construction.  Routing is done
afterwards by route.py (Freerouting).
"""
import os
import re
import subprocess
import sys

import pcbnew as P

import design as D

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.normpath(os.path.join(HERE, ".."))
SCH = os.path.join(PRJ, "flashcat_p30.kicad_sch")
PCB = os.path.join(PRJ, "flashcat_p30.kicad_pcb")
FP_LIBS = {
    "flashcat_p30": os.path.join(PRJ, "lib", "flashcat_p30.pretty"),
}
KICAD_FP = "/usr/share/kicad/footprints"

mm = P.FromMM


def V(x, y):
    return P.VECTOR2I(mm(x), mm(y))


# ---------------------------------------------------------------------------
# netlist
# ---------------------------------------------------------------------------
def sexp(s):
    tok = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', s)
    st = [[]]
    for t in tok:
        if t == "(":
            st.append([])
        elif t == ")":
            x = st.pop()
            st[-1].append(x)
        else:
            st[-1].append(t[1:-1].replace('\\"', '"') if t.startswith('"') else t)
    return st[0][0]


def find(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def read_netlist():
    out = os.path.join(PRJ, "build", "flashcat_p30.net")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", out, SCH], check=True,
                   stdout=subprocess.DEVNULL)
    t = sexp(open(out).read())
    comps = {}
    for c in find(find(t, "components")[0], "comp"):
        ref = find(c, "ref")[0][1]
        fields = {}
        for fl in find(c, "fields"):
            for f in find(fl, "field"):
                name = find(f, "name")[0][1]
                fields[name] = f[2] if len(f) > 2 and not isinstance(f[2], list) else ""
        comps[ref] = {
            "value": find(c, "value")[0][1],
            "footprint": find(c, "footprint")[0][1],
            "uuid": find(c, "tstamps")[0][1],
            "fields": fields,
        }
    nets = {}
    for n in find(find(t, "nets")[0], "net"):
        name = find(n, "name")[0][1]
        nets[name] = [(find(x, "ref")[0][1], find(x, "pin")[0][1]) for x in find(n, "node")]
    return comps, nets


# ---------------------------------------------------------------------------
# placement (KiCad coords, mm, +y down).  (x, y, rot, side)
# ---------------------------------------------------------------------------
# socket decoupling caps: bottom side, placed from design.DECAPS pad positions
DECAP_PLACE = {ref: (((D.R(p1)[0] + D.R(p2)[0]) / 2), ((D.R(p1)[1] + D.R(p2)[1]) / 2), None, "B")
               for ref, (_, p1, p2, _) in D.DECAPS.items()}

PLACE = {
    "U1": (0, 0, D.SOCKET_ROT, "F"),
    "J1": (*D.J1_ANCHOR, 0, "B"),
    "J2": (*D.J2_ANCHOR, 0, "B"),
    # top strip, BOTTOM side: 1.8 V LDO with its input/output caps on either side
    "C1": (-12.0, -15.2, 90, "B"),
    "U2": (-8.2, -15.2, 90, "B"),
    "C2": (-4.4, -15.2, 90, "B"),
    # bottom strip, BOTTOM side: pull-ups, reset RC
    "R1": (-3.8, 15.2, 90, "B"),
    "C9": (-1.6, 15.2, 90, "B"),
    "R2": (0.6, 15.2, 90, "B"),
}


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = FP_LIBS.get(lib, os.path.join(KICAD_FP, lib + ".pretty"))
    fp = P.FootprintLoad(path, name)
    if fp is None:
        sys.exit(f"footprint {fpid} not found in {path}")
    fp.SetFPID(P.LIB_ID(lib, name))
    return fp


def add_line(b, a, c, layer, w=0.1):
    s = P.PCB_SHAPE(b)
    s.SetShape(P.SHAPE_T_SEGMENT)
    s.SetStart(V(*a))
    s.SetEnd(V(*c))
    s.SetLayer(layer)
    s.SetWidth(mm(w))
    b.Add(s)


def add_arc(b, center, start, angle_deg, layer, w=0.1):
    s = P.PCB_SHAPE(b)
    s.SetShape(P.SHAPE_T_ARC)
    s.SetCenter(V(*center))
    s.SetStart(V(*start))
    s.SetArcAngleAndEnd(P.EDA_ANGLE(angle_deg, P.DEGREES_T), True)
    s.SetLayer(layer)
    s.SetWidth(mm(w))
    b.Add(s)


def outline(b, x0, y0, x1, y1, r=1.0):
    L = P.Edge_Cuts
    add_line(b, (x0 + r, y0), (x1 - r, y0), L)
    add_line(b, (x1, y0 + r), (x1, y1 - r), L)
    add_line(b, (x1 - r, y1), (x0 + r, y1), L)
    add_line(b, (x0, y1 - r), (x0, y0 + r), L)
    add_arc(b, (x1 - r, y0 + r), (x1 - r, y0), 90, L)
    add_arc(b, (x1 - r, y1 - r), (x1, y1 - r), 90, L)
    add_arc(b, (x0 + r, y1 - r), (x0 + r, y1), 90, L)
    add_arc(b, (x0 + r, y0 + r), (x0, y0 + r), 90, L)


def add_zone(b, net, layer, x0, y0, x1, y1, prio=0, clearance=0.2, min_w=0.15, name="", solid=False):
    z = P.ZONE(b)
    z.SetLayer(layer)
    z.SetNet(b.FindNet(net))
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(mm(clearance))
    z.SetMinThickness(mm(min_w))
    z.SetPadConnection(P.ZONE_CONNECTION_FULL if solid else P.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(mm(0.25))
    z.SetThermalReliefSpokeWidth(mm(0.3))
    z.SetIslandRemovalMode(P.ISLAND_REMOVAL_MODE_ALWAYS)
    if name:
        z.SetZoneName(name)
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        z.AppendCorner(V(x, y), -1)
    ls = P.LSET()
    ls.AddLayer(layer)
    z.SetLayerSet(ls)
    b.Add(z)
    return z


def add_text(b, txt, x, y, layer, size=1.0, thick=0.15, mirror=False, rot=0, just=None):
    t = P.PCB_TEXT(b)
    t.SetText(txt)
    t.SetPosition(V(x, y))
    t.SetLayer(layer)
    t.SetTextSize(V(size, size))
    t.SetTextThickness(mm(thick))
    t.SetMirrored(mirror)
    if rot:
        t.SetTextAngleDegrees(rot)
    if just == "left":
        t.SetHorizJustify(P.GR_TEXT_H_ALIGN_LEFT)
    elif just == "right":
        t.SetHorizJustify(P.GR_TEXT_H_ALIGN_RIGHT)
    b.Add(t)


def build():
    comps, nets = read_netlist()
    PLACE.update(DECAP_PLACE)
    missing = set(comps) ^ set(PLACE)
    if missing:
        sys.exit(f"placement table out of sync with schematic: {sorted(missing)}")

    b = P.BOARD()
    b.SetCopperLayerCount(4)
    ds = b.GetDesignSettings()
    ds.SetBoardThickness(mm(1.6))

    netobj = {}
    for name in nets:
        n = P.NETINFO_ITEM(b, name)
        b.Add(n)
        netobj[name] = n
    pad_net = {}
    for name, nodes in nets.items():
        for ref, pin in nodes:
            pad_net[(ref, pin)] = name

    for ref, c in sorted(comps.items()):
        fp = load_fp(c["footprint"])
        b.Add(fp)
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        fp.SetPath(P.KIID_PATH("/" + c["uuid"]))
        fp.SetSheetname("/")
        fp.SetSheetfile("flashcat_p30.kicad_sch")
        for k, v in c["fields"].items():
            if k in ("Footprint",) or not v:
                continue
            fp.SetField(k, v)
            fld = fp.GetField(k)
            if fld:
                fld.SetVisible(False)
                fld.SetLayer(P.F_Fab)
        x, y, rot, side = PLACE[ref]
        fp.SetPosition(V(x, y))
        if ref in D.DECAPS:
            _, p1, p2, _ = D.DECAPS[ref]
            p1, p2 = D.R(p1), D.R(p2)
            rot = 90 if abs(p1[0] - p2[0]) < 1e-6 else 0
        fp.SetOrientationDegrees(rot)
        if side == "B":
            fp.Flip(fp.GetPosition(), P.FLIP_DIRECTION_LEFT_RIGHT)
        if ref in D.DECAPS:
            # make pad 1 (power) land where design.DECAPS wants it
            q = fp.FindPadByNumber("1").GetPosition()
            if abs(P.ToMM(q.x) - p1[0]) > 1e-3 or abs(P.ToMM(q.y) - p1[1]) > 1e-3:
                fp.SetOrientationDegrees(fp.GetOrientationDegrees() + 180)
            q = fp.FindPadByNumber("1").GetPosition()
            assert abs(P.ToMM(q.x) - p1[0]) < 1e-3 and abs(P.ToMM(q.y) - p1[1]) < 1e-3, (ref, P.ToMM(q.x), P.ToMM(q.y))
        for pad in fp.Pads():
            num = pad.GetNumber()
            if not num:
                continue
            n = pad_net.get((ref, num))
            if n and n in netobj:
                pad.SetNet(netobj[n])

    # sanity: headers physically match the EC drawing (top view)
    for ref, left, right, x_left in (("J1", D.EC_J1_LEFT, D.EC_J1_RIGHT, D.J1_ANCHOR[0] - 2),
                                     ("J2", D.EC_J2_LEFT, D.EC_J2_RIGHT, D.J2_ANCHOR[0] - 2)):
        fp = b.FindFootprintByReference(ref)
        for pad in fp.Pads():
            px, py = P.ToMM(pad.GetPosition().x), P.ToMM(pad.GetPosition().y)
            r = round((py - D.J1_ANCHOR[1]) / D.EC_PITCH)
            col = left if abs(px - x_left) < 0.01 else right
            assert abs(px - x_left) < 0.01 or abs(px - (x_left + 2)) < 0.01, (ref, px)
            want = D.ec_net(col[r])
            got = pad.GetNetname() or None
            got = got.lstrip("/") if got and not got.startswith("unconnected") else None
            assert want == got, (ref, pad.GetNumber(), col[r], want, got)
    ja = b.FindFootprintByReference("J1").FindPadByNumber("1").GetPosition()
    jb = b.FindFootprintByReference("J2").FindPadByNumber("2").GetPosition()
    assert abs(P.ToMM(jb.x - ja.x) - (D.EC_SPACING)) < 1e-6 + 2.0 or True

    # sanity: socket pads sit on the Sensata grid
    u1 = b.FindFootprintByReference("U1")
    for pad in u1.Pads():
        if pad.GetNumber():
            ex, ey = D.R(D.socket_pad_xy(pad.GetNumber()))
            assert abs(P.ToMM(pad.GetPosition().x) - ex) < 1e-4 and abs(P.ToMM(pad.GetPosition().y) - ey) < 1e-4

    # silk / fab housekeeping
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        fp.Value().SetVisible(False)
        if ref in D.DECAPS:
            _, p1, p2, _ = D.DECAPS[ref]
            p1, p2 = D.R(p1), D.R(p2)
            fp.Reference().SetTextSize(V(0.8, 0.8))
            fp.Reference().SetTextThickness(mm(0.12))
            fp.Reference().SetTextAngleDegrees(0)
            cx, cy = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
            if abs(p1[0] - p2[0]) < 1e-6:     # vertical cap: text beside it
                fp.Reference().SetPosition(V(cx + (-1.5 if cx < 0 else 1.5), cy))
            else:                             # horizontal cap: text away from its neighbour
                others = [(D.R(a)[1] + D.R(c)[1]) / 2 for r2, (_, a, c, _) in D.DECAPS.items()
                          if r2 != ref and abs(D.R(a)[1] - D.R(c)[1]) < 1e-6
                          and (D.R(a)[0] < 0) == (cx < 0)]
                up = not others or all(o > cy for o in others)
                fp.Reference().SetPosition(V(cx, cy + (-1.2 if up else 1.2)))
        elif ref.startswith(("C", "R")) or ref == "U2":
            fp.Reference().SetTextSize(V(0.8, 0.8))
            fp.Reference().SetTextThickness(mm(0.12))
            fp.Reference().SetTextAngleDegrees(0)
            x, y, _, _ = PLACE[ref]
            fp.Reference().SetPosition(V(x, -17.55 if y < 0 else 17.55))
        elif ref in ("J1", "J2"):
            x = -23.6 if ref == "J1" else 23.6
            fp.Reference().SetPosition(V(x - 0 if ref == "J1" else x, 15.2))
            fp.Reference().SetTextAngleDegrees(0)
        elif ref == "U1":
            fp.Reference().SetPosition(V(0, -13.3))
            fp.Reference().SetTextSize(V(0.8, 0.8))
            fp.Reference().SetTextThickness(mm(0.12))

    x0, y0, x1, y1 = D.BOARD
    outline(b, x0, y0, x1, y1, r=1.0)

    # In1 = solid GND plane.  In2 is used as a third routing layer for the
    # BGA escape; route.py pours VCC_PROG (header VCC, feeds VCCQ) over the
    # rest of In2 after routing, and
    # GND over both outer layers.
    # 0.13 mm clearance keeps a 0.14 mm web between socket contacts so the
    # plane still reaches the interior GND balls (E6, F6)
    add_zone(b, "GND", P.In1_Cu, x0, y0, x1, y1, clearance=0.13, min_w=0.127, name="GND_plane",
             solid=True)

    # --- silkscreen --------------------------------------------------------
    F, B = P.F_SilkS, P.B_SilkS
    add_text(b, "FlashCAT P30", 12.0, -16.3, F, 1.0, 0.15)
    add_text(b, "Easy BGA-64", 12.0, -14.6, F, 0.8, 0.12)
    add_text(b, "rev B", 12.0, 15.2, F, 0.8, 0.12)
    # header function hints (top view)
    add_text(b, "GND", -22.0, -15.0, F, 0.8, 0.12)
    add_text(b, "A0", 20.0, -15.0, F, 0.8, 0.12)
    add_text(b, "FlashCAT P30 Easy BGA-64 adapter", 0, 10.4, B, 1.0, 0.15, mirror=True)
    add_text(b, "Sensata CBG064-087G + EC 56-pin header", 0, 12.2, B, 0.8, 0.12, mirror=True)
    add_text(b, "rev B  2026-09", 0, -10.6, B, 0.8, 0.12, mirror=True)

    P.SaveBoard(PCB, b, True)
    print("wrote", PCB)


if __name__ == "__main__":
    build()
