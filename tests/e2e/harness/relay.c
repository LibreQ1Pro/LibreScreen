/*
 * pty drain relay for the E2E harness: reads everything the program writes to
 * the pty (fd given as argv[1]) as fast as possible and forwards it to stdout
 * (a pipe read by the harness), buffering without limit in between.  This
 * keeps the kernel pty buffer empty so the program's non-blocking writes
 * never fail because the (emulated, slower) Python harness lags behind.
 */
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    int in = atoi(argv[1]);
    int out = 1;
    size_t cap = 1 << 20, len = 0, off = 0;
    char *buf = malloc(cap);
    fcntl(out, F_SETFL, fcntl(out, F_GETFL) | O_NONBLOCK);
    fcntl(out, 1031 /* F_SETPIPE_SZ */, 1 << 20);
    for (;;) {
        struct pollfd p[2] = {{in, POLLIN, 0}, {out, POLLOUT, 0}};
        int n = poll(p, (len > off) ? 2 : 1, -1);
        if (n < 0) { if (errno == EINTR) continue; return 1; }
        if (p[0].revents & POLLIN) {
            if (cap - len < 65536) {
                if (off > 0) { memmove(buf, buf + off, len - off); len -= off; off = 0; }
                if (cap - len < 65536) { cap *= 2; buf = realloc(buf, cap); }
            }
            ssize_t r = read(in, buf + len, cap - len);
            if (r > 0) len += r;
        } else if (p[0].revents & (POLLHUP | POLLERR)) {
            usleep(20000);
        }
        if (len > off && (p[1].revents & POLLOUT)) {
            ssize_t w = write(out, buf + off, len - off);
            if (w > 0) off += w;
            if (off == len) off = len = 0;
        }
    }
}
