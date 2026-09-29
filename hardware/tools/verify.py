#!/usr/bin/env python3
"""Independent checks: ERC, DRC (+schematic parity) and ball/header mapping.

Exit code != 0 if anything is wrong.
"""
import os
import re
import subprocess
import sys

import design as D
from gen_pcb import read_netlist

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.normpath(os.path.join(HERE, ".."))
BUILD = os.path.join(PRJ, "build")


def kicad(*args):
    r = subprocess.run(["kicad-cli", *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    ok = True
    os.makedirs(BUILD, exist_ok=True)

    # 1. mapping: every P30 ball and EC header pin lands on the intended net
    _, nets = read_netlist()
    pin2net = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
    errs = []
    for ball, sig in D.P30_BALLS.items():
        exp, got = D.p30_net(sig), pin2net.get(("U1", ball), "")
        if (exp is None and not got.startswith("unconnected")) or (exp and got.lstrip("/") != exp):
            errs.append(f"U1.{ball} ({sig}): want {exp} got {got}")
    for ref, pins in (("J1", D.J1_PINS), ("J2", D.J2_PINS)):
        for n, sig in pins.items():
            exp, got = D.ec_net(sig), pin2net.get((ref, str(n)), "")
            if (exp is None and not got.startswith("unconnected")) or (exp and got.lstrip("/") != exp):
                errs.append(f"{ref}.{n} ({sig}): want {exp} got {got}")
    # data/address nets must be exactly header pin <-> P30 ball (+ optional pull-up)
    for n, nodes in nets.items():
        m = re.fullmatch(r"/(A|DQ)(\d+)", n)
        if m:
            refs = sorted(r for r, _ in nodes)
            if refs not in (["J1", "U1"], ["J2", "U1"]):
                errs.append(f"{n}: unexpected nodes {nodes}")
    print(f"[mapping] {len(errs)} error(s)")
    for e in errs:
        print("   ", e)
    ok &= not errs

    # 2. ERC
    rpt = os.path.join(BUILD, "erc.rpt")
    kicad("sch", "erc", "--severity-all", "-o", rpt, os.path.join(PRJ, "flashcat_p30.kicad_sch"))
    txt = open(rpt).read()
    m = re.search(r"ERC messages: (\d+)\s+Errors (\d+)\s+Warnings (\d+)", txt)
    print(f"[erc] messages={m.group(1)} errors={m.group(2)} warnings={m.group(3)}")
    ok &= m.group(1) == "0"

    # 3. DRC with schematic parity, all severities
    rpt = os.path.join(BUILD, "drc.rpt")
    kicad("pcb", "drc", "--schematic-parity", "--severity-all", "--refill-zones", "-o", rpt,
          os.path.join(PRJ, "flashcat_p30.kicad_pcb"))
    txt = open(rpt).read()
    viol = re.search(r"\*\* Found (\d+) DRC violations", txt)
    unc = re.search(r"\*\* Found (\d+) unconnected pads", txt)
    par = re.search(r"\*\* Found (\d+) Footprint errors", txt)
    kinds = {}
    for k in re.findall(r"^\[(\w+)\]", txt, re.M):
        kinds[k] = kinds.get(k, 0) + 1
    print(f"[drc] violations={viol.group(1) if viol else '?'} unconnected={unc.group(1) if unc else '?'} "
          f"parity={par.group(1) if par else '?'} {kinds}")
    ok &= bool(viol and unc and par) and viol.group(1) == unc.group(1) == par.group(1) == "0"

    print("ALL CHECKS PASSED" if ok else "CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
