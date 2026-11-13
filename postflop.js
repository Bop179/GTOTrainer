// Postflop (ROADMAP item 9): a preflop hand that ends heads-up in a solved single-raised pot plays on to the river.
// Flop and turn come from the VM pre-solves (post/ from solver/pull_post.sh, else straight from the VM's Caddy); the river is solved live (river.js).
// Everything runs in the solver's suits: the solved flop is shown with its suits relabelled (P.sig), and your preflop
// cards are mapped back into solver suits. Uses index.html's globals ($, st, pick, bb, play, tally, ...) at call time.
window.POST = {};
const PI = window.POST_INDEX || {};
const SUIT = "shdc"; // SUITS order in index.html
const UP = "23456789TJQKA";
const scenOf = (game, stack, opener, caller) => PI[`${game}_${stack}_${opener}_v_${caller}`] && `${game}_${stack}_${opener}_v_${caller}`;
const postGames = () => Object.keys(PI).map(s => s.split("_").slice(0, 2).join("/"));

// "Play to postflop": a preflop spot that leads into a solved matchup (an open from the opener's seat, or the caller
// facing that open), with a hand that opens or calls there. The others are scripted to let it through (see postReply).
function postDeal(g, pos) {
  const [game, stack] = g.split("/"), opts = [];
  for (const scen of Object.keys(PI)) {
    const [gm, sk, opener, , caller] = scen.split("_");
    if (gm !== game || sk !== stack) continue;
    for (const [hero, key, col] of [[opener, `${g}/${opener}/RFI`, 1], [caller, `${g}/${opener}/${caller}/FACINGRFI`, 2]])
      if (SPOTS[key] && (!pos.length || pos.includes(hero))) opts.push({ scen, key, col });
  }
  if (!opts.length) return null;
  const o = opts[Math.floor(Math.random() * opts.length)], rows = SPOTS[o.key];
  return { spot: parse(o.key), i: pick(rows.map((r, k) => COMBOS(HANDS[k]) * r[4] * r[o.col])), scen: o.scen };
}
// with "Play to postflop" on: you made the move that leads to the flop, so the scripted caller calls and the rest fold
function postReply(c, a) {
  if (!c.scen) return null;
  const [, , opener, , caller] = c.scen.split("_");
  if (c.spot.node === "RFI" && a === "Raise" && c.z.raise < c.z.S) return { text: `${caller} calls and the rest fold: on to the flop!`, post: c.scen };
  if (c.spot.node === "FACINGRFI" && a === "Call") return { text: `The rest fold: heads-up with ${opener} to the flop!`, post: c.scen };
  return null;
}

// ---------- data: each piece is a script setting POST[path] to base64 gzipped JSON ----------
function loadPiece(path) {
  return new Promise((ok, bad) => {
    const s = document.createElement("script");
    s.src = `${POST_BASE}${path}.js`; s.onload = ok; s.onerror = () => bad(new Error(`${POST_BASE}${path}.js is missing (run solver/pull_post.sh, or the VM is down)`));
    document.head.append(s); s.remove();
  }).then(() => {
    const b = Uint8Array.from(atob(POST[path]), x => x.charCodeAt(0)); delete POST[path];
    return new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream("gzip"))).json();
  });
}

// ---------- cards (solver spelling: "Ah"; a hand is the higher card first, as the solver writes it) ----------
const cid = x => UP.indexOf(x[0]) * 4 + "cdhs".indexOf(x[1]);
const holeStr = (x, y) => cid(x) > cid(y) ? x + y : y + x;
const cardsOf = h => [h.slice(0, 2), h.slice(2)];
const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
function cardHTML(x, cls = "") { // x in solver suits, shown in table suits
  const [sym, red] = SUITS[SUIT.indexOf(P.sig[x[1]])];
  return `<div class="card${red ? " red" : ""}${cls}">${x[0] === "T" ? "10" : x[0]}<span>${sym}</span></div>`;
}
const cardText = x => (x[0] === "T" ? "10" : x[0]) + SUITS[SUIT.indexOf(P.sig[x[1]])][0];
function dealOne() {
  const used = new Set([...P.board, ...P.hands.flatMap(cardsOf)]);
  const deck = [...UP].flatMap(r => [...SUIT].map(s => r + s)).filter(x => !used.has(x));
  return deck[Math.floor(Math.random() * deck.length)];
}

// ---------- the hand ----------
let P = null; // the postflop hand: st.cur while it plays
const cur = () => P.nodes[P.k];
const potNow = () => P.pot0 + P.spent[0] + P.spent[1];
const STREET = ["Flop", "Turn", "River"];
const kind = a => a.split(" ")[0]; // Check, Call, Fold, Bet, Raise, Allin
const amt = a => +a.split(" ")[1] || 0;
const AC = { Fold: "var(--fold)", Check: "var(--call)", Call: "var(--call)", Bet: "var(--raise)", Raise: "var(--raise)", Allin: "var(--allin)" };
function actName(a) { // button text
  const k = kind(a), x = amt(a), p = cur().player, call = P.put[1 - p] - P.put[p];
  if (k === "Bet") return `Bet ${bb(x)} (${Math.round(x / potNow() * 100)}%)`;
  if (k === "Raise") return `Raise to ${bb(x)}`;
  if (k === "Allin") return `All-in ${bb(P.stack - P.spent[p] + P.put[p])}`;
  return k === "Call" ? `Call ${bb(call)}` : k;
}
// button: the action's name, then its amount on a second, smaller line (bets: small up to half pot, big up to pot, overbet past it)
function btnLabel(a, i) {
  const k = kind(a), x = amt(a), pct = Math.round(x / potNow() * 100), sub = t => `<small class="amt">${t}</small>`;
  const key = `<kbd>${i + 1}</kbd>`;
  if (k === "Bet") return `Bet ${pct <= 50 ? "small" : pct <= 100 ? "big" : "overbet"}${key}${sub(`${bb(x)} · ${pct}%`)}`;
  if (k === "Raise") return `Raise${key}${sub(`to ${bb(x)}`)}`;
  if (k === "Allin" || k === "Call") return `${k === "Call" ? "Call" : "All-in"}${key}${sub(actName(a).split(" ").at(-1))}`;
  return k + key;
}
function say(p, a, add) {
  const me = p === P.me, k = kind(a), x = amt(a);
  const v = { Check: ["check", "checks"], Call: ["call", "calls"], Fold: ["fold", "folds"], Bet: ["bet", "bets"], Raise: ["raise to", "raises to"], Allin: ["go all-in", "goes all-in"] }[k][me ? 0 : 1];
  return `${me ? "you" : P.seat[p]} ${v}${k === "Bet" || k === "Raise" ? " " + bb(x) : k === "Call" ? " " + bb(add) : ""}`;
}
const say0 = s => s[0].toUpperCase() + s.slice(1);

// preflop just closed heads-up in a solved matchup (c.post = scenario): deal the flop and play on
async function postBegin(c) {
  replayTimers.forEach(clearTimeout);
  const scen = c.post, m = PI[scen], me = m.oop === c.spot.hero ? 0 : 1;
  c.post = null; // a second Space while the flop loads doesn't deal twice
  $("feedback").classList.remove("show");
  $("actions").innerHTML = ""; $("situation").textContent = "Dealing the flop…";
  // random suit relabel (solver suit -> table suit), then a solved flop that misses your cards in solver suits
  let sig, mine, flop;
  for (let t = 0; t < 24 && !flop; t++) {
    const perm = shuffle([...SUIT]); sig = Object.fromEntries([...SUIT].map((s, i) => [s, perm[i]]));
    const back = Object.fromEntries(Object.entries(sig).map(([s, d]) => [d, s]));
    mine = c.cards.map(([r, sy]) => r + back[SUIT[SUITS.indexOf(sy)]]);
    flop = shuffle([...m.flops]).find(f => !cardsOf(f).concat(f.slice(4)).some(x => mine.includes(x)));
  }
  let nodes;
  try { nodes = await loadPiece(`${scen}/${flop}/flop`); } catch (e) { $("situation").textContent = e.message; return; }
  const [, , opener, , caller] = scen.split("_");
  const hero = holeStr(...mine), vr = nodes[me ? "" : "0"], hr = nodes[me ? "0" : ""]; // villain's / your range at the flop
  P = { postflop: true, scen, me, sig, seat: [m.oop, m.ip], pot0: m.pot, stack: m.stack, board: [flop.slice(0, 2), flop.slice(2, 4), flop.slice(4)],
    flop, nodes, k: "", street: 0, spent: [0, 0], put: [0, 0], tag: ["", ""], hist: [], over: false, answered: false, cards: c.cards, isNew: 3,
    // the hand so far: street names ({s}) and actions ({t, k}); a closing message ({t, end}) when it's over
    story: [{ s: "Preflop" }, { t: `${opener === c.spot.hero ? "you open" : opener + " opens"} ${bb(100 - m.stack)}`, k: "Raise" }, { t: caller === c.spot.hero ? "you call" : caller + " calls", k: "Call" }] };
  P.hands = [];
  P.hands[me] = hero;
  P.hands[1 - me] = vr.hands[pick(vr.hands.map((h, i) => cardsOf(h).some(x => mine.includes(x)) ? 0 : vr.reach[i]))];
  P.story.push({ s: "Flop" }); // the cards are on the board; the story only says who did what
  st.cur = P;
  if (!hr.hands.includes(hero)) end(`${HANDS[c.i]} isn't in the solved range at the flop (the solver doesn't play it this way preflop), so the hand ends here.`);
  postDraw(true);
  if (!P.over) { P.busy = true; await run(); P.busy = false; postDraw(false); }
}

// apply action i at the current node, for whoever is to act; deals the next card when a street closes
// hold: your own action closed the street; the next card waits until you continue (closeStreet from postNext)
async function step(i, hold) {
  const node = cur(), p = node.player, a = node.actions[i], k = kind(a);
  let add = 0;
  if (k === "Call") add = P.put[1 - p] - P.put[p];
  if (k === "Bet" || k === "Raise" || k === "Allin") add = amt(a) - P.put[p];
  P.put[p] += add; P.spent[p] += add;
  P.hist.push({ street: P.street, node, p, i });
  P.tag[p] = k === "Allin" ? "All-in" : k;
  P.story.push({ t: say(p, a, add), k });
  if (k === "Fold") return end(`${say0(P.me === p ? `${P.seat[1 - p]} takes` : "you take")} the ${bb(potNow() - P.put[1 - p] + P.put[p])} pot.`); // the uncalled bet goes back
  const nk = P.k ? P.k + "-" + i : String(i);
  if (P.nodes[nk]) { P.k = nk; return; }
  // street over: a call, or a check behind. Let it land on the table before the chips go in and the next card comes
  P.nk = nk; P.closing = true;
  if (hold) return;
  postDraw(false); await new Promise(r => setTimeout(r, 700));
  return closeStreet();
}
async function closeStreet() {
  const nk = P.nk; P.closing = false;
  if (P.spent[0] >= P.stack - .01 && P.spent[1] >= P.stack - .01) {
    while (P.board.length < 5) P.board.push(dealOne());
    return end(`All-in: ${P.seat[1 - P.me]} shows ${cardsOf(P.hands[1 - P.me]).map(cardText).join("")}.`, true);
  }
  if (P.street === 2) return end(`Showdown: ${P.seat[1 - P.me]} shows ${cardsOf(P.hands[1 - P.me]).map(cardText).join("")}.`, true);
  const c = dealOne();
  P.board.push(c); P.street++; P.put = [0, 0]; P.tag = ["", ""]; P.isNew = P.board.length - 1;
  P.story.push({ s: STREET[P.street] });
  if (P.street === 1) {
    const turn = await loadPiece(`${P.scen}/${P.flop}/${c}`);
    P.nodes = { ...P.nodes, ...turn }; P.k = nk + "-" + c;
    // ponytail: the pre-solve keeps turns only after an unraised flop; a live turn solve would cover the rest
    if (!P.nodes[P.k]) return end("The flop was raised, and turns after a raised flop aren't solved yet, so the hand ends here.");
  } else {
    $("situation").textContent = "Solving the river…";
    await new Promise(r => setTimeout(r, 30)); // let the text paint: the solve blocks the page
    P.nodes = (await RiverSolver.solve(riverJob())).nodes; P.k = "";
  }
}
// each player's river range: reach × the frequency of the action they took at their last turn decision, scaled to 0..1.
// Both real hands keep a small weight, so a hand that took a 0% line still plays on.
// ponytail: "reach" carries a card-removal factor from the other range; small, ignored.
function riverJob() {
  const r = [0, 1].map(p => {
    const h = P.hist.filter(x => x.street === 1 && x.p === p).at(-1), w = {};
    h.node.hands.forEach((x, j) => { const v = h.node.reach[j] * h.node.strat[h.i][j]; if (v > 0) w[x] = v; });
    const top = Math.max(...Object.values(w), 1e-9);
    for (const x in w) { w[x] = Math.min(1, w[x] / top); if (cardsOf(x).includes(P.board[4]) || w[x] < .0005) delete w[x]; }
    w[P.hands[p]] = Math.max(w[P.hands[p]] || 0, .001);
    return w;
  });
  return { oop: r[0], ip: r[1], board: P.board.join(""), pot: potNow(), stack: P.stack - P.spent[0],
    river_sizes: ["33%, 75%, 125%", "2.5x"], target: 0.01, max_iter: 300 };
}
const strat = (node, hand) => {
  const h = node.hands.indexOf(hand);
  if (h >= 0) return node.strat.map(s => s[h]);
  return node.strat.map(s => s.reduce((t, x, j) => t + x * node.reach[j], 0)); // trimmed hand: the range's average
};
// the villain acts until it's your turn or the hand ends
// one action at a time, like preflop: a beat, then the action lands on the table
async function run() {
  try {
    while (!P.over && cur().player !== P.me) {
      await new Promise(r => setTimeout(r, 650));
      await step(pick(strat(cur(), P.hands[1 - P.me])));
      postDraw(false);
    }
  } catch (e) { return end(e.message); }
  if (!P.over && !cur().hands.includes(P.hands[P.me])) end("The solver never gets here with your hand, so the hand ends.");
}
function end(text, show) { P.over = true; P.show = show; P.story.push({ t: text, end: true }); }

// redraws the table; whatever changed since the last draw animates as in preflop: bets slide in, a fold tosses its cards
function postDraw(fresh) {
  const me = P.me, them = 1 - me, was = P.drawn || { put: [0, 0], tag: ["", ""] }, mine = !P.over && !P.closing && cur().player === me;
  const key = JSON.stringify([P.put, P.tag, P.spent, P.board, P.over, P.show, mine, P.story]);
  if (!fresh && key === P.drawnKey) return postButtons(mine); // nothing new: don't cut a running animation short
  P.drawn = { put: [...P.put], tag: [...P.tag] }; P.drawnKey = key;
  const moved = p => P.put[p] && P.put[p] !== was.put[p], folds = p => P.tag[p] === "Fold" && was.tag[p] !== "Fold";
  if (moved(them)) play("chip");
  if (folds(them) || P.isNew < P.board.length) play("deal");
  const rows = []; // one row per street, shown once someone acts on it
  for (const x of P.story) if (x.s) rows.push([x.s]); else if (!x.end) rows.at(-1).push(x);
  $("situation").innerHTML = `<div class="hist">${rows.filter(r => r.length > 1).map(([s, ...xs]) =>
    `<b>${s}</b><div>${xs.map(x => `<span style="--c:${AC[x.k]}">${say0(x.t)}</span>`).join("")}</div>`).join("")}</div>`
    + P.story.filter(x => x.end).map(x => `<div class="end">${x.t}</div>`).join("");
  const seat = (p, s) => `<div class="seat${p === me ? " hero" : ""}${P.tag[p] === "Fold" ? " folded" : ""}${p === me && mine ? " turn" : ""}${folds(p) ? " toss" : ""}" style="--c:0;--s:${s};--r:1">`
    + (p === me || P.show ? `<div class="cards">${cardsOf(P.hands[p]).map(x => cardHTML(x)).join("")}</div>`
      : `<div class="backs">${P.tag[p] !== "Fold" || folds(p) ? "<i></i><i></i>" : ""}</div>`)
    + `<div class="plate"><b>${p === me ? "You · " : ""}${P.seat[p]}</b><span>${bb(P.stack - P.spent[p])}</span></div>`
    + `<em class="tag"${P.tag[p] ? ` style="background:${AC[kind(P.tag[p] === "All-in" ? "Allin" : P.tag[p])]}"` : " hidden"}>${P.tag[p]}</em></div>`
    + (P.put[p] ? `<div class="bet post${moved(p) ? " fly" : ""}" style="--c:${p === me ? .35 : .4};--s:${p === me ? .68 : -.66};--r:1;--y0:${50 + s * 41}%">${bb(P.put[p])}</div>` : "");
  $("felt").classList.toggle("still", !fresh);
  $("felt").innerHTML = seat(them, -1) + seat(me, 1)
    + `<div class="board">${P.board.map((x, j) => cardHTML(x, j >= P.isNew ? " new" : "")).join("")}</div>`
    + `<div class="pot" style="left:74%;top:64%">Pot <b>${bb(potNow() - P.put[0] - P.put[1])}</b></div>`;
  P.isNew = 9;
  postButtons(mine);
}
function postButtons(mine) {
  if (!P.over && (!mine || P.busy)) return document.querySelectorAll("#actions button").forEach(b => b.disabled = true); // their move: keep your last buttons, greyed
  if (P.over) { P.answered = true; $("actions").innerHTML = `<button data-next style="background:var(--panel)">Next hand<kbd>Space</kbd></button>`; return; }
  $("actions").innerHTML = cur().actions.map((a, i) => `<button data-a="${i}" style="background:${AC[kind(a)]}">${btnLabel(a, i)}</button>`).join("");
}

// a short read of the spot: what you hold, the board, the price, where your hand sits in your range,
// and what the solver does with hands like it (the classification is local rules; the numbers are the solver's)
function postExplain(node, h) {
  const out = [], board = P.board, me = P.me, hc = handClass(cardsOf(P.hands[me]), board);
  out.push(`You have ${hc.text}. The board is ${texture(board)}.`);
  // the maths: equity needed to call, and a draw's outs by the rule of 2 and 4
  const call = P.put[1 - me] - P.put[me], need = call / (potNow() + call) * 100, f1 = x => +x.toFixed(1);
  if (call > 0) out.push(`Equity needed to call = call ÷ (pot + call) = ${f1(call)} ÷ (${f1(potNow())} + ${f1(call)}) = ${f1(call)} ÷ ${f1(potNow() + call)} = <b>${f1(need)}%</b>.`);
  if (hc.draw) {
    const hole = cardsOf(P.hands[me]), used = new Set([...hole, ...board]), left = 52 - used.size;
    const BIG = ["a straight", "a flush", "a full house", "quads"];
    const outs = [...UP].flatMap(r => [...SUIT].map(s => r + s)).filter(c => !used.has(c) && BIG.includes(handClass(hole, [...board, c]).made)).length;
    const next = outs * 2, both = outs * 4, allin = call > 0 && call >= P.stack - P.spent[me] - .01;
    const goal = [hc.draw.includes("flush") && "flush", hc.draw.includes("straight") || hc.draw.includes("gutshot") ? "straight" : ""].filter(Boolean).join(" or ");
    out.push(`Outs: <b>${outs}</b> cards make your ${goal}. Next card ≈ ${outs} × 2 = <b>${next}%</b> (exactly ${outs} ÷ ${left} = ${f1(outs / left * 100)}%)`
      + (board.length === 3 ? `; by the river ≈ ${outs} × 4 = <b>${both}%</b>, but only if you get to see both cards.` : "."));
    if (call > 0) {
      // compare exact odds: one card, or both when this call is all-in on the flop
      const have = 100 * (board.length === 3 && allin ? 1 - (left - outs) / left * (left - 1 - outs) / (left - 1) : outs / left);
      out.push(have >= need ? `${f1(have)}% ≥ ${f1(need)}%: the draw alone pays for the call.`
        : `${f1(have)}% < ${f1(need)}%: the draw alone doesn't pay for the call${board.length === 3 && !allin ? " on one card" : ""}; it needs extra from money you win when you hit (implied odds), hitting a pair instead, or a later bluff.`);
    }
  }
  // your range here ranked by the solver's EV for each hand (best action)
  const best = j => Math.max(...node.ev.map(e => e[j])), mine = best(h);
  let tot = 0, above = 0;
  node.hands.forEach((_, j) => { const w = node.reach[j]; if (!w) return; tot += w; if (best(j) > mine) above += w; });
  const topPct = Math.max(1, Math.round(above / (tot || 1) * 100));
  out.push(`By the solver's EV, about ${topPct}% of the hands you'd have here do better than yours: ${topPct <= 25 ? "near the top of your range" : topPct <= 60 ? "the middle of your range" : "the bottom part of your range"}.`);
  // hands in the same group: same made hand and draw; if that's thin, same made hand only
  const cls = node.hands.map(x => handClass(cardsOf(x), board));
  const group = by => node.hands.map((_, j) => j).filter(j => node.reach[j] > 0 && by(cls[j]));
  let g = group(c => c.made === hc.made && c.draw === hc.draw), label = hc.text;
  if (g.length < 6) { g = group(c => c.made === hc.made); label = hc.made; }
  if (g.length >= 2) {
    const w = g.reduce((t, j) => t + node.reach[j], 0) || 1;
    const mix = node.actions.map((a, k) => [actName(a), g.reduce((t, j) => t + node.strat[k][j] * node.reach[j], 0) / w]).filter(([, v]) => v >= .5).sort((x, y) => y[1] - x[1]);
    out.push(`Hands like yours (${label}, ${g.length} combos): ${mix.map(([n, v]) => `${n} ${Math.round(v)}%`).join(" · ")}.`);
  }
  return out;
}

// graded by frequency first, EV second: EV gaps of a few % of the pot are solver noise (a 35% action can trail by that much),
// so a small gap can't rescue an action the solver (almost) never takes.
// right: played 25%+, or 5%+ and within 2% of the pot. acceptable: played 5%+, or 1%+ and within 5%, or under 1% and within 1%.
// ponytail: thresholds are a judgment call
async function postAnswer(i) {
  if (P.over || P.answered || P.busy || !cur().actions[i]) return;
  P.answered = P.busy = true;
  const node = cur(), h = node.hands.indexOf(P.hands[P.me]), f = node.strat[i][h], ev = node.ev.map(e => e[h]);
  const best = ev.indexOf(Math.max(...ev)), loss = ev[best] - ev[i], pot = potNow();
  const grade = f >= 25 || f >= 5 && loss <= .02 * pot ? "great" : f >= 5 || f >= 1 && loss <= .05 * pot || loss <= .01 * pot ? "ok" : "bad";
  tally(grade); play(kind(node.actions[i]) === "Fold" ? "deal" : "chip");
  stamp(String(i), j => node.strat[j][h], j => ev[j].toFixed(2) + "bb");
  const btns = $("actions").innerHTML; // the graded buttons stay up until you continue, though the hand has moved on
  const names = node.actions.map(actName), hand = cardsOf(P.hands[P.me]).map(cardText).join("");
  $("verdict").className = "verdict " + grade;
  $("verdict").textContent = { great: "✓ Correct", ok: "≈ Acceptable", bad: "✗ Mistake" }[grade];
  const pill = (j, v) => `<span class="pill" style="--c:${AC[kind(node.actions[j])]}"><span>${names[j]}</span><b>${Math.round(v)}%</b></span>`;
  // whole range at this node, weighted by reach
  const tot = node.reach.reduce((x, y) => x + y, 0) || 1, rm = node.strat.map(s => s.reduce((t, x, j) => t + x * node.reach[j], 0) / tot);
  $("range").innerHTML = `<h4>Whole range · ${P.seat[P.me]} on the ${STREET[P.board.length - 3].toLowerCase()}</h4>
    <div class="mix">${rm.map((v, j) => v >= .5 ? `<div style="background:${AC[kind(node.actions[j])]};width:${v}%"></div>` : "").join("")}</div>
    <div class="pills">${rm.map((v, j) => v >= .5 ? pill(j, v) : "").join("")}</div>`;
  $("grid").innerHTML = gridHTML(classRows(node), "POST", HANDS.indexOf(classOf(P.hands[P.me])));
  const why = [`<b>${hand}</b> on ${P.board.map(cardText).join(" ")}, pot ${bb(pot)}, ${P.me ? "in" : "out of"} position.`, ...postExplain(node, h),
    i === best ? "You picked the highest-EV action." : `Your pick gives up ${loss.toFixed(2)}bb against ${names[best]}${f >= 25 ? ", but the solver plays it often enough here that the gap is noise" : f < 1 ? ", and the solver never plays it here" : ""}.`,
    "~Hand groups and board reads come from simple local rules; the percentages and EVs are the solver's."];
  try { await step(i, true); } catch (e) { end(e.message); }
  P.busy = false;
  postDraw(false);
  $("actions").innerHTML = btns;
  $("why").innerHTML = why.map(p => `<p${p.startsWith("~") ? ' class="muted"' : ""}>${p.replace(/^~/, "")}</p>`).join("");
  $("next").innerHTML = P.over ? "Next hand <kbd>Space</kbd>" : "Continue hand ▸<kbd>Space</kbd>";
  $("feedback").classList.add("show");
}
async function postNext() {
  if (P.over || P.busy) return P.busy || newHand();
  $("feedback").classList.remove("show");
  P.busy = true;
  if (P.closing) { try { await closeStreet(); } catch (e) { end(e.message); } postDraw(false); }
  await run(); P.busy = false; P.answered = false;
  postDraw(false);
}
// the node's strategy folded into the 13×13 chart: [all-in, bet/raise, check/call, fold, reach 0..1] per hand class
const classOf = h => { const [a, b] = [h[0], h[2]]; return a === b ? a + b : a + b + (h[1] === h[3] ? "s" : "o"); };
function classRows(node) {
  const rows = HANDS.map(() => [0, 0, 0, 0, 0]), col = { Allin: 0, Bet: 1, Raise: 1, Check: 2, Call: 2, Fold: 3 };
  node.hands.forEach((x, j) => {
    const r = rows[HANDS.indexOf(classOf(x))], w = node.reach[j];
    node.actions.forEach((a, k) => r[col[kind(a)]] += w * node.strat[k][j]); r[4] += w;
  });
  const top = Math.max(...rows.map((r, k) => r[4] / COMBOS(HANDS[k]))) || 1;
  rows.forEach((r, k) => { if (r[4]) { for (let q = 0; q < 4; q++) r[q] /= r[4]; r[4] = r[4] / COMBOS(HANDS[k]) / top; } else r[3] = 100; });
  return rows;
}
