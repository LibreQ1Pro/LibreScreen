"""What the service does with input it should never get: it logs and goes on."""
import logging
import unittest
from unittest.mock import patch

from librescreen.moonraker import rpc_messages
from librescreen.pages import connections
from librescreen.util import guard
from support import IsolatedState


class GuardTest(unittest.TestCase):
    def setUp(self):
        guard._count.clear()

    def test_the_result_of_a_good_call_is_returned(self):
        self.assertEqual(guard.run_guarded(lambda a, b: a + b, 1, 2), 3)

    def test_an_exception_is_logged_and_does_not_escape(self):
        def broken():
            raise ValueError("boom")
        with self.assertLogs(guard.log, logging.ERROR) as logs:
            self.assertIsNone(guard.run_guarded(broken))
        self.assertIn("broken failed", logs.output[0])

    def test_the_same_error_is_logged_rarely(self):
        def broken():
            raise ValueError("boom")
        with self.assertLogs(guard.log, logging.ERROR) as logs:
            for _ in range(50):
                guard.run_guarded(broken)
        self.assertEqual(len(logs.output), 3)


class JunkFromMoonrakerTest(unittest.TestCase):
    def test_messages_that_are_no_jsonrpc_do_not_escape(self):
        for junk in ("[]", "{", "not json", "[1, 2]", '"text"', "null", "12", '{"id": "x"}', '{"method": 5}',
                     '{"jsonrpc":"2.0","method":"notify_status_update","params":[null]}', '{"jsonrpc":"2.0","method":"notify_status_update"}'):
            with self.subTest(junk=junk), patch.object(rpc_messages.log, "error"), patch.object(guard.log, "exception"):
                self.assertIsNone(guard.run_guarded(rpc_messages.handle_message, junk))


class NetworkDetailWithoutNetworkTest(IsolatedState):
    def test_an_event_of_the_detail_page_without_a_chosen_network_goes_back(self):
        connections.S.sel = None
        with patch.object(connections, "_leave_detail") as leave:
            connections.detail_clicked(1)
            connections.confirm_clicked(1)
        self.assertEqual(leave.call_count, 2)


if __name__ == "__main__":
    unittest.main()
