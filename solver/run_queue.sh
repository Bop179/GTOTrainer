#!/bin/bash
# Solve ~/jobs/<scenario>/<flop>.json into ~/results/<scenario>/<flop>.json.gz, scenarios in ~/jobs/order.txt order
# (most common first), skipping finished ones. The next job is looked up after every solve, so adding, removing or
# reordering jobs takes effect without a restart.
# Run on the VM only:  sudo systemd-run --unit gto-queue --uid ubuntu -p WorkingDirectory=/home/ubuntu -p Environment=HOME=/home/ubuntu /bin/bash /home/ubuntu/solver/run_queue.sh
# Progress: tail ~/results/queue.log   Stop: sudo systemctl stop gto-queue
# Parallel (trial worker): ORDER=jobs/worker_order.txt RAYON_NUM_THREADS=4 run_queue.sh 5   (5 solves x 4 threads)
# A result only counts as done if it is newer than results/.since (touched when the dump format changes, so older
# results get re-solved in place; they keep being served until overwritten). No .since file: any result counts.
# REVERSE=1 takes each scenario's flops last-first: gto-vm does that while the worker goes first-first, so both follow
# the scenario priority without solving the same flop.
cd ~ || exit 1
BIN=~/solver/target/release/gto-solve
ORDER=${ORDER:-jobs/order.txt}
N=${1:-1}
CLAIMS=$(mktemp -d)  # jobs taken by this run, so parallel loops never solve the same one
mkdir -p results

next() {
  local d j
  for d in $(cat "$ORDER"); do
    for j in $(ls ${REVERSE:+-r} jobs/$d/*.json); do
      [ "results/${j#jobs/}.gz" -nt results/.since ] || [ "results/${j#jobs/}.gz.failed" -nt results/.since ] || ! mkdir "$CLAIMS/${j//\//_}" 2>/dev/null || { echo "$j"; return 0; }
    done
  done
  return 1
}

loop() {
  local j out tmp=/tmp/gto-out.$1.json err=/tmp/gto-err.$1.txt
  while j=$(next); do
    out=results/${j#jobs/}.gz
    mkdir -p "$(dirname "$out")"
    if "$BIN" "$j" $tmp 2>$err && gzip -c $tmp > "$out.tmp"; then
      mv "$out.tmp" "$out"
      echo "$(date -u +%FT%TZ) ok $j $(grep -o 'solved.*' $err)" >> results/queue.log
    else
      # exit 2 = tree over max_gb; anything else is a crash. Either way keep going and leave a marker to look at.
      cp $err "$out.failed"
      echo "$(date -u +%FT%TZ) FAILED $j $(tail -1 $err)" >> results/queue.log
    fi
  done
}

for i in $(seq "$N"); do loop "$i" & done
wait
rm -rf "$CLAIMS"
echo "$(date -u +%FT%TZ) queue done: $(find results -name '*.gz' | wc -l) solved, $(find results -name '*.failed' | wc -l) failed" >> results/queue.log
