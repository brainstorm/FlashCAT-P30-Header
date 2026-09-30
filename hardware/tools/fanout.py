"""Deterministic escape (fanout) of the 8x8 socket grid.

The socket contacts are plated through-holes on a 1.0 mm grid with 0.6 mm
pads, so every channel between two pads takes exactly one 0.127 mm track per
layer.  Autorouters struggle with the inner rings, so the escape is fixed
here and the rest (grid edge -> headers/passives) is left to Freerouting.

  F.Cu : ring 1 (straight stubs) + ring 2 (diagonal to interstitial, then out)
  B.Cu : ring 3
  In2  : ring 4 (centre 2x2)
  GND balls connect to the In1 plane through their barrels (no track).

Directions are KiCad screen coords: -y is "up" (towards row 8).
"""
import pcbnew as P

import design as D

W = 0.127
STUB = 0.9      # ring-1 stubs end this far beyond the pad
CHAN = 1.3      # channel escapes end this far beyond the outermost pad row/col

L, R, U, Dn = (-1, 0), (1, 0), (0, -1), (0, 1)

# (ball, layer, first diagonal (dx, dy) or None for a straight stub, exit direction)
F, B, I2 = "F.Cu", "B.Cu", "In2.Cu"
ESCAPES = [
    # --- ring 1, F.Cu stubs
    *[(b, F, None, U) for b in ("A8", "B8", "C8", "D8", "F8", "G8", "H8")],
    *[(b, F, None, L) for b in ("A7", "A6", "A5", "A4", "A3", "A2", "A1")],
    *[(b, F, None, R) for b in ("H7", "H5", "H3")],
    *[(b, F, None, Dn) for b in ("B1", "C1", "D1", "E1", "G1", "H1")],
    # --- ring 2, F.Cu diagonal + channel
    *[(b, F, (-1, -1), L) for b in ("B7", "B6", "B5", "B4", "B3")],
    *[(b, F, (1, -1), R) for b in ("G6", "G5", "G4", "G3")],
    ("G7", F, (1, -1), U),
    *[(b, F, (-1, -1), U) for b in ("D7", "E7", "F7")],
    ("C7", B, (-1, -1), L),     # B.Cu row 7/8 gap: faces J2 once the socket is rotated
    *[(b, F, (-1, 1), Dn) for b in ("C2", "D2", "E2", "F2")],
    # --- ring 3, B.Cu
    # C6 moved to In2 so the B.Cu row 6/7 gap is free for the A6 decap path
    *[(b, B, (-1, -1), L) for b in ("C5", "C4")],
    ("C3", I2, (-1, 1), Dn),     # In2: bottom of B.Cu is busy
    *[(b, B, (-1, 1), Dn) for b in ("D3", "E3")],
    # right side of B.Cu is kept free for the H3/G4 decaps
    ("F3", B, (-1, 1), Dn),
    ("D6", B, (-1, -1), U),
    # --- ring 4, In2
    ("D4", I2, (-1, 1), Dn),
    ("E4", I2, (-1, 1), Dn),
    ("E5", I2, (-1, -1), L),
    ("C6", I2, (-1, -1), L),
    ("F4", I2, (1, 1), Dn),
    ("F5", I2, (1, 1), R),      # row 4/5 gap: faces J1 once the socket is rotated
]

# same-net neighbours joined directly instead of escaping separately
LINKS = [
    ("D5", "D6", F),     # VCCQ + VCCQ; frees the In2 row-5/6 channel for DQ4
]

# grid extents (pad centres)
X_MIN, _ = D.socket_pad_xy("A1")
X_MAX, _ = D.socket_pad_xy("H1")
_, Y_MAX = D.socket_pad_xy("A1")   # row 1 (bottom, +y)
_, Y_MIN = D.socket_pad_xy("A8")   # row 8 (top, -y)


def _end(x, y, d, dist):
    """Extend from (x, y) in direction d until `dist` beyond the grid edge."""
    if d == L:
        return (X_MIN - dist, y)
    if d == R:
        return (X_MAX + dist, y)
    if d == U:
        return (x, Y_MIN - dist)
    return (x, Y_MAX + dist)


def paths():
    """Yield (ball, layer, [points]) for every escape."""
    seen = set()
    for ball, layer, diag, out in ESCAPES:
        assert ball not in seen, ball
        seen.add(ball)
        x, y = D.socket_pad_xy(ball)
        pts = [(x, y)]
        if diag is None:
            pts.append(_end(x, y, out, STUB))
        else:
            ix, iy = x + 0.5 * diag[0], y + 0.5 * diag[1]
            pts.append((ix, iy))
            pts.append(_end(ix, iy, out, CHAN))
        yield ball, layer, pts
    for a, c, layer in LINKS:
        assert D.p30_net(D.P30_BALLS[a]) == D.p30_net(D.P30_BALLS[c]), (a, c)
        assert a not in seen, a
        seen.add(a)
        yield a, layer, [D.socket_pad_xy(a), D.socket_pad_xy(c)]
    # every signal/VCC/+1V8 ball must have an escape (or link); GND/NC must not
    for ball, sig in D.P30_BALLS.items():
        net = D.p30_net(sig)
        needs = net is not None and net != "GND"
        assert needs == (ball in seen), (ball, sig, net)


def decap_paths():
    """(ball, "B.Cu", points) joining each bottom decap to its ball."""
    for ref, (ball, p1, p2, path) in D.DECAPS.items():
        if path:
            yield ball, B, path


def _decap_w(pts):
    """0.25 mm for paths that only skirt the grid edge; 0.127 mm when any
    segment runs through a channel between contacts (inside the pad ring)."""
    inner = any(X_MIN < x < X_MAX and Y_MIN < y < Y_MAX for x, y in pts[:-1])
    return W if inner else 0.25


def apply(board):
    fp = board.FindFootprintByReference("U1")
    layers = {"F.Cu": P.F_Cu, "B.Cu": P.B_Cu, "In2.Cu": P.In2_Cu}
    n = 0
    items = [(b, l, [D.R(q) for q in p], W) for b, l, p in paths()] + \
        [(b, l, [D.R(q) for q in p], _decap_w(p)) for b, l, p in decap_paths()] + \
        [(b, l, p, w) for b, l, w, p in D.PREROUTES]   # already in board frame
    for ball, layer, pts, width in items:
        pad = fp.FindPadByNumber(ball)
        net = pad.GetNet()
        for a, c in zip(pts, pts[1:]):
            t = P.PCB_TRACK(board)
            t.SetStart(P.VECTOR2I(P.FromMM(a[0]), P.FromMM(a[1])))
            t.SetEnd(P.VECTOR2I(P.FromMM(c[0]), P.FromMM(c[1])))
            t.SetWidth(P.FromMM(width))
            t.SetLayer(layers[layer])
            t.SetNet(net)
            t.SetLocked(True)
            board.Add(t)
            n += 1
    return n


def decap_vias(board):
    """VCC_PROG vias tying the VCCQ decap clusters to the In2 VCC pour."""
    fp = board.FindFootprintByReference("U1")
    net = fp.FindPadByNumber("G4").GetNet()
    for a, v in D.DECAP_VIAS:
        a, v = D.R(a), D.R(v)
        via = P.PCB_VIA(board)
        via.SetPosition(P.VECTOR2I(P.FromMM(v[0]), P.FromMM(v[1])))
        via.SetWidth(P.FromMM(0.5))
        via.SetDrill(P.FromMM(0.3))
        via.SetNet(net)
        via.SetLocked(True)
        board.Add(via)
        t = P.PCB_TRACK(board)
        t.SetStart(P.VECTOR2I(P.FromMM(a[0]), P.FromMM(a[1])))
        t.SetEnd(P.VECTOR2I(P.FromMM(v[0]), P.FromMM(v[1])))
        t.SetWidth(P.FromMM(0.25))
        t.SetLayer(P.B_Cu)
        t.SetNet(net)
        t.SetLocked(True)
        board.Add(t)
    pts = [D.R(q) for q in D.VCCQ_LINK]
    for a, c in zip(pts, pts[1:]):
        t = P.PCB_TRACK(board)
        t.SetStart(P.VECTOR2I(P.FromMM(a[0]), P.FromMM(a[1])))
        t.SetEnd(P.VECTOR2I(P.FromMM(c[0]), P.FromMM(c[1])))
        t.SetWidth(P.FromMM(0.25))
        t.SetLayer(P.B_Cu)
        t.SetNet(net)
        t.SetLocked(True)
        board.Add(t)
    return len(D.DECAP_VIAS)


def gnd_vias(board, dist=0.95):
    """Locked GND via next to every SMD GND pad (straight down to the In1 plane)."""
    n = 0
    for fp in board.GetFootprints():
        if fp.GetReference() in ("U1", "J1", "J2"):
            continue
        c = fp.GetPosition()
        for pad in fp.Pads():
            if pad.GetNetname() != "GND":
                continue
            p = pad.GetPosition()
            dx, dy = p.x - c.x, p.y - c.y
            ln = (dx * dx + dy * dy) ** 0.5 or 1
            v = P.VECTOR2I(int(p.x + dx / ln * P.FromMM(dist)), int(p.y + dy / ln * P.FromMM(dist)))
            via = P.PCB_VIA(board)
            via.SetPosition(v)
            via.SetWidth(P.FromMM(0.5))
            via.SetDrill(P.FromMM(0.3))
            via.SetNet(pad.GetNet())
            via.SetLocked(True)
            board.Add(via)
            t = P.PCB_TRACK(board)
            t.SetStart(p)
            t.SetEnd(v)
            t.SetWidth(P.FromMM(0.3))
            t.SetLayer(P.B_Cu if fp.IsFlipped() else P.F_Cu)
            t.SetNet(pad.GetNet())
            t.SetLocked(True)
            board.Add(t)
            n += 1
    return n
