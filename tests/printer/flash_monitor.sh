#!/bin/bash
# What exactly drops out while the screen firmware is being flashed (the printer hangs about a minute into --flash-screen).
#
#   sudo ./flash_monitor.sh [OUTDIR]        (run it in an SSH session, leave it running, start the flash in another one)
#
# Once a second one line of numbers goes to the terminal AND to OUTDIR/samples.log; the file is fsync-ed every second (the file system of the printer
# commits every 120 s, a hang loses what is not synced).  The kernel messages (dmesg -w) and the journal are followed into their own files.
# The first lines of samples.log describe the machine (UART, network driver, kernel, governors).  Stop with Ctrl+C.
#
# Columns of samples.log: time uptime load1 cpu% memfree_MB temp_C(max) freqMHz(cpu0) uartIRQ/s eth_rx_err eth_tx_err eth_drops wlan_err D-state top-process
set -u
OUT=${1:-/home/mks/flash-monitor/$(date +%Y%m%d-%H%M%S)}
UART=${UART:-ttyS1}
IFACE=${IFACE:-eth0}
mkdir -p "$OUT"
S="$OUT/samples.log"

fsync() { sync "$@" 2>/dev/null || sync; }

{
  echo "# $(date -Is) $(uname -a)"
  echo "# governor: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null) freq: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null)"
  echo "# cores: $(nproc)  mem: $(awk '/MemTotal/{print $2/1024" MB"}' /proc/meminfo)"
  echo "# uart $UART: $(stty -F /dev/$UART -a 2>&1 | head -1)"
  echo "# uart driver: $(grep -H . /proc/tty/driver/* 2>/dev/null | grep -i "$(echo "$UART" | tr -dc 0-9):" | head -2)"
  echo "# interrupts of the uart:"; grep -iE "uart|serial|ttyS|dw-apb" /proc/interrupts | sed 's/^/#   /'
  echo "# $IFACE driver: $(ethtool -i "$IFACE" 2>/dev/null | tr '\n' ' ')"
  echo "# thermal zones: $(for z in /sys/class/thermal/thermal_zone*; do echo -n "$(basename $z)=$(cat $z/type 2>/dev/null) "; done)"
  echo "# regulators/power: $(ls /sys/class/power_supply 2>/dev/null | tr '\n' ' ')"
  echo "# modules: $(lsmod | awk 'NR>1{print $1}' | tr '\n' ' ')"
  echo "# last boot kernel errors:"; dmesg 2>/dev/null | grep -iE "error|fail|warn|oops|hung|lockup|thermal" | tail -15 | sed 's/^/#   /'
} | tee "$S"
fsync "$S"

# the kernel and the journal into files of their own (flushed every second by the loop below)
( stdbuf -oL dmesg -w --time-format iso 2>/dev/null > "$OUT/kernel.log" ) &
K=$!
( stdbuf -oL journalctl -f -n 0 -o short-iso-precise 2>/dev/null > "$OUT/journal.log" ) &
J=$!
trap 'kill $K $J 2>/dev/null; fsync "$S" "$OUT/kernel.log" "$OUT/journal.log"; echo "# stopped $(date -Is)" | tee -a "$S"; exit 0' INT TERM

uart_irq() { grep -iE "uart|serial|ttyS" /proc/interrupts | awk '{n=0; for(i=2;i<=NF;i++) if($i ~ /^[0-9]+$/) n+=$i; else break; s+=n} END{print s+0}'; }
cpu_total() { awk '/^cpu /{print $2+$3+$4+$5+$6+$7+$8, $5+$6}' /proc/stat; }
stat_of() { cat "/sys/class/net/$1/statistics/$2" 2>/dev/null || echo 0; }

read pt pi < <(cpu_total); pirq=$(uart_irq)
while true; do
  sleep 1
  read ct ci < <(cpu_total)
  dt=$((ct-pt)); di=$((ci-pi)); [ "$dt" -gt 0 ] && cpu=$(( (100*(dt-di))/dt )) || cpu=0
  pt=$ct; pi=$ci
  irq=$(uart_irq); dirq=$((irq-pirq)); pirq=$irq
  temp=$(cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | sort -n | tail -1); temp=$(( ${temp:-0} / 1000 ))
  freq=$(( $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo 0) / 1000 ))
  memfree=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  top=$(ps -eo pcpu,comm --sort=-pcpu | awk 'NR==2{print $2"("$1"%)"}')
  dstate=$(ps -eo stat | grep -c '^D')
  line="$(date +%T.%N | cut -c1-12) up=$(cut -d' ' -f1 /proc/uptime) load=$(cut -d' ' -f1 /proc/loadavg) cpu=${cpu}% mem=${memfree}M temp=${temp}C f=${freq}MHz uartirq/s=$dirq eth_rxerr=$(stat_of $IFACE rx_errors) txerr=$(stat_of $IFACE tx_errors) drop=$(( $(stat_of $IFACE rx_dropped) + $(stat_of $IFACE tx_dropped) )) D=$dstate top=$top"
  echo "$line" | tee -a "$S"
  fsync "$S" "$OUT/kernel.log" "$OUT/journal.log"
done
