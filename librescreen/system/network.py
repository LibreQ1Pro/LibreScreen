"""Wi-Fi and LAN through NetworkManager (``nmcli``).

QIDI's xindi drives wpa_supplicant of ``wlan0`` directly and shows the address of
``eth0``. Here NetworkManager owns the connections instead, so the screen, KlipperScreen
and ``nmcli`` all see and change the same state, and the real names of the interfaces
(e.g. ``wlx40a5ef2378f6`` of an USB adapter) are looked up instead of assumed.

The status keeps the wpa_supplicant vocabulary the screen code was written for:
``wpa_state`` is "COMPLETED" when the wifi is connected.
"""

import logging
import select
import subprocess
import time

from librescreen import state as g
from librescreen.screen import navigation, pageids as ids
from librescreen.util.cpp import pthread_create

log = logging.getLogger(__name__)

NMCLI = "nmcli"
ENV = {"LC_ALL": "C", "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}


def _run(args, timeout=20):
    """Runs nmcli (no shell, so SSIDs and passwords need no quoting). Returns (code, stdout)."""
    try:
        proc = subprocess.run([NMCLI] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, env=ENV)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.info("nmcli %s failed: %s", args[0] if args else "", e)
        return -1, ""
    out = proc.stdout.decode("utf-8", "replace")
    if proc.returncode != 0:
        log.info("nmcli: %s", proc.stderr.decode("utf-8", "replace").strip())
    return proc.returncode, out


def _split(line):
    """Splits a line of ``nmcli -t`` output at the ':' that are not escaped."""
    fields, cur, escaped = [], [], False
    for ch in line:
        if escaped:
            cur.append(ch)
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == ":":
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    fields.append("".join(cur))
    return fields


def _device(kind):
    """Name of the first network interface of the type ``kind`` ("wifi" / "ethernet") or None."""
    ret, out = _run(["-t", "-f", "DEVICE,TYPE", "dev"])
    for line in out.splitlines():
        fields = _split(line)
        if len(fields) == 2 and fields[1] == kind:
            return fields[0]
    return None


def _device_info(dev):
    """The ``dev show`` fields of the interface as a dict (the first value of the repeated ones)."""
    ret, out = _run(["-t", "-f", "GENERAL.STATE,GENERAL.CON-UUID,GENERAL.HWADDR,IP4.ADDRESS", "dev", "show", dev])
    info = {}
    if ret == 0:
        for line in out.splitlines():
            key, _, value = line.partition(":")
            info.setdefault(key.split("[")[0], value)
    return info


def detected_wlan0():
    """Is there a wifi interface?"""
    return _device("wifi") is not None


def mks_wifi_run_cmd_status(result):
    """Fills ``result`` (mks_wifi_status_result_t) with the state of the wifi connection."""
    fresh = g.mks_wifi_status_result_t()
    dev = _device("wifi")
    if dev is None:
        fresh.wpa_state = "INTERFACE_DISABLED"
    else:
        info = _device_info(dev)
        state = info.get("GENERAL.STATE", "")
        fresh.address = info.get("GENERAL.HWADDR", "")
        if "(connected)" in state:
            fresh.wpa_state = "COMPLETED"
            fresh.ip_address = info.get("IP4.ADDRESS", "").split("/")[0]
            uuid = info.get("GENERAL.CON-UUID", "")
            if uuid:
                ret, out = _run(["-t", "-f", "802-11-wireless.ssid", "con", "show", "uuid", uuid])
                if ret == 0 and out.strip():
                    fresh.ssid = _split(out.splitlines()[0])[-1]
        elif "(connecting" in state or "(need_auth)" in state:
            fresh.wpa_state = "ASSOCIATING"
        else:
            fresh.wpa_state = "DISCONNECTED"
    g.net.wifi_ip_address = fresh.ip_address
    result.__dict__.update(fresh.__dict__)


def mks_wpa_scan_scanresults():
    """Scans, fills ``g.net.ssid_list`` (the connected network first, then by signal) and ``g.levelling.level_list``."""
    dev = _device("wifi")
    if dev is None:
        log.info("No wifi interface")
        return -3
    args = ["-t", "-f", "SSID,SIGNAL", "dev", "wifi", "list", "ifname", dev, "--rescan"]
    ret, out = _run(args + ["yes"], timeout=40)
    if ret != 0:        # e.g. the previous scan was too recent: show what NetworkManager already knows
        ret, out = _run(args + ["no"])
        if ret != 0:
            return ret

    best = {}
    for line in out.splitlines():
        fields = _split(line)
        if len(fields) != 2 or not fields[0]:       # hidden networks have no name
            continue
        signal = int(fields[1]) if fields[1].isdigit() else 0
        best[fields[0]] = max(signal, best.get(fields[0], 0))

    connected = g.net.current_connected_ssid_name if g.net.status_result.wpa_state == "COMPLETED" else ""
    ssids = sorted(best, key=lambda s: -best[s])
    if connected:
        if connected in ssids:
            ssids.remove(connected)
        ssids.insert(0, connected)
        best.setdefault(connected, 0)

    g.net.ssid_list = ssids
    g.levelling.level_list = [best[s] for s in ssids]
    for ssid in ssids:
        log.info("%s", ssid)
    return 0


def _forget(ssid):
    """Deletes the saved wifi connections named like the network."""
    ret, out = _run(["-t", "-f", "NAME,UUID,TYPE", "con", "show"])
    for line in out.splitlines():
        fields = _split(line)
        if len(fields) == 3 and fields[0] == ssid and fields[2] == "802-11-wireless":
            _run(["con", "delete", "uuid", fields[1]])


def mks_connect(ssid, psk, hidden=False):
    """Connects to the network and saves the connection (NetworkManager keeps it by itself).
    Returns True on success."""
    dev = _device("wifi")
    if dev is None:
        log.info("No wifi interface")
        return False
    _forget(ssid)       # the typed password replaces an older connection of the network
    args = ["-w", "40", "dev", "wifi", "connect", ssid, "ifname", dev]
    if psk:
        args += ["password", psk]
    if hidden:
        args += ["hidden", "yes"]
    ret, out = _run(args, timeout=60)
    if ret != 0:
        _forget(ssid)   # do not keep a connection with a wrong password
    return ret == 0


def connect_saved(uuid, psk=None):
    """Brings a saved connection up, with a new password if given. Returns True on success."""
    if psk is not None:
        ret, out = _run(["-t", "-f", "802-11-wireless-security.key-mgmt", "con", "show", "uuid", uuid])
        args = ["con", "modify", "uuid", uuid]
        if ret == 0 and not _kv(out).get("802-11-wireless-security.key-mgmt"):
            args += ["wifi-sec.key-mgmt", "wpa-psk"]    # an open network gets a password
        ret, out = _run(args + ["wifi-sec.psk", psk])
        if ret != 0:
            return False
    dev = _device("wifi")
    ret, out = _run(["-w", "40", "con", "up", "uuid", uuid] + (["ifname", dev] if dev else []), timeout=60)
    return ret == 0


def _connect_thread(arg):
    func, args, ssid = arg
    log.debug("Connecting to %s", ssid)
    ok = func(*args)
    mks_wifi_run_cmd_status(g.net.status_result)
    if g.screen.page == ids.WIFI_CONNECT:
        navigation.page_to(ids.WIFI_SUCCESS if ok else ids.WIFI_FAILED)


def mks_start_connect(ssid, psk, hidden=False):
    """Starts the connection in the background; the screen is moved to the result page."""
    pthread_create(_connect_thread, (mks_connect, (ssid, psk, hidden), ssid))


def start_connect_saved(uuid, name, psk=None):
    pthread_create(_connect_thread, (connect_saved, (uuid, psk), name))


# ---------------------------------------------------------------------------------------------- saved networks
def _unescape(value):
    return value.replace("\\:", ":").replace("\\\\", "\\")


def _kv(out):
    """``nmcli -t -f A,B ...`` output as a dict (repeated fields "X[1]" keep the first value)."""
    info = {}
    for line in out.splitlines():
        key, _, value = line.partition(":")
        info.setdefault(key.split("[")[0], _unescape(value))
    return info


def saved_wifi():
    """The saved wifi connections: the active one first, then the most recently used."""
    ret, out = _run(["-t", "-f", "NAME,UUID,TYPE,ACTIVE", "con", "show"])
    items = []
    for line in out.splitlines():
        fields = _split(line)
        if len(fields) != 4 or fields[2] != "802-11-wireless":
            continue
        ret, detail = _run(["-t", "-f", "802-11-wireless.ssid,connection.autoconnect,connection.timestamp",
                            "con", "show", "uuid", fields[1]])
        kv = _kv(detail)
        stamp = kv.get("connection.timestamp", "0")
        items.append({"name": fields[0], "uuid": fields[1], "ssid": kv.get("802-11-wireless.ssid") or fields[0],
                      "autoconnect": kv.get("connection.autoconnect", "yes") == "yes",
                      "active": fields[3] == "yes", "stamp": int(stamp) if stamp.isdigit() else 0})
    items.sort(key=lambda c: (not c["active"], -c["stamp"], c["ssid"].lower()))
    return items


def forget(uuid):
    return _run(["con", "delete", "uuid", uuid])[0] == 0


def set_autoconnect(uuid, enabled):
    return _run(["con", "modify", "uuid", uuid, "connection.autoconnect", "yes" if enabled else "no"])[0] == 0


def disconnect_wifi():
    dev = _device("wifi")
    return dev is not None and _run(["dev", "disconnect", dev])[0] == 0


# ---------------------------------------------------------------------------------------------- interfaces
def wifi_radio():
    """Is the wifi radio switched on?"""
    return _run(["radio", "wifi"])[1].strip() == "enabled"


def set_wifi_radio(enabled):
    return _run(["radio", "wifi", "on" if enabled else "off"])[0] == 0


def device_report(kind):
    """State of the interface: dict(name, state, ip, gateway, mac, ssid); name is None without an interface."""
    dev = _device(kind)
    report = {"name": dev, "state": "", "ip": "", "gateway": "", "mac": "", "ssid": ""}
    if dev is None:
        return report
    ret, out = _run(["-t", "-f", "GENERAL.STATE,GENERAL.HWADDR,GENERAL.CON-UUID,IP4.ADDRESS,IP4.GATEWAY",
                     "dev", "show", dev])
    info = _kv(out)
    state = info.get("GENERAL.STATE", "")
    report["state"] = "connected" if "(connected)" in state else ("unavailable" if "(unavailable)" in state
                                                                  else "disconnected")
    report["ip"] = info.get("IP4.ADDRESS", "").split("/")[0]
    report["gateway"] = info.get("IP4.GATEWAY", "")
    report["mac"] = info.get("GENERAL.HWADDR", "")
    uuid = info.get("GENERAL.CON-UUID", "")
    if kind == "wifi" and report["state"] == "connected" and uuid:
        ret, out = _run(["-t", "-f", "802-11-wireless.ssid", "con", "show", "uuid", uuid])
        report["ssid"] = _kv(out).get("802-11-wireless.ssid", "")
    return report


def mks_wifi_hdlevent_thread(arg=None):
    """Keeps the status of the wifi up to date: refreshed on every change NetworkManager reports
    (``nmcli monitor``) and every 30 seconds."""
    while True:
        try:
            proc = subprocess.Popen([NMCLI, "monitor"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=ENV,
                                    bufsize=0)
        except OSError:
            time.sleep(10)
            continue
        try:
            while proc.poll() is None:
                ready, _, _ = select.select([proc.stdout], [], [], 30)
                if ready and not proc.stdout.readline():
                    break
                time.sleep(1)       # let a burst of events settle
                while select.select([proc.stdout], [], [], 0)[0] and proc.stdout.readline():
                    pass
                mks_wifi_run_cmd_status(g.net.status_result)
                g.net.wlan_state_str = "connected" if g.net.status_result.wpa_state == "COMPLETED" else "disconnected"
                g.net.lan_connected = device_report("ethernet")["state"] == "connected"
        finally:
            proc.kill()
            proc.wait()
        time.sleep(5)        # NetworkManager restarted or is not running yet


def set_page_wifi_ssid_list(pages):
    g.net.wifi_ssid_list[0] = ""
    g.net.wifi_ssid_list[1] = ""
    g.net.wifi_ssid_list[2] = ""
    g.net.wifi_ssid_list[3] = ""
    g.net.wifi_ssid_list[4] = ""

    it = 0
    for i in range(pages * 5):
        it += 1

    for k in range(5):
        if it < len(g.net.ssid_list):
            g.net.wifi_ssid_list[k] = g.net.ssid_list[it]
            it += 1

    for j in range(5):
        log.debug("%s", g.net.wifi_ssid_list[j])


def get_ssid_list_pages():
    """4.4.1 CLL wifi refresh fix"""
    if len(g.net.ssid_list) % 5 == 0:
        g.net.wifi_ssid_list_pages = len(g.net.ssid_list) // 5
    else:
        g.net.wifi_ssid_list_pages = len(g.net.ssid_list) // 5 + 1

    if g.net.wifi_ssid_list_pages > 5:
        g.net.wifi_ssid_list_pages = 5


def get_wlan0_status():
    mks_wifi_run_cmd_status(g.net.status_result)
