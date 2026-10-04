"""Plain HTTP requests to Moonraker (Python only: the original runs ``curl`` for these)."""

import logging
import urllib.request

from librescreen.config import runtime

log = logging.getLogger(__name__)


def request(method, path, timeout=5):
    """``curl -X <method> http://<moonraker>/<path>``; returns True when Moonraker answered with a success code."""
    url = runtime.cfg.moonraker_url(path)
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=b"" if method == "POST" else None, method=method),
                               timeout=timeout).close()
        return True
    except Exception as e:
        log.error("%s %s: %s", method, url, e)
        return False
