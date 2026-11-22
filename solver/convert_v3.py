# One-off (2026-11-22): rewrite v1 and v2 pieces as v3 (split.py pack3, a third smaller) in place, on the VM:
#   nice python3 ~/solver/convert_v3.py DIR...
# Each new piece is decoded again and compared with the old one before it replaces it. Already-v3 pieces are left alone, so it
# can be re-run. Don't run it while split.py is writing pieces: it could put an old solve back. Can be deleted once done.
import gzip, json, multiprocessing, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from split import pack3, unpack3, same, save

def old_nodes(raw):
    """v1 or v2 piece bytes -> pack3's nodes; None for v3."""
    n = struct.unpack_from("<I", raw)[0]; h = json.loads(raw[4:4 + n]); p = 4 + n
    def take(c, dt, flat=True):
        nonlocal p
        w = np.dtype(dt).itemsize; x = np.frombuffer(raw, "u1", c * w, p); p += c * w
        return np.frombuffer((x if flat else x.reshape(w, c).T).tobytes(), dt)
    if isinstance(h, list):
        out = [(k, pl, a, take(c, "<u2"), take(c, "<u4"), take(len(a) * c, "u1").reshape(-1, c), take(len(a) * c, "<i4").reshape(-1, c)) for k, pl, a, c in h]
    elif h["v"] == 2:
        lists = [take(c, "<u2", False) for c in h["lists"]]
        H, E = sum(x[3] for x in h["nodes"]), sum(len(x[2]) * x[3] for x in h["nodes"])
        reach, st, ev, out, r, e = take(H, "<u4", False), take(E, "u1"), take(E, "<i4", False), [], 0, 0
        for k, pl, a, c, li in h["nodes"]:
            m = len(a) * c
            out.append((k, pl, a, lists[li], reach[r:r + c], st[e:e + m].reshape(-1, c), ev[e:e + m].reshape(-1, c))); r += c; e += m
    else: return None
    assert p == len(raw)
    return out

def one(path):
    try:
        with open(path, "rb") as f: old = f.read()
        nodes = old_nodes(gzip.decompress(old))
        if nodes is None: return 0, None
        flop, name = path.split("/")[-2:]
        raw = pack3(nodes, flop + (name[:-4] if name != "flop.bin" else ""))
        if not same(nodes, unpack3(raw)): return 0, path + ": differs, left alone"
        save(path, raw)
        return len(old) - os.path.getsize(path), None
    except Exception as e: return 0, f"{path}: {e!r}, left alone"

def pieces(dirs):
    for top in dirs:
        for scen in sorted(os.listdir(top)):
            d = os.path.join(top, scen)
            if os.path.islink(d) or not os.path.isdir(d): continue
            for root, _, files in os.walk(d):
                yield from (os.path.join(root, f) for f in sorted(files) if f.endswith(".bin"))

if __name__ == "__main__":
    n = saved = bad = 0
    with multiprocessing.Pool(4) as pool:
        for s, err in pool.imap_unordered(one, pieces(sys.argv[1:]), chunksize=64):
            n += 1; saved += s
            if err: bad += 1; print(err, flush=True)
            if n % 20000 == 0: print(f"{n} pieces, {saved / 1e9:.1f} GB saved", flush=True)
    print(f"done: {n} pieces, {saved / 1e9:.1f} GB saved, {bad} left alone", flush=True)
