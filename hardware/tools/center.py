#!/usr/bin/env python3
"""Move the finished board to the middle of the A4 drawing sheet.

The generators work around the socket datum at (0, 0), i.e. the sheet's
top-left corner.  This rigid move (idempotent: offset is computed from the
current board centre) puts the board centre at the sheet centre, and sets
the aux (drill/place) and grid origins to the socket datum so exported
coordinates stay relative to the socket centre.
"""
import os

import pcbnew as P

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.normpath(os.path.join(HERE, "..", "flashcat_p30.kicad_pcb"))
SHEET_CENTRE = (297.0 / 2, 210.0 / 2)   # A4 landscape


def main():
    b = P.LoadBoard(PCB)
    tb = b.GetTitleBlock()
    tb.SetTitle("FlashCAT P30 Easy BGA-64 adapter")
    tb.SetRevision("B")
    tb.SetDate("2026-09-27")
    tb.SetCompany("brainstorm@nopcode.org")
    tb.SetComment(0, "Socket: Sensata CBG064-087G. Target: Intel/Micron StrataFlash P30 (Easy BGA-64)")
    tb.SetComment(1, "4 layers 1.6 mm: F.Cu / In1 GND / In2 sig+VCC / B.Cu. Min track/space 0.127 mm, via 0.3/0.5")
    c = b.GetBoardEdgesBoundingBox().GetCenter()
    target = P.VECTOR2I(P.FromMM(SHEET_CENTRE[0]), P.FromMM(SHEET_CENTRE[1]))
    d = P.VECTOR2I(target.x - c.x, target.y - c.y)
    moved = bool(d.x or d.y)
    if moved:
        # the socket datum sits at the board centre (board outline is symmetric about it)
        datum = P.VECTOR2I(b.FindFootprintByReference("U1").GetPosition())
        for fp in b.GetFootprints():
            fp.Move(d)
        for t in b.GetTracks():
            t.Move(d)
        for z in b.Zones():
            z.Move(d)
        for dr in b.GetDrawings():
            dr.Move(d)
        datum = P.VECTOR2I(datum.x + d.x, datum.y + d.y)
        ds = b.GetDesignSettings()
        ds.SetAuxOrigin(datum)
        ds.SetGridOrigin(datum)
        P.ZONE_FILLER(b).Fill(b.Zones())
    P.SaveBoard(PCB, b, True)
    print(f"moved by ({P.ToMM(d.x):.3f}, {P.ToMM(d.y):.3f}) mm; board centre now at sheet centre {SHEET_CENTRE}")


if __name__ == "__main__":
    main()
