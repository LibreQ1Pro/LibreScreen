#!/bin/bash
# Timestamped ping of the printer from another machine: shows the exact second the network of the printer drops while it is busy
# (run it next to flash_monitor.sh, which sees the printer from the inside).
#
#   ./pingwatch.sh 192.168.199.104 [LOGFILE]
HOST=${1:?usage: pingwatch.sh HOST [LOGFILE]}
LOG=${2:-pingwatch.log}
while true; do
  if ping -c1 -W1 "$HOST" >/dev/null 2>&1; then r=up; else r=DOWN; fi
  echo "$(date +%T.%N | cut -c1-12) $r" | tee -a "$LOG"
  sleep 0.5
done
