// Postflop (ROADMAP item 9): a preflop hand that ends heads-up in a solved single-raised pot plays on to the river.
// Flop and turn come from the VM pre-solves (loaded one piece at a time from the VM's Caddy); the river is solved live (river.js).
// Everything runs in the solver's suits: the solved flop is shown with its suits relabelled (P.sig), and your preflop
// cards are mapped back into solver suits. Uses index.html's globals ($, st, pick, bb, play, tally, ...) at call time.
// PI: the VM's index of solved pots, {scenario: {oop, ip, flops, pot, stack}}. Empty until the fetch below lands (or for good, VM down).
// 9-max shares the 8-max solves once UTG has folded (its ranges there are the 8-max ones, see index.html): the same pot with
// the seats renamed, and src naming the 8-max scenario whose pieces it loads.
let PI = {};
const to9max = p => ({ UTG: "UTG1", UTG1: "UTG2" })[p] || p;
function setIndex(idx) {
  PI = { ...idx };
  for (const [scen, m] of Object.entries(idx)) {
    const p = scen.split("_");
    if (p[0] === "8max") PI[["9max", p[1], ...p.slice(2).map(to9max)].join("_")] = { ...m, oop: to9max(m.oop), ip: to9max(m.ip), src: scen };
  }
}
setIndex(window.POST_INDEX || {}); // only set by solver/test_postways.js
const SUIT = "shdc"; // SUITS order in index.html
const UP = "23456789TJQKA";
// The two players' last preflop decisions into a solved pot, as [seat, spot key, column: 1 raise, 2 call]; the second one
// is the call (or the BB's check) that closes preflop. Scenario names are solver/make_jobs.py's: seats are parts [2] and [4],
// the kind is [5], and squeezes and cold 4-bets name the opener (who folds) in [6].
function ways(scen) {
  const [g, sk, a, , b, kind = "", o] = scen.split("_"), K = (...p) => [g, sk, ...p].join("/");
  return {
    "": [[a, K(a, "RFI"), 1], [b, K(a, b, "FACINGRFI"), 2]],
    "3bet": [[b, K(a, b, "FACINGRFI"), 1], [a, K(b, a, "FACING3B"), 2]],
    "4bet": [[a, K(b, a, "FACING3B"), 1], [b, K(a, b, "FACING4B"), 2]],
    limp: [[a, K(a, "RFI"), 2], [b, K(a, b, "FACINGLIMP"), 2]],
    limpraise: [[b, K(a, b, "FACINGLIMP"), 1], [a, K(b, a, "LIMP_FACING2B"), 2]],
    sqz: [[b, K(`${o}+${a}`, b, "FACINGRFI_CALL"), 1], [a, K(`${o}+${b}`, a, "FACINGSQZ_CALLER"), 2]],
    c4b: [[b, K(`${o}+${a}`, b, "FACING3B_COLD"), 1], [a, K(`${o}+${b}`, a, "FACINGC4B_3B"), 2]],
  }[kind];
}
const colOf = a => a === "Raise" ? 1 : a === "Call" ? 2 : 0;
// the solved pot that action a at spot s leads to, when `closer` makes the closing call (you, unless someone calls you)
const postScen = (s, a, closer = s.hero) => Object.keys(PI).find(scen => {
  const w = ways(scen);
  return w && w[1][0] === closer && w.some(([, key, col]) => key === s.key && col === colOf(a));
});
const postGames = () => Object.keys(PI).map(s => s.split("_").slice(0, 2).join("/"));

// "Play to postflop": a preflop spot that leads into a solved pot, with a hand that takes the line there (see ways).
// The others are scripted to let it through (see postReply).
function postDeal(g, pos) {
  const [game, stack] = g.split("/"), opts = [];
  for (const scen of Object.keys(PI)) {
    const [gm, sk] = scen.split("_");
    if (gm !== game || sk !== stack) continue;
    for (const [hero, key, col] of ways(scen) || [])
      if (SPOTS[key] && (!pos.length || pos.includes(hero)) && SPOTS[key].some((r, k) => r[4] * r[col] && handOk(HANDS[k]))) opts.push({ scen, key, col });
  }
  if (!opts.length) return null;
  const o = opts[Math.floor(Math.random() * opts.length)], rows = SPOTS[o.key];
  return { spot: parse(o.key), i: pick(rows.map((r, k) => COMBOS(HANDS[k]) * r[4] * r[o.col] * handOk(HANDS[k]))), scen: o.scen };
}
// with "Play to postflop" on: you made the move that leads to the flop, so the scripted closer calls and the rest fold
function postReply(c, a) {
  if (!c.scen) return null;
  const w = ways(c.scen), mine = w.find(([, key]) => key === c.spot.key);
  if (!mine || colOf(a) !== mine[2] || a === "Raise" && c.z.raise >= c.z.S) return null;
  const o = c.scen.split("_")[6], [p, key] = w[1], v = key.endsWith("FACINGLIMP") ? "check" : "call";
  const text = mine === w[1] ? `You ${v}: on to the flop!` : `${o ? o + " folds, " : "The rest fold, "}${p} ${v}s: on to the flop!`;
  return { text, post: c.scen };
}

// ---------- data: each piece is a gzipped binary file on the VM (format in solver/split.py) ----------
// swap: [a, b] reads a piece stored for suit a as suit b (turns in suits the flop lacks are stored once, see split.py)
// The index is fetched as data and parsed, never run: the page is up before it arrives, a VM that is down or slow costs
// nothing but postflop, and whoever answers at that address can't run code here. index.js is "POST_INDEX={...};" (split.py).
// If the VM doesn't answer it's asked again every 5 s, five more times (preflop plays on meanwhile); after that, no postflop this visit.
(function getIndex(left) {
  fetch(POST_BASE + "index.js", { signal: AbortSignal.timeout(15000) }).then(r => r.ok ? r.text() : Promise.reject())
    .then(t => JSON.parse(t.slice(t.indexOf("{"), t.lastIndexOf("}") + 1)))
    .then(idx => {
      setIndex(idx);
      try {
        drawSettings(); // the Streets row can show now
        // "Postflop only" was saved, and the hand dealt before the index came hasn't been played: deal the hand it asks for
        if (toPost() && st.cur?.steps && !st.cur.answered && !undos.length) newHand();
      } catch {} // the page's own script hasn't run yet: it draws with the index when it does
    }, () => left && setTimeout(getIndex, 5000, left - 1));
})(5);
async function loadPiece(path, swap) {
  const url = `${POST_BASE}${path}.bin`;
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(15000) }); // a stalled VM ends the hand with the message below, not a spinner forever
    if (!r.ok) throw 0;
    return decodePiece(await new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer(), swap);
  } catch { throw new Error(`${url} didn't load (the VM is down, or that flop isn't solved yet)`); }
}
function decodePiece(buf, swap) {
  const v = new DataView(buf), hl = v.getUint32(0, true), head = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, hl)));
  const sx = x => !swap ? x : x[0] + (x[1] === swap[0] ? swap[1] : x[1] === swap[1] ? swap[0] : x[1]);
  const c52 = i => sx(UP[i >> 2] + SUIT[i & 3]), out = {};
  let o = 4 + hl;
  for (const [k, player, actions, h] of head) {
    const hands = [], reach = [], strat = [], ev = [];
    for (let i = 0; i < h; i++, o += 2) { const c = v.getUint16(o, true); hands.push(holeStr(c52(Math.floor(c / 52)), c52(c % 52))); }
    for (let i = 0; i < h; i++, o += 4) reach.push(v.getUint32(o, true) / 1000);
    for (const _ of actions) { strat.push(Array.from(new Uint8Array(buf, o, h))); o += h; }
    for (const _ of actions) { const row = []; for (let i = 0; i < h; i++, o += 4) row.push(v.getInt32(o, true) / 100); ev.push(row); }
    out[k.split("-").map(t => t.length === 2 && SUIT.includes(t[1]) ? sx(t) : t).join("-")] = { player, actions, hands, reach, strat, ev };
  }
  return out;
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
// size as a fraction of the pot: 1/3 pot, 3/4 pot, pot, 1.5× pot; a size off every fraction reads 70% pot (or 1.8× pot past the pot)
const fracText = f => { for (const [n, d] of [[1, 4], [1, 3], [1, 2], [2, 3], [3, 4]]) if (Math.abs(f - n / d) < .03) return `${n}/${d} pot`;
  return Math.abs(f - 1) < .03 ? "pot" : f > 1 ? `${+f.toFixed(2)}× pot` : `${Math.round(f * 100)}% pot`; };
const potFrac = x => fracText(x / potNow());
const AC = { Fold: "var(--fold)", Check: "var(--call)", Call: "var(--call)", Bet: "var(--raise)", Raise: "var(--raise)", Allin: "var(--allin)" };
function actName(a) { // button text
  const k = kind(a), x = amt(a), p = cur().player, call = P.put[1 - p] - P.put[p];
  if (k === "Bet") return `Bet ${bb(x)} (${potFrac(x)})`;
  if (k === "Raise") return `Raise to ${bb(x)}`;
  if (k === "Allin") return `All-in ${bb(P.stack - P.spent[p] + P.put[p])}`;
  return k === "Call" ? `Call ${bb(call)}` : k;
}
// button: the action's name, then its amount on a second, smaller line (bets: small up to half pot, big up to pot, overbet past it)
function btnLabel(a, i) {
  const k = kind(a), x = amt(a), pct = Math.round(x / potNow() * 100), sub = t => `<small class="amt">${t}</small>`;
  const key = `<kbd>${i + 1}</kbd>`;
  if (k === "Bet") return `Bet ${pct <= 50 ? "small" : pct <= 100 ? "big" : "overbet"}${key}${sub(`${bb(x)} · ${potFrac(x)}`)}`;
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
  c.post = null; c.busy = true; // a second Space while the flop loads doesn't deal twice, and undo waits for it
  RiverSolver.load().catch(() => {}); // fetch the river solver now, so it's there by the river (a failure shows when the river is solved)
  $("feedback").classList.remove("show");
  const from = fromSt();
  $("actions").innerHTML = "";
  // starting on the turn or river: the streets before it play out unseen (fast), and a line that ends early is replayed on
  // the same flop, so you only ever see a hand that gets to your street
  if (from) { $("felt").innerHTML = ""; $("situation").innerHTML = `<span class="spin"></span>Finding a hand that reaches the ${STREET[from].toLowerCase()}…`; }
  else $("situation").textContent = "Dealing the flop…";
  // random suit relabel (solver suit -> table suit), then a solved flop that misses your cards in solver suits
  let sig, mine, flop;
  for (let t = 0; t < 24 && !flop; t++) {
    const perm = shuffle([...SUIT]); sig = Object.fromEntries([...SUIT].map((s, i) => [s, perm[i]]));
    const back = Object.fromEntries(Object.entries(sig).map(([s, d]) => [d, s]));
    mine = c.cards.map(([r, sy]) => r + back[SUIT[SUITS.indexOf(sy)]]);
    flop = shuffle([...m.flops]).find(f => !cardsOf(f).concat(f.slice(4)).some(x => mine.includes(x)));
  }
  let nodes;
  try { nodes = await loadPiece(`${m.src || scen}/${flop}/flop`); } catch (e) { c.busy = false; $("situation").textContent = e.message; return; }
  if (st.cur !== c) return; // a new hand was dealt while this flop loaded (a settings change)
  const [p0, key0] = ways(scen)[1], z0 = sizing(parse(key0)), who = (p, v1, v3) => p === c.spot.hero ? "you " + v1 : `${p} ${v3}`;
  const VERB = { Limp: ["limp", "limps"], Call: ["call", "calls"], Check: ["check", "checks"], Fold: ["fold", "folds"], Open: ["open", "opens"] };
  const told = ([p, to, tag]) => { // a preflop bet from sizing()'s line, as a story entry
    const [v1, v3] = VERB[tag] || [`${tag.toLowerCase()} to`, `${tag.toLowerCase()}s to`];
    return { t: who(p, v1, v3) + (VERB[tag] && tag !== "Open" ? "" : " " + bb(to)), k: tag === "Fold" ? "Fold" : ["Limp", "Call", "Check"].includes(tag) ? "Call" : "Raise" };
  };
  const hero = holeStr(...mine), vr = nodes[me ? "" : "0"], hr = nodes[me ? "0" : ""]; // villain's / your range at the flop
  P = { postflop: true, scen, src: m.src || scen, me, sig, seat: [m.oop, m.ip], pot0: m.pot, stack: m.stack, board: [flop.slice(0, 2), flop.slice(2, 4), flop.slice(4)],
    flop, nodes, vr, k: "", street: 0, spent: [0, 0], put: [0, 0], tag: ["", ""], hist: [], over: false, answered: false, cards: c.cards, isNew: 3,
    // the hand so far: street names ({s}) and actions ({t, k}); a closing message ({t, end}) when it's over
    story: [{ s: "Preflop" }, ...[...z0.line, [p0, 0, key0.endsWith("FACINGLIMP") ? "Check" : "Call"]].map(told)] };
  P.hands = [];
  P.hands[me] = hero;
  // TEMPORARY until the keep-every-hand re-solve (results/.since, 2026-11-15) finishes; then delete this and the "off && P.inRange" message in postAnswer.
  // Your hand is in the flop range but may be missing later: flops solved before then dropped hands under 0.1% reach.
  P.inRange = hr.hands.includes(hero);
  P.hands[1 - me] = vr.hands[pick(vr.hands.map((h, i) => cardsOf(h).some(x => mine.includes(x)) ? 0 : vr.reach[i]))];
  P.story.push({ s: "Flop" }); // the cards are on the board; the story only says who did what
  st.cur = P;
  // not in the solved range (the solver doesn't play it this way preflop): it still plays on, ungraded (see postAnswer)
  P.quiet = from > 0;
  if (!P.quiet) postDraw(true);
  P.busy = true;
  const start = copyP(P);
  // an all-in runout (or an unsolved turn) before your first decision: replay the line, then try another flop
  for (let t = 0; t < 30 && (!t || from && P.over && !P.err); t++) {
    if (t) P = st.cur = copyP(start);
    const h = P; await run(); if (P !== h) return;
  }
  P.busy = false;
  if (P.over && !P.err && from) return newHand();
  reveal(); postDraw(false);
}
// the hand was playing out unseen (P.quiet) and reached your street: show the table, every board card dealing in
function reveal() { if (P.quiet && P.street >= fromSt()) { P.quiet = false; P.isNew = 0; postDraw(true); } }

// apply action i at the current node, for whoever is to act; deals the next card when a street closes
// hold: your own action closed the street; the next card waits until you continue (closeStreet from postNext)
// P is global: a new hand can be dealt while this one awaits (a settings change), so after every wait the old hand
// checks it's still the one on the table, and stops (throws STALE) if not
const STALE = new Error("stale"), live = h => { if (P !== h) throw STALE; };
async function step(i, hold) {
  const h = P;
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
  if (!P.quiet) { postDraw(false); await new Promise(r => setTimeout(r, 700)); live(h); }
  return closeStreet();
}
async function closeStreet() {
  const h = P;
  const nk = P.nk; P.closing = false;
  if (P.spent[0] >= P.stack - .01 && P.spent[1] >= P.stack - .01) {
    // cards face up and chips into the pot, then the runout one card at a time
    if (P.quiet) return end("All-in before your street."); // replayed unseen (postBegin)
    P.show = true; P.put = [0, 0]; postDraw(false);
    while (P.board.length < 5) {
      await new Promise(r => setTimeout(r, 1000)); live(h);
      P.board.push(dealOne()); P.isNew = P.board.length - 1; postDraw(false);
    }
    await new Promise(r => setTimeout(r, 600)); live(h);
    return end(`All-in: ${P.seat[1 - P.me]} shows ${cardsOf(P.hands[1 - P.me]).map(cardText).join("")}. ${winner()}`, true);
  }
  if (P.street === 2) return end(`Showdown: ${P.seat[1 - P.me]} shows ${cardsOf(P.hands[1 - P.me]).map(cardText).join("")}. ${winner()}`, true);
  const c = dealOne();
  P.board.push(c); P.street++; P.put = [0, 0]; P.tag = ["", ""]; P.isNew = P.board.length - 1;
  P.story.push({ s: STREET[P.street] });
  if (P.street === 1) {
    const absent = [...SUIT].filter(x => ![1, 3, 5].some(i => P.flop[i] === x)), swap = absent.indexOf(c[1]) > 0 ? [absent[0], c[1]] : null;
    const turn = await loadPiece(`${P.src}/${P.flop}/${swap ? c[0] + absent[0] : c}`, swap);
    live(h);
    P.nodes = { ...P.nodes, ...turn }; P.k = nk + "-" + c;
    // TEMPORARY until the 2026-11-15 re-solve finishes: solves since 2026-11-13 keep the turn after a raised flop too;
    // after that this only fires if a piece is missing
    if (!P.nodes[P.k]) return end("The flop was raised, and turns after a raised flop aren't solved yet, so the hand ends here.");
  } else {
    if (!P.quiet) $("situation").innerHTML = '<span class="spin"></span>Solving the river…';
    await new Promise(r => setTimeout(r, 30)); // let the text paint: the solve blocks the page
    const r = await RiverSolver.solve(riverJob()); live(h);
    P.nodes = r.nodes; P.k = "";
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
// "Start deciding on" the flop, turn or river (cfg.postFrom): preflop is skipped (newHand), and your earlier postflop decisions play themselves the solver's way,
// and before your street nobody folds when they have another line (a fold would end the hand before you decide)
const FROM = { flop: 0, turn: 1, river: 2 };
const fromSt = () => toPost() && FROM[cfg.postFrom] || 0; // only in "Postflop only": a hand played on from preflop decides every street
async function run() {
  const from = fromSt(), h = P;
  try {
    for (let p; !P.over && ((p = cur().player) !== P.me || P.street < from); P.quiet || postDraw(false)) {
      reveal();
      if (!P.quiet) { await new Promise(r => setTimeout(r, 650)); live(h); }
      let s = strat(cur(), P.hands[p]);
      const f = P.street < from ? cur().actions.indexOf("Fold") : -1;
      if (f >= 0 && s.some((x, j) => j !== f && x >= 1)) s = s.map((x, j) => j === f ? 0 : x);
      await step(pick(s));
    }
  } catch (e) { if (e === STALE) return; P.err = true; return end(e.message); }
}
// the villain's range now: reach × how often they took the action they took at their last decision (all of it before one)
function villainRange() {
  const h = P.hist.filter(x => x.p !== P.me).at(-1), n = h ? h.node : P.vr, w = {};
  n.hands.forEach((x, j) => w[x] = n.reach[j] * (h ? n.strat[h.i][j] : 1));
  return w;
}
function winner() {
  const id = x => UP.indexOf(x[0]) * 4 + SUIT.indexOf(x[1]), sc = p => strength([...cardsOf(P.hands[p]), ...P.board].map(id)), d = sc(P.me) - sc(1 - P.me);
  return d > 0 ? `You win the ${bb(potNow())} pot.` : d < 0 ? `${P.seat[1 - P.me]} wins the ${bb(potNow())} pot.` : "Split pot.";
}
// undo (index.html): the hand as it was before your decision. Arrays are copied; the nodes are shared, since a piece
// is never changed (a new street replaces P.nodes).
const copyP = x => ({ ...x, spent: [...x.spent], put: [...x.put], tag: [...x.tag], hist: [...x.hist], story: [...x.story], board: [...x.board], hands: [...x.hands] });
function postRestore(s) { P = st.cur = copyP(s); P.isNew = 9; P.drawnKey = null; postDraw(false); }
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
    `<b>${s}</b><div>${xs.map(x => `<span style="--c:${AC[x.k]}">${say0(x.t)}</span>`).join("")}</div>`).join("")}</div>`;
  const seat = (p, s) => `<div class="seat${p === me ? " hero" : ""}${P.tag[p] === "Fold" ? " folded" : ""}${p === me && mine ? " turn" : ""}${folds(p) ? " toss" : ""}" style="--c:0;--s:${s};--r:1">`
    + (p === me || P.show ? `<div class="cards">${cardsOf(P.hands[p]).map(x => cardHTML(x)).join("")}</div>`
      : `<div class="backs">${P.tag[p] !== "Fold" || folds(p) ? "<i></i><i></i>" : ""}</div>`)
    + `<div class="plate"><b>${p === me ? "You · " : ""}${P.seat[p]}</b><span>${bb(P.stack - P.spent[p])}</span></div>`
    + `<em class="tag"${P.tag[p] ? ` style="background:${AC[kind(P.tag[p] === "All-in" ? "Allin" : P.tag[p])]}"` : " hidden"}>${P.tag[p]}</em></div>`
    + (P.put[p] ? `<div class="bet post${p === me ? " me" : ""}${moved(p) ? " fly" : ""}" style="--c:${p === me ? .35 : .4};--s:${p === me ? .68 : -.66};--r:1;--y0:${50 + s * 41}%">${bb(P.put[p])}</div>` : "");
  $("felt").classList.toggle("still", !fresh);
  $("felt").innerHTML = seat(them, -1) + seat(me, 1)
    + `<div class="board">${P.board.map((x, j) => cardHTML(x, j >= P.isNew ? " new" : "")).join("")}</div>`
    + `<div class="pot" style="left:74%;top:64%">Pot <b>${bb(potNow() - P.put[0] - P.put[1])}</b></div>`;
  P.isNew = 9;
  postButtons(mine);
}
function postButtons(mine) {
  if (!P.over && (!mine || P.busy)) return document.querySelectorAll("#actions button").forEach(b => b.disabled = true); // their move: keep your last buttons, greyed
  if (P.over) { P.answered = true; setNext(false); $("actions").innerHTML = P.story.filter(x => x.end).map(x => `<div class="end">${x.t}</div>`).join("") + `<button data-next>Next hand<kbd>Space</kbd></button>`; return; }
  $("actions").innerHTML = cur().actions.map((a, i) => `<button data-a="${i}" style="background:${AC[kind(a)]}">${btnLabel(a, i)}</button>`).join("");
}

// The read of the spot after your decision, as the parts of the feedback panel: what you hold (have) and the board, tiles for
// your equity, your outs and where the hand sits in your range, how often hands like yours take each action (like), and the
// working behind "Show the maths". The hand groups and board read are local rules; the numbers are the solver's.
let mathsOpen = false; // "Show the maths" stays as you left it from one decision to the next
document.addEventListener("toggle", e => { if (e.target.classList?.contains("maths")) mathsOpen = e.target.open; }, true);
function postExplain(node, h) {
  const board = P.board, me = P.me, hole = cardsOf(P.hands[me]), hc = handClass(hole, board), f1 = x => +x.toFixed(1), maths = [], tiles = [];
  const tile = (name, big, bar, ...notes) => `<div class="tile"><small>${name}</small><b>${big}</b>${bar}${notes.filter(Boolean).map(n => `<span>${n}</span>`).join("")}</div>`;
  // equity against the villain's range now; the mark on the bar is what a call needs
  const call = P.put[1 - me] - P.put[me], need = call / (potNow() + call) * 100, eq = equity(hole, board, villainRange()) * 100;
  if (call > 0) maths.push(`Equity needed to call = call ÷ (pot + call) = ${f1(call)} ÷ (${f1(potNow())} + ${f1(call)}) = ${f1(call)} ÷ ${f1(potNow() + call)} = <b>${f1(need)}%</b>.`);
  if (!isNaN(eq)) {
    tiles.push(tile("Equity", f1(eq) + "%", `<i><b style="width:${eq}%"></b>${call > 0 ? `<u style="left:${need}%"></u>` : ""}</i>`, call > 0 ? `a call needs ${f1(need)}%` : `against ${P.seat[1 - me]}'s range`));
    maths.push(`Equity is your share of the pot against ${P.seat[1 - me]}'s range if the hand checked down from here${call > 0 ? `: ${f1(eq)}% ${eq >= need ? "≥" : "<"} the ${f1(need)}% a call needs` : ""}. The solver's EV also counts the betting still to come, so the two can disagree.`);
  }
  // a draw's outs: exact in the tile, the rule of 2 and 4 in the maths
  if (hc.draw) {
    const used = new Set([...hole, ...board]), left = 52 - used.size, flop = board.length === 3;
    const BIG = ["a straight", "a flush", "a full house", "quads"];
    const outs = [...UP].flatMap(r => [...SUIT].map(s => r + s)).filter(c => !used.has(c) && BIG.includes(handClass(hole, [...board, c]).made)).length;
    const allin = call > 0 && call >= P.stack - P.spent[me] - .01, one = outs / left * 100, two = (1 - (left - outs) / left * (left - 1 - outs) / (left - 1)) * 100;
    const goal = [hc.draw.includes("flush") && "flush", hc.draw.includes("straight") || hc.draw.includes("gutshot") ? "straight" : ""].filter(Boolean).join(" or ");
    tiles.push(tile("Outs", outs, "", `${f1(one)}% next card`, flop && `${f1(two)}% by the river`));
    maths.push(`Outs: <b>${outs}</b> cards make your ${goal}. Next card ≈ ${outs} × 2 = ${outs * 2}% (exactly ${outs} ÷ ${left} = ${f1(one)}%)`
      + (flop ? `; by the river ≈ ${outs} × 4 = ${outs * 4}% (exactly ${f1(two)}%), but only if you get to see both cards.` : "."));
    if (call > 0) {
      const have = flop && allin ? two : one; // both cards only when this call is all-in on the flop
      maths.push(have >= need ? `${f1(have)}% ≥ ${f1(need)}%: the draw alone pays for the call.`
        : `${f1(have)}% < ${f1(need)}%: the draw alone doesn't pay for the call${flop && !allin ? " on one card" : ""}; it needs extra from money you win when you hit (implied odds), hitting a pair instead, or a later bluff.`);
    }
  }
  // where the hand sits in your range here, ranked by the solver's EV for each hand (its best action)
  if (h >= 0) {
    const best = j => Math.max(...node.ev.map(e => e[j])), mine = best(h);
    let tot = 0, above = 0;
    node.hands.forEach((_, j) => { const w = node.reach[j]; if (!w) return; tot += w; if (best(j) > mine) above += w; });
    const top = Math.min(99, Math.max(1, Math.round(above / (tot || 1) * 100)));
    tiles.push(tile("In your range", top <= 50 ? `top ${top}%` : `bottom ${100 - top}%`, `<i><u class="dot" style="left:${100 - top}%"></u></i>`, top <= 25 ? "near the top" : top <= 60 ? "the middle" : "the bottom part"));
    maths.push(`In your range: by the solver's EV, about ${top}% of the hands you'd have here do better than yours.`);
  }
  // hands in the same group (same made hand and draw; if that's thin, same made hand only): how often they take each action
  const cls = node.hands.map(x => handClass(cardsOf(x), board));
  const group = by => node.hands.map((_, j) => j).filter(j => node.reach[j] > 0 && by(cls[j]));
  let g = group(c => c.made === hc.made && c.draw === hc.draw), label = hc.text;
  if (g.length < 6) { g = group(c => c.made === hc.made); label = hc.made; }
  const w = g.reduce((t, j) => t + node.reach[j], 0) || 1, bare = x => x.replace(/\ban? /g, "");
  return { tiles: tiles.join(""), maths, board: texture(board),
    have: [hc.made === "no pair" && hc.draw ? "" : hc.made, ...hc.draw.split(" and ")].filter(Boolean).map(bare),
    like: g.length >= 2 ? node.strat.map(s => g.reduce((t, j) => t + s[j] * node.reach[j], 0) / w) : null, likeNote: `${bare(label)}, ${g.length} combos` };
}

// graded by frequency first, EV second: EV gaps of a few % of the pot are solver noise (a 35% action can trail by that much),
// so a small gap can't rescue an action the solver (almost) never takes.
// right: played 25%+, or 5%+ and within 2% of the pot. acceptable: played 5%+, or 1%+ and within 5%, or under 1% and within 1%.
// ponytail: thresholds are a judgment call
async function postAnswer(i) {
  if (P.over || P.answered || P.busy || !cur().actions[i]) return;
  snap({ post: copyP(P) });
  P.answered = P.busy = true;
  // h < 0: the solve has no strategy or EV for your hand here: it isn't in the preflop range, or (flops solved before
  // 2026-11-15 only) its reach fell under 0.1% and it was trimmed. Play on ungraded; the buttons show the range's average mix instead.
  const node = cur(), h = node.hands.indexOf(P.hands[P.me]), off = h < 0, f = off ? 0 : node.strat[i][h], ev = node.ev.map(e => e[h]);
  const best = ev.indexOf(Math.max(...ev)), loss = ev[best] - ev[i], pot = potNow();
  const grade = off ? "" : f >= 25 || f >= 5 && loss <= .02 * pot ? "great" : f >= 5 || f >= 1 && loss <= .05 * pot || loss <= .01 * pot ? "ok" : "bad";
  if (grade && !atEnd()) tally(grade);
  if (grade) { // the Leaks log, grouped loosely: street, position and what you face; made hand, or the draw when there's nothing better
    const me = P.me, face = P.put[1 - me] > P.put[me] ? (P.put[me] > 0 ? "facing a raise" : "facing a bet") : me ? "checked to you" : "first to act";
    const hc = handClass(cardsOf(P.hands[me]), P.board), made = hc.made.replace(/^an? /, "");
    const fav = node.strat.reduce((b, s, j) => s[h] > node.strat[b][h] ? j : b, 0);
    prog.plog ||= []; prog.plog.push([`${STREET[P.board.length - 3]} · ${me ? "IP" : "OOP"} ${face}`, hc.draw && /no pair|ace high/.test(made) ? hc.draw.replace(/\ban? /g, "") : made,
      grade, kind(node.actions[i]), kind(node.actions[fav]), Math.round(loss * 100) / 100, // [5]: bb lost
      ["Fold", "Bet|Raise|Allin"].map(k => Math.round(node.actions.reduce((t, x, j) => t + (k.split("|").includes(kind(x)) ? node.strat[j][h] : 0), 0)))]); // [6]: solver fold %, bet/raise %
    if (prog.plog.length > 3000) prog.plog.shift();
    saveProg();
  }
  play(kind(node.actions[i]) === "Fold" ? "deal" : "chip");
  const short = `${STREET[P.board.length - 3][0]} · ${abbr({ Bet: `Bet ${potFrac(amt(node.actions[i])).replace(/ pot$/, "")}`, Allin: "All-in" }[kind(node.actions[i])] || kind(node.actions[i]))}`;
  const plain = $("actions").innerHTML;
  const rsum = node.reach.reduce((x, y) => x + y, 0) || 1, mix = off ? strat(node, "").map(x => x / rsum) : node.strat.map(s => s[h]);
  stamp(String(i), j => mix[j], !off && (j => sbb(ev[j])));
  const btns = $("actions").innerHTML; // the graded buttons stay up until you continue, though the hand has moved on
  const names = node.actions.map(actName), hand = cardsOf(P.hands[P.me]).map(cardText).join("");
  $("verdict").className = "verdict " + grade;
  $("verdict").textContent = verdictText(grade, f);
  // the grade is up (buttons, verdict, sound): let it paint before the analysis, whose exact flop equity can take a few hundred ms
  // on a phone. Not in "Feedback after the hand", where the graded buttons mustn't show yet.
  const h0 = P;
  if (!atEnd()) { await new Promise(r => setTimeout(r, 30)); if (st.cur !== h0) return; }
  const pill = (j, v) => `<span class="pill" style="--c:${AC[kind(node.actions[j])]}"><span>${names[j]}</span><b>${Math.round(v)}%</b></span>`;
  // whole range at this node, weighted by reach
  const tot = node.reach.reduce((x, y) => x + y, 0) || 1, rm = node.strat.map(s => s.reduce((t, x, j) => t + x * node.reach[j], 0) / tot);
  $("range").innerHTML = `<h4>Whole range · ${P.seat[P.me]} on the ${STREET[P.board.length - 3].toLowerCase()}</h4>
    <div class="mix">${rm.map((v, j) => v >= .5 ? `<div style="background:${AC[kind(node.actions[j])]};width:${v}%"></div>` : "").join("")}</div>
    <div class="pills">${rm.map((v, j) => v >= .5 ? pill(j, v) : "").join("")}</div>`;
  $("grid").innerHTML = gridHTML(classRows(node), "POST", HANDS.indexOf(classOf(P.hands[P.me])));
  // correct though the solver mostly plays something else: say why right under the spot line
  const top = mix.indexOf(Math.max(...mix)), gap = Math.abs(ev[top] - ev[i]);
  const rare = grade === "great" && mix[top] - f >= 20 && `<b>Why ${Math.round(f)}% is still correct:</b> the solver prefers ${names[top]} (${Math.round(mix[top])}%), `
    + `but the EVs are nearly equal (${ev[i].toFixed(2)} vs ${ev[top].toFixed(2)}bb${i === best ? ", yours higher" : `, ${gap.toFixed(2)}bb apart`}). `
    + "When actions are worth about the same, the solver mixes them to stay unreadable, and either one is a fine play.";
  // the panel: the spot, what you hold, three tiles, one row per action (this hand, hands like it, EV), then the maths folded away
  const X = postExplain(node, h), para = (t, c) => t ? `<p${c ? ` class="${c}"` : ""}>${t}</p>` : "";
  const table = `<table class="acts"><tr><th></th><th>This hand</th><th>Hands like it</th><th>EV bb</th><th></th></tr>${node.actions.map((a, j) =>
    `<tr${j === i ? ' class="you"' : ""}><td><i style="background:${AC[kind(a)]}"></i>${names[j]}</td><td>${off ? "–" : Math.round(mix[j]) + "%"}</td><td>${X.like ? Math.round(X.like[j]) + "%" : "–"}</td>`
    + `<td>${off ? "–" : sbb(ev[j]).replace("bb", "")}</td><td>${off ? "" : j === best ? "best" : "−" + (ev[best] - ev[j]).toFixed(2)}</td></tr>`).join("")}</table>`
    + para(X.like && `Hands like it: ${X.likeNote}.`, "muted");
  const why = para(`<b>${hand}</b> on ${P.board.map(cardText).join(" ")} · pot ${bb(pot)} · ${P.me ? "in" : "out of"} position`)
    + `<div class="pills">${X.have.map(t => `<span class="pill" style="--c:var(--ok)">${t}</span>`).join("")}<span class="sub">Board: ${X.board}</span></div>`
    + para(rare) + `<div class="tiles">${X.tiles}</div>` + table
    + para(off && P.inRange ? "Not graded: this flop was solved before every hand was kept, and the solver gets here with your hand so rarely (under 0.1%) that it was left out of this spot. It will be graded once this flop is re-solved. The % on each button is what its whole range does in this spot." // TEMPORARY, see P.inRange
      : off ? "Not graded: your preflop play with this hand isn't in the solver's range, so it has no strategy for it here. The % on each button is what its whole range does in this spot."
      : i === best ? "" : `Your pick gives up ${loss.toFixed(2)}bb against ${names[best]}${f >= 25 ? ", but the solver plays it often enough here that the gap is noise" : f < 1 ? ", and the solver never plays it here" : ""}.`)
    + `<details class="maths"${mathsOpen ? " open" : ""}><summary>Show the maths</summary>${X.maths.map(t => para(t)).join("")}`
    + `${para("Hand groups and board reads come from simple local rules; the percentages and EVs are the solver's.", "muted")}</details>`;
  try { await step(i, true); } catch (e) { end(e.message); }
  P.busy = false;
  $("why").innerHTML = why;
  if (atEnd()) { // nothing shown yet: keep the analysis, put back the plain buttons and play on; the review comes when the hand ends
    keep(short, grade, btns);
    $("actions").innerHTML = plain; P.drawnKey = null; postDraw(false);
    if (!P.over) await postNext();
    return P.over && review(P.story.filter(x => x.end).map(x => x.t).join(" "));
  }
  postDraw(false);
  $("actions").innerHTML = btns;
  setNext(!P.over);
  showFeedback();
}
async function postNext() {
  if (P.over || P.busy) return P.busy || newHand();
  $("feedback").classList.remove("show");
  P.busy = true;
  const h = P;
  if (P.closing) { try { await closeStreet(); } catch (e) { if (e === STALE) return; end(e.message); } postDraw(false); }
  await run(); if (P !== h) return;
  P.busy = false; P.answered = false;
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
