// Exercise actual UI handlers with a small DOM surface; network responses are controlled to test recovery.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const input = {board:'AhKd2c',pot:5.5,stack:97.5,oop:'22+,AQs',ip:'AA,KK',flop_sizes:['33%','3x'],turn_sizes:['75%','3x'],river_sizes:['75%','3x']};
const result = {board:input.board,pot:5.5,stack:97.5,iters:10,exploit:.005,mem_gb:.1,nodes:{'':{player:0,actions:['Check','Bet 2'],hands:['AsQs'],reach:[.00001],strat:[[25],[75]],ev:[[2],[3]]}}};
function setup(respond) {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id,{value:'',textContent:'',hidden:false,disabled:false,showModal(){},close(){},setAttribute(){}}); return elements.get(id); };
  const storage = new Map([['gto-custom-job','a'.repeat(32)]]);
  const ctx = {document:{getElementById:get,addEventListener(_,f){f();}},window:{POST_BASE:'https://example.test/'},
    sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    setTimeout:()=>1,clearTimeout(){},AbortSignal,Response,fetch:respond,console};
  vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../custom-solver.js'),'utf8'),ctx);
  return get;
}
const flush = async () => { for (let i=0;i<10;i++) await new Promise(setImmediate); };
(async () => {
  const get = setup(async url => new Response(JSON.stringify(url.endsWith('/result') ? result : {state:'done',input,id:'a'.repeat(32)})));
  assert.equal(get('solveSubmit').disabled,true,'Unresolved restored job must not allow another submission');
  get('solveModeCustom').onclick();
  get('solveResume').onclick(); await flush();
  assert.equal(get('solveResult').hidden,false);
  assert.match(get('solveSubmitted').textContent,/22\+,AQs/,'Result must identify the submitted OOP range, not the form defaults');
  assert.match(get('solveSubmitted').textContent,/AA,KK/);
  assert.match(get('solveSubmitted').textContent,/33%.*3x/);
  assert.match(get('solveActions').innerHTML,/75\.0%/);
  assert.match(get('solveBoard').innerHTML,/A♥/);
  assert.match(get('solveSummary').innerHTML,/5\.5bb/);
  assert.match(get('solveGrid').innerHTML,/class="selected"/);
  assert.equal(get('solveSubmit').disabled,false);
  const disconnected = setup(async () => { throw new Error('Network unavailable'); });
  disconnected('solveResume').onclick(); await flush();
  assert.equal(disconnected('solveSubmit').disabled,true);
  assert.equal(disconnected('solveResume').hidden,false);
  assert.equal(disconnected('solveCancel').hidden,false);
  const expired = setup(async () => new Response(JSON.stringify({error:'Expired'}),{status:404}));
  expired('solveResume').onclick(); await flush();
  assert.equal(expired('solveSubmit').disabled,false);
  console.log('ok: UI reconnect, immutable submitted ranges, weighted results, disconnected and expired jobs');
})().catch(e=>{console.error(e);process.exitCode=1;});
