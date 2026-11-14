#!/usr/bin/env python3
"""Pack the GTO Wizard per-action EV reads (.claude/gw*_ev.json, ROADMAP item 8) into ev.js.
Re-run after each daily pull: python3 build_ev.py
ev.js: EV[spot key] = 169 rows in HANDS order, [allin, raise, call, fold] in bb like SPOTS' columns, null where not offered."""
import json, pathlib

ROOT = pathlib.Path(__file__).parent
R = "AKQJT98765432"
HANDS = [R[i] + R[j] + ("" if i == j else "s" if i < j else "o")
         if i <= j else R[j] + R[i] + "o" for i in range(13) for j in range(13)]
COL = {"RAI": 0, "C": 2, "X": 2, "F": 3}  # anything else (R2.5, R11...) is the raise column
# the SB-limp line is stored by its action line; the trainer names its nodes in SPOTS
LIMP = ["SB/BB/FACINGLIMP", "BB/SB/LIMP_FACING2B", "SB/BB/LIMP_FACING3B",
        "BB/SB/LIMP_FACING4B", "SB/BB/LIMP_FACING5B", "BB/SB/LIMP_FACING6B"]

ev = {}
for f in sorted((ROOT / ".claude").glob("gw*_ev.json")):
    for key, node in json.loads(f.read_text()).items():
        if "|" in key:  # "8max/100bb|F-F-F-F-F-F-C-R3.5": the limp line, one node per action after the limp
            gs, pa = key.split("|"); acts = pa.split("-"); n = acts.index("C")
            assert set(acts[:n]) == {"F"}, key
            key = f"{gs}/{LIMP[len(acts) - n - 1]}"
        cols = [COL.get(o, 1) for o in node["opts"]]
        assert len(set(cols)) == len(cols), (key, node["opts"])
        rows = []
        for h in HANDS:
            row = [None] * 4
            for c, v in zip(cols, node["ev"][h]): row[c] = v
            rows.append(row)
        ev[key] = rows

out = ROOT / "ev.js"
out.write_text("// Per-action EV in bb from GTO Wizard (ROADMAP item 8); built by build_ev.py. Rows share the SPOTS array, so 9-max aliases get it too.\n"
               "window.EV=" + json.dumps(ev, separators=(",", ":")) + ";\n"
               "for (const k in EV) if (SPOTS[k]) SPOTS[k].ev = EV[k];\n")
print(f"{len(ev)} spots -> {out} ({out.stat().st_size // 1024} KB)")
