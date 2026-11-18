# python3 -I split.py results_dir out_dir   (run on the VM by cron every 10 minutes)
# Splits each results/<scenario>/<flop>.json.gz (gto-solve output) into the pieces the trainer's postflop mode loads one at a
# time: out/<scenario>/<flop>/flop.bin (flop nodes) and out/<scenario>/<flop>/<turn card>.bin (that turn's nodes), plus
# out/index.js listing what's there (a script: POST_INDEX = {...}).
# Piece format (2026-11-15; about half the size of the old base64 JSON scripts), gzipped:
#   u32 header length, header JSON [[key, player, [actions], hands], ...] per node, then per node in the same order:
#   u16 hand[hands] (card a * 52 + card b, card = rank "23456789TJQKA" * 4 + suit "shdc"), u32 reach x1000 [hands],
#   u8 strategy % [actions][hands], i32 EV x100 bb [actions][hands]. All little-endian. postflop.js loadPiece reads it.
# Since 2026-11-18 pieces are written as v2 (pack2 below: the same numbers rearranged, ~19% smaller gzipped); postflop.js
# reads both. convert_v2.py rewrote the v1 pieces already on disk.
# Turns that play the same are stored once: with suits the flop doesn't have, a turn in any of them is the first one's
# piece with the two suits swapped (postflop.js does the swap).
# Once split, a result is truncated to an empty marker with its mtime kept (run_queue.sh only looks at mtimes; worker_sync.sh
# skips empty files), so ~/results costs no disk. Everything the trainer needs is in the pieces.
import collections, gzip, json, os, struct, sys
from array import array  # little-endian on the VM (aarch64)

ORDER = ["SB", "BB", "UTG", "UTG1", "LJ", "HJ", "CO", "BTN"]  # postflop action order (6-max and 8-max seats): the later seat is in position
# Pot kinds postflop.js can deal (name part [5], see ways() there). Others stay in ~/results only, so ~/post (served
# to every user, and short on disk) holds just what the trainer plays. Add a kind here when postflop.js learns it.
TRAINER_KINDS = {"", "3bet", "4bet", "limp", "limpraise", "sqz", "c4b"}
R, S = "23456789TJQKA", "shdc"

CID = {r + x: R.index(r) * 4 + S.index(x) for r in R for x in S}

def write(path, nodes):
    head, body = [], []
    for k, n in nodes.items():
        h = len(n["hands"]); head.append([k, n["player"], n["actions"], h])
        body.append(array("H", [CID[x[:2]] * 52 + CID[x[2:]] for x in n["hands"]]).tobytes())
        body.append(array("I", [round(r * 1000) for r in n["reach"]]).tobytes())
        body += [bytes(map(int, row)) for row in n["strat"]]
        body += [array("i", [round(x * 100) for x in row]).tobytes() for row in n["ev"]]
    hj = json.dumps(head, separators=(",", ":")).encode()
    with open(path + ".tmp", "wb") as f: f.write(gzip.compress(pack2(struct.pack("<I", len(hj)) + hj + b"".join(body)), 6))
    os.replace(path + ".tmp", path)

def pack2(raw):
    """v1 piece bytes -> v2, the same numbers: {"v":2,"lists":[hands per list],"nodes":[[key, player, [actions], hands,
    list]]} header, then each distinct hand list once, every node's reach, every node's strategy, every node's EV, the
    u16/u32/i32 arrays stored as byte planes (all low bytes, then the next byte...). Gzips ~19% smaller than v1."""
    n = struct.unpack_from("<I", raw)[0]; p = 4 + n
    lists, nodes, reach, strat, ev = [], [], [], [], []
    for k, pl, acts, h in json.loads(raw[4:p]):
        a = len(acts); hs = raw[p:p + 2 * h]; p += 2 * h
        if hs not in lists: lists.append(hs)
        nodes.append([k, pl, acts, h, lists.index(hs)])
        reach.append(raw[p:p + 4 * h]); p += 4 * h
        strat.append(raw[p:p + a * h]); p += a * h
        ev.append(raw[p:p + 4 * a * h]); p += 4 * a * h
    planes = lambda b, w: b"".join(b[i::w] for i in range(w))
    hj = json.dumps({"v": 2, "lists": [len(x) // 2 for x in lists], "nodes": nodes}, separators=(",", ":")).encode()
    return (struct.pack("<I", len(hj)) + hj + b"".join(planes(x, 2) for x in lists) + planes(b"".join(reach), 4)
            + b"".join(strat) + planes(b"".join(ev), 4))

def split(scen, flop, gz, d):
    r = json.load(gzip.open(gz))
    os.makedirs(d, exist_ok=True)
    json.dump({"pot": r["pot"], "stack": r["stack"], "iters": r.get("iters"), "exploit": r.get("exploit"), "secs": r.get("secs")},
              open(os.path.join(d, "meta.json"), "w"))
    card = lambda t: len(t) == 2 and t[1] in "shdc"
    absent = [x for x in S if x not in flop[1::2]]  # suits not on the flop: turns in these play alike
    parts = collections.defaultdict(dict)
    for k, v in r.pop("nodes").items():
        c = [t for t in k.split("-") if card(t)] if k else []
        if c and c[0][1] in absent[1:]: continue  # stored as absent[0]
        parts[c[0] if c else "flop"][k] = v
    for f in os.listdir(d):  # the old format, and anything the new split doesn't write
        if f.endswith(".js") or f.endswith(".bin") and f[:-4] not in parts: os.remove(os.path.join(d, f))
    for name in sorted(parts, key=lambda x: x == "flop"):  # flop.bin last: it marks the flop as done
        write(os.path.join(d, name + ".bin"), parts[name])
    return len(parts) - 1

def one(job):
    scen, flop, gz, d = job
    st = os.stat(gz)
    n = split(scen, flop, gz, d)
    open(gz, "w").close(); os.utime(gz, ns=(st.st_atime_ns, st.st_mtime_ns))  # empty marker, same mtime
    return f"{scen}/{flop}: {n} turn pieces"

if __name__ == "__main__":
    from multiprocessing import Pool
    src, out = sys.argv[1], sys.argv[2]
    kinds = lambda scen: os.path.isdir(os.path.join(src, scen)) and (scen.split("_")[5:] or [""])[0] in TRAINER_KINDS
    scens = [x for x in sorted(os.listdir(src)) if kinds(x)]
    files = lambda scen: [f[:-8] for f in sorted(os.listdir(os.path.join(src, scen))) if f.endswith(".json.gz")]
    gz = lambda scen, flop: os.path.join(src, scen, flop + ".json.gz")
    todo = [(sc, fl, gz(sc, fl), os.path.join(out, sc, fl)) for sc in scens for fl in files(sc) if os.path.getsize(gz(sc, fl))]
    with Pool(3) as pool:  # ponytail: 3 of the VM's 4 cores; a keep-every-hand SRP result needs ~2.5 GB while it splits
        for line in pool.imap_unordered(one, todo): print(line, flush=True)
    index = {}
    for scen in scens:
        opener, caller = scen.split("_")[2], scen.split("_")[4]  # 6max_100bb_BTN_v_BB
        ip_opener = ORDER.index(opener) > ORDER.index(caller)
        meta = {"oop": caller if ip_opener else opener, "ip": opener if ip_opener else caller, "flops": []}
        for flop in files(scen):
            d = os.path.join(out, scen, flop)
            if not os.path.exists(os.path.join(d, "flop.bin")): continue
            meta["flops"].append(flop)
            if "pot" not in meta: meta.update({k: v for k, v in json.load(open(os.path.join(d, "meta.json"))).items() if k in ("pot", "stack")})
        if meta["flops"]: index[scen] = meta
    with open(os.path.join(out, "index.js.tmp"), "w") as f:  # atomic: the VM serves this file live (Caddy)
        f.write("POST_INDEX=" + json.dumps(index, separators=(",", ":")) + ";\n")
    os.replace(os.path.join(out, "index.js.tmp"), os.path.join(out, "index.js"))
    print(f"{sum(len(m['flops']) for m in index.values())} flops in {len(index)} scenarios -> {out}/index.js")
