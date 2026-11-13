# python3 -I split.py results_dir out_dir   (run on the VM by pull_post.sh)
# Splits each results/<scenario>/<flop>.json.gz (gto-solve output) into the pieces the trainer's postflop mode loads one at a
# time: out/<scenario>/<flop>/flop.js (flop nodes) and out/<scenario>/<flop>/<turn card>.js (that turn's nodes), plus
# out/index.js listing what's there. Each piece is a script, POST["<scenario>/<flop>/<piece>"] = "<base64 of gzipped JSON>",
# so index.html can load it with a <script> tag from file:// as well as from a server.
import base64, collections, gzip, json, os, sys

ORDER = ["SB", "BB", "UTG", "HJ", "CO", "BTN"]  # postflop action order: the later seat is in position
src, out = sys.argv[1], sys.argv[2]
index = {}

def write(path, key, obj):
    b = base64.b64encode(gzip.compress(json.dumps(obj, separators=(",", ":")).encode(), 9)).decode()
    with open(path + ".tmp", "w") as f: f.write(f'POST["{key}"]="{b}";\n')
    os.replace(path + ".tmp", path)

for scen in sorted(os.listdir(src)):
    if not os.path.isdir(os.path.join(src, scen)): continue
    opener, caller = scen.split("_")[2], scen.split("_")[4]  # 6max_100bb_BTN_v_BB
    ip_opener = ORDER.index(opener) > ORDER.index(caller)
    meta = {"oop": caller if ip_opener else opener, "ip": opener if ip_opener else caller, "flops": []}
    for f in sorted(os.listdir(os.path.join(src, scen))):
        if not f.endswith(".json.gz"): continue
        flop, gz = f[:-8], os.path.join(src, scen, f)
        d = os.path.join(out, scen, flop)
        meta["flops"].append(flop)
        if os.path.exists(os.path.join(d, "flop.js")) and os.path.getmtime(os.path.join(d, "flop.js")) > os.path.getmtime(gz):
            if "pot" not in meta: meta.update(json.load(open(os.path.join(d, "meta.json"))))
            continue
        r = json.load(gzip.open(gz))
        meta.update(pot=r["pot"], stack=r["stack"])
        os.makedirs(d, exist_ok=True)
        json.dump({"pot": r["pot"], "stack": r["stack"]}, open(os.path.join(d, "meta.json"), "w"))
        card = lambda t: len(t) == 2 and t[1] in "shdc"
        parts = collections.defaultdict(dict)
        for k, v in r.pop("nodes").items():
            c = [t for t in k.split("-") if card(t)] if k else []
            parts[c[0] if c else "flop"][k] = v
        for name in sorted(parts, key=lambda x: x == "flop"):  # flop.js last: it marks the flop as done
            write(os.path.join(d, name + ".js"), f"{scen}/{flop}/{name}", parts[name])
        print(f"{scen}/{flop}: {len(parts) - 1} turn cards", flush=True)
    if meta["flops"]: index[scen] = meta

with open(os.path.join(out, "index.js"), "w") as f:
    f.write("POST_INDEX=" + json.dumps(index, separators=(",", ":")) + ";\n")
print(f"{sum(len(m['flops']) for m in index.values())} flops in {len(index)} scenarios -> {out}/index.js")
