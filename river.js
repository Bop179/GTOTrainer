// Live river solves in the browser: postflop-solver compiled to WebAssembly (solver/src/lib.rs), single-threaded.
// river_wasm.js holds the binary as base64 (rebuild with solver/build_wasm.sh) so this works from file:// too.
//   const r = await RiverSolver.solve({oop: {"AhKh": 0.4, ...}, ip: {...}, board: "Ks7d2c5h9s", pot: 20, stack: 87.5,
//                                      river_sizes: ["75%, 125%", "2.5x"], target: 0.01, max_iter: 300});
//   r = {iters, exploit, mem_mb, nodes: {"": root node, "0": after action 0, ...}}  (node format in solver/src/lib.rs)
// ponytail: runs on the main thread (the page pauses while it solves); move into a Worker if solves get slow.
window.RiverSolver = (() => {
  let ready;
  const load = () => ready ??= WebAssembly.instantiate(Uint8Array.from(atob(window.RIVER_WASM), c => c.charCodeAt(0)))
    .then(r => r.instance.exports);
  return {
    load,
    async solve(job) {
      const w = await load(), input = new TextEncoder().encode(JSON.stringify(job));
      const p = w.alloc(input.length);
      new Uint8Array(w.memory.buffer, p, input.length).set(input);
      const r = w.river(p, input.length), n = new DataView(w.memory.buffer).getUint32(r, true);
      const out = JSON.parse(new TextDecoder().decode(new Uint8Array(w.memory.buffer, r + 4, n)));
      w.free(r, n + 4);
      if (out.error) throw new Error(out.error);
      return out;
    },
  };
})();
