"""
Helpers that reproduce C / C++ semantics the original code relies on.

The original backend is written in C++ and a lot of its observable behaviour
depends on details such as 32-bit float rounding, ``std::to_string`` formatting,
``std::string::substr``/``npos`` arithmetic, truncating integer division,
``strtol``/``atof``/``std::stof`` parsing rules and the type checks performed by
nlohmann::json.  Everything that is needed to keep the Python port behaving the
same way is collected here so the ported modules can stay a line-by-line
transliteration of the C++ sources.

String convention
-----------------
``std::string`` values are represented by Python ``str``.  Raw bytes coming
from files / sockets are decoded as UTF-8 with ``surrogateescape`` (see
:func:`b2s`) and encoded back the same way (:func:`s2b`), so arbitrary bytes
survive a round trip exactly like they would in a ``std::string``.
"""

import math
import os
import re
import struct


ENCODING = "utf-8"
ERRORS = "surrogateescape"

# std::string::npos is represented by -1 (what str.find() returns).  Adding a
# small positive number to it gives the same result as the size_t wrap-around
# in C++ (npos + 1 == 0, npos + 2 == 1, ...).
NPOS = -1


def b2s(data):
    """bytes -> std::string (str)"""
    if isinstance(data, str):
        return data
    return bytes(data).decode(ENCODING, ERRORS)


def s2b(text):
    """std::string (str) -> bytes"""
    if isinstance(text, (bytes, bytearray)):
        return bytes(text)
    return text.encode(ENCODING, ERRORS)


def cstr(data):
    """Interpret a byte buffer as a NUL terminated C string."""
    data = bytes(data)
    pos = data.find(b"\0")
    if pos >= 0:
        data = data[:pos]
    return data


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_F32 = struct.Struct("f")


def f32(value):
    """Round a Python float to the nearest IEEE-754 single precision value."""
    value = float(value)
    if math.isnan(value) or math.isinf(value):
        return value
    try:
        return _F32.unpack(_F32.pack(value))[0]
    except OverflowError:
        return math.copysign(math.inf, value)


def i32(value):
    """Wrap an integer to a signed 32 bit int (C 'int')."""
    value = int(value) & 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def c_int(value):
    """(int)x for a floating point value: truncation towards zero."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return i32(value)
    if math.isnan(value) or math.isinf(value):
        return -0x80000000
    return i32(int(value))


def cdiv(a, b):
    """C integer division (truncates towards zero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def cmod(a, b):
    """C integer remainder (sign follows the dividend)."""
    return a - cdiv(a, b) * b


def c_round(value):
    """C round(): halfway cases away from zero (Python's round() is banker's)."""
    value = float(value)
    if math.isnan(value) or math.isinf(value):
        return value
    a = abs(value)
    r = math.floor(a)
    if a - r >= 0.5:
        r += 1.0
    return math.copysign(r, value)


def to_string(value):
    """std::to_string()"""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    return "%f" % value


# ---------------------------------------------------------------------------
# std::string helpers
# ---------------------------------------------------------------------------

class OutOfRange(IndexError):
    """std::out_of_range"""


class InvalidArgument(ValueError):
    """std::invalid_argument"""


def substr(s, pos=0, n=None):
    """std::string::substr(pos, n)

    A negative ``pos`` stands for a wrapped-around size_t (npos) and throws like
    the C++ version does; a negative ``n`` means "until the end".
    """
    if pos < 0 or pos > len(s):
        raise OutOfRange("basic_string::substr: __pos (which is %d) > this->size() (which is %d)" % (pos, len(s)))
    if n is None or n < 0:
        return s[pos:]
    return s[pos:pos + n]


def find_last_of(s, chars):
    best = -1
    for c in chars:
        p = s.rfind(c)
        if p > best:
            best = p
    return best


def str_lower_ascii(s):
    """std::transform(..., tolower) in the "C" locale: only ASCII letters change."""
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in s)


# ---------------------------------------------------------------------------
# C library number parsing
# ---------------------------------------------------------------------------

_C_SPACE = " \t\n\v\f\r"
_FLOAT_RE = re.compile(
    r"[+-]?(?:"
    r"(?:0[xX](?:[0-9a-fA-F]+\.?[0-9a-fA-F]*|\.[0-9a-fA-F]+)(?:[pP][+-]?[0-9]+)?)|"
    r"(?:(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)|"
    r"(?:inf(?:inity)?)|(?:nan(?:\([0-9A-Za-z_]*\))?)"
    r")", re.IGNORECASE)


def _strtod_prefix(s):
    """Returns (value, consumed) like strtod(); consumed == 0 if no conversion."""
    i = 0
    while i < len(s) and s[i] in _C_SPACE:
        i += 1
    m = _FLOAT_RE.match(s, i)
    if not m or m.end() == i:
        return 0.0, 0
    text = m.group(0)
    body = text.lstrip("+-")
    sign = -1.0 if text.startswith("-") else 1.0
    low = body.lower()
    if low.startswith("0x"):
        value = sign * _parse_hex_float(body[2:])
    elif low.startswith("inf"):
        value = sign * math.inf
    elif low.startswith("nan"):
        value = math.nan
    else:
        value = float(text)
    return value, m.end()


def _parse_hex_float(body):
    exp = 0
    if "p" in body.lower():
        idx = body.lower().index("p")
        exp = int(body[idx + 1:])
        body = body[:idx]
    if "." in body:
        ip, fp = body.split(".", 1)
    else:
        ip, fp = body, ""
    mant = int(ip or "0", 16) if ip else 0
    for ch in fp:
        mant = mant * 16 + int(ch, 16)
        exp -= 4
    return math.ldexp(mant, exp)


def stof(s):
    """std::stof(): throws std::invalid_argument when nothing can be parsed."""
    value, used = _strtod_prefix(s)
    if used == 0:
        raise InvalidArgument("stof")
    value = f32(value)
    if math.isinf(value) and not s.strip().lstrip("+-").lower().startswith("inf"):
        raise OutOfRange("stof")
    return value


def strtol(s, base=10):
    """strtol(s, NULL, base) with the usual C rules (base 0 auto-detects)."""
    i = 0
    n = len(s)
    while i < n and s[i] in _C_SPACE:
        i += 1
    sign = 1
    if i < n and s[i] in "+-":
        if s[i] == "-":
            sign = -1
        i += 1
    if base == 0:
        if s[i:i + 2].lower() == "0x" and i + 2 < n and s[i + 2] in "0123456789abcdefABCDEF":
            base = 16
            i += 2
        elif s[i:i + 1] == "0":
            base = 8
        else:
            base = 10
    elif base == 16 and s[i:i + 2].lower() == "0x" and i + 2 < n and s[i + 2] in "0123456789abcdefABCDEF":
        i += 2
    value = 0
    digits = 0
    while i < n:
        c = s[i].lower()
        if "0" <= c <= "9":
            d = ord(c) - 48
        elif "a" <= c <= "z":
            d = ord(c) - 87
        else:
            break
        if d >= base:
            break
        value = value * base + d
        digits += 1
        i += 1
    if digits == 0:
        return 0
    value *= sign
    # long is 64 bit on aarch64, saturates like strtol()
    if value > 0x7FFFFFFFFFFFFFFF:
        value = 0x7FFFFFFFFFFFFFFF
    elif value < -0x8000000000000000:
        value = -0x8000000000000000
    return value


def stream_float(s):
    """``std::stringstream ss(s); float f; ss >> f;`` (0 when extraction fails)."""
    value, used = _strtod_prefix(s)
    if used == 0:
        return 0.0
    return f32(value)


# ---------------------------------------------------------------------------
# libc wrappers
# ---------------------------------------------------------------------------

def read_file_bytes(path):
    """``std::ifstream f(path); std::stringstream ss; ss << f.rdbuf();`` - None if the file can't be opened."""
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def read_file(path):
    data = read_file_bytes(path)
    return None if data is None else b2s(data)


# ---------------------------------------------------------------------------
# nlohmann::json emulation helpers
# ---------------------------------------------------------------------------
#
# JSON values are plain Python objects (dict / list / str / int / float / bool /
# None).  The helpers below reproduce the checks nlohmann::json performs when a
# value is accessed through operator[] or converted to a C++ type, including the
# exceptions it throws on type mismatches.

class JsonTypeError(TypeError):
    """nlohmann::json::type_error"""


def _jtype(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "discarded"


def jget(value, key):
    """``json[key]`` (read access).  Missing keys / indexes give null."""
    if isinstance(key, str):
        if value is None:
            return None
        if isinstance(value, dict):
            return value.get(key)
        raise JsonTypeError("[json.exception.type_error.305] cannot use operator[] with a string argument with " + _jtype(value))
    if value is None:
        return None
    if isinstance(value, list):
        if 0 <= key < len(value):
            return value[key]
        return None
    raise JsonTypeError("[json.exception.type_error.305] cannot use operator[] with a numeric argument with " + _jtype(value))


def jpath(value, *keys):
    for key in keys:
        value = jget(value, key)
    return value


def jstr(value):
    """``std::string s = json;``"""
    if isinstance(value, str):
        return value
    raise JsonTypeError("[json.exception.type_error.302] type must be string, but is " + _jtype(value))


def jnum(value):
    """Conversion of a json value to an arithmetic C++ type (before the cast)."""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    raise JsonTypeError("[json.exception.type_error.302] type must be number, but is " + _jtype(value))


def jfloat(value):
    """``float f = json;``"""
    return f32(jnum(value))


def jdouble(value):
    """``double d = json;``"""
    return float(jnum(value))


def jint(value):
    """``int i = json;``"""
    return c_int(jnum(value))


def jbool(value):
    """``bool b = json;``"""
    if isinstance(value, bool):
        return value
    raise JsonTypeError("[json.exception.type_error.302] type must be boolean, but is " + _jtype(value))


def jsize(value):
    """``json.size()``"""
    if value is None:
        return 0
    if isinstance(value, (list, dict)):
        return len(value)
    return 1


def jeq(value, other):
    """``json == other`` for scalars (number comparisons ignore int/float)."""
    if isinstance(value, bool) or isinstance(other, bool):
        return isinstance(value, bool) and isinstance(other, bool) and value == other
    if isinstance(value, (int, float)) and isinstance(other, (int, float)):
        return value == other
    if type(value) is not type(other):
        return False
    return value == other


def json_dump(value):
    """``json.dump()`` - compact, keys sorted like std::map, no ASCII escaping."""
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
                      default=str)


def json_parse(text):
    """``nlohmann::json::parse()``"""
    import json
    if isinstance(text, (bytes, bytearray)):
        text = b2s(text)
    try:
        return json.loads(text)
    except ValueError as e:
        raise JsonParseError(str(e))


class JsonParseError(ValueError):
    """nlohmann::json::parse_error"""


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------

def terminate(exc=None):
    """std::terminate(): an exception escaped a thread function -> abort()."""
    import sys
    import traceback
    if exc is not None:
        sys.stderr.write("terminate called after throwing an instance of '%s'\n  what():  %s\n"
                         % (type(exc).__name__, exc))
        traceback.print_exc()
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os.abort()


def pthread_create(target, arg=None):
    """pthread_create() replacement; an uncaught exception aborts the process
    like an uncaught C++ exception in a thread calls std::terminate()."""
    import threading

    def runner():
        try:
            target(arg)
        except SystemExit:
            raise
        except BaseException as e:      # noqa
            terminate(e)

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    return t
