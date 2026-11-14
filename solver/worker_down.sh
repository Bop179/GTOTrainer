#!/bin/bash
# End the trial-credit worker: terminate gto-worker (its boot volume goes with it), stop gto-vm's sync cron, and put
# the quota back to free-tier only (A1 4/24, 200 GB). Run from the Mac by hand once the worker's queue is done;
# launchd (com.gtotrainer.worker-down) also runs it on 2026-12-10, before the $300 credits end (~2026-12-13) and the
# Pay As You Go card would be charged. Safe to run twice.
export SUPPRESS_LABEL_WARNING=True PATH=/opt/homebrew/bin:$PATH
C=$(grep -m1 '^tenancy' ~/.oci/config | cut -d= -f2 | tr -d ' ')
ssh -o ConnectTimeout=10 gto-vm '~/worker_sync.sh; crontab -l | grep -v worker_sync | crontab -'
for id in $(oci compute instance list -c "$C" --display-name gto-worker --query "data[?\"lifecycle-state\"!='TERMINATED'].id" --raw-output | tr -d '[]",'); do
  oci compute instance terminate --instance-id "$id" --preserve-boot-volume false --force && echo "terminated $id"
done
Q=$(oci limits quota list -c "$C" --name free-tier-only --query 'data[0].id' --raw-output)
python3 -c 'import json,sys; json.dump(json.load(open(sys.argv[1]))["data"]["statements"], open("/tmp/free_stmts.json","w"))' ~/.oci/quota_backup_20261113_191627_pre_trial.json
oci limits quota update --quota-id "$Q" --statements file:///tmp/free_stmts.json --description "Free tier only" --force --query 'data."lifecycle-state"' && echo "quota restored"
rm -f ~/Library/LaunchAgents/com.gtotrainer.worker-down.plist; launchctl bootout gui/$(id -u)/com.gtotrainer.worker-down 2>/dev/null
