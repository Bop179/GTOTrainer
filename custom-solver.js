// Saved and custom heads-up postflop solves. Never changes the trainer's hand or statistics.
const CustomSolver = (() => {
  const ranks = 'AKQJT98765432';
  const suits = { c: ['♣', 'clubs'], d: ['♦', 'diamonds'], h: ['♥', 'hearts'], s: ['♠', 'spades'] };
  const cardText = value => value.replace(/([2-9TJQKA])([cdhs])/g, (_, rank, suit) => rank + suits[suit][0]);
  function cardsHTML(value) {
    if (!/^(?:[2-9TJQKA][cdhs]){1,5}$/.test(value)) throw new Error('Invalid cards');
    return value.match(/../g).map(c => `<span class="solve-card${'dh'.includes(c[1]) ? ' red' : ''}" role="img" aria-label="${c[0]} ${suits[c[1]][1]}">${cardText(c)}</span>`).join('');
  }
  function board(value) {
    const b = value.replace(/\s+/g, '').replace(/([2-9tjqka])([cdhs])/gi, (_, r, s) => r.toUpperCase() + s.toLowerCase());
    if (!/^(?:[2-9TJQKA][cdhs]){3,5}$/.test(b) || new Set(b.match(/../g)).size !== b.length / 2)
      throw new Error('Enter 3, 4 or 5 different board cards, e.g. Ks 7d 2c.');
    return b;
  }
  function handClass(h) {
    const a = h.slice(0, 2), b = h.slice(2);
    return a[0] === b[0] ? a[0] + b[0] : [a[0], b[0]].sort((x, y) => ranks.indexOf(x) - ranks.indexOf(y)).join('') + (a[1] === b[1] ? 's' : 'o');
  }
  function estimateTime(value, pot, stack) {
    let cards;
    try { cards = board(value).length / 2; } catch { return { time: '—', detail: 'Enter 3–5 distinct board cards.' }; }
    if (![pot, stack].every(n => Number.isFinite(n) && n >= .05 && n <= 2000))
      return { time: '—', detail: 'Enter pot and stack between 0.05 and 2,000 bb.' };
    const spr = stack / pot, detail = `${['Flop', 'Turn', 'River'][cards - 3]} · SPR ${spr.toFixed(1)}`;
    if (cards === 5) return { time: 'Seconds for small ranges', detail: detail + ' · Wider ranges may take longer.' };
    if (cards === 4) return { time: 'Not yet benchmarked', detail: detail + ' · Usually faster than a comparable flop solve.' };
    // shortcut: SPR buckets use batch timings, not custom-tree calibration; replace when custom timing samples exist.
    const time = spr <= 2 ? '2–7 sec' : spr <= 6 ? '20–75 sec' : spr <= 22 ? '4–12 min' : spr <= 40 ? '7–21 min' : spr <= 60 ? '12–24 min' : '20–35+ min';
    return { time: '≈ ' + time, detail: detail + (spr > 60 ? ' · May hit the 30 min limit.' : ' · Flop reference') };
  }
  const group = (n, h) => n.hands.flatMap((c, i) => handClass(c) === h ? [i] : []);
  function average(n, indices) {
    const total = indices.reduce((s, i) => s + n.reach[i], 0);
    return n.actions.map((_, a) => total ? indices.reduce((s, i) => s + n.reach[i] * n.strat[a][i], 0) / total : 0);
  }
  const nextKey = (k, i) => k ? `${k}-${i}` : String(i);
  function findFlop(value, flops) {
    const wanted = board(value);
    if (wanted.length !== 6) throw new Error('Enter exactly three flop cards.');
    const sorted = wanted.match(/../g).sort().join(''), suits = [...'cdhs'];
    const permutations = a => a.length ? a.flatMap((x, i) => permutations(a.filter((_, j) => i !== j)).map(p => [x, ...p])) : [[]];
    for (const f of flops) for (const p of permutations(suits)) {
      const map = Object.fromEntries(suits.map((s, i) => [s, p[i]]));
      if (f.match(/../g).map(c => c[0] + map[c[1]]).sort().join('') === sorted) return { flop: f, suits: map };
    }
    return null;
  }
  function remapNodes(nodes, suits) {
    return Object.fromEntries(Object.entries(nodes).map(([k, n]) => [k, {
      ...n, hands: n.hands.map(h => h[0] + suits[h[1]] + h[2] + suits[h[3]]),
    }]));
  }
  function ending(result, path) {
    let key = '', put = [0, 0];
    for (const i of path) {
      const node = result.nodes[key], a = node.actions[i], p = node.player;
      if (a === 'Fold') return 'Hand ends with a fold.';
      if (a === 'Call') put[p] = Math.max(...put);
      else if (/^(Bet|Raise|Allin) /.test(a)) put[p] = Number(a.split(' ')[1]);
      key = nextKey(key, i);
    }
    if (put.every(v => v >= result.stack - .01)) return 'All-in called. No betting decisions remain.';
    return result.board.length === 10 ? 'River complete: showdown.' : 'Street complete. Enter a later street as a new spot to solve it.';
  }
  return { board, handClass, group, average, nextKey, ending, findFlop, remapNodes, cardText, cardsHTML, estimateTime };
})();
if (typeof module !== 'undefined') module.exports = CustomSolver;
if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', () => {
  const el = id => document.getElementById(id), dialog = el('solverDialog'), form = el('solveForm');
  const esc = x => String(x).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = n => Number(n).toFixed(2), signed = n => (n >= 0 ? '+' : '') + fmt(n);
  const state = { id: null, result: null, path: [], selected: '', timer: null, busy: false, input: null,
    mode: 'stored', jobDone: false, customResult: null, customInput: null, stored: null, storedRequest: 0 };
  try { state.id = sessionStorage.getItem('gto-custom-job'); } catch {}
  const remember = () => { try { state.id ? sessionStorage.setItem('gto-custom-job', state.id) : sessionStorage.removeItem('gto-custom-job'); } catch {} };
  const message = text => { el('solveStatus').textContent = text; };
  function updateEstimate() {
    const value = name => form.elements.namedItem(name).value;
    const estimate = CustomSolver.estimateTime(value('board'), +value('pot'), +value('stack'));
    el('solveEstimate').textContent = estimate.time;
    el('solveEstimateDetail').textContent = estimate.detail;
  }
  form.oninput = updateEstimate;
  updateEstimate();
  function busy(on) {
    state.busy = on;
    const unresolved = !!state.id && !state.jobDone;
    el('solveInputs').disabled = on || unresolved; el('solveSubmit').disabled = on || unresolved;
    el('solveCancel').hidden = !on; el('solveResume').hidden = !state.id || on;
  }
  async function api(method, path, body) {
    const r = await fetch(window.POST_BASE + 'solve/' + path, {
      method, headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(15000),
    });
    const text = await r.text();
    let out;
    try { out = JSON.parse(text); } catch { throw new Error('The solver service did not respond with a result. Try again.'); }
    if (!r.ok) { const error = new Error(out.error || `Server error ${r.status}`); error.status = r.status; throw error; }
    return out;
  }
  function resetJob() { clearTimeout(state.timer); state.id = null; state.jobDone = false; remember(); busy(false); }
  async function poll(id) {
    try {
      const j = await api('GET', 'jobs/' + id);
      if (id !== state.id) return;
      state.customInput = j.input;
      if (j.state === 'running') {
        busy(true);
        message(`◌ Solving · ${Math.max(0, Math.floor(Date.now() / 1000 - j.started))}s`);
        state.timer = setTimeout(() => poll(id), 2000);
      } else if (j.state === 'done') {
        message('Loading strategy…');
        const r = await api('GET', 'jobs/' + id + '/result');
        if (id !== state.id) return;
        state.customResult = r; state.jobDone = true; busy(false);
        message(r.exploit <= .01 ? '✓ Solved · 1% target met' : '⚠ Iteration limit · Above 1% target; approximate result');
        if (state.mode === 'custom') show(r, j.input);
      } else { resetJob(); message(j.error || 'Solve cancelled.'); }
    } catch (e) {
      if (id !== state.id) return;
      busy(false);
      if (e.status === 404) resetJob();
      message(e.message + (state.id ? ' Reconnect to check progress.' : ''));
      el('solveCancel').hidden = !state.id;
    }
  }
  el('solverBtn').onclick = () => { dialog.showModal(); el('solveResume').hidden = !state.id || state.busy; if (!el('storedSpot').value) refreshStored(); };
  el('closeSolver').onclick = () => dialog.close();
  el('solveResume').onclick = () => { if (state.id) { clearTimeout(state.timer); busy(true); poll(state.id); } };
  el('solveCancel').onclick = async () => {
    const id = state.id; if (!id) return;
    clearTimeout(state.timer); el('solveCancel').disabled = true;
    try {
      const j = await api('DELETE', 'jobs/' + id);
      if (id !== state.id) return;
      if (j.state === 'done') { await poll(id); return; }
      resetJob(); message('Solve cancelled.');
    } catch (e) { message(e.message + ' Job may still be running. Retry Cancel or Reconnect.'); busy(false); el('solveCancel').hidden = false; }
    finally { el('solveCancel').disabled = false; }
  };
  form.onsubmit = async e => {
    e.preventDefault(); if (state.busy) return;
    let job;
    try {
      const data = new FormData(form);
      job = { board: CustomSolver.board(data.get('board')), pot: +data.get('pot'), stack: +data.get('stack'), oop: data.get('oop').trim(), ip: data.get('ip').trim() };
      for (const s of ['flop', 'turn', 'river']) job[s + '_sizes'] = [data.get(s + '_bets').trim(), data.get('raises').trim()];
      // Stable request ID lets a lost POST response be recovered without submitting another solve.
      job.request_id = Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('');
    } catch (error) { message(error.message); return; }
    clearTimeout(state.timer); state.id = job.request_id; state.jobDone = false; remember();
    state.result = state.customResult = null; busy(true); el('solveResult').hidden = true; message('Submitting spot…');
    const id = state.id;
    try { await api('POST', 'jobs', job); if (id === state.id) poll(id); }
    catch (error) {
      if (id !== state.id) return;
      if (error.status) resetJob(); else { busy(false); el('solveCancel').hidden = false; }
      message(error.message + (state.id ? ' Reconnect to check submission.' : ''));
    }
  };
  function show(result, input) {
    state.result = result; state.input = input; state.path = []; state.selected = '';
    el('solveHand').value = ''; el('solveHandNote').textContent = '';
    el('solveResult').hidden = !result;
    if (result) draw();
  }
  function mode(value) {
    state.mode = value;
    el('solveStoredPane').hidden = value !== 'stored'; el('solveCustomPane').hidden = value !== 'custom';
    el('solveModeStored').setAttribute('aria-pressed', String(value === 'stored'));
    el('solveModeCustom').setAttribute('aria-pressed', String(value === 'custom'));
    show(value === 'custom' ? state.customResult : state.stored?.result, value === 'custom' ? state.customInput : state.stored?.input);
    if (value === 'stored' && !el('storedSpot').value) refreshStored();
  }
  el('solveModeStored').onclick = () => mode('stored');
  el('solveModeCustom').onclick = () => mode('custom');
  function invalidateStored() {
    state.storedRequest++; state.stored = null;
    if (state.mode === 'stored') show(null, null);
    el('storedStatus').textContent = 'Pick a saved flop or enter 3 cards.';
  }
  const spotLabel = (s, m) => {
    const p = s.split('_'), kind = { '': 'Single-raised', '3bet': '3-bet', '4bet': '4-bet', limp: 'Limped', limpraise: 'Limp-raised', sqz: 'Squeeze', c4b: 'Cold 4-bet' }[p[5] || ''] || p[5];
    return `${p[2]} vs ${p[4]} · ${kind}${p[6] ? ' · ' + p[6] + ' folded' : ''}`;
  };
  function populateFlops() {
    invalidateStored();
    const m = PI[el('storedSpot').value];
    el('storedFlop').innerHTML = (m?.flops || []).map(f => `<option value="${esc(f)}">${esc(CustomSolver.cardText(f).match(/../g).join(' '))}</option>`).join('');
    el('storedBoard').value = m?.flops[0]?.match(/../g).join(' ') || '';
    el('storedLoad').disabled = !m;
    if (m) el('storedStatus').textContent = `${m.flops.length} flops · ${m.oop} (OOP) / ${m.ip} (IP) · ${+fmt(m.pot)}bb pot`;
  }
  function populateSpots() {
    const group = el('storedGame').value, old = el('storedSpot').value;
    const scenarios = Object.entries(PI).filter(([s]) => s.split('_').slice(0, 2).join('/') === group).sort(([a], [b]) => a.localeCompare(b));
    el('storedSpot').innerHTML = scenarios.map(([s, m]) => `<option value="${esc(s)}">${esc(spotLabel(s, m))}</option>`).join('');
    if (scenarios.some(([s]) => s === old)) el('storedSpot').value = old;
    populateFlops();
  }
  async function refreshStored() {
    el('storedRefresh').disabled = true; el('storedStatus').textContent = 'Loading flops…';
    try {
      setIndex(await fetchPostIndex());
      const groups = [...new Set(Object.keys(PI).map(s => s.split('_').slice(0, 2).join('/')))].sort();
      const prior = el('storedGame').value || (typeof cfg !== 'undefined' ? cfg.game + '/' + cfg.stack : '6max/100bb');
      el('storedGame').innerHTML = groups.map(g => `<option value="${esc(g)}">${esc(g.replace('max/', '-max · '))}</option>`).join('');
      if (groups.includes(prior)) el('storedGame').value = prior;
      populateSpots();
      if (!groups.length) el('storedStatus').textContent = 'No solved flops are available yet.';
    } catch (e) { el('storedStatus').textContent = e.message || 'The solved-flop list did not load. Try Refresh.'; }
    finally { el('storedRefresh').disabled = false; }
  }
  async function loadStored() {
    invalidateStored();
    const request = state.storedRequest, scenario = el('storedSpot').value, m = PI[scenario];
    try {
      if (!m) throw new Error('Choose a solved spot first.');
      const requested = CustomSolver.board(el('storedBoard').value), match = CustomSolver.findFlop(requested, m.flops);
      if (!match) { el('storedStatus').textContent = '∅ Not solved here · Pick a saved flop or use Custom.'; return; }
      el('storedStatus').textContent = 'Loading saved strategy…';
      const base = `${m.src || scenario}/${match.flop}`;
      const [nodes, meta] = await Promise.all([loadPiece(base + '/flop'), fetch(window.POST_BASE + base + '/meta.json', { signal: AbortSignal.timeout(15000) }).then(r => {
        if (!r.ok) throw new Error('Saved solve details did not load. Try again.'); return r.json();
      })]);
      if (request !== state.storedRequest) return;
      const result = { ...meta, board: requested, pot: m.pot, stack: m.stack, source: 'saved', nodes: CustomSolver.remapNodes(nodes, match.suits) };
      const input = { description: `${el('storedGame').selectedOptions[0].textContent}\n${spotLabel(scenario, m)}\nOut of position: ${m.oop}\nIn position: ${m.ip}\nUses this matchup's built-in preflop ranges and pre-solve bet sizes, not the custom form inputs.\nStored board: ${match.flop.match(/../g).join(' ')}; displayed cards and combinations are suit-mapped to your flop.` };
      state.stored = { result, input };
      if (state.mode === 'stored') show(result, input);
      el('storedStatus').textContent = `✓ Saved${requested !== match.flop ? ' · Suits / order matched' : ''}${meta.exploit > .01 ? ' · ⚠ Above 1% accuracy target' : ''}`;
    } catch (e) { if (request === state.storedRequest) el('storedStatus').textContent = e.message; }
  }
  el('storedRefresh').onclick = refreshStored;
  el('storedGame').onchange = populateSpots;
  el('storedSpot').onchange = populateFlops;
  el('storedBoard').oninput = invalidateStored;
  el('storedFlop').onchange = () => { el('storedBoard').value = el('storedFlop').value.match(/../g).join(' '); loadStored(); };
  el('storedLoad').onclick = loadStored;
  function color(a) { return a.startsWith('Allin') ? 'var(--allin)' : /^(Bet|Raise)/.test(a) ? 'var(--raise)' : a === 'Fold' ? 'var(--fold)' : 'var(--call)'; }
  function draw() {
    const r = state.result; if (!r) return;
    el('solveResult').hidden = false;
    const key = state.path.join('-'), n = r.nodes[key];
    el('solveBoard').innerHTML = CustomSolver.cardsHTML(r.board);
    el('solveSummary').innerHTML = [['Pot', `${+fmt(r.pot)}bb`], ['Stack', `${+fmt(r.stack)}bb`],
      ...(r.exploit != null ? [['Exploit.', `${(r.exploit * 100).toFixed(2)}%`]] : [])]
      .map(([label, value]) => `<span class="solve-metric"><small>${label}</small><b>${value}</b></span>`).join('');
    el('solveRun').textContent = [r.source === 'saved' ? 'Saved solution' : 'Custom solve',
      r.iters != null ? `${r.iters} iterations` : '', r.mem_gb != null ? `${r.mem_gb} GB` : ''].filter(Boolean).join(' · ');
    const input = state.input;
    el('solveSubmitted').textContent = input.description || (`Out of position: ${input.oop}\nIn position: ${input.ip}\n`
      + ['flop', 'turn', 'river'].map(s => `${s}: ${input[s + '_sizes'].join(' / ')}`).join('\n'));
    let prior = '', crumbs = ['Start'];
    state.path.forEach(i => { const node = r.nodes[prior]; crumbs.push(`${node.player ? 'IP' : 'OOP'} ${node.actions[i]}`); prior = CustomSolver.nextKey(prior, i); });
    el('solvePath').textContent = crumbs.join(' → ');
    el('solveBack').disabled = el('solveRoot').disabled = !state.path.length;
    el('solveNode').hidden = !n; el('solveEnding').hidden = !!n;
    if (!n) { el('solveEnding').textContent = CustomSolver.ending(r, state.path); return; }
    el('solvePlayer').textContent = `${n.player ? 'IP' : 'OOP'} → Act`;
    const whole = CustomSolver.average(n, n.hands.map((_, i) => i));
    el('solveActions').innerHTML = n.actions.map((a, i) => `<button type="button" data-action="${i}" style="border-color:${color(a)}">${esc(a)} <b>${whole[i].toFixed(1)}%</b></button>`).join('');
    if (!state.selected || !CustomSolver.group(n, state.selected).length) state.selected = n.hands.length ? CustomSolver.handClass(n.hands[n.reach.indexOf(Math.max(...n.reach))]) : '';
    const hands = [...'AKQJT98765432'];
    el('solveGrid').innerHTML = hands.flatMap((a, i) => hands.map((b, j) => {
      const h = i === j ? a + b : i < j ? a + b + 's' : b + a + 'o', indices = CustomSolver.group(n, h);
      const mix = CustomSolver.average(n, indices), total = mix.reduce((s, v) => s + v, 0); let at = 0;
      const stops = mix.map((v, k) => { const start = at; at += total ? v * 100 / total : 0; return `${color(n.actions[k])} ${start}% ${at}%`; });
      const title = `${h}: ` + (total ? n.actions.map((a, k) => `${a} ${mix[k].toFixed(1)}%`).join(', ') : 'not reached');
      return `<button type="button" data-hand="${h}" aria-label="${esc(title)}" title="${esc(title)}" ${indices.length ? '' : 'disabled'} class="${state.selected === h ? 'selected' : ''}" style="${total ? `background:linear-gradient(to right,${stops});` : 'opacity:.3;'}">${h}</button>`;
    })).join('');
    const indices = CustomSolver.group(n, state.selected), mix = CustomSolver.average(n, indices);
    el('solveHandTitle').textContent = `${state.selected} · ${indices.length} combo${indices.length === 1 ? "" : "s"}`;
    el('solveHandMix').textContent = n.actions.map((a, i) => `${a}: ${mix[i].toFixed(1)}%`).join(' · ');
    el('solveCombos').innerHTML = '<thead><tr><th>Hand</th>' + n.actions.map(a => `<th>${esc(a)}<br><small>% · EV (bb)</small></th>`).join('') + '</tr></thead><tbody>'
      + indices.map(h => `<tr><th>${CustomSolver.cardsHTML(n.hands[h])}${n.reach[h] ? '' : '<br><small>Off-path</small>'}</th>` + n.actions.map((_, a) => `<td>${n.strat[a][h]}% · ${signed(n.ev[a][h])}</td>`).join('') + '</tr>').join('') + '</tbody>';
  }
  el('solveActions').onclick = e => { const b = e.target.closest('[data-action]'); if (b) { state.path.push(+b.dataset.action); draw(); } };
  el('solveGrid').onclick = e => { const b = e.target.closest('[data-hand]'); if (b) { state.selected = b.dataset.hand; draw(); } };
  el('solveBack').onclick = () => { state.path.pop(); draw(); };
  el('solveRoot').onclick = () => { state.path = []; draw(); };
  el('solveHand').oninput = () => {
    const h = el('solveHand').value.trim(), n = state.result?.nodes[state.path.join('-')];
    if (!n) return;
    if (/^[2-9TJQKA][cdhs][2-9TJQKA][cdhs]$/i.test(h)) {
      const c = h[0].toUpperCase() + h[1].toLowerCase() + h[2].toUpperCase() + h[3].toLowerCase();
      const index = n.hands.findIndex(v => v === c || v === c.slice(2) + c.slice(0, 2));
      if (index < 0) { el('solveHandNote').textContent = 'Blocked or outside this range.'; return; }
      state.selected = CustomSolver.handClass(c); draw(); el('solveHandNote').textContent = `${CustomSolver.cardText(n.hands[index])} · See combo below`;
    } else {
      const c = h.slice(0, 2).toUpperCase() + h.slice(2).toLowerCase();
      if (CustomSolver.group(n, c).length) { state.selected = c; draw(); el('solveHandNote').textContent = ''; }
      else el('solveHandNote').textContent = h ? 'Use AKs, AA or AhKh.' : '';
    }
  };
  busy(false);
});
