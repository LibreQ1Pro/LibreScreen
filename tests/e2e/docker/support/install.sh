#!/bin/sh
# Installs the test-harness shell wrapper and stub commands inside the image.
set -e
# /bin/sh wrapper: logs every "sh -c <cmd>" issued by the program under test
# (only the process that has LIBRESCREEN_SHELL_LOG in its environment).
ln -sf /bin/dash /bin/dash.real 2>/dev/null || true
cat > /bin/sh.librescreen <<'EOS'
#!/bin/dash
if [ "$1" = "-c" ] && [ -n "$LIBRESCREEN_SHELL_LOG" ]; then
    printf '%s\036' "$2" >> "$LIBRESCREEN_SHELL_LOG"
fi
unset LIBRESCREEN_SHELL_LOG
exec /bin/dash "$@"
EOS
chmod +x /bin/sh.librescreen
ln -sf /bin/sh.librescreen /bin/sh
for f in /opt/support/stubs/*; do
    install -m 755 "$f" /usr/local/sbin/
done
install -m 755 /opt/support/stubs/systemctl /usr/bin/systemctl
mkdir -p /opt/support/state
