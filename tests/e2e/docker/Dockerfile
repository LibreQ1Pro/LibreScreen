# Test environment of the Python port: a fake printer around it (virtual TJC screen, fake Moonraker,
# stubbed system tools). Native architecture, nothing of QIDI's program or binaries is in it.
FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libc6-dev python3 python3-pil python3-numpy python3-aiohttp procps psmisc \
    && rm -rf /var/lib/apt/lists/*

# Test harness support: logging /bin/sh wrapper, stub commands, sleep scaler, pty relay
COPY support/ /opt/support/
COPY relay.c /opt/support/relay.c
RUN gcc -O2 -shared -fPIC /opt/support/timescale.c -o /opt/support/timescale.so -ldl \
    && gcc -O2 /opt/support/relay.c -o /opt/support/relay \
    && sh /opt/support/install.sh
