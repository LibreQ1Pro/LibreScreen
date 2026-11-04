"""The screen pages that manage the NetworkManager connections (added to the screen firmware, see
display_firmware/tools/add_network_pages.py): saved networks, one network, "forget" confirmation, the state of the
interfaces, and the keyboard modes (password of a scanned / saved network, hidden network)."""

import logging
import time

from librescreen import state as g
from librescreen.pages import widgets
from librescreen.screen import navigation, pageids as ids
from librescreen.screen.text import fit_name
from librescreen.system import network
from librescreen.util import netstrings
from librescreen.util.cpp import pthread_create

log = logging.getLogger(__name__)

ROWS = 5

# modes of the keyboard page: what the text typed on it is
KB_PSK_SCANNED = 1      # password of the network chosen in the scan list (g.net.get_wifi_name)
KB_PSK_SAVED = 2        # new password of the saved connection S.sel
KB_HIDDEN_SSID = 3      # name of a hidden network
KB_HIDDEN_PSK = 4       # its password (empty = open network)


class S:
    saved = []          # saved wifi connections, see network.saved_wifi()
    page = 0
    enabled = [False] * ROWS
    sel = None          # the connection of the detail page
    origin = "saved"    # where the detail page was opened from: "saved" (the list of saved networks) or "list" (the scan list)
    hidden_ssid = ""
    kbmode = KB_PSK_SCANNED


def tr(key):
    """The text ``key`` of netstrings in the language of the screen."""
    return netstrings.text(key, g.config.language_status)


def _clip(text, length):
    """Text for a screen string: no quotes / control characters, at most ``length`` characters."""
    text = "".join(c if c >= " " and c != '"' else "'" for c in text if c >= " ")
    return text if len(text) <= length else text[:length - 2] + ".."


def _txt(obj, text):
    g.port.txt(obj, text)


# ---------------------------------------------------------------------------------------------- saved networks
def open_saved():
    S.saved = network.saved_wifi()
    S.page = 0
    navigation.page_to(ids.NET_SAVED)
    show_saved()


def _pages():
    return (len(S.saved) + ROWS - 1) // ROWS


def show_saved():
    pages = _pages()
    for i in range(ROWS):
        index = S.page * ROWS + i
        item = S.saved[index] if index < len(S.saved) else None
        row = "row" + str(i + 1)
        _txt(row + "_txt", _clip(item["ssid"], 24) if item else "")
        widgets.list_row(row, "check" if item and item["active"] else "item" if item else "blank")
        S.enabled[i] = item is not None
    first = pages <= 1 or S.page == 0
    last = pages <= 1 or S.page == pages - 1
    for button, off in (("prev_btn", first), ("next_btn", last)):
        g.port.face(button, "edge" if off else "more")


def saved_clicked(widget_id):
    if widget_id < ROWS:
        index = S.page * ROWS + widget_id
        if S.enabled[widget_id] and index < len(S.saved):
            open_detail(S.saved[index], "saved")
    elif widget_id == 5 and S.page > 0:         # previous
        S.page -= 1
        show_saved()
    elif widget_id == 6 and S.page < _pages() - 1:      # next
        S.page += 1
        show_saved()
    elif widget_id == 23:                       # back
        from librescreen.pages import wifi
        wifi.go_to_network()


# ---------------------------------------------------------------------------------------------- one network
def saved_by_ssid(ssid):
    """The saved connection of a network of the scan list, or None."""
    for item in network.saved_wifi():
        if item["ssid"] == ssid:
            return item
    return None


def _leave_detail():
    """Back from the detail page (or after the network was forgotten): to the list it was opened from."""
    if S.origin == "list":
        from librescreen.pages import wifi
        wifi.go_to_network()
    else:
        open_saved()


def open_detail(item, origin=None):
    S.sel = item
    if origin is not None:
        S.origin = origin
    navigation.page_to(ids.NET_DETAIL)
    show_detail()


def _reload_selected():
    for item in network.saved_wifi():
        if item["uuid"] == S.sel["uuid"]:
            S.sel = item
            return True
    return False


def show_detail():
    item = S.sel
    state = tr("saved")
    if item["active"]:
        ip = network.device_report("wifi")["ip"]
        state = tr("connected") + (", " + ip if ip else "")
    _txt("ssid_txt", _clip(item["ssid"], 24))
    _txt("status_txt", _clip(state, 30))
    _txt("connect_btn", tr("disconnect") if item["active"] else tr("connect"))
    g.port.face("auto_btn", "on" if item["autoconnect"] else "off")      # the switch of the row


def detail_clicked(widget_id):
    item = S.sel
    if item is None:             # an event of the page when no network was chosen (a late touch): back to the list
        _leave_detail()
        return
    if widget_id == 1:
        if item["active"]:
            network.disconnect_wifi()
            _reload_selected()
            show_detail()
        else:
            navigation.page_to(ids.WIFI_CONNECT)
            network.start_connect_saved(item["uuid"], item["ssid"])
    elif widget_id == 2:
        open_keyboard(KB_PSK_SAVED, 8, item["ssid"])
    elif widget_id == 3:
        network.set_autoconnect(item["uuid"], not item["autoconnect"])
        _reload_selected()
        show_detail()
    elif widget_id == 4:
        navigation.page_to(ids.NET_CONFIRM)
        _txt("msg", tr("forget_q"))
        _txt("ssid_msg", _clip(item["ssid"], 24))
    elif widget_id == 23:
        _leave_detail()


def confirm_clicked(widget_id):
    if S.sel is None:
        _leave_detail()
        return
    if widget_id == 1:
        network.forget(S.sel["uuid"])
        _leave_detail()
    elif widget_id in (0, 23):
        if _reload_selected():
            open_detail(S.sel)
        else:
            _leave_detail()


# ---------------------------------------------------------------------------------------------- interfaces
def open_info():
    navigation.page_to(ids.NET_INFO)
    show_info()


def _slot(value, width=166):
    """The value of a line of the page: the name of an interface, an SSID, an address (``---`` when it is not known)."""
    return fit_name(value, width, lines=1, extension=False) if value else "---"


def show_info():
    wifi = network.device_report("wifi")
    radio = network.wifi_radio()
    lan = network.device_report("ethernet")
    up = wifi["state"] == "connected" and radio
    _txt("wifi_if", _slot(wifi["name"], 140))
    _txt("wifi_ssid", _slot(wifi["ssid"] if up else ""))
    _txt("wifi_ip", _slot(wifi["ip"] if up else ""))
    _txt("wifi_gw", _slot(wifi["gateway"] if up else ""))
    _txt("lan_if", _slot(lan["name"], 140))
    _txt("lan_ip", _slot(lan["ip"] if lan["state"] == "connected" else ""))
    _txt("lan_gw", _slot(lan["gateway"] if lan["state"] == "connected" else ""))
    g.port.face("radio_btn", "on" if radio else "off")


def _toggle_thread(arg):
    network.set_wifi_radio(not network.wifi_radio())
    time.sleep(2)        # NetworkManager needs a moment to bring the radio up / down
    if g.screen.page == ids.NET_INFO:
        show_info()


def info_clicked(widget_id):
    if widget_id == ids.NET_INFO_RADIO:          # the wired link is never switched: LAN and Wi-Fi are used together
        pthread_create(_toggle_thread, None)
    elif widget_id == ids.NET_INFO_WIFI:        # the list of Wi-Fi networks
        from librescreen.pages import wifi
        wifi.go_to_network()
    elif widget_id == ids.NET_INFO_BACK:
        navigation.page_to(ids.COMMON_SETTING)


# ---------------------------------------------------------------------------------------------- keyboard
def open_keyboard(mode, minimum, title):
    """Opens the keyboard page; the screen sends back ``0x70 mode row text`` when the text is accepted.
    The title of the page is the name of the network (``g.net.get_wifi_name``)."""
    S.kbmode = mode
    g.net.get_wifi_name = title
    g.screen.printing_wifi_keyboard_enabled = True
    g.port.raw("kbmode=%d" % mode)
    g.port.raw("kbmin=%d" % minimum)
    navigation.page_to(ids.WIFI_KB)


def open_hidden():
    S.hidden_ssid = ""
    open_keyboard(KB_HIDDEN_SSID, 1, tr("network_name"))


def keyboard_back():
    g.screen.printing_wifi_keyboard_enabled = False
    if S.kbmode == KB_PSK_SAVED and S.sel is not None:
        open_detail(S.sel)
    else:
        from librescreen.pages import wifi
        wifi.go_to_network()


def keyboard_text(mode, text):
    """The text accepted on the keyboard page (str)."""
    from librescreen.pages import wifi
    log.debug("Keyboard mode %d", mode)
    g.screen.printing_wifi_keyboard_enabled = False
    if mode == KB_PSK_SCANNED:
        navigation.page_to(ids.WIFI_CONNECT)
        wifi.print_ssid_psk(text)
    elif mode == KB_PSK_SAVED and S.sel is not None:
        navigation.page_to(ids.WIFI_CONNECT)
        network.start_connect_saved(S.sel["uuid"], S.sel["ssid"], text)
    elif mode == KB_HIDDEN_SSID:
        S.hidden_ssid = text
        open_keyboard(KB_HIDDEN_PSK, 0, text)
    elif mode == KB_HIDDEN_PSK:
        navigation.page_to(ids.WIFI_CONNECT)
        network.mks_start_connect(S.hidden_ssid, text, hidden=True)
    else:
        log.info("Unknown keyboard mode %d", mode)
