"""
Single source of truth for the FlashCAT P30 Easy BGA-64 adapter ("hat").

Everything the generators emit (symbols, footprint, schematic, board) is
derived from the tables in this file.

Sources:
  * Intel/Numonyx "StrataFlash Embedded Memory (P30)" datasheet, order
    306666, Figure 7 "64-Ball Easy BGA Ballout" (top view, balls down).
  * HMILU BGA64-1.0-TP21NS socket drawing 007-BGA-1.0-64-10X13-B-01 rev A,
    "PCB Pattern (TOP View)": open-top socket for 10x13 mm BGA-64, 1.0 mm
    pitch, solderless double-sided spring contacts on 64 x dia 0.55 solid
    (flat) pads, 4 locator pins, 4 fixing holes.
  * Embedded Computers "EC 56-pin dual header" drawing (EC_56P_HEADER.png).
  * Embedded Computers TSOP-56 "Type-D" adapter schematic (SCM_TSOP56_D.png),
    the author's own P30/P33 adapter: 1.8 V LDO from header VCC for the core,
    VCCQ from header VCC, header VIO unused, WAIT -> RB0 with 4.7k pull-up,
    CLK/ADV# to GND, P30 A1 -> header A1.
  * Micron "Parallel NOR Flash Embedded Memory (P30-65nm)" 512Mb/1Gb/2Gb
    datasheet, Figure 7: same Easy BGA ballout, but the balls that are RFU
    on the 130 nm parts carry A26 (B8, 1Gb and up) and A27 (H1, 2Gb die
    select).  They are wired straight to header A26/A27, as EC's TSOP-56
    Type-D adapter does for the 65 nm TSOP pins.
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
    "B": ["A2", "VSS", "A9", "CE#", "A14", "A25", "A19", "A26"],   # B8: RFU on 130 nm
    "C": ["A3", "A7", "A10", "A12", "A15", "WP#", "A20", "A21"],
    "D": ["A4", "A5", "A11", "RST#", "VCCQ", "VCCQ", "A16", "A17"],
    "E": ["DQ8", "DQ1", "DQ9", "DQ3", "DQ4", "CLK", "DQ15", "RFU"],
    "F": ["RFU", "DQ0", "DQ10", "DQ11", "DQ12", "ADV#", "WAIT", "OE#"],
    "G": ["A23", "RFU", "DQ2", "VCCQ", "DQ5", "DQ6", "DQ14", "WE#"],
    "H": ["A27", "VSS", "VCC", "VSS", "DQ13", "VSS", "DQ7", "A24"],   # H1: RFU on 130 nm
}
ROW_LETTERS = "ABCDEFGH"

P30_BALLS = {f"{r}{c + 1}": sig for r, sigs in P30_ROWS.items() for c, sig in enumerate(sigs)}
assert len(P30_BALLS) == 64


def socket_pad_xy(ball):
    """KiCad footprint coordinates (mm, +y down) of a ball's socket contact.

    Geometry per the HMILU BGA64-1.0-TP21NS "PCB Pattern (TOP View)":
      * the IC sits with its 13 mm side along the socket X axis and pin A1
        at the top-right (datasheet top view rotated 90 deg clockwise, no
        mirror): letters A..H run right -> left, numbers 1..8 top -> bottom;
      * the 8x8 pad grid is NOT centred on the socket: the left column and
        the top row are 3.25 mm from the socket centre lines, the right
        column / bottom row 3.75 mm, i.e. grid centre = socket centre +
        (0.25, 0.25) in the drawing's top view.
    The footprint is defined in that top view rotated by 180 deg (see
    SOCKET_ROT below, which puts it back on the board), so in footprint
    coordinates A1 is the bottom-left pad: letters increase to the right,
    numbers upwards.  This keeps the same ball -> footprint-frame
    convention as the original Sensata/Eagle footprint, so the fanout plan
    in fanout.py and the decap geometry below still apply.
    """
    li = ROW_LETTERS.index(ball[0])
    n = int(ball[1:])
    x = GRID_X0 + li * 1.0
    y = GRID_Y0 - (n - 1) * 1.0
    return round(x, 3), round(y, 3)


# A1 pad in footprint coordinates (drawing top view: (+3.75, -3.25), rotated)
GRID_X0, GRID_Y0 = -3.75, 3.25
# Offset of this grid from the original Sensata one (A1 at (-3.41, +3.41)),
# applied to the hand-planned decap geometry below.
GRID_SHIFT = (GRID_X0 + 3.41, GRID_Y0 - 3.41)

# Socket mechanics, footprint coordinates (drawing top view rotated 180 deg).
# Locator pins: 3 x dia 1.45 +0.05/-0 and 1 x dia 1.75 +0.05/-0 (at the A1
# corner, polarises the socket), 11.20 x 20.00 mm apart, NPTH.
SOCKET_LOCATORS = [(-5.6, 10.0, 1.75), (5.6, 10.0, 1.45), (5.6, -10.0, 1.45), (-5.6, -10.0, 1.45)]
# Fixing holes (screws): 4 x dia 2.00, 21.20 x 22.20 mm apart, NPTH.
SOCKET_FIX_HOLES = [(sx * 10.6, sy * 11.1) for sx in (-1, 1) for sy in (-1, 1)]
SOCKET_BODY = (26.0, 30.0)       # outer body, X x Y
SOCKET_PAD = 0.55                # solid (flat) pad for the spring contacts


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
        # P30 256 Mbit uses A1..A24, 512 Mbit adds A25, the 65 nm 1 Gbit
        # adds A26 and the 2 Gbit dual-die part A27 (die select).  A0 (byte
        # address) is unused in x16 word mode.
        return base if 1 <= n <= 27 else None
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
BOARD = (-25.5, -16.5, 25.5, 16.5)   # x0, y0, x1, y1: 51 x 33 like the EC adapters


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
    # 27 address + 16 data balls present
    assert sum(1 for s in P30_BALLS.values() if s.startswith("A") and s[1:].isdigit()) == 27
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


_XL, _XR = -3.41, 3.59          # column A / H pad centres of the original grid
_DECAPS = {
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
_DECAP_VIAS = [
    ((0.64, -5.69), (1.6, -6.5)),     # C4/C7 (D5, D6)
    ((5.005, -0.09), (5.69, -0.09)),  # C8 (G4), also the end of G4's F.Cu escape
]

# Locked B.Cu link joining the G4/C8 VCCQ cluster to the C4/C7 cluster (and
# its via), so all VCCQ balls share one VCC_PROG connection regardless of
# how the In2 pour gets split by signal routing.
_VCCQ_LINK = [(5.005, -0.09), (5.005, -5.0), (3.505, -6.5), (1.6, -6.5)]


def _sh(p):
    return (round(p[0] + GRID_SHIFT[0], 3), round(p[1] + GRID_SHIFT[1], 3))


# The geometry above was planned on the Sensata grid; move it rigidly with
# the pad grid so it keeps its position relative to the balls.
DECAPS = {ref: (ball, _sh(p1), _sh(p2), [_sh(q) for q in path])
          for ref, (ball, p1, p2, path) in _DECAPS.items()}
DECAP_VIAS = [(_sh(a), _sh(v)) for a, v in _DECAP_VIAS]
VCCQ_LINK = [_sh(q) for q in _VCCQ_LINK]

# ---------------------------------------------------------------------------
# Socket orientation on the board.  Rotated 180 deg, which brings the
# footprint back to the drawing's top view: A1 top-right, address-heavy
# columns (A-D) facing the address header J2 and the data columns (E-H)
# facing the data header J1.  All fanout/decap geometry above is written in
# the socket footprint frame; R() maps it onto the board.
# ---------------------------------------------------------------------------
SOCKET_ROT = 180


def R(p):
    x, y = p
    if SOCKET_ROT == 180:
        return (round(-x, 4), round(-y, 4))
    assert SOCKET_ROT == 0
    return (x, y)

# Hand pre-routes (BOARD frame, i.e. already rotated; socket datum at 0,0).
# DQ12: from the end of ball F5's In2 escape to J1 pad 21; Freerouting could
# not finish this one on its own.
# A2: from the end of ball B1's In2 stub to J2 pad 6 (A2/CE3).  The top-row
# address balls reach the header in reverse order (A4..A1 left to right vs.
# A1..A4 top to bottom), and Freerouting kept boxing pad 6 in on all layers.
# WAIT: from the end of ball F7's F.Cu escape straight down between the
# C4/C7 decap vias, then through a via to R2 pad 2 on the bottom.
# DQ11: from the end of ball F4's In2 escape to J1 pad 19, parallel to DQ12
# and clear of the C6/C8 GND vias; J1 pad 19 also got boxed in otherwise.
PREROUTES = [
    ("F4", "In2.Cu", 0.127, [(-4.55, -0.75), (-6.2, -0.75), (-6.2, 2.35), (-8.85, 5.0), (-20.0, 5.0)]),
    ("F7", "F.Cu", 0.127, [(-0.75, 5.05), (-0.75, 11.1), (0.1, 11.95)]),
    ("F7", "B.Cu", 0.2, [(0.1, 11.95), (0.6, 12.45), (0.6, 13.1)]),
    ("B1", "F.Cu", 0.127, [(2.75, -4.15), (7.45, -8.85), (19.85, -8.85), (20.0, -9.0)]),
    ("F5", "In2.Cu", 0.127, [(-4.55, 0.25), (-4.55, 2.66), (-8.89, 7.0), (-20.0, 7.0)]),
]

# Vias joining pre-route segments on different layers (BOARD frame).
PREROUTE_VIAS = [
    ("F7", (0.1, 11.95)),       # WAIT: F.Cu -> B.Cu at R2
]
