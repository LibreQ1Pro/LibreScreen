#!/bin/bash
# shot.sh IDS OUT.png [lang] [zoom] [W H] [extra]  : screenshot of some screens (ids separated by commas); lang=all for every language
IDS=$1; O=$2; L=${3:-2}; Z=${4:-1}; W=${5:-1500}; H=${6:-540}; X=$7
if [ "$L" = "all" ]; then Q="only=$IDS&all=1&zoom=$Z"; else Q="only=$IDS&lang=$L&zoom=$Z"; fi
google-chrome --headless=new --disable-gpu --hide-scrollbars --window-size=$W,$H --screenshot=$O "file://$(dirname $(realpath $0))/index.html?$Q$X" >/dev/null 2>&1
