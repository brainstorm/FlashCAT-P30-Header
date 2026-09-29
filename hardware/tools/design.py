"""
Single source of truth for the FlashCAT P30 Easy BGA-64 adapter ("hat").

Everything the generators emit (symbols, footprint, schematic, board) is
derived from the tables in this file.

Sources:
  * Intel/Numonyx "StrataFlash Embedded Memory (P30)" datasheet, order
    306666, Figure 7 "64-Ball Easy BGA Ballout" (top view, balls down).
  * Sensata CBG064-087G sales drawing, sheet 2 "PCB hole pattern (top view)".
  * Embedded Computers "EC 56-pin dual header" drawing (EC_56P_HEADER.png).
  * Embedded Computers TSOP-56 "Type-D" adapter schematic (SCM_TSOP56_D.png),
    the author's own P30/P33 adapter: 1.8 V LDO from header VCC for the core,
    VCCQ from header VCC, header VIO unused, WAIT -> RB0 with 4.7k pull-up,
    CLK/ADV# to GND, P30 A1 -> header A1.
  * FlashcatUSB software: x16 NOR uses WORD addressing on header A1..A27
    ("Parallel_X16 = 2 'Addressing is done A1-A27 (WORD ADDR)"), so P30
    address ball An goes straight to header An; header A0 is unused.
"""

# ---------------------------------------------------------------------------
# P30 64-ball Easy BGA ballout, TOP VIEW (datasheet Figure 7).
# Row letter A..H, column number 1..8.  Ball name = <row><col>, e.g. "D4".
# ---------------------------------------------------------------------------
P30_ROWS = {
    "A": ["A1", "A6", "A8", "VPP", "A13", "VCC", "A18", "A22"],
    "B": ["A2", "VSS", "A9", "CE#", "A14", "A25", "A19", "RFU"],
    "C": ["A3", "A7", "A10", "A12", "A15", "WP#", "A20", "A21"],
    "D": ["A4", "A5", "A11", "RST#", "VCCQ", "VCCQ", "A16", "A17"],
    "E": ["DQ8", "DQ1", "DQ9", "DQ3", "DQ4", "CLK", "DQ15", "RFU"],
    "F": ["RFU", "DQ0", "DQ10", "DQ11", "DQ12", "ADV#", "WAIT", "OE#"],
    "G": ["A23", "RFU", "DQ2", "VCCQ", "DQ5", "DQ6", "DQ14", "WE#"],
    "H": ["RFU", "VSS", "VCC", "VSS", "DQ13", "VSS", "DQ7", "A24"],
}
ROW_LETTERS = "ABCDEFGH"

P30_BALLS = {f"{r}{c + 1}": sig for r, sigs in P30_ROWS.items() for c, sig in enumerate(sigs)}
assert len(P30_BALLS) == 64


def socket_pad_xy(ball):
    """KiCad footprint coordinates (mm, +y down) of a ball's socket contact.

    Geometry per the Sensata CBG064-087G PCB hole pattern (top view):
      * pin A1 is the bottom-left contact,
      * the 8x8 contact grid is NOT centred on the registration-hole datum:
        A1 sits 3.41 mm left/below the datum, the far row/column 3.59 mm
        right/above (i.e. grid centre = datum + (0.09, 0.09) in a y-up view).
    P30 ball letters run along the 13 mm package side (socket X axis), ball
    numbers along the 10 mm side (socket Y axis).  Rotating the datasheet
    top view by 90 deg CCW puts A1 bottom-left with letters increasing to
    the right and numbers increasing upwards (proper rotation, no mirror).
    This is the same ball-name -> position convention as the Eagle
    footprint supplied by Embedded Computers.
    """
    li = ROW_LETTERS.index(ball[0])
    n = int(ball[1:])
    x = -3.41 + li * 1.0
    y_up = -3.41 + (n - 1) * 1.0
    return round(x, 3), round(-y_up, 3)


# Registration (plastic locating pin) holes, NPTH 2.10 mm, KiCad coords.
# The one near A1 (bottom-left) is offset 1 mm inwards -> polarises socket.
SOCKET_REG_HOLES = [(-8.0, -8.0), (8.0, -8.0), (8.0, 8.0), (-7.0, 8.0)]
SOCKET_BODY = (28.0, 24.6)       # outer body, X x Y
SOCKET_KEEPOUT = (4.5, 2.8)      # hatched corner keep-out zones, per corner


# ---------------------------------------------------------------------------
# Signal -> schematic net for each P30 ball.
#   None  -> left unconnected (RFU)
# ---------------------------------------------------------------------------
def p30_net(sig):
    if sig.startswith("A") and sig[1:].isdigit():
        return sig
    if sig.startswith("DQ"):
        return sig
    return {
        "CE#": "~{CE}",
        "OE#": "~{OE}",
        "WE#": "~{WE}",
        "RST#": "~{RST}",
        "WP#": "VCC_PROG",  # tied high like EC TSOP-56 Type-D (lock-down disabled)
        "ADV#": "GND",     # tie low: asynchronous address flow-through
        "CLK": "GND",      # unused in async mode, must be tied off
        "WAIT": "WAIT",    # -> header RB0 + 4.7k pull-up (as EC TSOP-56 Type-D)
        "RFU": None,       # reserved, must float
        "VCC": "+1V8",     # core 1.7-2.0 V (abs max 2.5 V!)
        "VPP": "VCC_PROG",  # VPPL 0.9-3.6 V: from header VCC (3.3 V), not the LDO
        "VCCQ": "VCC_PROG",  # I/O 1.7-3.6 V from header VCC (as EC TSOP-56 Type-D)
        "VSS": "GND",
    }[sig]


# ---------------------------------------------------------------------------
# EC 56-pin dual header (FlashcatUSB Mach1 / XPORT parallel adapters),
# as seen from the TOP of the adapter.  Two 2x14, 2.00 mm pitch headers;
# the left columns of the two headers are 42.00 mm apart.
# Each entry: (row 0..13 top->bottom) signal name on the header.
# ---------------------------------------------------------------------------
EC_J1_LEFT = ["GND", "VPP", "CLE", "ALE", "RE/B#", "RB0",
              "DQ0", "DQ1", "DQ2", "DQ3", "DQ4", "DQ5", "DQ6", "DQ7"]
EC_J1_RIGHT = ["VCC", "VIO", "OE", "WE", "CE0", "DQS",
               "DQ8", "DQ9", "DQ10", "DQ11", "DQ12", "DQ13", "DQ14", "DQ15"]
EC_J2_LEFT = ["A0/CE1", "A1/CE2", "A2/CE3"] + [f"A{i}" for i in range(3, 14)]
EC_J2_RIGHT = ["A27/RB1", "A26/RB2", "A25/RB3"] + [f"A{i}" for i in range(24, 13, -1)]
assert len(EC_J2_RIGHT) == 14 and EC_J2_RIGHT[-1] == "A14"

EC_PITCH = 2.0
EC_SPACING = 42.0


def ec_net(sig):
    """Adapter net for an EC header signal (None = not used by this adapter)."""
    base = sig.split("/")[0]
    if base.startswith("DQ") and base != "DQS":
        return base
    if base.startswith("A") and base[1:].isdigit():
        n = int(base[1:])
        # P30 256 Mbit uses A1..A24; A25 selects the upper die on 512 Mbit
        # dual-die parts, so wire it too.  A0 (byte address) is unused in
        # x16 word mode, A26/A27 are beyond the largest P30.
        return base if 1 <= n <= 25 else None
    return {
        "GND": "GND",
        "VCC": "VCC_PROG",
        "RB0": "WAIT",
        "OE": "~{OE}",
        "WE": "~{WE}",
        "CE0": "~{CE}",
    }.get(base)


def header_pins(left_col, right_col):
    """Pad number -> header signal for a 2x14 header mounted on the BOTTOM.

    The KiCad PinHeader_2x14 footprint has odd pads in one column and even
    pads offset +2 mm in X.  Flipped to B.Cu (mirrored in X), the even column
    lands on the LEFT when viewed from the top.  So:
        pad 2r+1 -> right column, row r
        pad 2r+2 -> left column,  row r
    (verified against real pad coordinates by gen_pcb.py).
    """
    pins = {}
    for r in range(14):
        pins[2 * r + 1] = right_col[r]
        pins[2 * r + 2] = left_col[r]
    return pins


J1_PINS = header_pins(EC_J1_LEFT, EC_J1_RIGHT)
J2_PINS = header_pins(EC_J2_LEFT, EC_J2_RIGHT)

# Board-level placement (KiCad coords, mm).  Socket datum at origin.
J1_ANCHOR = (-20.0, -13.0)   # pad 1 of J1 (bottom-side footprint)
J2_ANCHOR = (22.0, -13.0)    # pad 1 of J2
BOARD = (-25.5, -18.5, 25.5, 18.5)   # x0, y0, x1, y1


def check():
    # every connected P30 signal must reach the header (or be a rail)
    header_nets = {ec_net(s) for s in list(J1_PINS.values()) + list(J2_PINS.values())}
    header_nets.discard(None)
    for ball, sig in P30_BALLS.items():
        n = p30_net(sig)
        # RST# is not on the EC header: pulled up to header VCC on the adapter
        if n is None or n in ("GND", "+1V8", "VCC_PROG", "~{RST}"):
            continue
        assert n in header_nets, (ball, sig, n)
    # every address/data header net must land on a P30 ball
    p30_nets = {p30_net(s) for s in P30_BALLS.values()}
    for n in header_nets:
        if n in ("VCC_PROG",):
            continue
        assert n in p30_nets, n
    # 25 address + 16 data balls present
    assert sum(1 for s in P30_BALLS.values() if s.startswith("A") and s[1:].isdigit()) == 25
    assert sum(1 for s in P30_BALLS.values() if s.startswith("DQ")) == 16


check()


# ---------------------------------------------------------------------------
# Decoupling caps on the BOTTOM side, right at the socket power balls.
# ref: (ball, pad1 (power) xy, pad2 (GND) xy, path from ball to pad1 on B.Cu)
# Paths leave the grid through channels kept free of other B.Cu escapes
# (see fanout.py).  KiCad coords, socket datum at (0, 0).
# ---------------------------------------------------------------------------
def _pad_off(edge, d):
    return round(edge + d, 3)


_XL, _XR = -3.41, 3.59          # column A / H pad centres
DECAPS = {
    # VCC A6 (+1V8): out through the row 6/7 gap on the left
    "C5": ("A6", (_pad_off(_XL, -1.415), -2.09), (_pad_off(_XL, -2.965), -2.09),
           [(-3.41, -1.59), (-3.91, -2.09), (_pad_off(_XL, -1.415), -2.09)]),
    # VPP A4 (header VCC), 10 uF: out through the row 3/4 gap on the left
    "C3": ("A4", (_pad_off(_XL, -1.415), 0.91), (_pad_off(_XL, -2.965), 0.91),
           [(-3.41, 0.41), (-3.91, 0.91), (_pad_off(_XL, -1.415), 0.91)]),
    # VCC H3 (+1V8): out through the row 2/3 gap on the right
    "C6": ("H3", (_pad_off(_XR, 1.415), 1.91), (_pad_off(_XR, 2.965), 1.91),
           [(3.59, 1.41), (4.09, 1.91), (_pad_off(_XR, 1.415), 1.91)]),
    # VCCQ G4: diagonal to the row 4/5 channel, out between H4 and H5
    "C8": ("G4", (_pad_off(_XR, 1.415), -0.09), (_pad_off(_XR, 2.965), -0.09),
           [(2.59, 0.41), (3.09, -0.09), (_pad_off(_XR, 1.415), -0.09)]),
    # VCCQ D6 (+D5 linked): the D6 B.Cu escape runs up the C|D channel; this
    # path overlaps its end and continues onto the pad
    "C7": ("D6", (-0.91, -5.69), (-0.91, -7.24), [(-0.91, -4.0), (-0.91, -5.69)]),
    # VCCQ 10 uF bulk next to C7, pad1 tied to C7 pad1 on B.Cu
    "C4": ("D6", (0.64, -5.69), (0.64, -7.24), [(-0.91, -5.69), (0.64, -5.69)]),
}

# VCCQ decap clusters sit on VCC_PROG islands inside the grid: drop each onto
# the In2 VCC pour (solid outside the grid) with a via.  (from pad xy, via xy)
DECAP_VIAS = [
    ((0.64, -5.69), (1.6, -6.5)),     # C4/C7 (D5, D6)
    ((5.005, -0.09), (5.69, -0.09)),  # C8 (G4), also the end of G4's F.Cu escape
]

# Locked B.Cu link joining the G4/C8 VCCQ cluster to the C4/C7 cluster (and
# its via), so all VCCQ balls share one VCC_PROG connection regardless of
# how the In2 pour gets split by signal routing.
VCCQ_LINK = [(5.005, -0.09), (5.005, -5.0), (3.505, -6.5), (1.6, -6.5)]

# ---------------------------------------------------------------------------
# Socket orientation on the board.  Rotated 180 deg so the address-heavy
# columns (A-D) face the address header J2 and the data columns (E-H) face
# the data header J1.  All fanout/decap geometry above is written in the
# socket footprint frame; R() maps it onto the board.
# ---------------------------------------------------------------------------
SOCKET_ROT = 180


def R(p):
    x, y = p
    if SOCKET_ROT == 180:
        return (round(-x, 4), round(-y, 4))
    assert SOCKET_ROT == 0
    return (x, y)

# Hand pre-routes (BOARD frame, i.e. already rotated; socket datum at 0,0).
# DQ12: from the end of ball F5's In2 escape to J1 pad 21, around the
# registration hole; Freerouting could not finish this one on its own.
PREROUTES = [
    ("F5", "In2.Cu", 0.127, [(-4.89, 0.09), (-4.89, 2.5), (-9.39, 7.0), (-20.0, 7.0)]),
]
