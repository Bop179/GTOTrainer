#!/usr/bin/env python3
"""Pack GTO Nexus's bundled preflop ranges into data.js for index.html.
Re-run after a GTO Nexus update: python3 build.py"""
import json, pathlib, sys

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else
                   "/Applications/GTO Nexus.app/Contents/Resources/preflop_ranges_viewer")
R = "AKQJT98765432"
HANDS = [R[i] + R[j] + ("" if i == j else "s" if i < j else "o")
         if i <= j else R[j] + R[i] + "o" for i in range(13) for j in range(13)]

spots = {}
for f in sorted(SRC.rglob("*.txt")):
    rows = {r["type"]: r for r in json.loads(f.read_text())}
    # [allin, raise, call, fold, reach]; reach = how often the hand gets to this node
    spots[str(f.relative_to(SRC).with_suffix(""))] = [
        [rows[h][k] for k in ("Allin", "Raise", "Call", "Fold", "Range")] if h in rows else [0, 0, 0, 100, 0]
        for h in HANDS]

out = pathlib.Path(__file__).with_name("data.js")
out.write_text("window.HANDS=" + json.dumps(HANDS) + ";\nwindow.SPOTS=" +
               json.dumps(spots, separators=(",", ":")) + ";\n")
print(f"{len(spots)} spots -> {out} ({out.stat().st_size // 1024} KB)")
