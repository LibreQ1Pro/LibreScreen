"""The connection to Moonraker is made again when it is gone."""
import unittest
from unittest.mock import patch

from librescreen import main
from librescreen import state as g


class FakeClient:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = []

    def poll_status(self):
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]

    def close(self):
        self.calls.append("close")

    def connect(self, url):
        self.calls.append("connect " + url)


class ReconnectTest(unittest.TestCase):
    def reconnect(self, statuses):
        client = FakeClient(statuses)
        with patch.object(g, "ep", client), patch.object(main.time, "sleep"), \
             patch.object(main.klipper, "sub_object_status") as subscribe, patch.object(main.klipper, "get_object_status") as query:
            return client, main.reconnect_moonraker("ws://x/websocket?"), subscribe, query

    def test_a_closed_connection_is_made_again_and_the_state_is_asked_for(self):
        client, done, subscribe, query = self.reconnect(["Closed", "Connecting", "Open"])
        self.assertTrue(done)
        self.assertEqual(client.calls, ["close", "connect ws://x/websocket?"])
        subscribe.assert_called_once()
        query.assert_called_once()

    def test_an_open_or_a_connecting_connection_is_left_alone(self):
        for status in ("Open", "Connecting"):
            client, done, subscribe, query = self.reconnect([status])
            self.assertFalse(done)
            self.assertEqual(client.calls, [])
            subscribe.assert_not_called()

    def test_a_server_that_does_not_answer_is_tried_again_later(self):
        with patch.object(main.time, "monotonic", side_effect=[0.0, 1.0, 9.0]):
            client = FakeClient(["Failed", "Failed", "Failed"])
            with patch.object(g, "ep", client), patch.object(main.time, "sleep"), patch.object(main.klipper, "sub_object_status") as subscribe:
                self.assertFalse(main.reconnect_moonraker("ws://x/websocket?"))
        subscribe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
