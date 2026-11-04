#!/bin/sh
# Builds the test image librescreen-port-test (native architecture, a minute or so).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cp "$HERE/harness/relay.c" "$HERE/docker/relay.c"
trap 'rm -f "$HERE/docker/relay.c"' EXIT
docker build -t librescreen-port-test "$HERE/docker"
