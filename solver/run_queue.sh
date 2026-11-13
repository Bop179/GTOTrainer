#!/bin/bash
# Solve every ~/jobs/<scenario>/<flop>.json into ~/results/<scenario>/<flop>.json.gz, skipping finished ones.
# Run on the VM only:  sudo systemd-run --unit gto-queue --uid ubuntu -p WorkingDirectory=/home/ubuntu bash ~/solver/run_queue.sh
# Progress: tail ~/results/queue.log   Stop: sudo systemctl stop gto-queue
cd ~ || exit 1
BIN=~/solver/target/release/gto-solve
mkdir -p results
for j in jobs/*/*.json; do
  out=results/${j#jobs/}.gz
  [ -e "$out" ] || [ -e "$out.failed" ] && continue
  mkdir -p "$(dirname "$out")"
  if "$BIN" "$j" /tmp/gto-out.json 2>/tmp/gto-err.txt && gzip -c /tmp/gto-out.json > "$out.tmp"; then
    mv "$out.tmp" "$out"
    echo "$(date -u +%FT%TZ) ok $j $(grep -o 'solved.*' /tmp/gto-err.txt)" >> results/queue.log
  else
    # exit 2 = tree over max_gb; anything else is a crash. Either way keep going and leave a marker to look at.
    cp /tmp/gto-err.txt "$out.failed"
    echo "$(date -u +%FT%TZ) FAILED $j $(tail -1 /tmp/gto-err.txt)" >> results/queue.log
  fi
done
echo "$(date -u +%FT%TZ) queue done: $(find results -name '*.gz' | wc -l) solved, $(find results -name '*.failed' | wc -l) failed" >> results/queue.log
