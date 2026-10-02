#!/usr/bin/env python3
"""Autoroute flashcat_p30.kicad_pcb with Freerouting, then pour + fill.

Needs Java 25 for Freerouting 2.4.1 (FR_VERSION=2.1.0 works with Java 21).
The jar is downloaded into hardware/build/ unless FREEROUTING_JAR is set.
"""
import os
import re
import shutil
import subprocess
import sys
import urllib.request

import pcbnew as P

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.normpath(os.path.join(HERE, ".."))
PCB = os.path.join(PRJ, "flashcat_p30.kicad_pcb")
BUILD = os.path.join(PRJ, "build")
PREROUTE = os.path.join(BUILD, "preroute.kicad_pcb")
FR_VERSION = os.environ.get("FR_VERSION", "2.4.1")   # 2.4.x needs Java 25; 2.1.0 runs on Java 21
JAR_URL = f"https://github.com/freerouting/freerouting/releases/download/v{FR_VERSION}/freerouting-{FR_VERSION}.jar"
PASSES = int(os.environ.get("FR_PASSES", "100"))
PASS_SCHEDULE = [PASSES, 60, 150, 80]

sys.path.insert(0, HERE)
import design as D  # noqa: E402
import fanout  # noqa: E402
from gen_pcb import add_zone  # noqa: E402


def jar():
    j = os.environ.get("FREEROUTING_JAR")
    if j:
        return j
    j = os.path.join(BUILD, f"freerouting-{FR_VERSION}.jar")
    if not os.path.exists(j):
        print("downloading", JAR_URL)
        urllib.request.urlretrieve(JAR_URL, j)
    return j


def _on_segment(p, a, c, tol):
    """Distance-based test: p lies on segment a-c (within tol); returns t in [0,1] or None."""
    ax, ay, cx, cy, px, py = a.x, a.y, c.x, c.y, p.x, p.y
    dx, dy = cx - ax, cy - ay
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return None
    t = ((px - ax) * dx + (py - ay) * dy) / l2
    if t < -1e-9 or t > 1 + 1e-9:
        return None
    qx, qy = ax + t * dx, ay + t * dy
    return t if (qx - px) ** 2 + (qy - py) ** 2 <= tol * tol else None


def trim_dangling(b):
    """Remove / shorten track segments that end in free space.

    Freerouting often joins a pre-routed (fanout) stub part-way along, leaving
    the rest of the stub dangling.  For a segment with a free end, cut it back
    to the farthest point where something else of the same net attaches;
    delete it if nothing attaches except at its other end.
    """
    tol = P.FromMM(0.002)
    changed, total = True, 0
    skip = set()
    while changed:
        changed = False
        tracks = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
        vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
        pads = [p for p in b.GetPads()]
        for s in tracks:
            net = s.GetNetCode()
            layer = s.GetLayer()
            if (s.GetStart().x, s.GetStart().y, s.GetEnd().x, s.GetEnd().y, layer) in skip:
                continue
            ends = [s.GetStart(), s.GetEnd()]

            def attached(pt):
                for o in tracks:
                    if o is s or o.GetNetCode() != net or o.GetLayer() != layer:
                        continue
                    if _on_segment(pt, o.GetStart(), o.GetEnd(), tol) is not None:
                        return True
                for v in vias:
                    if v.GetNetCode() == net and (v.GetPosition() - pt).EuclideanNorm() <= v.GetWidth(layer) // 2:
                        return True
                for p in pads:
                    if p.GetNetCode() == net and p.IsOnLayer(layer) and p.HitTest(pt):
                        return True
                return False

            free = [not attached(e) for e in ends]
            if not any(free) or all(free):
                continue
            fe, oe = (0, 1) if free[0] else (1, 0)
            a, c = ends[oe], ends[fe]
            # attachment points along s (other same-net track ends, vias, pads)
            best = None
            for o in tracks:
                if o is s or o.GetNetCode() != net or o.GetLayer() != layer:
                    continue
                for q in (o.GetStart(), o.GetEnd()):
                    t = _on_segment(q, a, c, tol)
                    if t is not None and t > 1e-6 and (best is None or t > best[0]):
                        best = (t, q)
            for v in vias:
                if v.GetNetCode() == net:
                    t = _on_segment(v.GetPosition(), a, c, tol)
                    if t is not None and t > 1e-6 and (best is None or t > best[0]):
                        best = (t, v.GetPosition())
            before = _unconnected(b)
            old = (P.VECTOR2I(s.GetStart()), P.VECTOR2I(s.GetEnd()))
            if best is None:
                b.Remove(s)
            elif fe == 0:
                s.SetStart(best[1])
            else:
                s.SetEnd(best[1])
            if _unconnected(b) > before:          # never trade a stub for an open
                if best is None:
                    b.Add(s)
                else:
                    s.SetStart(old[0])
                    s.SetEnd(old[1])
                skip.add((old[0].x, old[0].y, old[1].x, old[1].y, layer))
                _unconnected(b)
                continue
            changed = True
            total += 1
            break
    return total


def _unconnected(b):
    b.BuildConnectivity()
    return b.GetConnectivity().GetUnconnectedCount(True)


def main():
    """Retry in fresh processes (pcbnew does not survive re-loading a board)."""
    if "--once" in sys.argv:
        left = route_once()
        print(f"UNCONNECTED={left}")
        return 0
    # every attempt starts from the same unrouted board (fresh gen_pcb output)
    os.makedirs(BUILD, exist_ok=True)
    shutil.copy(PCB, PREROUTE)
    shutil.copy(PCB.replace(".kicad_pcb", ".kicad_pro"), PREROUTE.replace(".kicad_pcb", ".kicad_pro"))
    attempts = int(os.environ.get("FR_ATTEMPTS", "4"))
    for i in range(1, attempts + 1):
        # Freerouting is deterministic for a given input: vary the pass budget
        # between attempts so a retry is a genuinely different search.
        env = dict(os.environ, FR_PASSES=str(PASS_SCHEDULE[(i - 1) % len(PASS_SCHEDULE)]))
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--once"],
                           capture_output=True, text=True, env=env)
        sys.stdout.write("\n".join(ln for ln in r.stdout.splitlines() if "property.h" not in ln) + "\n")
        m = re.search(r"UNCONNECTED=(\d+)", r.stdout)
        left = int(m.group(1)) if m else -1
        print(f"attempt {i} (passes {env['FR_PASSES']}): {left} unconnected (exit {r.returncode})", flush=True)
        if left == 0:
            return 0
    return 1


def route_once():
    os.makedirs(BUILD, exist_ok=True)
    dsn = os.path.join(BUILD, "flashcat_p30.dsn")
    ses = os.path.join(BUILD, "flashcat_p30.ses")
    b = P.LoadBoard(PREROUTE if os.path.exists(PREROUTE) else PCB)
    # start from a clean slate (FR_KEEP=1: keep existing tracks, only
    # route what is still open), always dropping the post-route pours
    if os.environ.get("FR_KEEP") != "1":
        for t in list(b.GetTracks()):
            b.Remove(t)
    for z in list(b.Zones()):
        if z.GetZoneName() in ("GND_top", "GND_bottom", "VIO_plane", "VCC_plane"):
            b.Remove(z)
    if os.environ.get("FR_KEEP") != "1":
        print("fanout tracks:", fanout.apply(b))
        print("socket pad vias:", fanout.pad_vias(b))
        print("GND vias:", fanout.gnd_vias(b))
        print("VCCQ decap vias:", fanout.decap_vias(b))
    assert P.ExportSpecctraDSN(b, dsn)
    # In1 is the solid GND plane: forbid signal routing on it
    txt = open(dsn).read()
    txt2 = re.sub(r"(\(layer In1\.Cu\s*\(type )signal\)", r"\1power)", txt)
    assert txt2 != txt, "could not mark In1.Cu as power layer in DSN"
    open(dsn, "w").write(txt2)
    if os.path.exists(ses):
        os.remove(ses)
    subprocess.run(["java", "-Djava.awt.headless=true", "-jar", jar(), "-de", dsn, "-do", ses,
                    "-mp", str(PASSES), "--gui.enabled=false", "--api_server.enabled=false"],
                   check=True, cwd=BUILD)
    assert os.path.exists(ses), "freerouting produced no session file"
    assert P.ImportSpecctraSES(b, ses)

    print("trimmed dangling segments:", trim_dangling(b))
    print("redundant socket pad vias removed:", fanout.prune_pad_vias(b, _unconnected))
    x0, y0, x1, y1 = D.BOARD
    add_zone(b, "VCC_PROG", P.In2_Cu, x0, y0, x1, y1, prio=0, clearance=0.2, min_w=0.2, name="VCC_plane")
    add_zone(b, "GND", P.F_Cu, x0, y0, x1, y1, prio=0, clearance=0.2, min_w=0.2, name="GND_top")
    add_zone(b, "GND", P.B_Cu, x0, y0, x1, y1, prio=0, clearance=0.2, min_w=0.2, name="GND_bottom")
    P.ZONE_FILLER(b).Fill(b.Zones())
    left = _unconnected(b)
    P.SaveBoard(PCB, b, True)
    print("routed + filled:", PCB, "tracks:", len(b.GetTracks()))
    return left


if __name__ == "__main__":
    sys.exit(main())
