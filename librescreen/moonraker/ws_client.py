"""Websocket client for Moonraker (was MakerbaseClient.cpp).

The C++ code uses websocketpp (asio, no TLS).  It is replaced by a small RFC 6455
client implemented inline here.  The externally visible behaviour is kept:
connections are established asynchronously, the status string goes through
"Connecting" -> "Open" / "Failed" -> "Closed", every received text frame is
stored in the global ``message`` and ``is_get_message`` is set (without waiting
for the previous message to be consumed, exactly like the original), sending on
a connection that is not open fails with an error message.
"""

import base64
import logging
import os
import socket
import struct
import threading

from librescreen import state as g
from librescreen.moonraker.rpc_requests import json_run_a_gcode
from librescreen.util.cpp import b2s, s2b

log = logging.getLogger(__name__)

_OP_CONT = 0x0
_OP_TEXT = 0x1
_OP_BINARY = 0x2
_OP_CLOSE = 0x8
_OP_PING = 0x9
_OP_PONG = 0xA

CLOSE_NORMAL = 1000
CLOSE_GOING_AWAY = 1001


class WebsocketError(Exception):
    pass


def _parse_ws_url(url):
    """Returns (host, port, resource) for a ws:// url (websocketpp::uri)."""
    if not url.startswith("ws://"):
        raise WebsocketError("Invalid URI")
    rest = url[5:]
    pos = rest.find("/")
    if pos == -1:
        authority, resource = rest, "/"
    else:
        authority, resource = rest[:pos], rest[pos:]
    if authority.startswith("["):
        end = authority.find("]")
        host = authority[1:end]
        port_part = authority[end + 1:]
        port = int(port_part[1:]) if port_part.startswith(":") else 80
    elif ":" in authority:
        host, port_s = authority.rsplit(":", 1)
        port = int(port_s)
    else:
        host, port = authority, 80
    if not host:
        raise WebsocketError("Invalid URI")
    return host, port, resource


class _Connection(object):
    """One websocket connection (websocketpp::connection)."""

    def __init__(self, url):
        self.url = url
        self.host, self.port, self.resource = _parse_ws_url(url)
        self.sock = None
        self.state = "connecting"       # connecting, open, closing, closed, failed
        self.lock = threading.Lock()
        self.response_headers = {}
        self.remote_close_code = 1005
        self.remote_close_reason = ""
        self.error = ""
        self.open_handler = None
        self.fail_handler = None
        self.close_handler = None
        self.message_handler = None

    def get_response_header(self, name):
        return self.response_headers.get(name.lower(), "")

    # -- connection thread ------------------------------------------------
    def start(self):
        t = threading.Thread(target=self._run, name="websocket", daemon=True)
        t.start()

    def _fail(self, reason):
        self.error = reason
        self.state = "failed"
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        if self.fail_handler:
            self.fail_handler(self)

    def _run(self):
        try:
            self.sock = socket.create_connection((self.host, self.port))
        except OSError as e:
            self._fail(str(e))
            return
        key = base64.b64encode(os.urandom(16)).decode()
        port_suffix = "" if self.port == 80 else ":%d" % self.port
        request = ("GET %s HTTP/1.1\r\n"
                   "Connection: Upgrade\r\n"
                   "Host: %s%s\r\n"
                   "Sec-WebSocket-Key: %s\r\n"
                   "Sec-WebSocket-Version: 13\r\n"
                   "Upgrade: websocket\r\n"
                   "User-Agent: WebSocket++/0.8.2\r\n"
                   "\r\n") % (self.resource, self.host, port_suffix, key)
        try:
            self.sock.sendall(request.encode("latin-1"))
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = self.sock.recv(4096)
                if not chunk:
                    raise WebsocketError("connection closed during handshake")
                data += chunk
            header, rest = data.split(b"\r\n\r\n", 1)
            lines = header.decode("latin-1").split("\r\n")
            status = lines[0].split(" ")
            if len(status) < 2 or status[1] != "101":
                raise WebsocketError("Invalid HTTP status.")
            for line in lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    self.response_headers[k.strip().lower()] = v.strip()
        except (OSError, WebsocketError) as e:
            self._fail(str(e))
            return

        self.state = "open"
        if self.open_handler:
            self.open_handler(self)
        self._read_loop(rest)

    def _read_loop(self, buf):
        fragments = []
        frag_opcode = None
        try:
            while True:
                frame, buf = self._read_frame(buf)
                if frame is None:
                    break
                fin, opcode, payload = frame
                if opcode == _OP_PING:
                    self._send_frame(_OP_PONG, payload)
                elif opcode == _OP_PONG:
                    pass
                elif opcode == _OP_CLOSE:
                    if len(payload) >= 2:
                        self.remote_close_code = struct.unpack("!H", payload[:2])[0]
                        self.remote_close_reason = b2s(payload[2:])
                    if self.state == "open":
                        try:
                            self._send_frame(_OP_CLOSE, payload[:2])
                        except OSError:
                            pass
                    break
                elif opcode in (_OP_TEXT, _OP_BINARY):
                    if fin:
                        self._deliver(opcode, payload)
                    else:
                        frag_opcode = opcode
                        fragments = [payload]
                elif opcode == _OP_CONT:
                    fragments.append(payload)
                    if fin:
                        self._deliver(frag_opcode, b"".join(fragments))
                        fragments = []
        except (OSError, WebsocketError):
            pass
        self.state = "closed"
        try:
            self.sock.close()
        except OSError:
            pass
        if self.close_handler:
            self.close_handler(self)

    def _recv_exact(self, buf, n):
        while len(buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                return None, buf
            buf += chunk
        return buf[:n], buf[n:]

    def _read_frame(self, buf):
        head, buf = self._recv_exact(buf, 2)
        if head is None:
            return None, buf
        fin = bool(head[0] & 0x80)
        opcode = head[0] & 0x0F
        masked = bool(head[1] & 0x80)
        length = head[1] & 0x7F
        if length == 126:
            ext, buf = self._recv_exact(buf, 2)
            if ext is None:
                return None, buf
            length = struct.unpack("!H", ext)[0]
        elif length == 127:
            ext, buf = self._recv_exact(buf, 8)
            if ext is None:
                return None, buf
            length = struct.unpack("!Q", ext)[0]
        mask = b""
        if masked:
            mask, buf = self._recv_exact(buf, 4)
            if mask is None:
                return None, buf
        payload, buf = self._recv_exact(buf, length)
        if payload is None:
            return None, buf
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return (fin, opcode, payload), buf

    def _deliver(self, opcode, payload):
        if self.message_handler:
            self.message_handler(self, opcode, payload)

    # -- sending ----------------------------------------------------------
    def _send_frame(self, opcode, payload):
        header = bytearray([0x80 | opcode])
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack("!H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack("!Q", n)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        with self.lock:
            self.sock.sendall(bytes(header) + masked)

    def send(self, message):
        """Returns an error string or None."""
        if self.state != "open":
            return "invalid state"
        try:
            self._send_frame(_OP_TEXT, s2b(message))
        except OSError as e:
            return str(e)
        return None

    def close(self, code, reason):
        """Returns an error string or None."""
        if self.state != "open":
            return "invalid state"
        self.state = "closing"
        payload = struct.pack("!H", code) + s2b(reason)
        try:
            self._send_frame(_OP_CLOSE, payload)
        except OSError as e:
            return str(e)
        return None


class ConnectionMetadata(object):
    """Keeps the metadata of one connection."""

    def __init__(self, hdl, url):
        self.m_Hdl = hdl                    # websocketpp connection handle
        self.m_Status = "Connecting"        # connection state
        self.m_Url = url                    # connection URI
        self.m_Server = "N/A"               # server information
        self.m_Error_reason = ""            # error reason
        self.m_Message = ""                 # received message
        self.is_recv_result = False         # whether a callback with result "OK" was received

    def on_open(self, con):
        self.m_Status = "Open"
        self.m_Server = con.get_response_header("Server")
        log.info("websocket connected\n")

    def on_fail(self, con):
        self.m_Status = "Failed"
        self.m_Server = con.get_response_header("Server")
        self.m_Error_reason = con.error
        log.debug("Failed to connect to the server, please reconnect")

    def on_close(self, con):
        self.m_Status = "Closed"
        self.m_Error_reason = "close code: %d (%s), close reason: %s" % (
            con.remote_close_code, "", con.remote_close_reason)

    def on_message(self, con, opcode, payload):
        if opcode == _OP_TEXT:
            g.rpc.message_queue.put(b2s(payload))

    def get_hdl(self):
        return self.m_Hdl

    def get_status(self):
        return self.m_Status


class MoonrakerClient(object):
    def __init__(self, host="localhost", port="7125"):
        self.is_connected = False           # connection flag
        self.status = "none"                # connection state as a string
        self.host = host                    # target host
        self.port = port                    # target port
        self.sending_message = ""           # last sent message
        self.m_ConnectionMetadataPtr = None

    def connect(self, url):
        try:
            con = _Connection(url)
        except (WebsocketError, ValueError) as e:
            log.debug("> Connect initialization error: %s", str(e))
            return False

        # create the metadata of the connection and keep it
        metadata_ptr = ConnectionMetadata(con, url)
        self.m_ConnectionMetadataPtr = metadata_ptr

        try:
            con.open_handler = metadata_ptr.on_open
            con.fail_handler = metadata_ptr.on_fail
            con.close_handler = metadata_ptr.on_close
            con.message_handler = metadata_ptr.on_message
            con.start()
            log.debug("Websocket connecting")
        except Exception as e:
            log.debug("%s", str(e))
        return True

    def close(self, reason=""):
        if self.m_ConnectionMetadataPtr is not None:
            ec = self.m_ConnectionMetadataPtr.get_hdl().close(CLOSE_NORMAL, reason)
            if ec:
                log.debug("> Error initiating close: %s", ec)
                return False
            log.debug("Websocket connection closed")
        return True

    def send(self, message):
        if self.m_ConnectionMetadataPtr is not None:
            ec = self.m_ConnectionMetadataPtr.get_hdl().send(message)
            if ec:
                log.debug("> Error sending message: %s", ec)
                return False
            else:
                self.sending_message = message
                log.debug("%s", "Data sent, content: " + self.sending_message)
        return True

    def run_gcode(self, script):
        """Ask Klipper to run a gcode script."""
        return self.send(json_run_a_gcode(script))

    def connected(self):
        return self.is_connected

    def poll_status(self):
        if self.m_ConnectionMetadataPtr is not None:
            self.status = self.m_ConnectionMetadataPtr.get_status()
        if self.status == "Open":
            self.is_connected = True
        else:
            self.is_connected = False
        return self.status

    def url(self):
        return "ws://" + self.host + ":" + self.port + "/websocket?"
