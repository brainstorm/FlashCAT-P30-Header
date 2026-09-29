#!/usr/bin/env python3
"""Produce manufacturing outputs in hardware/fab/ using kicad-cli.

  fab/gerbers/            Gerber X2 + Excellon (PTH/NPTH split) + drill map
  fab/flashcat_p30-gerbers.zip
  fab/assembly/bom.csv            grouped BOM (all fields)
  fab/assembly/bom_jlc.csv        JLCPCB-style BOM (Comment,Designator,Footprint,MPN)
  fab/assembly/cpl_jlc.csv        JLCPCB-style pick & place (top side SMD)
  fab/assembly/positions.csv      KiCad position file (all parts, both sides)
  fab/docs/schematic.pdf, fab/docs/pcb_layers.pdf
"""
import csv
import os
import shutil
import subprocess
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.normpath(os.path.join(HERE, ".."))
SCH = os.path.join(PRJ, "flashcat_p30.kicad_sch")
PCB = os.path.join(PRJ, "flashcat_p30.kicad_pcb")
FAB = os.path.join(PRJ, "fab")


def run(*args):
    subprocess.run(["kicad-cli", *args], check=True, stdout=subprocess.DEVNULL)


def main():
    if os.path.isdir(FAB):
        shutil.rmtree(FAB)
    g = os.path.join(FAB, "gerbers")
    a = os.path.join(FAB, "assembly")
    d = os.path.join(FAB, "docs")
    for p in (g, a, d):
        os.makedirs(p)

    layers = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    run("pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask", "-o", g + "/", PCB)
    run("pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
        "--excellon-units", "mm", "--generate-map", "--map-format", "gerberx2", "-o", g + "/", PCB)
    zpath = os.path.join(FAB, "flashcat_p30-gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(g)):
            z.write(os.path.join(g, f), f)

    # BOM
    bom = os.path.join(a, "bom.csv")
    run("sch", "export", "bom", "--fields", "Reference,Value,Footprint,MPN,Manufacturer,${QUANTITY}",
        "--labels", "Reference,Value,Footprint,MPN,Manufacturer,Qty",
        "--group-by", "Value,Footprint,MPN", "--ref-range-delimiter", "", "-o", bom, SCH)
    with open(bom) as f, open(os.path.join(a, "bom_jlc.csv"), "w", newline="") as o:
        w = csv.writer(o)
        w.writerow(["Comment", "Designator", "Footprint", "Manufacturer Part", "Qty"])
        for r in csv.DictReader(f):
            # U1 is the socket (the P30 itself is the part being programmed)
            comment = "BGA-64 socket Sensata CBG064-087G" if r["Reference"] == "U1" else r["Value"]
            w.writerow([comment, r["Reference"], r["Footprint"].split(":")[-1], r["MPN"], r["Qty"]])

    # placement
    pos = os.path.join(a, "positions.csv")
    run("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
        "--use-drill-file-origin", "-o", pos, PCB)
    with open(pos) as f, open(os.path.join(a, "cpl_jlc.csv"), "w", newline="") as o:
        w = csv.writer(o)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in csv.DictReader(f):
            if r["Ref"][0] in "CRU" and r["Ref"] != "U1":   # SMD parts only (U1/J* are THT)
                w.writerow([r["Ref"], r["PosX"] + "mm", r["PosY"] + "mm",
                            "Top" if r["Side"] == "top" else "Bottom", r["Rot"]])

    # docs
    run("sch", "export", "pdf", "-o", os.path.join(d, "schematic.pdf"), SCH)
    run("pcb", "export", "pdf", "--mode-separate", "--include-border-title",
        "-l", "F.Cu,In1.Cu,In2.Cu,B.Cu,F.SilkS,B.SilkS,F.Fab,Edge.Cuts",
        "--common-layers", "Edge.Cuts", "-o", d + "/", PCB)
    print("fab outputs in", FAB)


if __name__ == "__main__":
    main()
