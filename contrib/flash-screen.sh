#!/bin/sh

# flash-screen.sh FILE.tft [extra flasher arguments]
# Stops the librescreen service, flashes the screen firmware, then starts the service
# again (on every exit path).

set -u
PATH=/usr/sbin:/usr/bin:/sbin:/bin

FILE=${1:-}
if [ -z "$FILE" ]; then
    echo "usage: flash-screen.sh FILE.tft [extra flasher arguments]" >&2
    exit 2
fi
if [ ! -f "$FILE" ]; then
    echo "flash-screen.sh: $FILE is not a file" >&2
    exit 2
fi
shift
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SERVICE=${LIBRESCREEN_SERVICE:-librescreen}
FLASH_TIMEOUT=${LIBRESCREEN_FLASH_TIMEOUT:-1800}

trap 'systemctl start "$SERVICE"; systemctl is-active "$SERVICE"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

echo "Stopping $SERVICE"
systemctl stop "$SERVICE"

export PYTHONDONTWRITEBYTECODE=1
status=0
timeout --signal=INT --kill-after=10s "$FLASH_TIMEOUT" \
    python3 -u "$DIR/main.py" --flash-screen "$FILE" ${1+"$@"} || status=$?

case "$status" in
0)
    echo "Firmware transfer acknowledged in full"
    ;;
130 | 143)
    echo "flash-screen.sh: interrupted. The screen is likely stuck in download mode;" >&2
    echo "power-cycle the printer before the next flashing attempt." >&2
    ;;
*)
    echo "flash-screen.sh: flashing failed (status $status)." >&2
    echo "If the transfer was cut off, power-cycle the printer before the next attempt." >&2
    ;;
esac

echo "Starting $SERVICE"
exit "$status"
