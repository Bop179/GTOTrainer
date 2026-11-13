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
  console.log("handclass ok");
}
