/*
 * LD_PRELOAD helper used by the E2E tests: shortens long sleeps so that test
 * scenarios run faster.  Applied identically to the C++ binary and to the
 * Python port (CPython's time.sleep() ends up in clock_nanosleep()).
 *
 *   LIBRESCREEN_SLEEP_SCALE  multiplier applied to sleeps (default 1.0)
 *   LIBRESCREEN_SLEEP_MIN    only sleeps >= this many seconds are scaled (default 0.5)
 *
 * It also makes write() to a pty slave (the virtual screen on /dev/ttyS1)
 * complete instead of failing with EAGAIN / short writes: on the printer the
 * program calls tcdrain() before every write so the UART buffer is always
 * empty, but tcdrain() does not wait on a pty whose buffer is only ~12 KiB, so
 * without this the outcome of a burst of writes would depend on scheduling.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#include <errno.h>
#include <poll.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>

static double scale = -1.0, min_s = 0.5;

static void init(void) {
    if (scale >= 0) return;
    const char *s = getenv("LIBRESCREEN_SLEEP_SCALE");
    const char *m = getenv("LIBRESCREEN_SLEEP_MIN");
    scale = s ? atof(s) : 1.0;
    if (m) min_s = atof(m);
}

static double ts2d(const struct timespec *t) { return t->tv_sec + t->tv_nsec / 1e9; }
static struct timespec d2ts(double d) {
    struct timespec t;
    if (d < 0) d = 0;
    t.tv_sec = (time_t)d;
    t.tv_nsec = (long)((d - (double)t.tv_sec) * 1e9);
    return t;
}
static double adj(double d) { init(); return (d >= min_s) ? d * scale : d; }

int clock_nanosleep(clockid_t clk, int flags, const struct timespec *req, struct timespec *rem) {
    static int (*real)(clockid_t, int, const struct timespec *, struct timespec *);
    if (!real) real = dlsym(RTLD_NEXT, "clock_nanosleep");
    if (flags & TIMER_ABSTIME) {
        struct timespec now;
        clock_gettime(clk, &now);
        double rel = ts2d(req) - ts2d(&now);
        struct timespec nd = d2ts(ts2d(&now) + adj(rel));
        return real(clk, flags, &nd, rem);
    }
    struct timespec r = d2ts(adj(ts2d(req)));
    return real(clk, flags, &r, rem);
}

static int real_nanosleep(const struct timespec *req, struct timespec *rem) {
    static int (*real)(const struct timespec *, struct timespec *);
    if (!real) real = dlsym(RTLD_NEXT, "nanosleep");
    return real(req, rem);
}

int nanosleep(const struct timespec *req, struct timespec *rem) {
    struct timespec r = d2ts(adj(ts2d(req)));
    return real_nanosleep(&r, rem);
}

unsigned int sleep(unsigned int s) {
    struct timespec r = d2ts(adj((double)s));
    while (real_nanosleep(&r, &r) != 0 && errno == EINTR) {}
    return 0;
}

int usleep(useconds_t us) {
    struct timespec r = d2ts(adj(us / 1e6));
    return real_nanosleep(&r, NULL);
}

static int is_pty_slave(int fd) {
    struct stat st;
    if (fstat(fd, &st) != 0 || !S_ISCHR(st.st_mode)) return 0;
    unsigned int maj = major(st.st_rdev);
    return maj >= 136 && maj <= 143;
}

ssize_t write(int fd, const void *buf, size_t n) {
    static ssize_t (*real)(int, const void *, size_t);
    if (!real) real = dlsym(RTLD_NEXT, "write");
    if (!is_pty_slave(fd)) return real(fd, buf, n);
    size_t done = 0;
    while (done < n) {
        ssize_t r = real(fd, (const char *)buf + done, n - done);
        if (r > 0) { done += (size_t)r; continue; }
        if (r < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)) {
            struct pollfd p = {fd, POLLOUT, 0};
            poll(&p, 1, 100);
            continue;
        }
        return done ? (ssize_t)done : r;
    }
    return (ssize_t)done;
}
