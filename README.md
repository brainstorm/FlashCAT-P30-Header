# FlashCAT P30 Easy BGA-64 adapter

A [FlashcatUSB](https://www.embeddedcomputers.net/products/ParallelAdapters/)
(Mach1 / XPORT) parallel adapter for reading and writing **Intel / Micron
StrataFlash P30** NOR flash in the **64-ball Easy BGA** package (e.g.
`PC28F256P30T85`), using a Sensata CBG064-087G burn-in socket. Designed in
KiCad 10; rev B.

| Top | Bottom |
|---|---|
| ![Top, perspective](hardware/renders/board_top_3d.png) | ![Bottom, perspective](hardware/renders/board_bottom_3d.png) |

* 4-layer, 51 × 37 mm, plugs into the Embedded Computers 56-pin dual header
* 1.8 V LDO for the P30 core (as in EC's own P30 TSOP-56 adapter), I/O and VPP
  from the programmer's VCC
* A1…A27 wired: every P30 density from 64 Mbit to 512 Mbit, plus Micron
  P30-65nm 1 Gbit / 2 Gbit (A26/A27 on the balls that are RFU on older parts)
* all SMD parts on the bottom, decoupling right at the socket power balls
* ERC / DRC / schematic-parity clean; gerbers, drill, BOM and pick-and-place
  in [`hardware/fab`](hardware/fab)

Full design notes, BOM and checks before ordering:
**[hardware/README.md](hardware/README.md)**
