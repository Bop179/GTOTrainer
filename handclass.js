// Postflop hand groups and board texture for the explanation, as simple local rules (not the solver).
// Cards are solver-spelled strings like "Ks". `node handclass.js` runs the self-check.
const HC_UP = "23456789TJQKA";
const hcRank = c => HC_UP.indexOf(c[0]);
const hcName = r => HC_UP[r] === "T" ? "10" : HC_UP[r];
function straightHigh(ranks) { // top rank of the best straight in a Set of ranks (ace also plays low), or -1
  for (let hi = 12; hi >= 3; hi--) {
    let ok = true;
    for (let r = hi; r > hi - 5; r--) if (!ranks.has(r < 0 ? 12 : r)) { ok = false; break; }
    if (ok) return hi;
  }
  return -1;
}

// what you've made using at least one of your cards, and what you're drawing to (not on the river)
function handClass(hole, board) {
  const all = [...hole, ...board], rs = cs => new Set(cs.map(hcRank));
  const count = cs => cs.reduce((m, c) => (m[hcRank(c)] = (m[hcRank(c)] || 0) + 1, m), {});
  const ca = count(all), cb = count(board), [a, b] = hole.map(hcRank);
  const nSuit = (cs, s) => cs.filter(c => c[1] === s).length;
  const top = Math.max(...board.map(hcRank)), ranks = [...rs(board)].sort((x, y) => y - x);
  const trips = Object.keys(ca).filter(r => ca[r] >= 3).map(Number);
  const full = trips.length && Object.keys(ca).some(r => ca[r] >= 2 && !trips.includes(+r) || trips.length > 1)
    && hole.some(c => ca[hcRank(c)] >= 2) && !(Object.values(cb).includes(3) && Object.values(cb).filter(n => n >= 2).length > 1);
  const flush = "shdc".split("").some(s => nSuit(all, s) >= 5 && nSuit(hole, s) > 0);
  let made;
  if (hole.some(c => ca[hcRank(c)] === 4)) made = "quads";
  else if (full) made = "a full house";
  else if (flush) made = "a flush";
  else if (straightHigh(rs(all)) > straightHigh(rs(board))) made = "a straight";
  else if (a === b && cb[a] === 1) made = "a set";
  else if (a !== b && (cb[a] === 2 || cb[b] === 2)) made = "trips";
  else if (a !== b && cb[a] && cb[b]) made = "two pair";
  else if (a === b) made = a > top ? "an overpair" : "a pocket pair below the top card";
  else {
    const p = cb[a] ? a : cb[b] ? b : -1;
    made = p === top ? "top pair" : p >= 0 && p === ranks[1] ? "second pair" : p >= 0 ? "a weak pair" : Math.max(a, b) === 12 ? "ace high" : "no pair";
  }
  const draws = [];
  if (board.length < 5 && !["quads", "a full house", "a flush", "a straight"].includes(made)) {
    if ("shdc".split("").some(s => nSuit(all, s) === 4 && nSuit(hole, s) > 0)) draws.push("a flush draw");
    let outs = 0; // ranks that make a straight you play a card in
    for (let r = 0; r < 13; r++) if (!ca[r] && straightHigh(new Set([...rs(all), r])) > straightHigh(new Set([...rs(board), r]))) outs++;
    if (outs >= 2) draws.push("an open-ended straight draw"); else if (outs === 1) draws.push("a gutshot");
  }
  const draw = draws.join(" and "), weak = made === "no pair" || made === "ace high";
  return { made, draw, text: weak && draw ? draw + (made === "ace high" ? " (ace high)" : "") : made + (draw ? " with " + draw : "") };
}

function texture(board) {
  const rs = board.map(hcRank), top = Math.max(...rs), n = board.length;
  const suited = Math.max(..."shdc".split("").map(s => board.filter(c => c[1] === s).length));
  const paired = new Set(rs).size < n;
  let conn = 0; // most distinct board ranks inside any 5-rank window: 3+ means a straight is possible
  for (let lo = -1; lo <= 8; lo++) conn = Math.max(conn, new Set(rs.flatMap(r => [r, r === 12 ? -1 : r]).filter(r => r >= lo && r < lo + 5)).size);
  const parts = [`${hcName(top)}-high${paired ? " and paired" : ""}`];
  parts.push(suited >= 3 ? "a flush is possible" : suited === 2 && n < 5 ? "two-tone (flush draws possible)" : n === 3 ? "rainbow" : "no flush possible");
  parts.push(conn >= 3 ? "straights are possible" : "no straight yet");
  return parts.join(", ");
}

// ---------- showdown equity (exact: every runout still to come) ----------
const hcBits = x => { let c = 0; for (; x; c++) x &= x - 1; return c; };
// a 5-7 card hand as one number: bigger wins, equal ties. Cards are ids rank * 4 + suit (rank 0 = deuce).
function strength(cs) {
  const n = new Int8Array(13), sm = [0, 0, 0, 0]; let m = 0;
  for (const c of cs) { n[c >> 2]++; sm[c & 3] |= 1 << (c >> 2); m |= 1 << (c >> 2); }
  const v = (cat, ...k) => { let x = cat; for (let i = 0; i < 5; i++) x = x * 13 + (k[i] ?? 0); return x; };
  const st = mask => { const x = mask << 1 | mask >> 12 & 1; for (let h = 13; h >= 4; h--) if ((x >> h - 4 & 31) === 31) return h - 1; return -1; }; // ace plays low too
  const hi = (mask, k, skip = []) => { const o = []; for (let r = 12; r >= 0 && o.length < k; r--) if (mask >> r & 1 && !skip.includes(r)) o.push(r); return o; };
  const by = c => { const o = []; for (let r = 12; r >= 0; r--) if (n[r] === c) o.push(r); return o; };
  const fl = sm.find(x => hcBits(x) >= 5), q = by(4), t = by(3), p = by(2);
  if (fl !== undefined && st(fl) >= 0) return v(8, st(fl));
  if (q.length) return v(7, q[0], ...hi(m, 1, q));
  if (t.length && (t.length > 1 || p.length)) return v(6, t[0], Math.max(t[1] ?? -1, p[0] ?? -1));
  if (fl !== undefined) return v(5, ...hi(fl, 5));
  if (st(m) >= 0) return v(4, st(m));
  if (t.length) return v(3, t[0], ...hi(m, 2, t));
  if (p.length >= 2) return v(2, p[0], p[1], ...hi(m, 1, p.slice(0, 2)));
  if (p.length) return v(1, p[0], ...hi(m, 3, p));
  return v(0, ...hi(m, 5));
}
// your share of the pot at showdown against a weighted range {"AhKh": weight, ...}, over every runout still to come
function equity(hole, board, range) {
  const id = c => HC_UP.indexOf(c[0]) * 4 + "shdc".indexOf(c[1]);
  const h = hole.map(id), b = board.map(id), dead = new Set([...h, ...b]);
  const vs = Object.entries(range).map(([x, w]) => [id(x.slice(0, 2)), id(x.slice(2)), w]).filter(([x, y, w]) => w > 0 && !dead.has(x) && !dead.has(y));
  const deck = [...Array(52).keys()].filter(c => !dead.has(c));
  const runs = board.length === 5 ? [[]] : board.length === 4 ? deck.map(c => [c]) : deck.flatMap((c, i) => deck.slice(i + 1).map(d => [c, d]));
  let win = 0, tot = 0;
  for (const r of runs) {
    const full = [...b, ...r], me = strength([...h, ...full]);
    for (const [x, y, w] of vs) {
      if (r.includes(x) || r.includes(y)) continue;
      const them = strength([x, y, ...full]);
      win += me > them ? w : me === them ? w / 2 : 0; tot += w;
    }
  }
  return tot ? win / tot : NaN;
}

if (typeof module === "object" && require.main === module) {
  const t = (hole, board, want) => { const got = handClass(hole.split(" "), board.split(" ")).text; console.assert(got === want, `${hole} on ${board}: ${got} != ${want}`); };
  t("Ks 5s", "6c 3c 2h", "a gutshot");
  t("Ah Ad", "Kc 7d 2s", "an overpair");
  t("7h 7d", "7c Kd 2s", "a set");
  t("Kh Qd", "Kc 7d 2s", "top pair");
  t("Ah Qd", "Kc 7d 2s", "ace high");
  t("9h 8h", "7h 6c 2h", "a flush draw and an open-ended straight draw");
  t("Ah 5h", "Kh 9h 2h 3c", "a flush");
  t("5h 4c", "6d 3s 2h", "a straight");
  t("Kh 2d", "Kc 2s 7d", "two pair");
  t("7h 6h", "7c 7d Ks", "trips");
  t("Kh 7h", "Kc 7d 7s", "a full house");
  t("Qh Jd", "Ac Kd 3s 9h 2c", "no pair");
  t("Ah Kd", "Ac Kh 3s", "two pair");
  t("5h 4d", "6d 3d 2h 2d 8d", "a flush");
  console.assert(texture("6c 3c 2h".split(" ")) === "6-high, two-tone (flush draws possible), straights are possible", texture("6c 3c 2h".split(" ")));
  console.assert(texture("Ks 7d 2c".split(" ")) === "K-high, rainbow, no straight yet", texture("Ks 7d 2c".split(" ")));
  const S = h => strength(h.split(" ").map(c => HC_UP.indexOf(c[0]) * 4 + "shdc".indexOf(c[1])));
  const order = ["As Ks Qs Js Ts 2c 3d", "5h 4h 3h 2h Ah Kd Kc", "9c 9d 9h 9s 2c 3d 4h", "Kc Kd Kh 2s 2c 3d 4h", "Ac Jc 8c 4c 2c Kd Kh",
    "5d 4c 3h 2s Ac Kd Kh", "7c 7d 7h Ks 2c 3d 9h", "Kc Kd 9h 9s 2c 2d Ah", "Kc Kd 9h 9s 2c 3d 4h", "Ac Ad Kh Qs 2c 3d 7h", "Ac Kd Qh Js 9c 3d 2h"];
  for (let i = 1; i < order.length; i++) console.assert(S(order[i - 1]) > S(order[i]), `${order[i - 1]} should beat ${order[i]}`);
  console.assert(S("Ac Ad Kh Qs Jc 3d 2h") === S("Ah As Kd Qc Jh 4c 3s"), "same pair and kickers tie");
  console.assert(S("Kc Kd 9h 9s 2c 2d Ah") > S("Kc Kd 9h 9s 2c 2d Qh"), "two pair: the 5th card plays");
  console.assert(Math.abs(equity(["Ah", "Ad"], ["Kc", "7d", "2s", "3h", "9c"], { KhKd: 1 }) - 0) < 1e-9, "set beats aces");
  console.assert(Math.abs(equity(["Ah", "Kh"], ["2c", "7d", "9s", "Jc", "Qd"], { AdKd: 1 }) - .5) < 1e-9, "chop");
  const e = equity(["Ah", "Ad"], ["Kc", "7d", "2s"], { KhKd: 1 }); // 990 runouts: 87 bring an ace, 2 of those also the Ks (quads)
  console.assert(Math.abs(e - 85 / 990) < 1e-9, `AA vs set: ${e}`);
  console.log("handclass ok");
}
