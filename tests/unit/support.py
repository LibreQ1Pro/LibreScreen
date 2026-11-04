"""What every unit test of the service shares: a clean state of the program for each test, and the screen port that records what it is sent.

The state of the service is a handful of global objects (librescreen.state) and the state of the network pages (connections.S). A test that changes them must not
change what the next test sees, whatever the order the tests run in (tests/run_unit.py --shuffle runs them in a random one).
"""
import copy
import unittest
from unittest.mock import patch

from librescreen import state as g
from librescreen.screen.tx import END, ScreenPort

GLOBALS = ("screen", "klippy", "shown", "levelling", "files", "net", "config", "update", "pictures", "rpc")


def _snapshot(obj):
    saved = {}
    for name, value in vars(obj).items():
        if isinstance(obj, type) and name.startswith("__"):        # a class used as a namespace (connections.S): its data, not the machinery of the class
            continue
        try:
            saved[name] = copy.deepcopy(value)
        except Exception:               # a queue or a lock: it is shared, the test leaves it as it found it
            saved[name] = value
    return saved


def _restore(obj, saved):
    if isinstance(obj, type):
        for name, value in saved.items():
            setattr(obj, name, value)
        return
    vars(obj).clear()
    vars(obj).update(saved)


class IsolatedState(unittest.TestCase):
    """The global state of the service is the same at the start of every test and is put back at its end."""

    def setUp(self):
        super().setUp()
        from librescreen.pages import connections
        targets = [getattr(g, name) for name in GLOBALS] + [connections.S]
        saved = [_snapshot(target) for target in targets]
        self.addCleanup(lambda: [_restore(target, state) for target, state in zip(targets, saved)])


class PortRecorder(IsolatedState):
    """A test that looks at what the service sends to the screen: ``self.sent()`` is the list of the instructions."""

    def setUp(self):
        super().setUp()
        self.commands = []
        self.port = ScreenPort()
        self.port._send = self.commands.append
        patcher = patch.object(g, "port", self.port)
        patcher.start()
        self.addCleanup(patcher.stop)

    def sent(self):
        return [c[:-len(END)].decode("utf-8") for c in self.commands]
