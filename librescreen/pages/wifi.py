"""The Wi-Fi list page, the IP address and the connection details."""

import logging

from librescreen import state as g
from librescreen.pages import widgets
from librescreen.screen import pageids as ids
from librescreen.screen.navigation import page_to
from librescreen.system import network
from librescreen.system.network import (detected_wlan0,
                                  get_ssid_list_pages,
                                  get_wlan0_status,
                                  set_page_wifi_ssid_list)
from librescreen.util.cpp import to_string

log = logging.getLogger(__name__)


def refresh_wifi_keyboard():
    if g.screen.printing_wifi_keyboard_enabled:
        g.port.txt("title", g.net.get_wifi_name)


def go_to_network():
    if detected_wlan0():
        get_wlan0_status()
        g.screen.wifi_ssid_button_enabled[0] = False
        g.screen.wifi_ssid_button_enabled[1] = False
        g.screen.wifi_ssid_button_enabled[2] = False
        g.screen.wifi_ssid_button_enabled[3] = False
        g.screen.wifi_ssid_button_enabled[4] = False
        g.net.wifi_ssid_list_pages = 0
        g.net.wifi_current_pages = 0
        if g.net.status_result.wpa_state == "COMPLETED":
            g.net.current_connected_ssid_name = g.net.status_result.ssid   # name of the connected wifi
        elif g.net.status_result.wpa_state != "INACTIVE":
            g.net.current_connected_ssid_name = ""      # not connected: forget the name of the connected wifi
        page_to(ids.WIFI_LIST)
        scan_ssid_and_show()
    else:
        page_to(ids.INTERNET)


def scan_ssid_and_show():
    if detected_wlan0():
        get_wlan0_status()
        network.mks_wpa_scan_scanresults()
        get_ssid_list_pages()
        g.net.wifi_current_pages = 0
        set_page_wifi_ssid_list(g.net.wifi_current_pages)
        refresh_wifi_list()
    else:
        page_to(ids.INTERNET)


def refresh_wifi_list():
    # 4.4.22: the names come from the list, the first entry of the first page is
    # the connected network; the page buttons are set once after the list
    log.debug("pages: %d / %d", g.net.wifi_current_pages + 1, g.net.wifi_ssid_list_pages)
    for i in range(5):
        log.debug("Refreshed wifi: %s", g.net.wifi_ssid_list[i])
        g.port.txt("row" + to_string(i + 1) + "_txt", g.net.wifi_ssid_list[i])
        if g.net.status_result.wpa_state == "COMPLETED" and g.net.wifi_current_pages == 0 and i == 0:
            widgets.list_row("row1", "check")
            g.screen.wifi_ssid_button_enabled[i] = True        # the connected network is a saved one: its page opens
        elif g.net.wifi_ssid_list[i] != "":
            widgets.list_row("row" + to_string(i + 1), "item")
            g.screen.wifi_ssid_button_enabled[i] = True
        else:
            widgets.list_row("row" + to_string(i + 1), "blank")
            g.screen.wifi_ssid_button_enabled[i] = False

    if g.net.wifi_ssid_list_pages == 0:
        g.port.face("prev_btn", "edge")
        g.port.face("next_btn", "edge")
    else:
        g.port.face("prev_btn", "edge" if g.net.wifi_current_pages == 0 else "more")
        g.port.face("next_btn", "edge" if g.net.wifi_ssid_list_pages - 1 == g.net.wifi_current_pages else "more")


def get_wifi_list_ssid(index):
    g.net.get_wifi_name = ""
    g.net.get_wifi_name = g.net.wifi_ssid_list[index]


def print_ssid_psk(psk):
    """psk: the password typed on the screen keyboard (str)"""
    log.info("SSID is %s", g.net.get_wifi_name)
    network.mks_start_connect(g.net.get_wifi_name, psk)


