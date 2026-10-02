#!/usr/bin/env python3
"""Generate the project symbol library and the BGA-64 socket footprint."""
import os

import design as D

HERE = os.path.dirname(os.path.abspath(__file__))
LIBDIR = os.path.join(HERE, "..", "lib")
LIBNAME = "flashcat_p30"


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def fnum(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ---------------------------------------------------------------------------
# Symbols
# ---------------------------------------------------------------------------
def prop(name, value, x=0.0, y=0.0, hide=False, justify=None, angle=0):
    j = f"\n\t\t\t\t(justify {justify})" if justify else ""
    h = "\n\t\t\t(hide yes)" if hide else ""
    return (f'\t\t(property {q(name)} {q(value)}\n\t\t\t(at {fnum(x)} {fnum(y)} {angle}){h}\n'
            f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t){j}\n\t\t\t)\n\t\t)\n')


def pin(etype, x, y, angle, name, number, length=2.54, hide=False, shape="line"):
    h = "\n\t\t\t\t(hide yes)" if hide else ""
    return (f'\t\t\t(pin {etype} {shape}\n\t\t\t\t(at {fnum(x)} {fnum(y)} {angle})\n'
            f'\t\t\t\t(length {fnum(length)}){h}\n'
            f'\t\t\t\t(name {q(name)}\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n'
            f'\t\t\t\t(number {q(str(number))}\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)\n')


def rect(x0, y0, x1, y1, fill="background"):
    return (f'\t\t\t(rectangle\n\t\t\t\t(start {fnum(x0)} {fnum(y0)})\n\t\t\t\t(end {fnum(x1)} {fnum(y1)})\n'
            f'\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n\t\t\t\t)\n'
            f'\t\t\t\t(fill\n\t\t\t\t\t(type {fill})\n\t\t\t\t)\n\t\t\t)\n')


def poly(pts, width=0.0, fill="none"):
    p = " ".join(f"(xy {fnum(x)} {fnum(y)})" for x, y in pts)
    return (f'\t\t\t(polyline\n\t\t\t\t(pts\n\t\t\t\t\t{p}\n\t\t\t\t)\n'
            f'\t\t\t\t(stroke\n\t\t\t\t\t(width {fnum(width)})\n\t\t\t\t\t(type default)\n\t\t\t\t)\n'
            f'\t\t\t\t(fill\n\t\t\t\t\t(type {fill})\n\t\t\t\t)\n\t\t\t)\n')


def symbol(name, props, graphics, pins, power=False, pin_names_offset=1.016,
           hide_pin_numbers=False, hide_pin_names=False, in_bom=True, on_board=True):
    out = f"\t(symbol {q(name)}\n"
    if power:
        out += "\t\t(power)\n"
    pn = []
    if hide_pin_numbers:
        out += "\t\t(pin_numbers\n\t\t\t(hide yes)\n\t\t)\n"
    out += f"\t\t(pin_names\n\t\t\t(offset {fnum(pin_names_offset)})"
    if hide_pin_names:
        out += "\n\t\t\t(hide yes)"
    out += "\n\t\t)\n"
    out += "\t\t(exclude_from_sim no)\n"
    out += f"\t\t(in_bom {'yes' if in_bom else 'no'})\n\t\t(on_board {'yes' if on_board else 'no'})\n"
    out += "".join(props)
    out += f'\t\t(symbol {q(name + "_0_1")}\n' + "".join(graphics) + "\t\t)\n"
    out += f'\t\t(symbol {q(name + "_1_1")}\n' + "".join(pins) + "\t\t)\n"
    out += "\t\t(embedded_fonts no)\n\t)\n"
    return out


def std_props(ref, value, footprint, datasheet, descr, ref_xy, val_xy, extra=None,
              ref_just=None, val_just=None):
    p = [prop("Reference", ref, *ref_xy, justify=ref_just),
         prop("Value", value, *val_xy, justify=val_just),
         prop("Footprint", footprint, hide=True),
         prop("Datasheet", datasheet, hide=True),
         prop("Description", descr, hide=True)]
    for k, v in (extra or {}).items():
        p.append(prop(k, v, hide=True))
    return p


def pin_etype(sig):
    if sig in ("VCC", "VCCQ", "VPP", "VSS"):
        return "power_in"
    if sig == "RFU":
        return "no_connect"
    if sig.startswith("DQ"):
        return "bidirectional"
    if sig == "WAIT":
        return "output"
    return "input"


def pin_label(sig):
    return {"CE#": "~{CE}", "OE#": "~{OE}", "WE#": "~{WE}", "RST#": "~{RST}",
            "WP#": "~{WP}", "ADV#": "~{ADV}"}.get(sig, sig)


# P30 symbol pin placement (lib coords, +y up).  Returns {ball: (x, y, angle)}.
P30_HALF_W = 15.24
P30_PIN_LEN = 2.54
P30_HALF_H = 38.1


def p30_layout():
    by_sig = {}
    for ball, sig in D.P30_BALLS.items():
        by_sig.setdefault(sig, []).append(ball)
    lay = {}
    top = 30.48
    # left: A1..A27
    for i in range(1, 28):
        (ball,) = by_sig[f"A{i}"]
        lay[ball] = (-P30_HALF_W - P30_PIN_LEN, top - (i - 1) * 2.54, 0)
    # right: DQ0..DQ15, gap, controls
    right = [f"DQ{i}" for i in range(16)] + [None] + ["CE#", "OE#", "WE#", "RST#", "WP#", "ADV#", "CLK", "WAIT"]
    for i, sig in enumerate(right):
        if sig is None:
            continue
        (ball,) = by_sig[sig]
        lay[ball] = (P30_HALF_W + P30_PIN_LEN, top - i * 2.54, 180)
    # top: power
    tops = sorted(by_sig["VCC"]) + by_sig["VPP"] + sorted(by_sig["VCCQ"])
    for i, ball in enumerate(tops):
        lay[ball] = (-7.62 + i * 2.54 + (2.54 if i >= 3 else 0), P30_HALF_H + P30_PIN_LEN, 270)
    # bottom: VSS + RFU
    bots = sorted(by_sig["VSS"]) + sorted(by_sig["RFU"])
    for i, ball in enumerate(bots):
        lay[ball] = (-12.7 + i * 2.54 + (2.54 if i >= 4 else 0), -P30_HALF_H - P30_PIN_LEN, 90)
    assert len(lay) == 64
    return lay


def sym_p30():
    lay = p30_layout()
    pins = [pin(pin_etype(D.P30_BALLS[b]), x, y, a, pin_label(D.P30_BALLS[b]), b)
            for b, (x, y, a) in sorted(lay.items())]
    g = [rect(-P30_HALF_W, P30_HALF_H, P30_HALF_W, -P30_HALF_H)]
    props = std_props(
        "U", "PC28F256P30T85", f"{LIBNAME}:HMILU_BGA64-1.0-TP21NS",
        "https://www.dataman.com/media/datasheet/Intel/P30Family.pdf",
        "Intel/Micron StrataFlash P30 parallel NOR, 64-ball Easy BGA (10x13 mm, 1.0 mm pitch), fitted in an HMILU BGA64-1.0-TP21NS socket",
        (-P30_HALF_W, P30_HALF_H + 3.81), (-P30_HALF_W, -P30_HALF_H - 5.08),
        {"Socket": "HMILU BGA64-1.0-TP21NS (64 pin, 1.0 mm pitch, 10x13 mm)",
         "MPN": "BGA64-1.0-TP21NS", "Manufacturer": "HMILU"},
        ref_just="left bottom", val_just="left top")
    return symbol("P30_EasyBGA64_Socket", props, g, pins)


def sym_header(name, pins_map, value):
    """2x14 header drawn as two columns in TOP VIEW order (left col, right col)."""
    pins = []
    for num, sig in pins_map.items():
        r = (num - 1) // 2
        odd = num % 2 == 1          # odd pads = right column (see design.header_pins)
        y = 16.51 - r * 2.54
        if odd:
            pins.append(pin("passive", 12.7, y, 180, sig, num))
        else:
            pins.append(pin("passive", -12.7, y, 0, sig, num))
    g = [rect(-10.16, 19.05, 10.16, -19.05)]
    props = std_props("J", value, "Connector_PinHeader_2.00mm:PinHeader_2x14_P2.00mm_Vertical",
                      "https://www.embeddedcomputers.net/products/ParallelAdapters/",
                      "Embedded Computers 56-pin parallel adapter header (half), 2x14 2.00 mm, top view pin arrangement",
                      (-10.16, 20.32), (-10.16, -20.32),
                      {"MPN": "2x14 male header, 2.00 mm pitch (e.g. Samtec TMM-114-01-G-D)"},
                      ref_just="left bottom", val_just="left top")
    return symbol(name, props, g, pins, pin_names_offset=0.762)


def sym_ldo():
    pins = [pin("power_in", -7.62, 2.54, 0, "IN", 1),
            pin("input", -7.62, 0, 0, "EN", 3),
            pin("power_in", 0, -7.62, 90, "GND", 2),
            pin("power_out", 7.62, 2.54, 180, "OUT", 5),
            pin("no_connect", 7.62, 0, 180, "NC", 4)]
    g = [rect(-5.08, 5.08, 5.08, -5.08)]
    props = std_props("U", "TLV75518PDBV", "Package_TO_SOT_SMD:SOT-23-5",
                      "https://www.ti.com/lit/ds/symlink/tlv755p.pdf",
                      "500 mA LDO, fixed 1.8 V, 1.45-5.5 V input, SOT-23-5",
                      (0, 6.35), (0, -10.16),
                      {"MPN": "TLV75518PDBVR", "Manufacturer": "Texas Instruments"})
    return symbol("TLV75518PDBV", props, g, pins)


def sym_2pin(name, ref, value, fp, descr, graphics, extra):
    pins = [pin("passive", 0, 3.81, 270, "~", 1, length=1.27),
            pin("passive", 0, -3.81, 90, "~", 2, length=1.27)]
    props = std_props(ref, value, fp, "", descr, (2.54, 1.27), (2.54, -1.27), extra,
                      ref_just="left", val_just="left")
    return symbol(name, props, graphics, pins, hide_pin_numbers=True, hide_pin_names=True,
                  pin_names_offset=0)


def sym_R():
    g = [rect(-1.016, 2.54, 1.016, -2.54, fill="none")]
    return sym_2pin("R", "R", "10k", "Resistor_SMD:R_0603_1608Metric", "Resistor", g,
                    {"MPN": "RC0603FR-0710KL"})


def sym_C():
    g = [poly([(-2.032, 0.762), (2.032, 0.762)], 0.508), poly([(-2.032, -0.762), (2.032, -0.762)], 0.508),
         poly([(0, 2.54), (0, 0.762)]), poly([(0, -2.54), (0, -0.762)])]
    return sym_2pin("C", "C", "100n", "Capacitor_SMD:C_0603_1608Metric", "Unpolarized capacitor", g,
                    {"MPN": ""})


def sym_power(name, is_gnd=False, flag=False):
    if flag:
        g = [poly([(0, 0), (0, 1.27), (-1.016, 1.905), (0, 2.54), (1.016, 1.905), (0, 1.27)])]
        pins = [pin("power_out", 0, 0, 90, "pwr", 1, length=0, hide=True)]
        props = [prop("Reference", "#FLG", 0, 1.905, hide=True), prop("Value", "PWR_FLAG", 0, 3.81),
                 prop("Footprint", "", hide=True), prop("Datasheet", "", hide=True),
                 prop("Description", "Special symbol for telling ERC where power comes from", hide=True)]
        return symbol("PWR_FLAG", props, g, pins, power=True, pin_names_offset=0,
                      hide_pin_numbers=True, hide_pin_names=True, in_bom=False, on_board=False)
    if is_gnd:
        g = [poly([(0, 0), (0, -1.27), (1.27, -1.27), (0, -2.54), (-1.27, -1.27), (0, -1.27)])]
        props = [prop("Reference", "#PWR", 0, -6.35, hide=True), prop("Value", name, 0, -3.81)]
        ang = 270
    else:
        g = [poly([(-0.762, 1.27), (0, 2.54)]), poly([(0, 2.54), (0.762, 1.27)]), poly([(0, 0), (0, 2.54)])]
        props = [prop("Reference", "#PWR", 0, -3.81, hide=True), prop("Value", name, 0, 3.556)]
        ang = 90
    props += [prop("Footprint", "", hide=True), prop("Datasheet", "", hide=True),
              prop("Description", f'Power symbol creates a global label with name "{name}"', hide=True)]
    pins = [pin("power_in", 0, 0, ang, name, 1, length=0, hide=True)]
    return symbol(name, props, g, pins, power=True, pin_names_offset=0,
                  hide_pin_numbers=True, hide_pin_names=True, in_bom=False, on_board=False)


def all_symbols():
    return {
        "P30_EasyBGA64_Socket": sym_p30(),
        "EC56_J1": sym_header("EC56_J1", D.J1_PINS, "EC56 J1 (control/data)"),
        "EC56_J2": sym_header("EC56_J2", D.J2_PINS, "EC56 J2 (address)"),
        "TLV75518PDBV": sym_ldo(),
        "R": sym_R(),
        "C": sym_C(),
        "GND": sym_power("GND", is_gnd=True),
        "+1V8": sym_power("+1V8"),
        "VIO": sym_power("VIO"),
        "VCC_PROG": sym_power("VCC_PROG"),
        "PWR_FLAG": sym_power("PWR_FLAG", flag=True),
    }


def write_symbol_lib():
    out = "(kicad_symbol_lib\n\t(version 20241209)\n\t(generator \"flashcat_p30_gen\")\n\t(generator_version \"1.0\")\n"
    out += "".join(all_symbols().values())
    out += ")\n"
    with open(os.path.join(LIBDIR, f"{LIBNAME}.kicad_sym"), "w") as f:
        f.write(out)


# ---------------------------------------------------------------------------
# Footprint: HMILU BGA64-1.0-TP21NS socket, P30 Easy BGA ball names
# ---------------------------------------------------------------------------
FP_NAME = "HMILU_BGA64-1.0-TP21NS"
SCREW_CLEAR = 4.6     # bottom-side keep-out around the fixing holes (screw head / nut)
LOCATOR_CLEAR = 2.6   # bottom-side keep-out around the locator pin tips (3.4 mm long pins)


def fp_line(x0, y0, x1, y1, layer, w):
    return (f'\t(fp_line\n\t\t(start {fnum(x0)} {fnum(y0)})\n\t\t(end {fnum(x1)} {fnum(y1)})\n'
            f'\t\t(stroke\n\t\t\t(width {fnum(w)})\n\t\t\t(type solid)\n\t\t)\n\t\t(layer {q(layer)})\n\t)\n')


def fp_rect(x0, y0, x1, y1, layer, w, fill=False):
    return (f'\t(fp_rect\n\t\t(start {fnum(x0)} {fnum(y0)})\n\t\t(end {fnum(x1)} {fnum(y1)})\n'
            f'\t\t(stroke\n\t\t\t(width {fnum(w)})\n\t\t\t(type solid)\n\t\t)\n'
            f'\t\t(fill {"yes" if fill else "no"})\n\t\t(layer {q(layer)})\n\t)\n')


def fp_circle(cx, cy, r, layer, w, fill=False):
    return (f'\t(fp_circle\n\t\t(center {fnum(cx)} {fnum(cy)})\n\t\t(end {fnum(cx + r)} {fnum(cy)})\n'
            f'\t\t(stroke\n\t\t\t(width {fnum(w)})\n\t\t\t(type solid)\n\t\t)\n'
            f'\t\t(fill {"yes" if fill else "no"})\n\t\t(layer {q(layer)})\n\t)\n')


def fp_text(kind, text, x, y, layer, size=1.0, thick=0.15, hide=False, justify=None):
    h = "\n\t\t(hide yes)" if hide else ""
    j = f"\n\t\t\t(justify {justify})" if justify else ""
    if kind in ("Reference", "Value"):
        return (f'\t(property {q(kind)} {q(text)}\n\t\t(at {fnum(x)} {fnum(y)} 0)\n\t\t(layer {q(layer)}){h}\n'
                f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {fnum(size)} {fnum(size)})\n\t\t\t\t(thickness {fnum(thick)})\n\t\t\t){j}\n\t\t)\n\t)\n')
    return (f'\t(fp_text user {q(text)}\n\t\t(at {fnum(x)} {fnum(y)} 0)\n\t\t(layer {q(layer)})\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {fnum(size)} {fnum(size)})\n\t\t\t\t(thickness {fnum(thick)})\n\t\t\t){j}\n\t\t)\n\t)\n')


def write_socket_footprint():
    bw, bh = D.SOCKET_BODY
    hx, hy = bw / 2, bh / 2
    out = f'(footprint "{FP_NAME}"\n\t(version 20241229)\n\t(generator "flashcat_p30_gen")\n\t(generator_version "1.0")\n\t(layer "F.Cu")\n'
    out += ('\t(descr "HMILU BGA64-1.0-TP21NS open-top BGA-64 socket, 8x8 1.0 mm pitch, for 10x13 mm packages '
            '(Intel/Micron P30 Easy BGA). Solderless double-sided spring contacts on 64 x dia 0.55 solid pads '
            '(no paste; vias in pads must be filled and capped). Pads named with P30 Easy BGA ball names. '
            'Pattern per HMILU drawing 007-BGA-1.0-64-10X13-B-01 rev A")\n')
    out += '\t(tags "BGA-64 socket HMILU TP21NS P30 Easy BGA 10x13")\n'
    out += fp_text("Reference", "REF**", 0, -hy - 1.2, "F.Fab")
    out += fp_text("Value", FP_NAME, 0, hy + 1.2, "F.Fab")
    out += '\t(attr smd exclude_from_pos_files)\n'
    # body outline (socket sits flat on the board: no silk inside it)
    out += fp_rect(-hx, -hy, hx, hy, "F.Fab", 0.1)
    out += fp_rect(-hx - 0.12, -hy - 0.12, hx + 0.12, hy + 0.12, "F.SilkS", 0.12)
    out += fp_rect(-hx - 0.5, -hy - 0.5, hx + 0.5, hy + 0.5, "F.CrtYd", 0.05)
    # IC (13 x 10, centred on the ball grid) on Fab
    gx, gy = D.GRID_X0 + 3.5, D.GRID_Y0 - 3.5
    out += fp_rect(gx - 6.5, gy - 5.0, gx + 6.5, gy + 5.0, "F.Fab", 0.1)
    # pin A1: silk triangle outside the body at the A1 corner, dot on Fab
    ax, ay = D.socket_pad_xy("A1")
    out += fp_circle(ax - 0.9, ay + 0.9, 0.2, "F.Fab", 0.1, fill=True)
    out += (f'\t(fp_poly\n\t\t(pts\n\t\t\t(xy {fnum(-hx - 0.4)} {fnum(hy + 0.4)}) (xy {fnum(-hx - 0.4)} {fnum(hy - 1.6)}) (xy {fnum(-hx + 1.6)} {fnum(hy + 0.4)})\n'
            f'\t\t)\n\t\t(stroke\n\t\t\t(width 0.12)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill yes)\n\t\t(layer "F.SilkS")\n\t)\n')
    out += fp_text("user", "A1", ax - 1.6, ay + 1.0, "F.Fab", size=0.6, thick=0.1)
    # row/column letters on Fab
    for L in D.ROW_LETTERS:
        x, _ = D.socket_pad_xy(f"{L}1")
        out += fp_text("user", L, x, D.GRID_Y0 - 8.0, "F.Fab", size=0.5, thick=0.08)
    for n in range(1, 9):
        _, y = D.socket_pad_xy(f"A{n}")
        out += fp_text("user", str(n), D.GRID_X0 - 1.0, y, "F.Fab", size=0.5, thick=0.08)
    out += fp_text("user", "${REFERENCE}", 0, -hy + 2.0, "F.Fab", size=1.0, thick=0.15)
    # bottom side: keep parts clear of the screw heads and locator pin tips
    for x, y in D.SOCKET_FIX_HOLES:
        out += fp_circle(x, y, SCREW_CLEAR / 2, "B.CrtYd", 0.05)
    for x, y, _ in D.SOCKET_LOCATORS:
        out += fp_circle(x, y, LOCATOR_CLEAR / 2, "B.CrtYd", 0.05)
    # contacts: solid SMD pads, mask opening, no paste (solderless contacts)
    for ball in sorted(D.P30_BALLS, key=lambda b: (b[0], int(b[1:]))):
        x, y = D.socket_pad_xy(ball)
        out += (f'\t(pad {q(ball)} smd circle\n\t\t(at {fnum(x)} {fnum(y)})\n\t\t(size {D.SOCKET_PAD} {D.SOCKET_PAD})\n'
                f'\t\t(layers "F.Cu" "F.Mask")\n\t)\n')
    # locator pins and fixing holes (NPTH)
    for x, y, d in D.SOCKET_LOCATORS:
        dd = round(d + 0.025, 3)      # drawing: +0.05/-0
        out += (f'\t(pad "" np_thru_hole circle\n\t\t(at {fnum(x)} {fnum(y)})\n\t\t(size {fnum(dd)} {fnum(dd)})\n'
                f'\t\t(drill {fnum(dd)})\n\t\t(layers "*.Cu" "*.Mask")\n\t)\n')
    for x, y in D.SOCKET_FIX_HOLES:
        out += (f'\t(pad "" np_thru_hole circle\n\t\t(at {fnum(x)} {fnum(y)})\n\t\t(size 2 2)\n'
                f'\t\t(drill 2)\n\t\t(layers "*.Cu" "*.Mask")\n\t)\n')
    out += ('\t(embedded_fonts no)\n'
            f'\t(model "${{KIPRJMOD}}/lib/flashcat_p30.3dshapes/{FP_NAME}.step"\n'
            '\t\t(offset\n\t\t\t(xyz 0 0 0)\n\t\t)\n\t\t(scale\n\t\t\t(xyz 1 1 1)\n\t\t)\n'
            '\t\t(rotate\n\t\t\t(xyz 0 0 0)\n\t\t)\n\t)\n)\n')
    d = os.path.join(LIBDIR, f"{LIBNAME}.pretty")
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    with open(os.path.join(d, f"{FP_NAME}.kicad_mod"), "w") as f:
        f.write(out)


if __name__ == "__main__":
    os.makedirs(LIBDIR, exist_ok=True)
    write_symbol_lib()
    write_socket_footprint()
    print("libs written to", os.path.normpath(LIBDIR))
