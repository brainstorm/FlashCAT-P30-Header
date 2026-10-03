# FlashCAT P30 Easy BGA-64 adapter

KiCad 10 project for a FlashcatUSB (Mach1 / XPORT) parallel adapter that reads
and writes **Intel / Micron StrataFlash P30** parallel NOR in the **64-ball
Easy BGA** package (e.g. `PC28F256P30T85`, `RC28F256P30T85`; the `JS28F…`
parts are TSOP-56 and need the TSOP adapter instead), using an **HMILU
BGA64-1.0-TP21NS** open-top socket made for **10 × 13 mm** BGA-64 parts, as
discussed with Embedded Computers (thread "256P30T", Oct 2020 – Feb 2021).
Rev C; rev B used a Sensata CBG064-087G, whose nest is for 11 × 13 mm parts.

| Top (socket) | Bottom (all SMD parts) |
|---|---|
| ![Top, perspective](renders/board_top_3d.png) | ![Bottom, perspective](renders/board_bottom_3d.png) |
| ![Top](renders/board_top.png) | ![Bottom](renders/board_bottom.png) |

| Side | Decoupling at the socket balls (bottom) |
|---|---|
| ![Side view](renders/board_side.png) | ![Bottom decaps close-up](renders/bottom_decaps_zoom.png) |

![Schematic](renders/schematic.png)

Schematic as PDF: [`fab/docs/schematic.pdf`](fab/docs/schematic.pdf) ·
Gerbers: [`fab/flashcat_p30-gerbers.zip`](fab/flashcat_p30-gerbers.zip)

```
hardware/
  flashcat_p30.kicad_pro / .kicad_sch / .kicad_pcb   the project
  lib/flashcat_p30.kicad_sym                         P30 socket, EC header, LDO, R, C, power symbols
  lib/flashcat_p30.pretty/HMILU_BGA64-1.0-TP21NS     socket footprint, pads named with P30 ball names
  lib/flashcat_p30.3dshapes/HMILU_BGA64-1.0-TP21NS.step  socket 3D model (built from the HMILU drawing)
  fab/                                               gerbers (+zip), drill, BOM, CPL, PDFs
  renders/                                           3D renders, schematic preview, sheet view
  tools/                                             generators + checks (source of truth: design.py)
```

## What the board does

| P30 ball(s) | Signal | Connected to |
|---|---|---|
| A1…A25 | address (A1 = LSB, word address) | EC header **A1…A25** (header A0 unused) |
| B8 / H1 | RFU on 130 nm parts; **A26 / A27** on Micron P30-65nm 1 / 2 Gbit | EC header **A26/RB2 / A27/RB1** |
| DQ0…DQ15 | data | EC header DQ0…DQ15 |
| CE#, OE#, WE# | control | EC header CE0, OE, WE (driven directly, no pull-ups) |
| RST# | reset | 10k to VCC + 100 nF to GND (~1 ms power-on reset) |
| WP# | write protect | tied to header VCC (lock-down disabled) |
| ADV#, CLK | sync-burst inputs | GND (asynchronous mode, per datasheet) |
| WAIT | wait/ready | EC header **RB0**, 4.7k pull-up to VCC |
| RFU (E8, F1, G2) | – | open |
| VCC ×2 | core 1.7–2.0 V | **+1V8** from U2 (TLV75518) – the LDO feeds only these |
| VPP | program/erase supply | header **VCC** (3.3 V) |
| VCCQ ×3 | I/O 1.7–3.6 V | header **VCC** (header VIO unused) |
| VSS ×4 | ground | GND |

Why these choices — cross-checked against the author's own **TSOP-56 Type-D**
adapter ("Supports P30 and P33 Strataflash devices such as 28F256P30",
schematic [`SCM_TSOP56_D.png`](https://www.embeddedcomputers.net/products/ParallelAdapters/SCM_TSOP56_D.png) on the [EC parallel adapters page](https://www.embeddedcomputers.net/products/ParallelAdapters/)):

| | EC TSOP-56 Type-D (P30) | this board |
|---|---|---|
| Core VCC | **MIC5504 1.8 V LDO** from header VCC, 3 × 1 µF | TLV75518 1.8 V LDO (same SOT-23-5 pinout; MIC5504-1.8YM5 is a drop-in) |
| VCCQ | header VCC | header VCC |
| Header VIO | unused | unused |
| WAIT | → RB0, 4.7k pull-up to VCC | same |
| CLK, ADV# | GND | GND |
| WP# | tied to VCC | tied to VCC |
| RST# | tied to VCC | 10k pull-up to VCC + 100 nF (~1 ms power-on reset) |
| TSOP pin 13 / pin 28 | wired to header A27/RB1 and A26/RB2 (see note) | Easy BGA B8 → A26/RB2, H1 → A27/RB1 (same idea) |
| VPP | VCC rail | header VCC |
| CE#, WE# pull-ups | none | none |
| Address | P30 A1 → header A1/CE2 … A25 → A25/RB3 | same, plus A26/A27 |

* **Verified in the Type-D schematic:** header VCC (pin 28) → MIC5504 VIN and
  EN, VOUT (P$5) → C3 1 µF → TSOP pin 33 **VCC**, part marked "1.8V LDO".
  Note: on that drawing TSOP pin 13 is labelled `VCC_A27` and routed to
  header A27/RB1, and pin 28 to header A26/RB2. That matches Micron's
  **P30-65nm** TSOP pinout (512 Mbit–1 Gbit): pin 28 is **A26** there (VSS on
  the 130 nm parts) and pin 13 became RFU (VCC on 130 nm). The Easy BGA
  equivalent is below.
* **Is the LDO needed? Yes.** None of the other EC adapters carry a regulator
  because they are all for 3 V (or 5 V) core parts; the only adapter on the
  page with an LDO is the P30 one, for exactly the reason below. (The other
  small ICs on those schematics are a VPP load switch on DIP-40 and
  push-pull/open-drain MOSFETs on BGA-153, not regulators.)

* **Addressing**: the FlashcatUSB firmware/software drives the header in x16 NOR
  mode as *"Addressing is done A1-A27 (WORD ADDR)"* (`Parallel_NOR_NAND.vb`,
  `E_EXPIO_WRADDR.Parallel_X16`). P30 names its LSB `A1`, so `An` → header
  `An` — the "same pin connection as the TSOP56" the author mentioned.
  A25 is wired so 512 Mbit dual-die P30 parts work too.
* **Micron P30-65nm (1 Gbit / 2 Gbit)** uses the same Easy BGA ballout but
  puts **A26 on ball B8** and **A27 on ball H1** (die select on the 2 Gbit
  dual-die part), balls that are RFU on the 130 nm Intel/Numonyx datasheet.
  Both are wired straight to header A26/RB2 and A27/RB1 so `PC28F00AP30…`
  and `PC28F00BP30…` parts work. On 130 nm parts those balls are unused
  inside the package, so the programmer driving them is expected to be
  harmless (the datasheet asks to treat RFU as do-not-connect, and EC's TSOP
  Type-D adapter makes the same trade-off). Needs FlashcatUSB to know the
  part; 65 nm parts also need ≥ 300 µs from VCC valid to RST# high, which
  the ~1 ms RC covers.
* **Core voltage**: P30 `VCC` is 1.7–2.0 V with an **absolute maximum of 2.5 V**,
  while the header VCC runs at 3.3 V for these adapters (the author's MIC5504
  needs ≥ 2.5 V in, so their design assumes 3.3 V too). Wiring `VCC` straight
  to the header would destroy the chip. U2 (TLV755P, 1.45–5.5 V input) was
  kept over the MIC5504 because it also survives a 1.8 V programmer setting:
  it just drops out and passes ~1.78 V through.
* **VPP** goes to header VCC (3.3 V), like the author's adapter. VPPL is
  0.9–3.6 V, but program/erase timings are specified at the higher end, and
  this keeps the LDO dedicated to the core VCC balls. The header's VPP pin (which can carry 12 V for old EPROMs)
  is deliberately left unconnected.

## Mechanical / geometry

* Board: 51 × 33 mm, 4 layers, 1.6 mm, rounded corners: the same outline as
  Embedded Computers' own adapters (measured from their TSOP-56 Type-D and
  BGA-64 board photos against the 2.00 mm header pitch, ≈ 51 × 33 mm),
  headers along the short edges. The 26 × 30 mm socket body fits inside it.
  Stack: F.Cu signals + GND pour · In1 solid GND plane · In2 signals + VCC
  pour · B.Cu signals + GND pour.
* BGA escape is a fixed, hand-planned fanout (`tools/fanout.py`): rings 1+2 on
  F.Cu, ring 3 on B.Cu, the centre balls on In2 (VCCQ D5 is linked to its
  VCCQ neighbour D6 instead of escaping), one 0.127 mm track per channel;
  each escape exits on the side facing its header (data → J1, address → J2);
  B.Cu channels next to A4/A6/H3/G4 are kept free for the bottom decap traces,
  and a locked B.Cu link joins the two VCCQ cap groups onto one VCC via. Balls
  that leave the top layer (inner escapes, GND balls, decap balls) do so
  through a **0.3/0.5 mm via in the centre of their pad** (23 pads), which
  has to be **resin filled and copper capped** (see fabrication spec); GND
  balls drop straight into the In1 plane that way. D3 (A11) and F4 (DQ11)
  escape sideways towards their header pins, and A2, DQ11, DQ12 and WAIT are
  pre-routed by hand (`design.PREROUTES`): Freerouting otherwise walled
  their header pins in. The rest was autorouted with Freerouting and
  cleaned up (dangling stubs and pad vias it made redundant removed).
* EC 56-pin header: two 2×14, 2.00 mm male headers mounted from the **bottom**
  (plastic spacer between adapter and programmer), left columns 42.00 mm
  apart, positions per [`EC_56P_HEADER.png`](https://www.embeddedcomputers.net/products/ParallelAdapters/EC_56P_HEADER.png). Top-silk "GND" and "A0" mark the
  first pins; all silkscreen reads the same way as the programmer's.
* **Socket:** footprint per the **HMILU drawing 007-BGA-1.0-64-10X13-B-01
  rev A** ("PCB Pattern (TOP View)"), placed exactly as drawn:
  * 64 × Ø0.55 mm **solid SMD pads** for the solderless double-sided spring
    contacts: mask opening, **no solder paste**. The 8×8 grid is offset from
    the socket centre: left column and top row 3.25 mm from the centre lines,
    right column and bottom row 3.75 mm.
  * 4 locator pins, NPTH at (±5.6, ±10.0) mm: Ø1.75 at the A1 corner
    (top-right), Ø1.45 for the other three, which polarises the socket.
    Drilled 1.475 / 1.775 mm (drawing: +0.05/−0).
  * 4 × Ø2.00 mm NPTH fixing holes at (±10.6, ±11.1) mm for the socket screws.
  * Bottom-side courtyards keep parts 2.3 mm clear of the screw holes and
    1.3 mm clear of the locator pin tips (3.4 mm long, ~1.8 mm below the board).
* **Socket orientation:** the IC sits with its 13 mm side along X and pin
  **A1 at the top-right** (silk triangle outside the socket body). Ball
  letters A–H run right → left, numbers 1–8 top → bottom (the datasheet top
  view turned 90° clockwise), so the address-heavy columns (A–D) face the
  address header J2 and the data columns (E–H) face J1.
* No silkscreen inside the socket body on the top side, so the socket base
  sits flat on the solder mask.

## ⚠ Check before ordering

1. **Socket fixing screws.** The drawing gives 4 × Ø2.00 mm fixing holes
   but not the screw. Check the screws that come with your socket and how
   they fasten (into the socket body, or with nuts under the board), and
   widen the holes if they need clearance. Their heads sit on the bottom
   side, inside the courtyards described above.
2. **Header orientation vs. your programmer.** With your working TSOP56
   adapter, check continuity: TSOP56 pin 29 (P30 A1) should go to header pin
   "A1/CE2" (J2, left column, 2nd row), and pin 30 (CE#) to "CE0". This
   confirms both the word-address convention and the top-view pin order used here.
3. **Programmer voltage.** Select the P30 device (28F256P30T) in FlashcatUSB
   and run it the same way as the TSOP-56 Type-D adapter (3.3 V). I/O runs at
   header VCC, like the author's adapter.
4. **Do not use EC's own "BGA-64 EasyBGA (28 series)" adapter for P30.** Its
   published pinout ([`BGA64_EasyBGA_Pinout.png`](https://www.embeddedcomputers.net/products/ParallelAdapters/BGA64_EasyBGA_Pinout.png)) is the J3-style ballout
   (VPEN, STS, BYTE#, CE0–CE2, RP#): it powers the core from 3 V, leaves
   P30's ADV#/CLK/VCCQ(D5, D6) balls on RFU pins, and would over-voltage a P30
   core. That is why this custom board is needed.
5. **Clearance under the board.** The bottom carries the two headers plus all
   SMD parts (0603 and a SOT-23-5, ≤ 1.45 mm tall), the socket screw heads and
   the locator pin tips (~1.8 mm), inside the header spacer height; check
   nothing tall on the programmer sits under the middle of the adapter.
6. **512 Mbit parts are 1.30 mm tall** (1.20 mm for smaller densities); the
   socket drawing shows a 1.2 mm IC. Check the cover still clamps a 512 Mbit
   part properly.

## Bill of materials

| Ref | Qty | Part | Notes |
|---|---|---|---|
| U1 | 1 | HMILU **BGA64-1.0-TP21NS** BGA-64 1.0 mm socket, 10 × 13 mm | solderless: screwed onto the board after assembly; not in the CPL. 3D model in `lib/flashcat_p30.3dshapes/` |
| J1, J2 | 2 | 2×14 male header, **2.00 mm** pitch (e.g. Samtec TMM-114-01-G-D) | mount on bottom |
| U2 | 1 | TI **TLV75518PDBVR** (SOT-23-5) | 1.8 V LDO, 1.45 V min input; alt. Microchip MIC5504-1.8YM5 (same pinout, needs ≥ 2.5 V in) |
| C1, C2 | 2 | 1 µF 25 V X5R 0603 (GRM188R61E105KA12D) | LDO in / out, either side of U2 |
| C3 | 1 | 10 µF 10 V X5R 0603 (GRM188R61A106KE69D) | **bottom**, at ball A4 (VPP, header VCC) |
| C5, C6 | 2 | 100 nF 16 V X7R 0603 (GRM188R71C104KA01D) | **bottom**, at balls A6 / H3 (VCC, +1V8) |
| C4, C7 | 2 | 10 µF + 100 nF 0603 | **bottom**, at balls D5/D6 (VCCQ) |
| C8 | 1 | 100 nF 0603 | **bottom**, at ball G4 (VCCQ) |
| C9 | 1 | 100 nF 0603 | RST# power-on RC |
| R1 | 1 | 10 kΩ 1 % 0603 (RC0603FR-0710KL) | RST# pull-up (with C9: power-on reset) |
| R2 | 1 | 4.7 kΩ 1 % 0603 (RC0603FR-074K7L) | WAIT → RB0 pull-up |

**All SMD parts are on the bottom side** (single-sided SMD assembly; the top
carries only the socket). The socket decoupling caps (C3–C8) sit 1–2 mm
from their VCC/VCCQ/VPP balls, each with its own short trace from the ball
and its own GND via into the In1 plane; the LDO (U2) with C1/C2, the
WAIT pull-up and the RST# RC sit in the strips above/below the socket. Reflow
the bottom, hand-solder the headers, then screw the socket on (no solder on
its pads). `fab/assembly/`
has a generic BOM plus JLCPCB-style `bom_jlc.csv` / `cpl_jlc.csv`; placement
coordinates are relative to the socket centre (board aux origin). Add LCSC
part numbers for your assembler before ordering. Check CPL rotations in the
assembler's preview.

## Fabrication spec

4 layers, FR-4 1.6 mm, 1 oz outer copper · min track/space 0.127/0.127 mm (power 0.2–0.25 mm) ·
vias 0.3/0.5 mm · any colour · **ENIG** (flat pads for the spring contacts;
HASL leaves domed pads) · **via-in-pad, resin filled and copper capped**
(JLCPCB "POFV" / epoxy filling + copper capping) for the vias in the socket
pads. Open or tented vias there would leave a hole or dimple under a
contact. The 1.0 mm socket grid leaves exactly one 0.127 mm track per
channel.

## Verification status (rev C)

`tools/verify.py`: ball/header mapping 0 errors · ERC 0 · DRC 0 violations,
0 unconnected (all severities) · schematic ↔ PCB parity 0.

## Regenerating

```
cd hardware/tools
python3 gen_libs.py     # symbols + socket footprint (references the 3D model)
../build/cqenv/bin/python make_socket_3d.py   # socket STEP model (CadQuery, Python 3.12 venv)
python3 gen_pro.py      # project, rules, net classes
python3 gen_sch.py      # schematic
python3 gen_pcb.py      # placement, nets, planes, silk (from schematic netlist)
python3 route.py        # fanout + Freerouting 2.4.1 (Java 25; FR_VERSION=2.1.0 for Java 21)
                        #   + stub trim + pours + fill, retries until 0 unconnected
python3 center.py       # move board to the middle of the A4 sheet, aux/grid origin = socket centre
python3 verify.py       # mapping + ERC + DRC with schematic parity
python3 make_fab.py     # gerbers, drill, BOM, CPL, PDFs
```

`design.py` is the single source of truth for the ballout, header pinout,
socket geometry and nets. Once hand-edited in KiCad, the `.kicad_*` files
become the master copy and the generators should not be re-run.

## 3D model of the socket

No vendor model is published for the BGA64-1.0-TP21NS, so
`tools/make_socket_3d.py` builds a simplified STEP from the HMILU drawing's
top, front-section and isometric views: a base with four corner towers
(3.3 mm slab, towers to 7.5 mm) and the 10 × 13 mm IC holder between them; a
26 × 30 mm cover (10.8–17.5 mm, cover up) with an 18 × 14 mm funnel window,
countersunk corner holes and a skirt in the middle of each side that drops
between the towers (with the guide slot and pin on the 30 mm faces); coil
springs on the towers around the corner screw posts; 64 contact blades down
to the pads and the four locator pins (3.4 mm). Hole, pin and contact
positions come from `design.py`, so they match the footprint exactly;
proportions the drawing does not dimension were measured from it. It is for
fit/clearance checks and renders, not a manufacturer-accurate model.

## References

* Intel StrataFlash Embedded Memory (P30) datasheet, order 306666 –
  [PDF](https://www.dataman.com/media/datasheet/Intel/P30Family.pdf)
* Micron Parallel NOR Flash Embedded Memory (P30-65nm) 512Mb/1Gb/2Gb
  datasheet (Easy BGA ballout with A26/A27) –
  [PDF](https://www.mouser.com/datasheet/2/12/P30_512M_Datasheet-1920645.pdf)
* HMILU BGA64-1.0-TP21NS BGA-64 socket, drawing
  007-BGA-1.0-64-10X13-B-01 rev A (from the socket vendor; not redistributed
  here)
* Embedded Computers FlashcatUSB parallel adapters (EC 56-pin header, TSOP-56
  Type-D P30 adapter) – [embeddedcomputers.net](https://www.embeddedcomputers.net/products/ParallelAdapters/)
