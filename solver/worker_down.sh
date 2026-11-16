#!/bin/bash
# TEMPORARY: delete this file once it has run (by 2026-11-30); it removes its own launchd job.
# End the trial-credit worker: terminate gto-worker (its boot volume goes with it), stop gto-vm's sync cron, and put
# the quota back to free-tier only (A1 4/24, 200 GB). Run from the Mac by hand once the worker's queue is done;
# launchd (com.gtotrainer.worker-down) also runs it on 2026-11-30, before the $300 credits end (~2026-12-13) and the
# Pay As You Go card would be charged. Safe to run twice; if the worker can't be confirmed gone it keeps the launchd
# job, shows a notification and exits 1, so run it again by hand.
# 2026-11-15: moved to Nov 30 (launchd 13:00 EST; the worker powers itself off at 17:00 UTC): A1 hours come out of one free
# allowance per calendar month (3,000 OCPU-h, 18,000 GB-h), which gto-vm alone nearly uses up, so worker hours in December
# would push gto-vm past it after the credits end.
export SUPPRESS_LABEL_WARNING=True PATH=/opt/homebrew/bin:$PATH
C=$(grep -m1 '^tenancy' ~/.oci/config | cut -d= -f2 | tr -d ' ')
# gto-vm took each scenario's flops last-first (REVERSE=1) while the worker went first-first; put it back to normal
ssh -o ConnectTimeout=10 gto-vm '~/worker_sync.sh; rm -f ~/.worker_status; crontab -l | grep -v -e worker_sync -e worker_status | sed "s|^@reboot REVERSE=1 |@reboot |" | crontab -
  sudo systemctl stop gto-queue; sudo systemd-run --unit gto-queue --uid ubuntu -p WorkingDirectory=/home/ubuntu -p Environment=HOME=/home/ubuntu /bin/bash /home/ubuntu/solver/run_queue.sh'
for id in $(oci compute instance list -c "$C" --display-name gto-worker --query "data[?\"lifecycle-state\"!='TERMINATED'].id" --raw-output | tr -d '[]",'); do
  oci compute instance terminate --instance-id "$id" --preserve-boot-volume false --force && echo "terminated $id"
done
Q=$(oci limits quota list -c "$C" --name free-tier-only --query 'data[0].id' --raw-output)
python3 -c 'import json,sys; json.dump(json.load(open(sys.argv[1]))["data"]["statements"], open("/tmp/free_stmts.json","w"))' ~/.oci/quota_backup_20261113_191627_pre_trial.json
oci limits quota update --quota-id "$Q" --statements file:///tmp/free_stmts.json --description "Free tier only" --force --query 'data."lifecycle-state"' && echo "quota restored"
# Retire the launchd job only once the worker is really gone. It used to remove itself whatever happened, so a failed run
# (Mac offline, oci login expired) left the worker up with nothing to say so; now the job stays and a notification asks for a re-run.
LEFT=$(oci compute instance list -c "$C" --display-name gto-worker --query "data[?\"lifecycle-state\"!='TERMINATED' && \"lifecycle-state\"!='TERMINATING'].id" --raw-output) || LEFT=unknown
if [ -z "$(printf %s "$LEFT" | tr -d '[]", \n')" ]; then
  rm -f ~/Library/LaunchAgents/com.gtotrainer.worker-down.plist; launchctl bootout gui/$(id -u)/com.gtotrainer.worker-down 2>/dev/null
else
  echo "gto-worker is NOT confirmed gone ($LEFT): the launchd job is kept. Fix the error above and run this script again."
  osascript -e 'display notification "gto-worker was not terminated. Run solver/worker_down.sh again (log: /tmp/worker_down.log)." with title "GTO Trainer: worker still running"' 2>/dev/null
  exit 1
fi
