// node solver/test_postways.js   Checks postflop.js's ways() against every scenario make_jobs.py writes: each player's last
// preflop spot exists, postScen() finds the scenario from it, and the closer's preflop line puts in the solved pot's size.
const fs = require("fs"), vm = require("vm"), path = require("path"), D = path.join(__dirname, "..");
const sizes = JSON.parse(require("child_process").execFileSync("python3", ["-I", "-c",
  "import sys,json; sys.path.insert(0, sys.argv[1]); import make_jobs as m; print(json.dumps({n: z for _, g, n, a, b, z, d in m.scenarios()}))", __dirname]));
const html = fs.readFileSync(path.join(D, "index.html"), "utf8");
const cut = (from, to) => { const i = html.indexOf(from), j = html.indexOf(to, i); if (i < 0 || j < 0) throw from; return html.slice(i, j); };
const ctx = vm.createContext({ window: {} }); ctx.window = ctx;
vm.runInContext("window.SPOTS = {}; window.SIZES = {};", ctx);
for (const f of ["data.js", "data200.js", "data8.js", "data6.js"]) vm.runInContext(fs.readFileSync(path.join(D, f), "utf8"), ctx);
vm.runInContext([cut("const ORDER = ", "\n"), cut("const RAISE_NAME", "\n// ---------- sound"), cut("function parse(key)", "const ALL ="),
  cut("function inPosition", "function actionText"), cut("const NEXT = {", "const nodeKey"),
  `window.POST_INDEX = ${JSON.stringify(Object.fromEntries(Object.keys(sizes).map(k => [k, {}])))};`,
  fs.readFileSync(path.join(D, "postflop.js"), "utf8").split("// ---------- data:")[0],
  "Object.assign(window, { ways, postScen, parse, sizing, SPOTS })"].join("\n"), ctx);
const { ways, postScen, parse, sizing, SPOTS } = ctx;
let bad = 0;
for (const [scen, size] of Object.entries(sizes)) {
  const w = ways(scen), fail = m => { bad++; console.log(scen, m); };
  if (!w) { fail("unknown kind"); continue; }
  for (const [p, key, col] of w) {
    if (!SPOTS[key]) { fail(`no spot ${key}`); continue; }
    if (parse(key).hero !== p) fail(`${key} isn't ${p}'s`);
    if (postScen(parse(key), col === 1 ? "Raise" : "Call", w[1][0]) !== scen) fail(`postScen misses it from ${key}`);
  }
  const line = sizing(parse(w[1][1])).line, put = Math.max(...line.map(x => x[1]));
  if (put !== size) fail(`closer's line ${JSON.stringify(line)} puts in ${put}, solved ${size}`);
}
console.log(bad ? `${bad} failures` : `ok: ${Object.keys(sizes).length} scenarios`);
process.exit(bad ? 1 : 0);
