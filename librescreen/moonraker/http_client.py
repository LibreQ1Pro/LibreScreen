"""Minimal HTTP/1.1 client (port of HTTPRequest.hpp) and the requests to Moonraker's HTTP API.

Only what the program needs is implemented: plain ``http://`` URLs, an empty
request body, Content-Length / chunked responses.  The response parsing loop is
transliterated from the header-only library, including its quirk of giving up
(returning an empty response) when the first recv() does not contain the
complete header section.
"""

import logging
import socket

from librescreen.util.cpp import b2s, s2b

log = logging.getLogger(__name__)


class RequestError(Exception):
    pass


class ResponseError(Exception):
    pass


class Uri(object):
    def __init__(self):
        self.scheme = ""
        self.user = ""
        self.password = ""
        self.host = ""
        self.port = ""
        self.path = ""
        self.query = ""
        self.fragment = ""


class Status(object):
    def __init__(self):
        self.httpVersion = ""
        self.code = 0
        self.reason = ""


class Response(object):
    def __init__(self):
        self.status = Status()
        self.headerFields = []
        self.body = b""


def _is_alpha(c):
    return ("a" <= c <= "z") or ("A" <= c <= "Z")


def _is_digit(c):
    return "0" <= c <= "9"


def parse_uri(uri_string):
    """RFC 3986, 3. Syntax Components"""
    result = Uri()
    s = uri_string
    i = 0
    if not s or not _is_alpha(s[0]):
        raise RequestError("Invalid scheme")
    result.scheme += s[i]
    i += 1
    while i < len(s) and (_is_alpha(s[i]) or _is_digit(s[i]) or s[i] in "+-."):
        result.scheme += s[i]
        i += 1
    for expected in (":", "/", "/"):
        if i >= len(s) or s[i] != expected:
            raise RequestError("Invalid scheme")
        i += 1

    authority = s[i:]

    pos = authority.find("#")
    if pos != -1:
        result.fragment = authority[pos + 1:]
        authority = authority[:pos]

    pos = authority.find("?")
    if pos != -1:
        result.query = authority[pos + 1:]
        authority = authority[:pos]

    pos = authority.find("/")
    if pos != -1:
        result.path = authority[pos:]
        authority = authority[:pos]
    else:
        result.path = "/"

    pos = authority.find("@")
    if pos != -1:
        userinfo = authority[:pos]
        ppos = userinfo.find(":")
        if ppos != -1:
            result.user = userinfo[:ppos]
            result.password = userinfo[ppos + 1:]
        else:
            result.user = userinfo
        result.host = authority[pos + 1:]
    else:
        result.host = authority

    # RFC 3986, 3.2.2. Host / 3.2.3. Port
    if result.host.startswith("["):
        end = result.host.find("]")
        if end == -1:
            raise RequestError("Invalid host")
        rest = result.host[end + 1:]
        result.host = result.host[1:end]
        if rest.startswith(":"):
            result.port = rest[1:]
    else:
        pos = result.host.find(":")
        if pos != -1:
            result.port = result.host[pos + 1:]
            result.host = result.host[:pos]
    return result


def _parse_status_line(header):
    line_end = header.find(b"\r\n")
    line = header[:line_end]
    status = Status()
    parts = line.split(b" ", 2)
    if len(parts) < 2:
        raise ResponseError("Invalid status line")
    status.httpVersion = parts[0].decode("latin-1")
    try:
        status.code = int(parts[1])
    except ValueError:
        raise ResponseError("Invalid status code")
    status.reason = parts[2].decode("latin-1") if len(parts) > 2 else ""
    return status, line_end + 2


class Request(object):
    def __init__(self, uri_string):
        self.uri = parse_uri(uri_string)

    def send(self, method="GET", body=b"", headerFields=None):
        uri = self.uri
        if uri.scheme != "http":
            raise RequestError("Only HTTP scheme is supported")
        port = int(uri.port) if uri.port else 80

        request_target = uri.path + ("" if not uri.query else "?" + uri.query)
        headers = list(headerFields or [])
        headers.append(("Host", uri.host))
        headers.append(("Content-Length", str(len(body))))
        data = s2b(method + " " + request_target + " HTTP/1.1\r\n")
        for name, value in headers:
            data += s2b(name + ": " + value + "\r\n")
        data += b"\r\n" + body

        infos = socket.getaddrinfo(uri.host, port, socket.AF_INET, socket.SOCK_STREAM)
        family, socktype, proto, _, addr = infos[0]
        sock = socket.socket(family, socktype, proto)
        try:
            sock.connect(addr)
            sock.sendall(data)

            response = Response()
            response_data = b""
            parsing_body = False
            content_length_received = False
            content_length = 0
            chunked = False
            expected_chunk_size = 0
            remove_crlf_after_chunk = False
            body_parts = []

            while True:
                chunk = sock.recv(4096)
                if not chunk:       # disconnected
                    response.body = b"".join(body_parts)
                    return response
                response_data += chunk

                if not parsing_body:
                    end = response_data.find(b"\r\n\r\n")
                    if end == -1:
                        break       # two consecutive CRLFs not found (library quirk)
                    header = response_data[:end + 2]
                    response.status, pos = _parse_status_line(header)
                    for line in header[pos:].split(b"\r\n"):
                        if not line:
                            continue
                        colon = line.find(b":")
                        name = line[:colon].decode("latin-1").lower()
                        value = line[colon + 1:].strip(b" \t").decode("latin-1")
                        if name == "transfer-encoding":
                            if value == "chunked":
                                chunked = True
                            else:
                                raise ResponseError("Unsupported transfer encoding: " + value)
                        elif name == "content-length":
                            content_length = int(value)
                            content_length_received = True
                        response.headerFields.append((name, value))
                    response_data = response_data[end + 4:]
                    parsing_body = True

                if parsing_body:
                    if chunked:
                        while True:
                            if expected_chunk_size > 0:
                                to_write = min(expected_chunk_size, len(response_data))
                                body_parts.append(response_data[:to_write])
                                response_data = response_data[to_write:]
                                expected_chunk_size -= to_write
                                if expected_chunk_size == 0:
                                    remove_crlf_after_chunk = True
                                if not response_data:
                                    break
                            else:
                                if remove_crlf_after_chunk:
                                    if len(response_data) < 2:
                                        break
                                    if response_data[:2] != b"\r\n":
                                        raise ResponseError("Invalid chunk")
                                    remove_crlf_after_chunk = False
                                    response_data = response_data[2:]
                                pos = response_data.find(b"\r\n")
                                if pos == -1:
                                    break
                                expected_chunk_size = int(response_data[:pos], 16)
                                response_data = response_data[pos + 2:]
                                if expected_chunk_size == 0:
                                    response.body = b"".join(body_parts)
                                    return response
                    else:
                        body_parts.append(response_data)
                        response_data = b""
                        if content_length_received and sum(len(p) for p in body_parts) >= content_length:
                            response.body = b"".join(body_parts)
                            return response

            response.body = b"".join(body_parts)
            return response
        finally:
            sock.close()


def send_request(ip, port, method, request_type):
    url = "http://" + ip + ":" + port + "/" + method
    str_response = ""
    url = url.replace(" ", "%20")
    log.debug("Sending request to %s", url)
    try:
        request = Request(url)
        response = request.send(request_type)
        str_response = b2s(response.body)
    except Exception as e:
        log.error("Request failed, error%s", str(e))
    return str_response
