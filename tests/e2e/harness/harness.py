#!/usr/bin/env python3
"""
E2E test harness - runs INSIDE the xindi-port-test docker image.

It starts the Python screen backend (mounted at /opt/src_py) in a simulated printer environment
and records everything the program does to the outside world:

* a virtual TJC screen on a pty linked to /dev/ttyS1 (records every
  instruction, injects touch / value / keyboard events, implements the
  firmware download (whmi-wri) and file transfer (twfile) protocols),
* a fake Moonraker (websocket JSON-RPC + HTTP API) on 127.0.0.1:7125,
* an optional fake wpa_supplicant control socket,
* every shell command run by the program (/bin/sh wrapper, see install.sh),
* the files the program creates or modifies.

The scenario (see scenarios.py) drives the program; the collected trace is
written as JSON and compared with the golden traces by golden.py.
"""

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import random
import socket
import subprocess
import sys
import threading
import time
import traceback
import tty

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

END = b"\xff\xff\xff"
SHELL_LOG = "/tmp/xindi_shell.log"


def sha(data):
    return hashlib.sha1(data).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Virtual TJC screen
# ---------------------------------------------------------------------------

PROJECT = "/opt/src_py/display_firmware"
_widgets = None


def widgets_of_pages():
    """{page id: (page key, {object key: {attribute names}})} of the screen project, for the check that the port only
    addresses objects the page has, and attributes the object has."""
    global _widgets
    if _widgets is None:
        _widgets = {}
        try:
            with open(os.path.join(PROJECT, "project.json"), encoding="utf-8") as f:
                project = json.load(f)
            for number, entry in enumerate(project["pages"]):
                with open(os.path.join(PROJECT, entry["content"]["path"]), encoding="utf-8") as f:
                    page = json.load(f)
                _widgets[number] = (entry["key"], {o["key"]: set(o["attributes"]) for o in page["objects"]})
        except (OSError, ValueError, KeyError):
            _widgets = {}
    return _widgets


class Screen(threading.Thread):
    """Plays the role of the TJC display on the master side of a pty."""

    def __init__(self, master_fd):
        super().__init__(daemon=True)
        self.fd = master_fd
        self.lock = threading.Lock()
        self.buf = b""
        self.mode = "cmd"           # cmd | twfile | download
        self.mode_info = {}
        self.visits = []            # [{"page": n, "attrs": {key: [values...]}}]
        self.pages = []             # sequence of "page" instructions
        self.events = []            # raw instruction count etc. (debug)
        self.current = {"page": None, "attrs": {}}
        self.visits.append(self.current)
        self.instructions = 0
        self.lang = 2               # the language of the screen (its global ``lang``)
        self.unknown = []           # "page: instruction" for objects the page does not have (invalid variable)
        self.last_instruction = time.time()
        self.lost_pages = []
        self.stopped = False
        self.page_changed = threading.Condition(self.lock)

    # -- outgoing (screen -> program) ------------------------------------
    def send(self, data):
        os.write(self.fd, data)

    def touch(self, page, widget, kind=1):
        self.send(bytes([0x65, page, widget, kind]) + END)

    def set_number(self, page, widget, value):
        self.send(bytes([0x71, page, widget, value & 0xFF, (value >> 8) & 0xFF]) + END)

    def keyboard(self, page, widget, text):
        if isinstance(text, str):
            text = text.encode("utf-8")
        self.send(bytes([0x70, page, widget]) + text + END)

    # -- incoming (program -> screen) ------------------------------------
    def run(self):
        """Reader thread: drains the pty as fast as possible (the program writes
        with O_NONBLOCK and loses data when the pty buffer is full), the data is
        parsed by a second thread."""
        import select
        import collections
        self.chunks = collections.deque()
        self.data_ready = threading.Event()
        parser = threading.Thread(target=self._parser, daemon=True)
        parser.start()
        # a native relay process drains the pty master into a pipe
        relay = "/opt/support/relay"
        rd, wr = os.pipe()
        subprocess.Popen([relay, str(self.fd)], stdout=wr, pass_fds=(self.fd,))
        os.close(wr)
        while not self.stopped:
            try:
                r, _, _ = select.select([rd], [], [], 0.2)
            except (OSError, ValueError):
                break
            if not r:
                continue
            try:
                data = os.read(rd, 1 << 20)
            except OSError:
                time.sleep(0.05)
                continue
            if data:
                self.chunks.append(data)
                self.data_ready.set()

    def _parser(self):
        while True:
            self.data_ready.wait(0.2)
            self.data_ready.clear()
            parts = []
            while self.chunks:
                parts.append(self.chunks.popleft())
            if not parts:
                continue
            with self.lock:
                self.buf += b"".join(parts)
                self._process()

    def _record(self, key, value):
        lst = self.current["attrs"].setdefault(key, [])
        if not lst or lst[-1] != value:
            lst.append(value)
            self.last_instruction = time.time()     # something new reached the screen (repeats do not count)

    def _new_visit(self, page):
        self.current = {"page": page, "attrs": {}}
        self.visits.append(self.current)
        self.pages.append(page)
        self.last_instruction = time.time()
        self.page_changed.notify_all()

    OBJECT_COMMANDS = ("vis", "tsw", "click", "ref", "picq", "cls")

    ignore_unknown = 0      # >0 while a scenario sends events for another page than the one shown
    page_loss = 0.0         # the probability that a "page" instruction is not carried out
    lost_pages = ()

    def _check_object(self, text):
        if self.ignore_unknown:
            return
        """The screen answers 0x1a (invalid variable name) for an object that is not on the page."""
        widgets = widgets_of_pages()
        page = self.current["page"]
        if not widgets or page not in widgets:
            return
        name = attribute = None
        eq, sp = text.find("="), text.find(" ")
        if eq != -1 and (sp == -1 or eq < sp):
            left = text[:eq]
            if "." in left:
                name, attribute = left.rsplit(".", 1)
        elif sp != -1 and text[:sp] in self.OBJECT_COMMANDS:
            name = text[sp + 1:].split(",")[0]
        if not name or not name.replace("_", "a").replace(".", "a").isalnum() or name.isdigit():
            return
        key, objects = widgets[page]
        if "." in name:
            other, _, obj = name.partition(".")
            target = [o for k, o in widgets.values() if k == other]
            ok = bool(target) and obj in target[0]
            attributes = target[0].get(obj) if ok else None
        else:
            ok = name in objects or name == key
            attributes = objects.get(name)
        if ok and attribute is not None and attributes is not None and attribute not in attributes:
            ok = False
        if not ok:
            entry = "page %d (%s): %s" % (page, key, text[:60])
            if entry not in self.unknown:
                self.unknown.append(entry)

    def set_language(self, lang):
        """The user picked a language on the screen: ``lang`` changes and the language pages report it."""
        self.lang = lang
        self.send(bytes([0xa0, lang]) + END)

    def _answer_prints(self, text):
        """``prints N,1`` / ``prints lang,1`` sent by the host: the screen prints the byte."""
        value = text[len("prints "):].split(",")[0]
        if value == "lang":
            self.send(bytes([self.lang]))
        elif value.isdigit() or value.lower().startswith("0x"):
            self.send(bytes([int(value, 0)]))

    def _handle_instruction(self, raw):
        self.instructions += 1
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", "surrogateescape")
        if text == "sendme":                # which page do you show? (the host asks all the time: not part of the trace)
            page = self.current["page"]            # (the lock is held: this runs inside the parser)
            if isinstance(page, int):
                self.send(bytes([0x66, page]) + END)
            return
        if text.startswith("prints "):
            self._answer_prints(text)
        if not text.startswith(("page ", "twfile ", "whmi-wri ")) and ".write(\"" not in text:
            self._check_object(text)
        if text.startswith("page "):
            try:
                page = int(text[5:])
            except ValueError:
                page = text[5:]
            if self.page_loss and random.random() < self.page_loss:
                self.lost_pages.append(page)        # the screen did not switch (the monkey test: a screen that misbehaves)
                return
            self._new_visit(page)
            return
        if ".write(\"" in text and text.endswith("\")"):
            obj = text[:text.index(".write(\"")]
            data = raw[raw.index(b".write(\"") + 8:-2]
            self._record(obj + ".write", "%s:%d" % (sha(data), len(data)))
            return
        if text.startswith("twfile "):
            args = text[7:]
            path, size = args.rsplit(",", 1)
            self.mode = "twfile"
            self.mode_info = {"path": path.strip("\""), "size": int(size), "data": b"", "frames": 0}
            self._record("twfile", args)
            return
        if text.startswith("whmi-wri "):
            args = text[9:].split(",")
            self.mode = "download"
            self.mode_info = {"size": int(args[0]), "received": 0, "hash": hashlib.sha1(), "next": 4096}
            self._record("whmi-wri", text[9:])
            # the real screen answers 0x05 once it is ready to receive (after its baud rate change)
            threading.Timer(0.5, lambda: self.send(b"\x05")).start()
            return
        eq = text.find("=")
        sp = text.find(" ")
        if eq != -1 and (sp == -1 or eq < sp):
            self._record(text[:eq], text[eq + 1:])
        elif sp != -1:
            args = text[sp + 1:]
            self._record(text[:sp] + " " + args.split(",")[0], args)
        else:
            self._record(text, "")

    def _process(self):
        while True:
            if self.mode == "cmd":
                pos = self.buf.find(END)
                if pos == -1:
                    return
                raw = self.buf[:pos]
                self.buf = self.buf[pos + 3:]
                self._handle_instruction(raw)
            elif self.mode == "twfile":
                info = self.mode_info
                if len(self.buf) < 12:
                    return
                header = self.buf[:12]
                if header[:7] != bytes([0x3A, 0xA1, 0xBB, 0x44, 0x7F, 0xFF, 0xFE]):
                    # garbage / unexpected data: back to command mode
                    self._record("twfile-error", sha(self.buf[:64]))
                    self.mode = "cmd"
                    continue
                length = header[10] | (header[11] << 8)
                if header[7] == 0x00 and header[8:10] == b"\xff\xff":
                    # exit pass-through mode
                    self.buf = self.buf[12:]
                    self._record("twfile-exit", info["path"])
                    self.mode = "cmd"
                    continue
                if len(self.buf) < 12 + length:
                    return
                payload = self.buf[12:12 + length]
                self.buf = self.buf[12 + length:]
                info["data"] += payload[:-2]
                info["frames"] += 1
                self.send(b"\x05" + END)
                if len(info["data"]) >= info["size"]:
                    self._record("twfile-data:" + info["path"], "%s:%d:%d" % (sha(info["data"]), len(info["data"]), info["frames"]))
                    self.mode = "cmd"
            elif self.mode == "download":
                info = self.mode_info
                if not self.buf:
                    return
                need = min(info["next"], info["size"]) - info["received"]
                take = self.buf[:need]
                self.buf = self.buf[len(take):]
                info["received"] += len(take)
                info["hash"].update(take)
                if info["received"] >= info["size"]:
                    self._record("whmi-data", "%s:%d" % (info["hash"].hexdigest()[:16], info["received"]))
                    self.mode = "cmd"
                    self.send(b"\x05")
                elif info["received"] >= info["next"]:
                    info["next"] += 4096
                    self.send(b"\x05")

    # -- helpers for scenarios -------------------------------------------
    @property
    def page(self):
        with self.lock:
            return self.current["page"]

    def wait_page(self, page, timeout=30.0):
        deadline = time.time() + timeout
        with self.lock:
            while self.current["page"] != page:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return False
                self.page_changed.wait(remaining)
            return True

    def value(self, key):
        with self.lock:
            lst = self.current["attrs"].get(key)
            return lst[-1] if lst else None

    def wait_value(self, key, predicate, timeout=6.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            v = self.value(key)
            if v is not None and predicate(v):
                return True
            time.sleep(0.05)
        return False

    def mark(self, label):
        with self.lock:
            self._record("#mark", label)


# ---------------------------------------------------------------------------
# Fake Moonraker
# ---------------------------------------------------------------------------

class Moonraker(object):
    def __init__(self, fixture):
        self.fixture = fixture
        self.received = []          # text messages received over the websocket
        self.http = []              # (method, path+query)
        self.state = fixture.printer_state()
        self.metadata = fixture.metadata()
        self.loop = None
        self.connections = []
        self.queue = None
        self.gap = 0.3              # seconds between two messages sent to the client
        self.started = threading.Event()
        self.lock = threading.Lock()
        self.responses_enabled = True
        self.host = "127.0.0.1"     # the dev server (devserver.py) opens it to the docker port mapping

    def start(self):
        t = threading.Thread(target=self._thread, daemon=True)
        t.start()
        self.started.wait(10)

    def _thread(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main())

    async def _main(self):
        from aiohttp import web, WSMsgType
        self.WSMsgType = WSMsgType
        self.queue = asyncio.Queue()
        app = web.Application()
        app.router.add_route("GET", "/websocket", self._ws)
        app.router.add_route("*", "/{tail:.*}", self._http)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, self.host, 7125)
        await site.start()
        self.started.set()
        await self._sender()

    async def _sender(self):
        while True:
            ws, text = await self.queue.get()
            if ws is None:
                ws = self.connections[-1] if self.connections else None
            if ws is not None and not ws.closed:
                try:
                    await ws.send_str(text)
                except Exception:
                    pass
            await asyncio.sleep(self.gap)

    async def _ws(self, request):
        from aiohttp import web
        ws = web.WebSocketResponse(autoping=True, max_msg_size=0)
        await ws.prepare(request)
        self.connections.append(ws)
        async for msg in ws:
            if msg.type == self.WSMsgType.TEXT:
                with self.lock:
                    self.received.append(msg.data)
                try:
                    req = json.loads(msg.data)
                except ValueError:
                    continue
                resp = self._handle_rpc(req)
                if resp is not None and self.responses_enabled:
                    await self.queue.put((ws, json.dumps(resp)))
        return ws

    def _handle_rpc(self, req):
        method = req.get("method")
        rid = req.get("id")
        params = req.get("params") or {}
        if method in ("printer.objects.query", "printer.objects.subscribe"):
            objects = params.get("objects") or {}
            status = {}
            for name in objects:
                if name in self.state:
                    status[name] = self.state[name]
            return {"jsonrpc": "2.0", "result": {"eventtime": 12345.678, "status": status}, "id": rid}
        if method == "server.history.totals":
            return {"jsonrpc": "2.0", "result": {"job_totals": self.fixture.job_totals(),
                                                  "auxiliary_totals": []}, "id": rid}
        if method == "server.files.metadata":
            name = params.get("filename", "")
            meta = self.metadata.get(name)
            if meta is None:
                return {"jsonrpc": "2.0", "error": {"code": 404, "message": "Metadata not available for <%s>" % name}, "id": rid}
            return {"jsonrpc": "2.0", "result": meta, "id": rid}
        if method == "printer.info":
            return {"jsonrpc": "2.0", "result": {"state": "ready", "software_version": "v0.12.0-test",
                                                  "hostname": "q1pro"}, "id": rid}
        if method in ("printer.gcode.script", "printer.print.start", "printer.emergency_stop",
                      "printer.print.pause", "printer.print.resume", "printer.print.cancel"):
            return {"jsonrpc": "2.0", "result": "ok", "id": rid}
        return {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": rid}

    async def _http(self, request):
        from aiohttp import web
        with self.lock:
            self.http.append("%s %s" % (request.method, request.path_qs))
        path = request.path
        if path == "/server/files/directory":
            target = request.query.get("path", "gcodes")
            result = self.fixture.directory(target)
            if result is None:
                return web.json_response({"error": {"code": 404, "message": "Directory does not exist"}}, status=404)
            return web.json_response({"result": result})
        if path.startswith("/server/files/gcodes/"):
            # file download (Range requests), used by the Python port to read
            # the thumbnails inside the gcode files
            import urllib.parse
            rel = urllib.parse.unquote(path[len("/server/files/gcodes/"):])
            full = os.path.normpath(os.path.join("/home/mks/gcode_files", rel))
            if not full.startswith("/home/mks/gcode_files/") or not os.path.isfile(full):
                return web.json_response({"error": {"code": 404, "message": "File not found"}}, status=404)
            with open(full, "rb") as f:
                data = f.read()
            rng = request.headers.get("Range", "")
            if rng.startswith("bytes="):
                first, _, last = rng[6:].partition("-")
                first = int(first)
                last = min(int(last) if last else len(data) - 1, len(data) - 1)
                if first >= len(data):
                    return web.Response(status=416, headers={"Content-Range": "bytes */%d" % len(data)})
                return web.Response(status=206, body=data[first:last + 1],
                                    headers={"Content-Range": "bytes %d-%d/%d" % (first, last, len(data))})
            return web.Response(body=data)
        if path == "/server/history/list":
            jobs = self.fixture.history_jobs()
            return web.json_response({"result": {"count": len(jobs), "jobs": jobs}})
        if path == "/server/files/metadata":
            name = request.query.get("filename", "")
            meta = self.metadata.get(name)
            if meta is None:
                return web.json_response({"error": {"code": 404}}, status=404)
            return web.json_response({"result": meta})
        return web.json_response({"error": {"code": 404, "message": "Not Found"}}, status=404)

    # -- scenario API ------------------------------------------------------
    def _push(self, obj):
        text = json.dumps(obj)
        self.loop.call_soon_threadsafe(self.queue.put_nowait, (None, text))

    def push_status(self, status):
        for name, values in status.items():
            self.state.setdefault(name, {}).update(values)
        self._push({"jsonrpc": "2.0", "method": "notify_status_update", "params": [status, 12345.678]})

    def push_gcode(self, text):
        self._push({"jsonrpc": "2.0", "method": "notify_gcode_response", "params": [text]})

    def notify(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._push(msg)

    def drop_connection(self):
        """The server closes the websocket (the program has to connect again)."""
        async def close():
            for ws in list(self.connections):
                if not ws.closed:
                    await ws.close()
        asyncio.run_coroutine_threadsafe(close(), self.loop)

    def push_raw(self, text):
        self.loop.call_soon_threadsafe(self.queue.put_nowait, (None, text))

    def wait_received(self, predicate, timeout=6.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                if any(predicate(m) for m in self.received):
                    return True
            time.sleep(0.05)
        return False

    def drain(self, timeout=10.0):
        """Waits until all queued messages were sent."""
        deadline = time.time() + timeout
        pending = self.queue is not None and not self.queue.empty()
        while time.time() < deadline and self.queue is not None and not self.queue.empty():
            time.sleep(0.05)
        if pending:
            time.sleep(self.gap)


# ---------------------------------------------------------------------------
# Fake wpa_supplicant control interface
# ---------------------------------------------------------------------------

class FakeWpa(threading.Thread):
    PATH = "/var/run/wpa_supplicant/wlan0"

    def __init__(self, status, scan_results):
        super().__init__(daemon=True)
        self.status = status            # bytes
        self.scan_results = scan_results  # bytes
        self.received = []
        self.attached = []
        os.makedirs(os.path.dirname(self.PATH), exist_ok=True)
        if os.path.exists(self.PATH):
            os.unlink(self.PATH)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(self.PATH)
        self.lock = threading.Lock()

    def run(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
            except OSError:
                return
            with self.lock:
                self.received.append(data.decode("utf-8", "replace"))
            reply = self._handle(data, addr)
            if reply is not None and addr:
                try:
                    self.sock.sendto(reply, addr)
                except OSError:
                    pass

    def _handle(self, data, addr):
        cmd = data.split(b" ")[0]
        if cmd == b"PING":
            return b"PONG\n"
        if cmd == b"ATTACH":
            self.attached.append(addr)
            return b"OK\n"
        if cmd == b"STATUS":
            return self.status
        if cmd == b"SCAN":
            threading.Timer(0.3, self.event, args=("CTRL-EVENT-SCAN-RESULTS ",)).start()
            return b"OK\n"
        if cmd == b"SCAN_RESULTS":
            return self.scan_results
        if cmd in (b"SET_NETWORK", b"ENABLE_NETWORK", b"DISABLE_NETWORK", b"SELECT_NETWORK",
                   b"SAVE_CONFIG", b"REASSOCIATE"):
            return b"OK\n"
        return b"FAIL\n"

    def event(self, text, level=3):
        for addr in list(self.attached):
            try:
                self.sock.sendto(b"<%d>%s" % (level, text.encode()), addr)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

class Harness(object):
    def __init__(self, impl, scenario, out_dir):
        import fixtures
        self.impl = impl
        self.scenario_name = scenario
        self.out_dir = out_dir
        self.fixture = fixtures.Fixture(scenario)
        self.proc = None
        self.wpa = None
        self.errors = []
        self.extra = {}                 # what a scenario wants to be in the result (the actions of the monkey test)
        self.options = {}               # the arguments of the scenario (seed, steps, ...)

    # -- scenario helpers --------------------------------------------------
    def touch(self, page, widget, settle=0.6):
        self.screen.touch(page, widget)
        self.settle(settle)

    def set_number(self, page, widget, value, settle=0.6):
        self.screen.set_number(page, widget, value)
        self.settle(settle)

    def keyboard(self, page, widget, text, settle=0.6):
        self.screen.keyboard(page, widget, text)
        self.settle(settle)

    def wait_page(self, page, timeout=6.0):
        t0 = time.time()
        ok = self.screen.wait_page(page, timeout)
        if os.environ.get("XINDI_E2E_TIMING"):
            print("wait_page %r: %.1fs" % (page, time.time() - t0), flush=True)
        if not ok:
            self.errors.append("timeout waiting for page %r (current %r)" % (page, self.screen.page))
        return ok

    QUIET = 0.5     # the port is done when the screen got nothing for this long

    def settle(self, seconds):
        """Waits until the port went quiet (no instruction for QUIET seconds), at most ``seconds``; the
        scenarios say how long a step may take, the port usually needs a fraction of it."""
        start = time.time()
        if os.environ.get("XINDI_E2E_TIMING"):
            print("settle(%s) at %.1f" % (seconds, start - self.t_start), flush=True)
        if getattr(self, "mr", None) is not None:
            self.mr.drain(timeout=seconds)
        while True:
            now = time.time()
            if now - start >= seconds or now - max(self.screen.last_instruction, start) >= self.QUIET:
                return
            time.sleep(0.05)

    def mark(self, label):
        self.screen.mark(label)

    @contextlib.contextmanager
    def other_page_events(self):
        """The events of the steps inside are meant for another page than the virtual screen shows (the scenario
        only wants the port's reaction), so the instructions the port answers with may name objects that are not on
        this page."""
        self.screen.ignore_unknown += 1
        try:
            yield
        finally:
            self.settle(0.6)
            self.screen.ignore_unknown -= 1

    def check(self, condition, message):
        if not condition:
            self.errors.append(message)

    # -- environment -----------------------------------------------------
    def setup(self):
        self.fixture.install()
        if os.path.exists(SHELL_LOG):
            os.unlink(SHELL_LOG)
        master, slave = os.openpty()
        tty.setraw(master)
        self.slave_name = os.ttyname(slave)
        self.master = master
        self.slave = slave
        if os.path.lexists("/dev/ttyS1"):
            os.unlink("/dev/ttyS1")
        os.symlink(self.slave_name, "/dev/ttyS1")
        self.screen = Screen(master)
        self.screen.start()
        self.mr = Moonraker(self.fixture)
        self.mr.start()
        wifi = self.fixture.wifi()
        if wifi is not None:
            self.wpa = FakeWpa(wifi["status"], wifi["scan_results"])
            self.wpa.start()

    def start_sut(self):
        env = dict(os.environ)
        env.update({
            "LD_PRELOAD": "/opt/support/timescale.so",
            "XINDI_SLEEP_SCALE": os.environ.get("XINDI_SLEEP_SCALE", "0.25"),
            "XINDI_SLEEP_MIN": os.environ.get("XINDI_SLEEP_MIN", "1.5"),
            "XINDI_SHELL_LOG": SHELL_LOG,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        })
        cmd = ["python3", "/opt/src_py/main.py", "localhost"]
        # lower priority than the harness so that the virtual screen keeps up
        cmd = ["nice", "-n", "10"] + cmd
        self.sut_log = open(os.path.join(self.out_dir, "%s_%s.log" % (self.impl, self.scenario_name)), "wb")
        if self.fixture.o["flash"]:
            # the screen firmware goes in first, with the service not running (--flash-screen)
            import fixtures
            flash_cmd = ["nice", "-n", "10", "python3", "/opt/src_py/main.py", "--flash-screen", fixtures.TFT_FILE]
            subprocess.run(flash_cmd, stdout=self.sut_log, stderr=subprocess.STDOUT, env=env, cwd="/", timeout=120, check=True)
        self.proc = subprocess.Popen(cmd, stdout=self.sut_log, stderr=subprocess.STDOUT, env=env,
                                     cwd="/", start_new_session=True)

    def stop_sut(self):
        if self.proc is None:
            return None
        rc = self.proc.poll()
        if rc is None:
            try:
                os.killpg(self.proc.pid, 9)
            except OSError:
                pass
            self.proc.wait(10)
        return rc

    def shell_log(self):
        try:
            with open(SHELL_LOG, "rb") as f:
                data = f.read()
        except OSError:
            return []
        cmds = [c.decode("utf-8", "replace") for c in data.split(b"\x1e") if c]
        return cmds

    def run(self):
        if self.scenario_name == "monkey":
            import monkey
            func = monkey.scenario_monkey
        else:
            import scenarios
            func = getattr(scenarios, "scenario_" + self.scenario_name)
        t0 = self.t_start = time.time()
        self.setup()
        self.start_sut()
        if os.environ.get("XINDI_E2E_TIMING"):
            print("setup %.1fs" % (time.time() - t0), flush=True)
        try:
            func(self)
        except Exception:
            self.errors.append("scenario exception: " + traceback.format_exc())
        if os.environ.get("XINDI_E2E_TIMING"):
            print("scenario done after %.1fs" % (time.time() - t0), flush=True)
        time.sleep(1.0)
        rc = self.stop_sut()
        self.screen.stopped = True
        result = {
            "impl": self.impl,
            "scenario": self.scenario_name,
            "exit_code_before_kill": rc,
            "errors": self.errors,
            "screen_visits": self.screen.visits,
            "screen_pages": self.screen.pages,
            "ws_received": list(self.mr.received),
            "http": list(self.mr.http),
            "shell": self.shell_log(),
            "wpa": list(self.wpa.received) if self.wpa else [],
            "unknown_objects": list(self.screen.unknown),
            "files": self.fixture.snapshot(),
            "extra": self.extra,
        }
        name = self.scenario_name if self.scenario_name != "monkey" else "monkey_%d" % self.options["seed"]
        with open(os.path.join(self.out_dir, "%s_%s.json" % (self.impl, name)), "w") as f:
            try:
                json.dump(result, f, indent=1, ensure_ascii=False)
            except UnicodeEncodeError:          # the program was sent bytes that are no text (the monkey test does it): the escapes keep them
                f.seek(0)
                f.truncate()
                json.dump(result, f, indent=1, ensure_ascii=True)
        return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl", choices=["py"], default="py")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--out", default="/out")
    ap.add_argument("--seed", type=int, default=1, help="monkey: the seed of the random choices")
    ap.add_argument("--steps", type=int, default=150, help="monkey: the number of random actions")
    ap.add_argument("--hostile", action="store_true", help="monkey: also send what Moonraker never sends (wrong types)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    h = Harness(args.impl, args.scenario, args.out)
    h.options = {"seed": args.seed, "steps": args.steps, "hostile": args.hostile}
    res = h.run()
    print("%s/%s: %d screen visits, %d ws messages, %d shell commands, errors: %d" % (
        args.impl, args.scenario, len(res["screen_visits"]), len(res["ws_received"]), len(res["shell"]),
        len(res["errors"])))
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
