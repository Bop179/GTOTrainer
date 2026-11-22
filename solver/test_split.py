# python3 solver/test_split.py: split.py's v3 pieces hold exactly the solver's numbers (needs numpy)
import gzip, os, random, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from split import CID, R, S, expand, same, sym_suits, unpack3, write

random.seed(1)
def node(board, mirrored):
    sym, cards = sym_suits(board), [c for c in CID if c not in [board[i:i + 2] for i in range(0, len(board), 2)]]
    hands = [a + b for a in cards for b in cards if CID[a] > CID[b]]
    rnd, seen, rows = lambda: (random.choice([0, random.randrange(10 ** 6) / 1000]), [random.randrange(101) for _ in range(3)], [random.randrange(-30000, 30000) / 100 for _ in range(3)]), {}, []
    for h in hands:
        i = expand(np.array([CID[h[:2]] * 52 + CID[h[2:]]], "<u2"), sym)[0].min() if mirrored else h
        rows.append(seen.setdefault(i, rnd()))
    return {"player": 0, "actions": ["Fold", "Call", "Allin 9"], "hands": hands, "reach": [x[0] for x in rows],
            "strat": [[x[1][a] for x in rows] for a in range(3)], "ev": [[x[2][a] for x in rows] for a in range(3)]}

size = {}
for board in ("Ks9h4d", "Ks9s4s", "KcKd5s", "KsKhKd", "Ks9h4d2c"):  # the third and fourth swap suits that are on the board
    for mirrored in (True, False):
        nodes = {"": node(board, mirrored), "1": node(board, mirrored)}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.bin"); write(p, nodes, board); size[board, mirrored] = os.path.getsize(p)
            got = unpack3(gzip.open(p).read())
        want = [(k, n["player"], n["actions"], np.array([CID[h[:2]] * 52 + CID[h[2:]] for h in n["hands"]], "<u2"), np.rint(np.array(n["reach"]) * 1000).astype("<u4"),
                 np.array(n["strat"], "u1"), np.rint(np.array(n["ev"]) * 100).astype("<i4")) for k, n in nodes.items()]
        assert same(want, got), (board, mirrored)
        assert not same(want, [got[0], got[1][:6] + (got[1][6] + 1,)])  # same() does look at the numbers
    assert bool(sym_suits(board)) == (board not in ("Ks9h4d", "Ks9h4d2c"))
assert size["Ks9s4s", True] < .5 * size["Ks9s4s", False]
print("split.py v3: ok")
