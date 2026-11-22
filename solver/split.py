# python3 -I split.py results_dir out_dir   (run on the VM by cron every 10 minutes)
# Splits each results/<scenario>/<flop>.json.gz (gto-solve output) into the pieces the trainer's postflop mode loads one at a
# time: out/<scenario>/<flop>/flop.bin (flop nodes) and out/<scenario>/<flop>/<turn card>.bin (that turn's nodes), plus
# out/index.js listing what's there (a script: POST_INDEX = {...}).
# Piece format v3 (pack3 below, 2026-11-22; a third smaller than v2, and nothing is rounded), gzipped, little-endian:
#   u32 header length, header JSON {"v":3, "sym":[[suits that can be swapped], ...], "lists":[[hands, 1 if mirrors are dropped], ...],
#   "nodes":[[key, player, [actions], list], ...]}, then the hand lists (u16 card a * 52 + card b, card = rank
#   "23456789TJQKA" * 4 + suit "shdc"), every node's reach (u32 x1000), every node's strategy rows but the first (u8 %), every
#   node's first row as (sum of all rows - 100), every node's EV (i32 x100 bb) as zigzagged differences from med()'s guess.
#   u16/u32 arrays are stored as byte planes (all low bytes, then the next byte...).
#   - Mirrors: suits with the same ranks on the board play alike, so of the hands that differ only by swapping them one is
#     stored. pack3 checks they really are identical; a list where they aren't is kept whole.
#   - Hands are sorted by EV (at their list's first node), so neighbours have close numbers and the differences are small.
# postflop.js decodePiece reads it. convert_v3.py rewrote the older pieces already on disk. Needs numpy (apt python3-numpy).
# Turns that play the same are stored once: with suits the flop doesn't have, a turn in any of them is the first one's
# piece with the two suits swapped (postflop.js does the swap).
# Once split, a result is truncated to an empty marker with its mtime kept (run_queue.sh only looks at mtimes; worker_sync.sh
# skips empty files), so ~/results costs no disk. Everything the trainer needs is in the pieces.
import collections, gzip, itertools, json, os, struct, sys
import numpy as np

ORDER = ["SB", "BB", "UTG", "UTG1", "LJ", "HJ", "CO", "BTN"]  # postflop action order (6-max and 8-max seats): the later seat is in position
# Pot kinds postflop.js can deal (name part [5], see ways() there). Others stay in ~/results only, so ~/post (served
# to every user, and short on disk) holds just what the trainer plays. Add a kind here when postflop.js learns it.
TRAINER_KINDS = {"", "3bet", "4bet", "limp", "limpraise", "sqz", "c4b"}
R, S = "23456789TJQKA", "shdc"

CID = {r + x: R.index(r) * 4 + S.index(x) for r in R for x in S}

def write(path, nodes, board):
    """nodes: gto-solve's {key: node}; board: the cards out, e.g. "Ks9h4d" or "Ks9h4d2c"."""
    save(path, pack3([(k, n["player"], n["actions"], np.array([CID[x[:2]] * 52 + CID[x[2:]] for x in n["hands"]], "<u2"),
                       np.rint(np.array(n["reach"]) * 1000).astype("<u4"), np.array(n["strat"]).astype("u1"),
                       np.rint(np.array(n["ev"]) * 100).astype("<i4")) for k, n in nodes.items()], board))

def save(path, raw):
    with open(path + ".tmp", "wb") as f: f.write(gzip.compress(raw, 6, mtime=0))
    os.replace(path + ".tmp", path)

def planes(x, dt): return np.frombuffer(x.astype(dt).tobytes(), "u1").reshape(-1, np.dtype(dt).itemsize).T.tobytes()

def med(x):  # guess for each EV from its left, upper and upper-left neighbours (the lossless-JPEG predictor)
    z = np.zeros((x.shape[0] + 1, x.shape[1] + 1), "i4"); z[1:, 1:] = x
    w, n, nw = z[1:, :-1], z[:-1, 1:], z[:-1, :-1]
    hi, lo = np.maximum(w, n), np.minimum(w, n)
    g = np.where(nw >= hi, lo, np.where(nw <= lo, hi, w + n - nw))
    g[0] = w[0]  # nothing above the first row
    return g

def unmed(d):
    x = np.zeros_like(d); x[0] = np.cumsum(d[0])
    for a in range(1, len(d)):
        row, up, left, ul = d[a].tolist(), x[a - 1].tolist(), 0, 0
        for j, n in enumerate(up):
            hi, lo = (left, n) if left > n else (n, left)
            row[j] = left = row[j] + (lo if ul >= hi else hi if ul <= lo else left + n - ul)
            ul = n
        x[a] = row
    return x

def sym_suits(board):
    by = collections.defaultdict(list)
    for s in range(4): by["".join(sorted(board[i] for i in range(0, len(board), 2) if board[i + 1] == S[s]))].append(s)
    return [g for g in by.values() if len(g) > 1]

def images(hands, sym):
    """Each hand (as high card * 52 + low card) under every swap of the sym suits: [swaps][hands]."""
    out = []
    for c in itertools.product(*map(itertools.permutations, sym)):
        m = np.arange(4)
        for g, p in zip(sym, c): m[g] = p
        a, b = (x // 4 * 4 + m[x % 4] for x in (hands.astype("i4") // 52, hands.astype("i4") % 52))
        out.append(np.maximum(a, b) * 52 + np.minimum(a, b))
    return np.array(out)

def expand(hands, sym):
    """Every hand a mirror-free list stands for, and the row of the list each one takes its numbers from."""
    u, i = np.unique(images(hands, sym), return_index=True)
    return u, i % len(hands)

def pack3(nodes, board):
    """nodes: [(key, player, actions, hands u16, reach u32, strat u8 [a][h], ev i32 [a][h])] -> v3 piece bytes."""
    sym, lists = sym_suits(board), {}
    for n in nodes: lists.setdefault(n[3].tobytes(), []).append(n)
    keep, whole = {}, []
    for k, ns in lists.items():
        hands = ns[0][3]; im = images(hands, sym)
        _, i, inv = np.unique(im.min(0), return_index=True, return_inverse=True)
        mirrors = len(i) < len(hands) and len(np.unique(im)) == len(hands) and all(
            (n[4][i][inv] == n[4]).all() and (n[5][:, i][:, inv] == n[5]).all() and (n[6][:, i][:, inv] == n[6]).all() for n in ns)
        if not mirrors: i = np.arange(len(hands))
        keep[k] = i[np.argsort(ns[0][6].max(0)[i], kind="stable")]; whole.append(not mirrors)
    at = {k: j for j, k in enumerate(keep)}
    reach, strat, first, ev = [], [], [], []
    for k, _, _, hands, r, s, e in nodes:
        i = keep[hands.tobytes()]; s, e = s[:, i], e[:, i]
        reach.append(r[i]); strat.append(s[1:].tobytes()); first.append((s.sum(0, "i4") - 100).astype("u1").tobytes())
        d = e - med(e); ev.append(((d << 1) ^ (d >> 31)).ravel())
    hj = json.dumps({"v": 3, "sym": sym, "lists": [[len(i), int(not w)] for i, w in zip(keep.values(), whole)],
                     "nodes": [[k, p, a, at[h.tobytes()]] for k, p, a, h, *_ in nodes]}, separators=(",", ":")).encode()
    return (struct.pack("<I", len(hj)) + hj + b"".join(planes(np.frombuffer(k, "<u2")[i], "<u2") for k, i in keep.items())
            + planes(np.concatenate(reach), "<u4") + b"".join(strat) + b"".join(first) + planes(np.concatenate(ev), "<u4"))

def unpack3(raw):
    """v3 piece bytes -> pack3's nodes, with the hands in another order."""
    n = struct.unpack_from("<I", raw)[0]; h = json.loads(raw[4:4 + n]); p = 4 + n
    def take(c, w):
        nonlocal p
        x = np.frombuffer(raw, "u1", c * w, p).reshape(w, c).T; p += c * w
        return np.frombuffer(x.tobytes(), f"<u{w}")
    lists = [take(c, 2) for c, _ in h["lists"]]
    full = [expand(x, h["sym"]) if m else (x, np.arange(len(x))) for x, (_, m) in zip(lists, h["lists"])]
    hs = [len(lists[x[3]]) for x in h["nodes"]]; acts = [len(x[2]) for x in h["nodes"]]
    reach, rest = take(sum(hs), 4), take(sum((a - 1) * c for a, c in zip(acts, hs)), 1)
    first, ev = take(sum(hs), 1), take(sum(a * c for a, c in zip(acts, hs)), 4)
    ev, out, r, s, e = (ev >> 1).astype("i4") ^ -(ev & 1).astype("i4"), [], 0, 0, 0
    for (k, pl, ac, li), c, a in zip(h["nodes"], hs, acts):
        u, i = full[li]
        st = rest[s:s + (a - 1) * c].reshape(a - 1, c)
        st = np.vstack([first[r:r + c].astype("i4") + 100 - st.sum(0, "i4"), st]).astype("u1")
        out.append((k, pl, ac, u, reach[r:r + c][i], st[:, i], unmed(ev[e:e + a * c].reshape(a, c))[:, i]))
        r += c; s += (a - 1) * c; e += a * c
    assert p == len(raw)
    return out

def same(a, b):
    """Do two node lists hold exactly the same numbers, whatever order their hands are in?"""
    def norm(n):
        x, y = n[3].astype("i4") // 52, n[3].astype("i4") % 52; k = np.maximum(x, y) * 52 + np.minimum(x, y); o = np.argsort(k)
        return [k[o], n[4][o], n[5][:, o], n[6][:, o]]
    return len(a) == len(b) and all(x[:3] == y[:3] and all(map(np.array_equal, norm(x), norm(y))) for x, y in zip(a, b))

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
        write(os.path.join(d, name + ".bin"), parts[name], flop + (name if name != "flop" else ""))
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
