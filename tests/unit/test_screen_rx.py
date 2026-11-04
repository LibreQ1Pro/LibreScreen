"""Frame splitting of the screen stream. Pure logic, nothing of the printer is touched:
    PYTHONPATH=. python3 -I -m unittest discover -s tests/unit -t .
"""
import queue
import unittest

from librescreen.screen.rx import END, FrameParser, next_frame


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class FrameParserTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.p = FrameParser(self.clock)

    def test_several_frames_in_one_read(self):
        data = b"\x65\x05\x03\x01" + END + b"\x65\x06\x01\x00" + END + b"\x1a" + END
        self.assertEqual(self.p.feed(data), [b"\x65\x05\x03\x01", b"\x65\x06\x01\x00", b"\x1a"])

    def test_frame_split_between_reads(self):
        self.assertEqual(self.p.feed(b"\x65\x05"), [])
        self.assertEqual(self.p.feed(b"\x03\x01\xff"), [])
        self.assertEqual(self.p.feed(b"\xff\xff\x66"), [b"\x65\x05\x03\x01"])
        self.assertEqual(self.p.feed(b"\x02" + END), [b"\x66\x02"])

    def test_byte_by_byte(self):
        out = []
        for b in (b"\x70\x02\x00abc" + END + b"\x65\x01\x02\x03" + END):
            out += self.p.feed(bytes([b]))
        self.assertEqual(out, [b"\x70\x02\x00abc", b"\x65\x01\x02\x03"])

    def test_click_frames_of_both_lengths(self):
        data = b"\x65\x05\x03" + END + b"\x65\x05\x03\x01" + END
        self.assertEqual(self.p.feed(data), [b"\x65\x05\x03", b"\x65\x05\x03\x01"])
        self.assertEqual(self.p.feed(b"\x65\x05\x03"), [])
        self.assertEqual(self.p.feed(END), [b"\x65\x05\x03"])

    def test_text_frame_runs_to_the_terminator(self):
        text = "пароль с пробелом".encode()
        self.assertEqual(self.p.feed(b"\x70\x01\x00" + text + END), [b"\x70\x01\x00" + text])

    def test_fixed_frame_may_hold_ff_in_the_data(self):
        # a number of -1 sent in two bytes: 71 page widget ff ff, then the terminator
        self.assertEqual(self.p.feed(b"\x71\x20\x07\xff\xff" + END), [b"\x71\x20\x07\xff\xff"])
        self.assertEqual(self.p.feed(b"\x71\x20\x07\xff"), [])
        self.assertEqual(self.p.feed(b"\xff" + END), [b"\x71\x20\x07\xff\xff"])

    def test_single_byte_ack_of_the_picture_transfer(self):
        self.assertEqual(self.p.feed(b"\x05"), [b"\x05"])
        self.assertEqual(self.p.feed(b"\x05\x05"), [b"\x05", b"\x05"])
        self.assertEqual(self.p.feed(b"\x05" + END + b"\x1a" + END), [b"\x05", b"\x1a"])

    def test_empty_frames_and_stray_terminators_are_skipped(self):
        self.assertEqual(self.p.feed(END + END + b"\x1a" + END), [b"\x1a"])

    def test_unfinished_frame_is_dropped_when_stale(self):
        self.p.feed(b"\x70\x01\x00ab")
        self.clock.now = 1.0
        self.assertEqual(self.p.feed(), [])
        self.assertEqual(self.p.dropped, 1)
        self.assertEqual(self.p.feed(b"\x1a" + END), [b"\x1a"])

    def test_fresh_unfinished_frame_is_kept(self):
        self.p.feed(b"\x70\x01\x00ab")
        self.clock.now = 0.05
        self.p.feed()
        self.assertEqual(self.p.feed(b"c" + END), [b"\x70\x01\x00abc"])

    def test_runaway_data_is_dropped(self):
        self.p.feed(b"\x70" + b"a" * 9000)
        self.assertEqual(self.p.dropped, 1)


class NextFrameTest(unittest.TestCase):
    def test_returns_none_when_empty(self):
        self.assertIsNone(next_frame(queue.Queue(), 0.01))

    def test_returns_the_frame(self):
        import time
        q = queue.Queue()
        q.put((time.monotonic(), b"\x1a"))
        self.assertEqual(next_frame(q, 0.01), b"\x1a")

    def test_drops_old_frames(self):
        import time
        q = queue.Queue()
        q.put((time.monotonic() - 60, b"\x65\x01\x02\x03"))
        self.assertIsNone(next_frame(q, 0.01))


if __name__ == "__main__":
    unittest.main()
