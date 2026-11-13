#!/bin/bash
# Bring the VM's finished flop+turn solves to the trainer: split them on the VM (~/post), then mirror the chosen scenarios
# into ../post and write ../post/index.js listing only what's on this disk (so the trainer never deals a missing flop).
# Usage: solver/pull_post.sh [scenario ...]   default 6max_100bb_BTN_v_BB; already split flops are skipped.
# About 14 MB a flop (BTN_v_BB ~1.3 GB, all 15 scenarios ~13 GB): the Mac can't hold everything, so pull what you train.
set -e
cd "$(dirname "$0")"
ssh gto-vm 'python3 -I - results post' < split.py >/dev/null
mkdir -p ../post
for s in "${@:-6max_100bb_BTN_v_BB}"; do rsync -a --delete "gto-vm:post/$s/" "../post/$s/"; done
scp -q gto-vm:post/index.js ../post/index.vm.js
python3 -I - ../post <<'EOF'
import json, os, sys
d = sys.argv[1]
idx = json.loads(open(os.path.join(d, "index.vm.js")).read().split("=", 1)[1].rstrip(";\n"))
local = {s: {**m, "flops": [f for f in m["flops"] if os.path.exists(os.path.join(d, s, f, "flop.js"))]} for s, m in idx.items()}
local = {s: m for s, m in local.items() if m["flops"]}
open(os.path.join(d, "index.js"), "w").write("POST_INDEX=" + json.dumps(local, separators=(",", ":")) + ";\n")
print("on disk:", {s: len(m["flops"]) for s, m in local.items()})
EOF
rm ../post/index.vm.js
