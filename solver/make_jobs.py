# python3 -I solver/make_jobs.py [outdir]   -> outdir/<scenario>/<flop>.json (default solver/jobs), outdir/order.txt
# (scenarios, most common first: the queue's order) and outdir/flops_<n>.json (each flop subset).
# Heads-up pots at 6-max 100bb, every opener and responder pair, from the trainer's preflop SPOTS rows
# ([allin, raise, call, fold, reach], percentages, 169 hands in grid order; reach = how often the hand got to that spot):
#   6max_100bb_<OPENER>_v_<CALLER>        single-raised: the opener's raises (RFI), the caller's flats (FACINGRFI)
#   6max_100bb_<OPENER>_v_<3BETTOR>_3bet  3-bet pot: the 3-bettor's raises (FACINGRFI), the opener's calls (FACING3B)
# Spot keys are <villain>/<hero>/<node>, e.g. BTN/CO/FACING3B = CO (the opener) facing BTN's 3-bet.
# ponytail: everyone else is assumed to fold; squeeze and multiway lines are separate pot types (ROADMAP item 9).
import itertools, json, os, sys

R = "AKQJT98765432"
H = [R[i] + R[j] if i == j else (R[i] + R[j] + "s" if i < j else R[j] + R[i] + "o") for i in range(13) for j in range(13)]
SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data6.js")).read()
_SZ = "Object.assign(window.SIZES,"
SZ = json.JSONDecoder().raw_decode(SRC[SRC.index(_SZ) + len(_SZ):])[0]  # preflop raise sizes per spot, in bb
SEATS = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]
ORDER = ["SB", "BB", "UTG", "HJ", "CO", "BTN"]  # postflop action order: the later seat is in position
SIZES = {"flop_sizes": ["33%, 75%", "2.5x"], "turn_sizes": ["75%, 125%", "2.5x"], "river_sizes": ["75%", "2.5x"]}
N_FLOPS, N_FLOPS_RARE = 95, 40
RARE = 0.05  # pots rarer than 5% of all heads-up single-raised pots get the smaller flop set
COMBOS = [6 if h[0] == h[1] else 4 if h.endswith("s") else 12 for h in H]
K = lambda *p: "6max/100bb/" + "/".join(p)

def rows(key):
    i = SRC.index(json.dumps(key) + ":[[") + len(json.dumps(key)) + 1
    return json.JSONDecoder().raw_decode(SRC[i:])[0]

def rng(rs, col):
    return ",".join(f"{h}:{min(1, r[col] / 100 * r[4]):.3f}" for h, r in zip(H, rs) if r[col] * r[4] > 0.05)

def freq(rs, col):
    """Share of all 1326 combos taking action col (rows are per hand class, in percent, times reach)."""
    return sum(c * r[col] / 100 * r[4] for c, r in zip(COMBOS, rs)) / 1326

def scenarios():
    """Every heads-up pot with data, most common first: (freq, name, (opener, rows, col), (responder, rows, col), size),
    where freq ~ the chance a hand plays that pot and size is the last preflop raise, which both players match.
    ponytail: freq multiplies the two players' frequencies and ignores the players behind; good enough to rank."""
    out = []
    for i, o in enumerate(SEATS[:-1]):
        for c in SEATS[i + 1:]:
            if K(o, c, "FACINGRFI") not in SZ: continue
            op, vs = rows(K(o, "RFI")), rows(K(o, c, "FACINGRFI"))
            out.append((freq(op, 1) * freq(vs, 2), f"6max_100bb_{o}_v_{c}", (o, op, 1), (c, vs, 2), SZ[K(o, "RFI")][0]))
            if K(c, o, "FACING3B") in SZ:
                v3 = rows(K(c, o, "FACING3B"))
                out.append((freq(vs, 1) * freq(v3, 2), f"6max_100bb_{o}_v_{c}_3bet", (o, v3, 2), (c, vs, 1), SZ[K(o, c, "FACINGRFI")][1]))
    return sorted(out, key=lambda x: -x[0])

def flops(n):
    """Representative flop subset: the 1755 suit-isomorphic flops, ordered by texture and weighted by how many
    real flops each stands for, sampled at n evenly spaced points of cumulative weight (so each pick ~ 1/n of deals)."""
    seen = {}
    for c in itertools.combinations([r + s for r in R for s in "shdc"], 3):
        # canonical form: the smallest spelling over all suit relabelings
        k = min("".join(sorted((x[0] + p["shdc".index(x[1])] for x in c), key=lambda x: (R.index(x[0]), x[1])))
                for p in itertools.permutations("shdc"))
        seen[k] = seen.get(k, 0) + 1
    tex = lambda k: (len(set(k[1::2])), len(set(k[0::2])), [R.index(x) for x in k[0::2]])
    keys = sorted(seen, key=tex)
    out, cum, step = [], 0, sum(seen.values()) / n
    for k in keys:
        cum += seen[k]
        while len(out) < n and cum >= step * (len(out) + 0.5): out.append(k)
    return out

def job(a, b, size, flop):
    """a, b = (seat, rows, col) for the opener and the responder; both have put in size bb."""
    (sa, ra, ca), (sb, rb, cb) = a, b
    dead = (0 if "SB" in (sa, sb) else 0.5) + (0 if "BB" in (sa, sb) else 1)  # blinds not in the pot's two players
    ip, oop = (a, b) if ORDER.index(sa) > ORDER.index(sb) else (b, a)
    return {"oop": rng(oop[1], oop[2]), "ip": rng(ip[1], ip[2]), "flop": flop,
            "pot": 2 * size + dead, "stack": 100 - size, **SIZES, "target": 0.01, "max_iter": 1000}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs")
    sets = {n: flops(n) for n in (N_FLOPS, N_FLOPS_RARE)}
    assert all(len(f) == n and len(set(f)) == n for n, f in sets.items())
    sc = scenarios()
    J = {name: (lambda f, a=a, b=b, z=z: job(a, b, z, f)) for _, name, a, b, z in sc}
    j = lambda name: J[name]("AsKdQh")
    assert j("6max_100bb_SB_v_BB")["oop"] == rng(rows(K("SB", "RFI")), 1)  # SB is out of position
    assert j("6max_100bb_CO_v_BTN")["ip"] == rng(rows(K("CO", "BTN", "FACINGRFI")), 2)  # BTN caller is in position
    assert [j(f"6max_100bb_{n}")["pot"] for n in ("BTN_v_BB", "SB_v_BB", "CO_v_BTN", "BTN_v_SB")] == [5.5, 7.0, 6.5, 6.0]
    # 3-bet pot: CO opens 2.5, BTN 3-bets to 8.5, CO calls; BTN is in position with its 3-bets, CO out of position with its calls
    t = j("6max_100bb_CO_v_BTN_3bet")
    assert (t["pot"], t["stack"]) == (2 * 8.5 + 1.5, 91.5)
    assert t["ip"] == rng(rows(K("CO", "BTN", "FACINGRFI")), 1) and t["oop"] == rng(rows(K("BTN", "CO", "FACING3B")), 2)
    assert j("6max_100bb_BTN_v_BB_3bet")["oop"] == rng(rows(K("BTN", "BB", "FACINGRFI")), 1)  # the BB 3-bettor is OOP
    os.makedirs(out, exist_ok=True)
    for n, f in sets.items(): json.dump(f, open(os.path.join(out, f"flops_{n}.json"), "w"))
    cut = RARE * sum(f for f, name, *_ in sc if not name.endswith("_3bet"))
    order = []
    for f, name, *_ in sc:
        fl = sets[N_FLOPS if f >= cut else N_FLOPS_RARE]
        d = os.path.join(out, name); os.makedirs(d, exist_ok=True)
        for x in fl: json.dump(J[name](x), open(os.path.join(d, x + ".json"), "w"))
        order.append(name); print(f"{name:<27} {f / cut * RARE:6.1%} of SRPs' total  {len(fl)} flops")
    open(os.path.join(out, "order.txt"), "w").write("\n".join(order) + "\n")
    print(f"{len(order)} scenarios, {sum(len(os.listdir(os.path.join(out, d))) for d in order)} jobs -> {out}")
