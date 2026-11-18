# One-off (2026-11-18): rewrite v1 pieces as v2 (split.py pack2, ~19% smaller) in place, on the VM:
#   nice python3 ~/solver/convert_v2.py [--skip PREFIX] DIR...
# Already-v2 pieces are left alone, so it can be re-run. --skip leaves scenarios a running split.py still writes to:
# converting a piece split.py is replacing could put the old solve back. Can be deleted once every piece is v2.
import gzip, multiprocessing, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from split import pack2

def one(path):
    with open(path, "rb") as f: old = f.read()
    raw = gzip.decompress(old)
    if raw[4:5] == b"{": return 0  # v2 header is a JSON object, v1 an array
    with open(path + ".tmp", "wb") as f: f.write(gzip.compress(pack2(raw), 6))  # 9 is 10x slower for 2.5% less
    saved = len(old) - os.path.getsize(path + ".tmp")
    os.replace(path + ".tmp", path)
    return saved

def pieces(dirs, skip):
    for top in dirs:
        for scen in sorted(os.listdir(top)):
            d = os.path.join(top, scen)
            if os.path.islink(d) or not os.path.isdir(d) or any(scen.startswith(s) for s in skip): continue
            for root, _, files in os.walk(d):
                yield from (os.path.join(root, f) for f in files if f.endswith(".bin"))

if __name__ == "__main__":
    args, skip = sys.argv[1:], []
    while "--skip" in args: i = args.index("--skip"); skip.append(args[i + 1]); del args[i:i + 2]
    n = saved = 0
    with multiprocessing.Pool(2) as pool:  # ponytail: 2 of 4 cores, leaving split.py's cron its 3 when it runs
        for s in pool.imap_unordered(one, pieces(args, skip), chunksize=64):
            n += 1; saved += s
            if n % 20000 == 0: print(f"{n} pieces, {saved / 1e9:.1f} GB saved", flush=True)
    print(f"done: {n} pieces, {saved / 1e9:.1f} GB saved", flush=True)
