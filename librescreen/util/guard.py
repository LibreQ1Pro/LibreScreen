"""A service must not die of a bug in one handler: an exception of a click, a refresh or a message of Moonraker is logged (with its traceback) and the
service goes on. The same error is logged in full the first three times, then once in a thousand (a refresh runs every 50 ms)."""

import logging

log = logging.getLogger(__name__)

_count = {}


def run_guarded(func, *args):
    """Calls ``func(*args)``; returns its result, or None when it raised (the exception is logged)."""
    try:
        return func(*args)
    except Exception as error:
        key = (getattr(func, "__module__", ""), getattr(func, "__name__", ""), type(error).__name__, str(error)[:80])
        _count[key] = _count.get(key, 0) + 1
        if _count[key] <= 3 or _count[key] % 1000 == 0:
            log.exception("%s failed (%d times)", getattr(func, "__name__", func), _count[key])
        return None
