#!/bin/bash
# Bring the VM's finished flop+turn solves to the trainer: split them on the VM (~/post), then mirror ~/post into ../post.
# Usage: solver/pull_post.sh   (re-run any time; already split flops are skipped)
# ponytail: mirrors everything (~15 MB a solve, ~11 GB for all 760); pass rsync filters if the Mac runs short of disk.
set -e
cd "$(dirname "$0")"
ssh gto-vm 'python3 -I - results post' < split.py
rsync -a --delete gto-vm:post/ ../post/
