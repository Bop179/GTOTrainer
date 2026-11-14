# python3 -I solver/make_jobs.py [outdir]   -> outdir/<scenario>/<flop>.json (default solver/jobs), outdir/order.txt
# (scenarios, most common first: the queue's order) and outdir/flops_<n>.json (each flop subset).
# Every heads-up postflop pot at 6-max and 8-max 100bb (9-max reuses 8-max), from the trainer's preflop SPOTS rows
# ([allin, raise, call, fold, reach], percentages, 169 hands in grid order; reach = how often the hand got to that spot,
# as a fraction). Spot keys are <villain>/<hero>/<node>, e.g. BTN/CO/FACING3B = CO (the opener) facing BTN's 3-bet;
# multiway keys join the earlier players with +, e.g. UTG+CO/HJ/FACINGSQZ_CALLER = HJ, who flatted UTG, facing CO's squeeze.
# Scenario names (seats are parts [2] and [4], which split.py and postflop.js rely on):
#   <game>_100bb_<OPENER>_v_<CALLER>             single-raised: opener's raises (RFI), caller's flats (FACINGRFI)
#   <game>_100bb_<OPENER>_v_<3BETTOR>_3bet       3-bettor's raises (FACINGRFI), opener's calls (FACING3B)
#   <game>_100bb_<OPENER>_v_<3BETTOR>_4bet       opener's 4-bets (FACING3B), 3-bettor's calls (FACING4B)
#   <game>_100bb_SB_v_BB_limp                    SB's limps (RFI call), BB's checks (FACINGLIMP call)
#   <game>_100bb_SB_v_BB_limpraise               BB's raises over the limp (FACINGLIMP), SB's calls (LIMP_FACING2B)
#   <game>_100bb_<CALLER>_v_<SQUEEZER>_sqz_<OPENER>   open, flat, squeeze, opener folds, caller calls
#   <game>_100bb_<3BETTOR>_v_<C4BETTOR>_c4b_<OPENER>  open, 3-bet, cold 4-bet, opener folds, 3-bettor calls
# Squeeze and cold 4-bet sizes come from the closing caller's SIZES (GTO Wizard: [open, 3-bet or squeeze, cold 4-bet, ...]),
# as index.html's sizing() reads them, so the pot matches the preflop replay. Spots without SIZES use sizing()'s fallback
# (open 2.5, or 3 from the SB; first raise x3 in position / x4 out of position; next raise x2.3; rounded to 0.5).
# ponytail: everyone else is assumed to fold; the opener-calls versions of squeezes and cold 4-bets aren't in the data.
import itertools, json, math, os, re, sys

R = "AKQJT98765432"
H = [R[i] + R[j] if i == j else (R[i] + R[j] + "s" if i < j else R[j] + R[i] + "o") for i in range(13) for j in range(13)]
COMBOS = [6 if h[0] == h[1] else 4 if h.endswith("s") else 12 for h in H]
HERE = os.path.dirname(os.path.abspath(__file__))
SEATS = {"6max": ["UTG", "HJ", "CO", "BTN", "SB", "BB"], "8max": ["UTG", "UTG1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]}
FILES = {"6max": "data6.js", "8max": "data8.js"}
SIZES = {"flop_sizes": ["33%, 75%", "2.5x"], "turn_sizes": ["75%, 125%", "2.5x"], "river_sizes": ["75%", "2.5x"]}
# Limped pots (2bb pot, 99bb behind) with SIZES need 62 GB; this needs 26 GB (13 GB compressed, so it fits the VM):
# no turn overbet, and 3x raises so the stacks go in after fewer raises.
LIMP_SIZES = {"flop_sizes": ["33%, 75%", "3x"], "turn_sizes": ["75%", "3x"], "river_sizes": ["75%", "3x"]}
FIRST = ["6max_100bb_BTN_v_BB"]  # already solving when the order was last changed: finish it before anything else
N_FLOPS, N_FLOPS_RARE = 95, 40
RARE = 0.05  # pots rarer than 5% of the game's heads-up single-raised pots get the smaller flop set
STACK = 100

SRC = {g: open(os.path.join(HERE, "..", f)).read() for g, f in FILES.items()}
SZ = {}  # preflop raise-to sizes per spot, in bb
for s in SRC.values():
    for m in re.finditer(r'(?:Object\.assign\(window\.SIZES(?:\|\|\{\})?,|window\.SIZES=)\s*(?=\{")', s):
        SZ.update(json.JSONDecoder().raw_decode(s[m.end():])[0])
K = lambda g, *p: f"{g}/100bb/" + "/".join(p)

def rows(key):
    s = SRC[key.split("/")[0]]
    i = s.index(json.dumps(key) + ":[[") + len(json.dumps(key)) + 1
    return json.JSONDecoder().raw_decode(s[i:])[0]

def has(key): return json.dumps(key) + ":[[" in SRC[key.split("/")[0]]

def rng(rs, col):
    return ",".join(f"{h}:{min(1, r[col] / 100 * r[4]):.3f}" for h, r in zip(H, rs) if r[col] * r[4] > 0.05)

def freq(rs, col):
    """Chance a random hand takes action col here (rows are per hand class, in percent, times reach)."""
    return sum(c * r[col] / 100 * r[4] for c, r in zip(COMBOS, rs)) / 1326

def ip(g, a, b):
    """True if seat a acts after seat b postflop (the blinds act first, then the preflop order)."""
    order = ["SB", "BB"] + SEATS[g][:-2]
    return order.index(a) > order.index(b)

def half(x):
    """index.html's sizing(): Math.round to 0.5 (halves round up, unlike Python's round), all-in past 55% of the stack."""
    x = math.floor(x * 2 + 0.5) / 2
    return STACK if x > STACK * 0.55 else x

def blinds_dead(seats):
    """Blinds posted by players not in `seats` (the pot's two players and anyone whose bet is counted separately)."""
    return (0 if "SB" in seats else 0.5) + (0 if "BB" in seats else 1)

def scenarios():
    """Every heads-up pot with data: (freq, game, name, (seat, rows, col), (seat, rows, col), size, dead), where freq ~
    the chance a hand plays that pot, size = what each of the two players put in, dead = everyone else's money.
    ponytail: freq multiplies the players' frequencies (reach carries the earlier actions) and ignores card removal
    and the players behind; good enough to rank pots and split common from rare."""
    out = []
    def add(f, g, name, a, b, size, dead):
        if size < STACK * 0.9: out.append((f, g, name, a, b, size, dead))  # an all-in preflop has no postflop
    multi = lambda g, node: re.findall(r'"(' + g + r'/100bb/[A-Z0-9]+\+[A-Z0-9]+/[A-Z0-9]+/' + node + r')":\[\[', SRC[g])
    seats3 = lambda key: re.match(r".*/([A-Z0-9]+)\+([A-Z0-9]+)/([A-Z0-9]+)/", key).groups()
    for g, seats in SEATS.items():
        n = lambda *p: f"{g}_100bb_" + "_".join(p)
        for i, o in enumerate(seats[:-1]):
            for c in seats[i + 1:]:
                if not has(K(g, o, c, "FACINGRFI")): continue
                op, vs = rows(K(g, o, "RFI")), rows(K(g, o, c, "FACINGRFI"))
                add(freq(op, 1) * freq(vs, 2), g, n(o, "v", c), (o, op, 1), (c, vs, 2), SZ[K(g, o, "RFI")][0], blinds_dead((o, c)))
                if has(K(g, c, o, "FACING3B")):
                    v3 = rows(K(g, c, o, "FACING3B"))
                    add(freq(vs, 1) * freq(v3, 2), g, n(o, "v", c, "3bet"), (o, v3, 2), (c, vs, 1), SZ[K(g, o, c, "FACINGRFI")][1], blinds_dead((o, c)))
                    if has(K(g, o, c, "FACING4B")):
                        v4 = rows(K(g, o, c, "FACING4B"))
                        add(freq(v3, 1) * freq(v4, 2), g, n(o, "v", c, "4bet"), (o, v3, 1), (c, v4, 2), SZ[K(g, o, c, "FACING4B")][2], blinds_dead((o, c)))
        if has(K(g, "SB", "BB", "FACINGLIMP")):
            sb, bb = rows(K(g, "SB", "RFI")), rows(K(g, "SB", "BB", "FACINGLIMP"))
            add(freq(sb, 2) * freq(bb, 2), g, n("SB", "v", "BB", "limp"), ("SB", sb, 2), ("BB", bb, 2), 1, 0)
            if has(K(g, "BB", "SB", "LIMP_FACING2B")):
                l2 = rows(K(g, "BB", "SB", "LIMP_FACING2B"))
                add(freq(bb, 1) * freq(l2, 2), g, n("SB", "v", "BB", "limpraise"), ("SB", l2, 2), ("BB", bb, 1), SZ[K(g, "SB", "BB", "FACINGLIMP")][0], 0)
        for key in multi(g, "FACINGSQZ_CALLER"):
            o, s_, c = seats3(key)  # opener+squeezer/caller
            sq, fold = K(g, f"{o}+{c}", s_, "FACINGRFI_CALL"), K(g, f"{c}+{s_}", o, "FACINGSQZ")
            if not (has(sq) and has(fold)): continue
            sq, call = rows(sq), rows(key)
            open_ = 3 if o == "SB" else 2.5
            size = SZ[key][1] if key in SZ else half(open_ * (3 if ip(g, s_, c) else 4))
            open_ = SZ[key][0] if key in SZ else open_
            add(freq(rows(fold), 3) * freq(call, 2) * freq(sq, 1), g, n(c, "v", s_, "sqz", o), (c, call, 2), (s_, sq, 1), size,
                open_ + blinds_dead((o, c, s_)))
        for key in multi(g, "FACINGC4B_3B"):
            o, f_, t = seats3(key)  # opener+cold 4-bettor/3-bettor
            c4, fold = K(g, f"{o}+{t}", f_, "FACING3B_COLD"), K(g, f"{t}+{f_}", o, "FACINGC4B")
            if not (has(c4) and has(fold)): continue
            c4, call = rows(c4), rows(key)
            open_ = 3 if o == "SB" else 2.5
            size = SZ[key][2] if key in SZ else half(half(open_ * (3 if ip(g, t, o) else 4)) * 2.3)
            open_ = SZ[key][0] if key in SZ else open_
            add(freq(rows(fold), 3) * freq(call, 2) * freq(c4, 1), g, n(t, "v", f_, "c4b", o), (t, call, 2), (f_, c4, 1), size,
                open_ + blinds_dead((o, t, f_)))
    return out

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

def job(g, a, b, size, dead, flop):
    """a, b = (seat, rows, col) for the pot's two players; each has put in size bb, and dead bb came from the others."""
    o, i = (b, a) if ip(g, a[0], b[0]) else (a, b)
    return {"oop": rng(o[1], o[2]), "ip": rng(i[1], i[2]), "flop": flop, "pot": 2 * size + dead, "stack": STACK - size,
            **(LIMP_SIZES if size == 1 else SIZES), "target": 0.01, "max_iter": 1000}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "jobs")
    sets = {n: flops(n) for n in (N_FLOPS, N_FLOPS_RARE)}
    assert all(len(f) == n and len(set(f)) == n for n, f in sets.items())
    sc = scenarios()
    J = {name: (lambda f, g=g, a=a, b=b, z=z, d=d: job(g, a, b, z, d, f)) for _, g, name, a, b, z, d in sc}
    assert len(J) == len(sc), "duplicate scenario names"
    j = lambda name: J[name]("AsKdQh")
    R6 = lambda *p: rows(K("6max", *p))
    assert j("6max_100bb_SB_v_BB")["oop"] == rng(R6("SB", "RFI"), 1)  # SB is out of position
    assert j("6max_100bb_CO_v_BTN")["ip"] == rng(R6("CO", "BTN", "FACINGRFI"), 2)  # BTN caller is in position
    assert [j(f"6max_100bb_{x}")["pot"] for x in ("BTN_v_BB", "SB_v_BB", "CO_v_BTN", "BTN_v_SB")] == [5.5, 7.0, 6.5, 6.0]
    t = j("6max_100bb_CO_v_BTN_3bet")  # CO opens 2.5, BTN 3-bets to 8.5, CO calls
    assert (t["pot"], t["stack"]) == (18.5, 91.5) and t["ip"] == rng(R6("CO", "BTN", "FACINGRFI"), 1) and t["oop"] == rng(R6("BTN", "CO", "FACING3B"), 2)
    assert j("6max_100bb_BTN_v_BB_3bet")["oop"] == rng(R6("BTN", "BB", "FACINGRFI"), 1)  # the BB 3-bettor is OOP
    t = j("6max_100bb_CO_v_BTN_4bet")  # CO 4-bets to 23 and BTN calls: CO OOP with its 4-bets
    assert (t["pot"], t["stack"]) == (47.5, 77) and t["oop"] == rng(R6("BTN", "CO", "FACING3B"), 1)
    assert (j("6max_100bb_SB_v_BB_limp")["pot"], j("6max_100bb_SB_v_BB_limpraise")["pot"]) == (2, 7)
    assert j("6max_100bb_SB_v_BB_limp")["turn_sizes"] == LIMP_SIZES["turn_sizes"] and j("6max_100bb_SB_v_BB_limpraise")["turn_sizes"] == SIZES["turn_sizes"]
    sz = lambda *p: SZ[K("6max", *p)]
    t = j("6max_100bb_HJ_v_CO_sqz_UTG")  # UTG opens 2.5, HJ flats, CO squeezes (to 11 in GTO Wizard's sizes), UTG folds, HJ calls
    q = sz("UTG+CO", "HJ", "FACINGSQZ_CALLER")[1]
    assert (t["pot"], t["stack"]) == (2 * q + 2.5 + 1.5, 100 - q) and t["ip"] == rng(R6("UTG+HJ", "CO", "FACINGRFI_CALL"), 1)
    t = j("6max_100bb_HJ_v_CO_c4b_UTG")  # UTG 2.5, HJ 3-bets, CO cold 4-bets, UTG folds, HJ calls
    q = sz("UTG+CO", "HJ", "FACINGC4B_3B")[2]
    assert (t["pot"], t["stack"]) == (2 * q + 2.5 + 1.5, 100 - q)
    os.makedirs(out, exist_ok=True)
    for n, f in sets.items(): json.dump(f, open(os.path.join(out, f"flops_{n}.json"), "w"))
    cut = {g: RARE * sum(f for f, gg, name, *_ in sc if gg == g and name.count("_") == 4) for g in SEATS}  # single-raised total
    order = []
    # 6-max first (every pot kind, most common first), 8-max last (decided 2026-11-13)
    for f, g, name, *_ in sorted(sc, key=lambda x: (x[2] not in FIRST, x[1] != "6max", -x[0] / cut[x[1]])):
        fl = sets[N_FLOPS if f >= cut[g] else N_FLOPS_RARE]
        d = os.path.join(out, name); os.makedirs(d, exist_ok=True)
        for x in fl: json.dump(J[name](x), open(os.path.join(d, x + ".json"), "w"))
        order.append(name); print(f"{name:<34} {f / cut[g] * RARE:7.2%}  {len(fl)} flops")
    open(os.path.join(out, "order.txt"), "w").write("\n".join(order) + "\n")
    print(f"{len(order)} scenarios, {sum(len(os.listdir(os.path.join(out, d))) for d in order)} jobs -> {out}")
