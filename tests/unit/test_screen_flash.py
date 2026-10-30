"""Firmware download: UART sequencing, deadlines and real CLI exit status. No printer UART is opened."""

from contextlib import ExitStack
import io
import os
import signal
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from unittest import mock

from xindi import main
from xindi.config import runtime
from xindi.screen import flash


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ScreenFlashTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = os.path.join(self.directory.name, "screen.tft")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(runtime, "cfg", runtime.Runtime()))
        self.stdout = self.stack.enter_context(mock.patch("sys.stdout", new_callable=io.StringIO))
        self.stderr = self.stack.enter_context(mock.patch("sys.stderr", new_callable=io.StringIO))
        self.events = []
        self.open = self.stack.enter_context(mock.patch.object(flash.os, "open", return_value=71))
        self.close = self.stack.enter_context(mock.patch.object(flash.os, "close"))
        self.baud = self.stack.enter_context(mock.patch.object(flash, "_set_baud", wraps=flash._set_baud))
        self.configure = self.stack.enter_context(mock.patch.object(flash.termios, "tcsetattr"))
        self.flush = self.stack.enter_context(mock.patch.object(flash.termios, "tcflush"))
        self.drain = self.stack.enter_context(mock.patch.object(flash.termios, "tcdrain", side_effect=lambda fd: self.events.append(("drain",))))
        self.sleep = self.stack.enter_context(mock.patch.object(flash.time, "sleep", side_effect=lambda delay: self.events.append(("sleep", delay))))
        self.ready = self.stack.enter_context(mock.patch.object(flash.select, "select", side_effect=lambda r, w, e, t: (r, w, [])))
        self.read = self.stack.enter_context(mock.patch.object(flash.os, "read", side_effect=self.ack))
        self.write = self.stack.enter_context(mock.patch.object(flash.os, "write", side_effect=self.write_bytes))

    def firmware(self, size):
        data = (bytes(range(256)) * ((size + 255) // 256))[:size]
        with open(self.path, "wb") as source:
            source.write(data)
        return data

    def write_bytes(self, fd, data):
        self.events.append(("write", bytes(data)))
        return len(data)

    def ack(self, fd, size):
        self.events.append(("ack",))
        return b"\x05"

    def test_short_and_full_blocks_wait_for_the_last_ack(self):
        for size in (1, 2048, 4095, 4096, 4097, 8192):
            with self.subTest(size=size):
                data = self.firmware(size)
                self.events.clear()
                self.assertEqual(flash.main(self.path), 0)
                command = ("whmi-wri %d,921600,0\xff\xff\xff" % size).encode("latin-1")
                expected = [("write", command), ("sleep", 0.01), ("ack",)]
                for offset in range(0, size, flash.BLOCK_SIZE):
                    block = data[offset:offset + flash.BLOCK_SIZE]
                    for start in range(0, len(block), flash.WRITE_SIZE):
                        chunk = block[start:start + flash.WRITE_SIZE]
                        expected.append(("write", chunk))
                        if len(chunk) == flash.WRITE_SIZE:
                            expected.append(("drain",))
                    expected.extend([("sleep", 0.005), ("ack",)])
                self.assertEqual(self.events, expected)
        self.assertIn("download acknowledged in full", self.stdout.getvalue())
        self.assertEqual(self.close.call_count, 12)

    def test_partial_writes_do_not_lose_bytes_or_shift_drain_boundaries(self):
        data = self.firmware(5000)
        command = b"whmi-wri 5000,921600,0\xff\xff\xff"
        sent = bytearray()
        drained = []

        def write(fd, chunk):
            count = min(7, len(chunk))
            sent.extend(chunk[:count])
            return count

        self.write.side_effect = write
        self.drain.side_effect = lambda fd: drained.append(len(sent) - len(command))
        self.assertEqual(flash.main(self.path), 0)
        self.assertEqual(bytes(sent), command + data)
        self.assertEqual(drained, [2048, 4096])

    def test_temporary_read_and_write_errors_are_retried(self):
        data = self.firmware(3)
        self.write.side_effect = [BlockingIOError(), InterruptedError(), len(b"whmi-wri 3,921600,0\xff\xff\xff"), 3]
        self.read.side_effect = [BlockingIOError(), InterruptedError(), b"\x05", b"\x05"]
        self.assertEqual(flash.main(self.path), 0)
        self.assertEqual(self.write.call_args.args[1], data)

    def test_the_baud_switch_preserves_the_working_open_command_close_reopen_sequence(self):
        data = self.firmware(1)
        runtime.cfg.screen_port = "/dev/ttyUSB3"
        runtime.cfg.transfer_baud = 230400
        self.open.side_effect = [71, 72]
        trace = mock.Mock()
        for name in ("open", "close", "baud", "write", "sleep", "read"):
            trace.attach_mock(getattr(self, name), name)
        self.assertEqual(flash.main(self.path), 0)
        flags = os.O_RDWR | os.O_NONBLOCK | os.O_NOCTTY
        self.assertEqual(trace.mock_calls, [
            mock.call.open("/dev/ttyUSB3", flags), mock.call.baud(71, 115200),
            mock.call.write(71, b"whmi-wri 1,230400,0\xff\xff\xff"), mock.call.sleep(0.01),
            mock.call.close(71), mock.call.open("/dev/ttyUSB3", flags), mock.call.baud(72, 230400),
            mock.call.read(72, 1), mock.call.write(72, data), mock.call.sleep(0.005),
            mock.call.read(72, 1), mock.call.close(72),
        ])
        self.assertEqual(self.flush.call_args_list, [mock.call(71, termios.TCIOFLUSH), mock.call(72, termios.TCIOFLUSH)])

    def test_the_same_baud_rate_needs_no_reopen_after_the_command(self):
        self.firmware(1)
        runtime.cfg.transfer_baud = runtime.cfg.screen_baud
        self.assertEqual(flash.main(self.path), 0)
        self.open.assert_called_once()
        self.baud.assert_called_once_with(71, runtime.cfg.screen_baud)
        self.close.assert_called_once_with(71)

    def test_empty_or_missing_firmware_is_rejected_before_opening_the_uart(self):
        for exists in (False, True):
            with self.subTest(exists=exists):
                if exists:
                    self.firmware(0)
                self.assertEqual(flash.main(self.path), 2)
        self.open.assert_not_called()
        self.close.assert_not_called()

    def test_an_unsupported_baud_rate_is_rejected_before_opening_the_uart(self):
        self.firmware(1)
        for setting in ("screen_baud", "transfer_baud"):
            for baud in (0, -1, 12345):
                with self.subTest(setting=setting, baud=baud):
                    with mock.patch.object(runtime.cfg, setting, baud):
                        self.assertEqual(flash.main(self.path), 2)
        self.open.assert_not_called()

    def test_an_unreadable_firmware_file_is_rejected_before_opening_the_uart(self):
        with mock.patch("builtins.open", side_effect=PermissionError("firmware unreadable")):
            self.assertEqual(flash.main(self.path), 2)
        self.open.assert_not_called()
        self.assertIn("firmware unreadable", self.stderr.getvalue())

    def test_an_open_error_is_reported_as_failure(self):
        self.firmware(1)
        self.open.side_effect = PermissionError("UART permission denied")
        self.assertEqual(flash.main(self.path), 1)
        self.close.assert_not_called()
        self.assertIn("UART permission denied", self.stderr.getvalue())

    def test_a_reopen_error_does_not_close_the_old_descriptor_twice(self):
        self.firmware(1)
        self.open.side_effect = [71, PermissionError("cannot reopen UART")]
        self.assertEqual(flash.main(self.path), 1)
        self.close.assert_called_once_with(71)
        self.read.assert_not_called()

    def test_baud_configuration_errors_close_each_opened_port(self):
        self.firmware(1)
        for results in ([termios.error("initial baud failed")], [None, termios.error("transfer baud failed")]):
            with self.subTest(results=results):
                self.close.reset_mock()
                self.baud.side_effect = results
                self.assertEqual(flash.main(self.path), 1)
                self.assertEqual(self.close.call_count, len(results))

    def test_a_flush_error_closes_the_port(self):
        self.firmware(1)
        self.flush.side_effect = termios.error("flush failed")
        self.assertEqual(flash.main(self.path), 1)
        self.write.assert_not_called()
        self.close.assert_called_once_with(71)

    def test_a_read_or_write_error_is_not_reported_as_success(self):
        self.firmware(1)
        for operation, closes in ((self.read, 2), (self.write, 1)):
            with self.subTest(operation=operation):
                self.close.reset_mock()
                previous = operation.side_effect
                operation.side_effect = OSError("UART disconnected")
                self.assertEqual(flash.main(self.path), 1)
                self.assertEqual(self.close.call_count, closes)
                operation.side_effect = previous
        self.assertNotIn("acknowledged in full", self.stdout.getvalue())

    def test_a_zero_length_read_or_write_fails(self):
        self.firmware(1)
        for operation, result, closes in ((self.read, b"", 2), (self.write, 0, 1)):
            with self.subTest(result=result):
                self.close.reset_mock()
                previous = operation.side_effect
                operation.side_effect = None
                operation.return_value = result
                self.assertEqual(flash.main(self.path), 1)
                self.assertEqual(self.close.call_count, closes)
                operation.side_effect = previous

    def test_the_initial_ack_timeout_sends_no_firmware(self):
        self.firmware(4097)
        with mock.patch.object(flash, "_wait_ack", side_effect=TimeoutError("screen did not answer")):
            self.assertEqual(flash.main(self.path), 1)
        self.assertEqual(self.write.call_count, 1)
        self.assertEqual(self.close.call_count, 2)

    def test_the_final_ack_timeout_is_failure_even_after_all_bytes_were_written(self):
        self.firmware(4097)
        with mock.patch.object(flash, "_wait_ack", side_effect=[None, None, TimeoutError("final ACK missing")]):
            self.assertEqual(flash.main(self.path), 1)
        self.assertIn("4096 bytes acknowledged", self.stderr.getvalue())
        self.assertIn("final ACK missing", self.stderr.getvalue())
        self.assertNotIn("100%", self.stdout.getvalue())
        self.assertNotIn("acknowledged in full", self.stdout.getvalue())
        self.assertEqual(self.close.call_count, 2)

    def test_a_drain_error_or_timeout_stops_the_transfer(self):
        self.firmware(4096)
        for error in (termios.error("drain failed"), TimeoutError("drain timed out")):
            with self.subTest(error=error):
                self.write.reset_mock()
                self.read.reset_mock()
                self.close.reset_mock()
                self.drain.side_effect = error
                self.assertEqual(flash.main(self.path), 1)
                self.assertEqual(self.write.call_count, 2)  # command and first 2048-byte piece
                self.read.assert_called_once()  # initial ACK only
                self.assertEqual(self.close.call_count, 2)
        self.assertNotIn("acknowledged in full", self.stdout.getvalue())

    def test_interruption_returns_130_and_closes_the_port(self):
        self.firmware(1)
        self.read.side_effect = KeyboardInterrupt
        self.assertEqual(flash.main(self.path), 130)
        self.assertEqual(self.close.call_count, 2)
        self.assertIn("interrupted", self.stderr.getvalue())

    def test_the_command_line_preserves_the_flash_exit_status(self):
        self.firmware(1)
        with mock.patch.object(main.runtime, "load"), mock.patch.object(main, "setup_logging"), \
             mock.patch.object(main.sys, "argv", ["main.py", "--flash-screen", self.path]):
            for status in (0, 1, 2, 130):
                with self.subTest(status=status), mock.patch.object(main.flash, "main", return_value=status):
                    self.assertEqual(main.run(), status)

    def test_the_command_line_rejects_a_missing_file_without_flashing(self):
        with mock.patch.object(main.runtime, "load"), mock.patch.object(main, "setup_logging"), \
             mock.patch.object(main.sys, "argv", ["main.py", "--flash-screen", self.path]), \
             mock.patch.object(main.flash, "main") as download:
            self.assertEqual(main.run(), 2)
        download.assert_not_called()

    def test_a_silent_uart_has_a_deadline(self):
        self.ready.side_effect = None
        self.ready.return_value = ([], [], [])
        with mock.patch.object(flash.time, "monotonic", side_effect=[0, 0, 11]):
            with self.assertRaisesRegex(TimeoutError, "waiting for ACK"):
                flash._wait_ack(71, "waiting for ACK")
        self.read.assert_not_called()

    def test_unrelated_bytes_do_not_extend_the_ack_deadline(self):
        self.read.side_effect = None
        self.read.return_value = b"\xff"
        with mock.patch.object(flash.time, "monotonic", side_effect=[0, 0, 5, 11]):
            with self.assertRaises(TimeoutError):
                flash._wait_ack(71, "waiting for ACK")
        self.assertEqual(self.read.call_count, 2)

    def test_a_blocked_write_has_a_deadline(self):
        self.write.side_effect = BlockingIOError
        with mock.patch.object(flash.time, "monotonic", side_effect=[0, 0, 5, 11]):
            with self.assertRaises(TimeoutError):
                flash._write_all(71, b"data", 10)
        self.assertEqual(self.write.call_count, 2)

    def test_partial_writes_do_not_reset_the_deadline(self):
        self.write.side_effect = None
        self.write.return_value = 1
        with mock.patch.object(flash.time, "monotonic", side_effect=[0, 0, 5, 11]):
            with self.assertRaises(TimeoutError):
                flash._write_all(71, b"data", 10)
        self.assertEqual(self.write.call_count, 2)

    def test_an_interrupted_select_keeps_the_original_deadline(self):
        self.ready.side_effect = InterruptedError
        with mock.patch.object(flash.time, "monotonic", side_effect=[0, 0, 11]):
            with self.assertRaises(TimeoutError):
                flash._wait_ready(71, True, 10, "waiting for ACK")
        self.assertEqual(self.ready.call_count, 2)

    def test_drain_and_writes_share_the_same_block_deadline(self):
        with mock.patch.object(flash.time, "monotonic", side_effect=[0, 0, 1, 2, 11]):
            with self.assertRaisesRegex(TimeoutError, "draining"):
                flash._write_all(71, b"x" * 4096, 10)
        self.drain.assert_called_once_with(71)
        self.assertEqual(self.write.call_count, 2)


class DrainTest(unittest.TestCase):
    def test_a_blocking_drain_is_interrupted_by_a_real_alarm(self):
        previous_handler = signal.getsignal(signal.SIGALRM)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0, 0))
        with mock.patch.object(flash.termios, "tcdrain", side_effect=lambda fd: signal.pause()):
            with self.assertRaisesRegex(TimeoutError, "draining"):
                flash._drain(71, time.monotonic() + 0.05)
        self.assertEqual(signal.getsignal(signal.SIGALRM), previous_handler)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0, 0))

    def test_an_already_expired_deadline_does_not_call_tcdrain(self):
        with mock.patch.object(flash.termios, "tcdrain") as drain:
            with self.assertRaises(TimeoutError):
                flash._drain(71, time.monotonic() - 1)
        drain.assert_not_called()

    def test_an_interrupted_drain_is_retried_without_resetting_the_alarm(self):
        with mock.patch.object(flash.termios, "tcdrain", side_effect=[InterruptedError(), None]) as drain, \
             mock.patch.object(flash.signal, "setitimer", wraps=signal.setitimer) as timer:
            flash._drain(71, time.monotonic() + 10)
        self.assertEqual(drain.call_count, 2)
        self.assertEqual(timer.call_count, 2)  # arm once, then disarm
        self.assertEqual(timer.call_args, mock.call(signal.ITIMER_REAL, 0))

    def test_the_previous_alarm_is_restored_on_success_and_failure(self):
        for error in (None, OSError("drain failed"), KeyboardInterrupt()):
            with self.subTest(error=error), \
                 mock.patch.object(flash.time, "monotonic", side_effect=[5, 6]), \
                 mock.patch.object(flash.termios, "tcdrain", side_effect=error), \
                 mock.patch.object(flash.signal, "getitimer", return_value=(9, 2)), \
                 mock.patch.object(flash.signal, "signal", return_value=signal.SIG_DFL) as handler, \
                 mock.patch.object(flash.signal, "setitimer") as timer:
                if error is None:
                    flash._drain(71, 10)
                else:
                    with self.assertRaises(type(error)):
                        flash._drain(71, 10)
                self.assertEqual(timer.call_args_list, [
                    mock.call(signal.ITIMER_REAL, 5), mock.call(signal.ITIMER_REAL, 0),
                    mock.call(signal.ITIMER_REAL, 8, 2),
                ])
                self.assertEqual(handler.call_args_list, [
                    mock.call(signal.SIGALRM, flash._drain_timeout), mock.call(signal.SIGALRM, signal.SIG_DFL),
                ])


class BaudTest(unittest.TestCase):
    def test_setting_baud_flushes_before_applying_the_old_raw_8n1_flags(self):
        with mock.patch.object(flash.termios, "tcsetattr") as configure, \
             mock.patch.object(flash.termios, "tcflush") as flush:
            trace = mock.Mock()
            trace.attach_mock(flush, "flush")
            trace.attach_mock(configure, "configure")
            flash._set_baud(71, 230400)
            args = configure.call_args.args
            self.assertEqual(trace.mock_calls[0], mock.call.flush(71, termios.TCIOFLUSH))
            self.assertEqual(args[:2], (71, termios.TCSANOW))
            self.assertEqual(args[2][4:6], [termios.B230400, termios.B230400])
            self.assertEqual(args[2][2], termios.CS8 | termios.CREAD)
            self.assertEqual(args[2][6][termios.VMIN], 0)
            self.assertEqual(args[2][6][termios.VTIME], 0)


class FlashEntryPointTest(unittest.TestCase):
    def test_both_real_entrypoints_return_file_and_uart_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "screen.tft")
            config = os.path.join(directory, "xindi.ini")
            for data, baud, status, message in (
                (None, 115200, 2, "is not a file"),
                (b"", 115200, 2, "firmware file is empty"),
                (b"test", 115200, 1, "screen flash failed"),
                (b"test", 12345, 2, "unsupported baud rate"),
            ):
                with open(config, "w") as source:
                    source.write("[screen]\nport=%s\nbaud=%d\n[paths]\ndata_dir=%s\n" % (
                        os.path.join(directory, "missing-uart"), baud, directory))
                if data is not None:
                    with open(path, "wb") as source:
                        source.write(data)
                for entrypoint in (["main.py"], ["-m", "xindi"]):
                    with self.subTest(entrypoint=entrypoint, data=data, baud=baud):
                        result = subprocess.run([sys.executable] + entrypoint + ["--config", config, "--flash-screen", path],
                                                cwd=ROOT, capture_output=True, text=True, timeout=10)
                        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
                        self.assertIn(message, result.stderr)
                        self.assertNotIn("Traceback", result.stderr)

    def test_both_entrypoints_propagate_all_run_return_values(self):
        for runner in ("runpy.run_path('main.py', run_name='__main__')", "runpy.run_module('xindi', run_name='__main__')"):
            for status in (None, 0, 1, 2, 130):
                with self.subTest(runner=runner, status=status):
                    code = ("import runpy\nfrom unittest import mock\n"
                            "with mock.patch('xindi.main.run', return_value=%r):\n    %s\n" % (status, runner))
                    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, status or 0, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
