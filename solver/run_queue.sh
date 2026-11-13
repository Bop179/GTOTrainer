#!/bin/bash
# Solve ~/jobs/<scenario>/<flop>.json into ~/results/<scenario>/<flop>.json.gz, scenarios in ~/jobs/order.txt order
# (most common first), skipping finished ones. The next job is looked up after every solve, so adding, removing or
# reordering jobs takes effect without a restart.
# Run on the VM only:  sudo systemd-run --unit gto-queue --uid ubuntu -p WorkingDirectory=/home/ubuntu -p Environment=HOME=/home/ubuntu /bin/bash /home/ubuntu/solver/run_queue.sh
# Progress: tail ~/results/queue.log   Stop: sudo systemctl stop gto-queue
cd ~ || exit 1
BIN=~/solver/target/release/gto-solve
mkdir -p results

next() {
  local d j
  for d in $(cat jobs/order.txt); do
    for j in jobs/$d/*.json; do
      [ -e "results/${j#jobs/}.gz" ] || [ -e "results/${j#jobs/}.gz.failed" ] || { echo "$j"; return 0; }
    done
  done
  return 1
}

while j=$(next); do
  out=results/${j#jobs/}.gz
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
