#!/usr/bin/env python3
"""Generate flashcat_p30.kicad_sch from design.py + gen_libs symbols."""
import os
import uuid

import design as D
import gen_libs as L

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = "flashcat_p30"
OUT = os.path.join(HERE, "..", f"{PROJ}.kicad_sch")

NS = uuid.UUID("5b0f2d8e-8c1f-4f59-9a55-7f3c3c0b1a30")


def uid(*parts):
    """Deterministic UUIDs so regenerating keeps schematic<->PCB links stable."""
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


ROOT = uid("root")
SYMS = L.all_symbols()
q, fnum = L.q, L.fnum
G = 1.27  # grid


def snap(v):
    return round(round(v / G) * G, 4)


class Sch:
    def __init__(self):
        self.items = []
        self.pwr_n = 0
        self.flg_n = 0

    # -- primitives ---------------------------------------------------------
    def wire(self, a, b):
        self.items.append(
            f"\t(wire\n\t\t(pts\n\t\t\t(xy {fnum(a[0])} {fnum(a[1])}) (xy {fnum(b[0])} {fnum(b[1])})\n\t\t)\n"
            f"\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid {q(uid('w', a, b))})\n\t)\n")

    def label(self, name, p, direction):
        """direction: outward unit vector of the stub the label sits on."""
        dx, dy = direction
        if dx < 0:
            ang, just = 180, "right bottom"
        elif dx > 0:
            ang, just = 0, "left bottom"
        elif dy < 0:
            ang, just = 90, "left bottom"
        else:
            ang, just = 270, "right bottom"
        self.items.append(
            f"\t(label {q(name)}\n\t\t(at {fnum(p[0])} {fnum(p[1])} {ang})\n"
            f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify {just})\n\t\t)\n"
            f"\t\t(uuid {q(uid('l', name, p))})\n\t)\n")

    def junction(self, p):
        self.items.append(f"\t(junction\n\t\t(at {fnum(p[0])} {fnum(p[1])})\n\t\t(diameter 0)\n"
                          f"\t\t(color 0 0 0 0)\n\t\t(uuid {q(uid('j', p))})\n\t)\n")

    def noconnect(self, p):
        self.items.append(f"\t(no_connect\n\t\t(at {fnum(p[0])} {fnum(p[1])})\n\t\t(uuid {q(uid('nc', p))})\n\t)\n")

    def text(self, s, p, size=1.27):
        self.items.append(
            f"\t(text {q(s).replace(chr(10), chr(92) + 'n')}\n\t\t(exclude_from_sim no)\n\t\t(at {fnum(p[0])} {fnum(p[1])} 0)\n"
            f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size})\n\t\t\t)\n\t\t\t(justify left top)\n\t\t)\n"
            f"\t\t(uuid {q(uid('t', s[:40], p))})\n\t)\n")

    def symbol(self, lib, ref, value, at, rot=0, fields=None, footprint=None, prop_pos=None):
        """Place a symbol; returns {pin_number: (x, y, outward_dir)} in sheet coords."""
        s_uuid = uid("sym", ref)
        body = SYMS[lib]
        fp = footprint if footprint is not None else _prop(body, "Footprint")
        ds = _prop(body, "Datasheet")
        descr = _prop(body, "Description")
        x0, y0 = at
        power = ref.startswith("#")
        rp, vp = prop_pos or ((x0 + 3.81, y0 - 1.27), (x0 + 3.81, y0 + 1.27))
        props = [("Reference", ref, rp, power), ("Value", value, vp, False),
                 ("Footprint", fp, at, True), ("Datasheet", ds, at, True), ("Description", descr, at, True)]
        for k, v in (fields or {}).items():
            props.append((k, v, at, True))
        just = "" if power or lib in ("P30_EasyBGA64_Socket", "EC56_J1", "EC56_J2", "TLV75518PDBV") \
            else "\n\t\t\t\t(justify left)"
        ptxt = ""
        for k, v, p, hide in props:
            h = "\n\t\t\t(hide yes)" if hide else ""
            j = just if k in ("Reference", "Value") else ""
            ptxt += (f"\t\t(property {q(k)} {q(v)}\n\t\t\t(at {fnum(p[0])} {fnum(p[1])} 0){h}\n"
                     f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t){j}\n\t\t\t)\n\t\t)\n")
        pins = _pins(body)
        pin_txt = "".join(f"\t\t(pin {q(n)}\n\t\t\t(uuid {q(uid('pin', ref, n))})\n\t\t)\n" for n in pins)
        self.items.append(
            f"\t(symbol\n\t\t(lib_id {q(L.LIBNAME + ':' + lib)})\n\t\t(at {fnum(x0)} {fnum(y0)} {rot})\n\t\t(unit 1)\n"
            f"\t\t(exclude_from_sim no)\n\t\t(in_bom {'no' if power else 'yes'})\n\t\t(on_board {'no' if power else 'yes'})\n"
            f"\t\t(dnp no)\n\t\t(uuid {q(s_uuid)})\n{ptxt}{pin_txt}"
            f"\t\t(instances\n\t\t\t(project {q(PROJ)}\n\t\t\t\t(path {q('/' + ROOT)}\n"
            f"\t\t\t\t\t(reference {q(ref)})\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n")
        out = {}
        for n, (px, py, ang) in pins.items():
            # lib (+y up) -> sheet (+y down), then rotate (CCW on screen)
            sx, sy = px, -py
            ox, oy = _dir(ang)
            for _ in range(rot // 90):
                sx, sy = sy, -sx
                ox, oy = oy, -ox
            out[n] = (snap(x0 + sx), snap(y0 + sy), (ox, oy))
        return out

    def power(self, net, p, rot=0):
        self.pwr_n += 1
        ref = f"#PWR{self.pwr_n:03d}"
        if net == "GND":
            vp = (p[0], p[1] + 5.08)
        else:
            vp = (p[0], p[1] - 3.81)
        self.symbol(net, ref, net, p, rot, prop_pos=((p[0], p[1]), vp))

    def pwr_flag(self, net, p):
        """PWR_FLAG on a power net, drawn as power symbol + short wire + flag."""
        self.flg_n += 1
        ref = f"#FLG{self.flg_n:02d}"
        if net == "GND":
            self.power("GND", (p[0], p[1] + 2.54))
            self.wire(p, (p[0], p[1] + 2.54))
            self.symbol("PWR_FLAG", ref, "PWR_FLAG", p, prop_pos=((p[0], p[1]), (p[0], p[1] - 3.81)))
        else:
            self.power(net, p)
            self.wire(p, (p[0], p[1] + 2.54))
            self.symbol("PWR_FLAG", ref, "PWR_FLAG", (p[0], p[1] + 2.54), 180,
                        prop_pos=((p[0], p[1]), (p[0], p[1] + 6.35)))

    # -- helpers ------------------------------------------------------------
    def attach(self, pinpos, net, stub=5.08):
        """Stub + label / power symbol / no-connect on a pin."""
        x, y, (dx, dy) = pinpos
        if net is None:
            self.noconnect((x, y))
            return
        e = (snap(x + dx * stub), snap(y + dy * stub))
        self.wire((x, y), e)
        if net in ("GND", "+1V8", "VIO", "VCC_PROG"):
            if net == "GND" and dy < 0:        # GND on an upward stub: turn it
                self.power(net, e, 180)
            elif net != "GND" and dy > 0:      # rail on a downward stub
                self.power(net, e, 180)
            else:
                self.power(net, e)
        else:
            self.label(net, e, (dx, dy))


def attach_group(s, pins, net, stub=2.54, sym_at="first"):
    """Join same-net pins: stubs, a bus wire across their ends, one rail symbol."""
    ends = []
    for x, y, (dx, dy) in pins:
        e = (snap(x + dx * stub), snap(y + dy * stub))
        s.wire((x, y), e)
        ends.append((e, (dx, dy)))
    ends.sort(key=lambda t: (t[0][0], t[0][1]))
    for (a, _), (b, _) in zip(ends, ends[1:]):
        s.wire(a, b)
    for (p, _) in ends[1:-1]:
        s.junction(p)
    p, (dx, dy) = ends[0] if sym_at == "first" else ends[-1]
    if len(ends) > 1:
        s.junction(p) if sym_at == "middle" else None
    if net == "GND":
        s.power(net, p, 180 if dy < 0 else 0)
    elif net is None:
        pass
    else:
        s.power(net, p, 180 if dy > 0 else 0)


def _prop(body, name):
    i = body.index(f"(property {q(name)} ")
    j = body.index('"', i + len(f"(property {q(name)} ") + 1)
    return body[i + len(f"(property {q(name)} ") + 1:j]


def _pins(body):
    import re
    pins = {}
    for m in re.finditer(r"\(pin \w+ \w+\n\t+\(at ([-\d.]+) ([-\d.]+) (\d+)\)(?:.|\n)*?\(number \"([^\"]+)\"", body):
        pins[m.group(4)] = (float(m.group(1)), float(m.group(2)), int(m.group(3)))
    return pins


def _dir(lib_angle):
    """Outward direction (sheet coords) for a pin whose lib angle is given."""
    return {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[lib_angle]


def lib_symbols_block():
    out = "\t(lib_symbols\n"
    for name, body in SYMS.items():
        b = body.replace(f"(symbol {q(name)}", f"(symbol {q(L.LIBNAME + ':' + name)}", 1)
        out += "".join("\t" + ln + "\n" if ln else "\n" for ln in b.rstrip("\n").split("\n"))
    out += "\t)\n"
    return out


RES_MPN = {"10k": "RC0603FR-0710KL", "4k7": "RC0603FR-074K7L"}
CAP_MPN = {"100n": "GRM188R71C104KA01D", "1u": "GRM188R61E105KA12D", "10u": "GRM188R61A106KE69D"}


def build():
    s = Sch()

    # ---- U1: P30 in socket -------------------------------------------------
    u1 = s.symbol("P30_EasyBGA64_Socket", "U1", "PC28F256P30T85", (215.9, 142.24),
                  fields={"Socket": "Sensata CBG064-087G", "MPN": "CBG064-087G",
                          "Manufacturer": "Sensata Technologies"},
                  prop_pos=((198.12, 92.71), (198.12, 196.85)))
    groups = {}
    for ball, pos in u1.items():
        sig = D.P30_BALLS[ball]
        net = D.p30_net(sig)
        side = pos[2]
        if net in ("GND", "+1V8", "VCC_PROG"):
            groups.setdefault((net, side), []).append(pos)
        else:
            s.attach(pos, net)
    for (net, side), pins in sorted(groups.items()):
        # bottom GND: symbol at the far left end; side GND (ADV#/CLK): lower end
        attach_group(s, pins, net, sym_at="last" if side == (1, 0) else "first")

    # ---- J1 / J2: EC 56-pin header ----------------------------------------
    j1 = s.symbol("EC56_J1", "J1", "EC56 J1 (control/data)", (99.06, 99.06),
                  fields={"MPN": "Samtec TMM-114-01-G-D (or any 2x14 2.00 mm male header)"},
                  prop_pos=((88.9, 78.74), (88.9, 119.38)))
    for n, pos in j1.items():
        s.attach(pos, D.ec_net(D.J1_PINS[int(n)]))
    j2 = s.symbol("EC56_J2", "J2", "EC56 J2 (address)", (99.06, 180.34),
                  fields={"MPN": "Samtec TMM-114-01-G-D (or any 2x14 2.00 mm male header)"},
                  prop_pos=((88.9, 160.02), (88.9, 200.66)))
    for n, pos in j2.items():
        s.attach(pos, D.ec_net(D.J2_PINS[int(n)]))

    # ---- U2: 1.8 V core LDO ------------------------------------------------
    u2 = s.symbol("TLV75518PDBV", "U2", "TLV75518PDBV", (322.58, 63.5),
                  fields={"MPN": "TLV75518PDBVR", "Manufacturer": "Texas Instruments"},
                  prop_pos=((322.58, 55.88), (322.58, 76.2)))
    attach_group(s, [u2["1"], u2["3"]], "VCC_PROG")
    s.attach(u2["2"], "GND", stub=2.54)
    s.attach(u2["5"], "+1V8")
    s.attach(u2["4"], None)

    def two_pin(kind, ref, value, at, top, bot):
        p = s.symbol(kind, ref, value, at,
                     fields={"MPN": CAP_MPN[value] if kind == "C" else RES_MPN[value]})
        s.attach(p["1"], top, stub=2.54)
        s.attach(p["2"], bot, stub=2.54)

    # LDO in/out caps and bulk
    two_pin("C", "C1", "1u", (297.18, 88.9), "VCC_PROG", "GND")
    two_pin("C", "C2", "1u", (345.44, 88.9), "+1V8", "GND")
    two_pin("C", "C3", "10u", (358.14, 88.9), "VCC_PROG", "GND")
    # socket decoupling: +1V8 at A6/H3 (VCC); VCC_PROG at A4 (VPP) and VCCQ D5/D6/G4
    two_pin("C", "C5", "100n", (297.18, 124.46), "+1V8", "GND")
    two_pin("C", "C6", "100n", (309.88, 124.46), "+1V8", "GND")
    two_pin("C", "C4", "10u", (335.28, 124.46), "VCC_PROG", "GND")
    two_pin("C", "C7", "100n", (347.98, 124.46), "VCC_PROG", "GND")
    two_pin("C", "C8", "100n", (360.68, 124.46), "VCC_PROG", "GND")
    # control pull-ups to header VCC + power-on reset RC on RST#
    two_pin("R", "R1", "10k", (297.18, 165.1), "VCC_PROG", "~{RST}")
    two_pin("C", "C9", "100n", (297.18, 185.42), "~{RST}", "GND")
    # WAIT -> header RB0, pulled up like the EC TSOP-56 Type-D adapter
    two_pin("R", "R2", "4k7", (322.58, 165.1), "VCC_PROG", "WAIT")

    # power flags (rails enter through the EC header / LDO)
    s.pwr_flag("VCC_PROG", (360.68, 38.1))
    s.pwr_flag("GND", (391.16, 38.1))

    # ---- notes ---------------------------------------------------------------
    s.text("FlashCAT (FlashcatUSB Mach1 / XPORT) adapter for Intel/Micron P30 StrataFlash in 64-ball Easy BGA\n"
           "(e.g. PC28F256P30T85 / RC28F256P30T85), using a Sensata CBG064-087G BGA socket.", (25.4, 22.86), 2.0)
    s.text("NOTES\n"
           "1. Ball names follow the P30 datasheet (row letter A-H along the 13 mm side, column number 1-8).\n"
           "   Pads of the socket footprint carry the same names; mapping remapped from the S29 footprint\n"
           "   supplied by Embedded Computers.\n"
           "2. x16 WORD addressing: FlashcatUSB drives header A1..A27 in x16 mode, so P30 A1 (LSB) -> header A1.\n"
           "   Header A0 is unused. A25 is used by 512 Mbit parts; B8 = A26 (1 Gbit) and H1 = A27 (2 Gbit)\n"
           "   only exist on Micron P30-65nm (RFU on 130 nm parts), wired as EC's TSOP-56 Type-D does.\n"
           "3. P30 VCC (core) is 1.7-2.0 V, ABS MAX 2.5 V. U2 makes 1.8 V from the programmer VCC:\n"
           "   programmer at 3.3 V -> regulated 1.8 V; programmer at 1.8 V -> U2 in dropout, ~1.78 V.\n"
           "   VCCQ (I/O, 1.7-3.6 V) is fed from header VCC, header VIO is unused (same as the EC P30\n"
           "   TSOP-56 Type-D adapter). VPP (VPPL 0.9-3.6 V) is tied to header VCC; U2 feeds VCC only.\n"
           "4. ADV# and CLK tied to GND (asynchronous mode). WAIT -> header RB0 with 4.7k pull-up. RFU open.\n"
           "5. RST#, WP# are not on the EC header. WP# is tied to header VCC (lock-down off, as the EC\n"
           "   TSOP-56 Type-D adapter); RST# is pulled up to header VCC with a ~1 ms power-on delay.\n"
           "   CE#, OE#, WE# are driven directly by the programmer (no pull-ups, as the EC adapters).\n"
           "6. Unused EC header pins (VPP, VIO, CLE, ALE, RE/B#, DQS, A0) are left open.",
           (25.4, 228.6), 1.524)
    return s


def write():
    s = build()
    out = (f"(kicad_sch\n\t(version 20250114)\n\t(generator \"eeschema\")\n\t(generator_version \"9.0\")\n"
           f"\t(uuid {q(ROOT)})\n\t(paper \"A3\")\n"
           f"\t(title_block\n\t\t(title \"FlashCAT P30 Easy BGA-64 adapter\")\n\t\t(date \"2026-09-27\")\n"
           f"\t\t(rev \"B\")\n\t\t(company \"brainstorm@nopcode.org\")\n"
           f"\t\t(comment 1 \"Socket: Sensata CBG064-087G. Target: Intel/Micron StrataFlash P30 (Easy BGA-64)\")\n"
           f"\t\t(comment 2 \"Plugs into the Embedded Computers 56-pin dual header (FlashcatUSB Mach1 / XPORT)\")\n"
           f"\t)\n")
    out += lib_symbols_block()
    out += "".join(s.items)
    out += "\t(sheet_instances\n\t\t(path \"/\"\n\t\t\t(page \"1\")\n\t\t)\n\t)\n\t(embedded_fonts no)\n)\n"
    with open(OUT, "w") as f:
        f.write(out)
    print("wrote", os.path.normpath(OUT))


if __name__ == "__main__":
    write()
