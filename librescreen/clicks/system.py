"""Clicks on the network, settings, error and pop-up pages. Each function gets the page id and the widget id the screen sent; HANDLERS maps pages to them."""

import logging
import time

from librescreen import state as g
from librescreen.clicks.common import nav_guarded
from librescreen.config import settings
from librescreen.pages import connections, file_list, wifi
from librescreen.printer import job, klipper
from librescreen.screen import pageids as ids
from librescreen.screen.navigation import page_to
from librescreen.system.network import set_page_wifi_ssid_list

log = logging.getLogger(__name__)


def internet(page_id, widget_id):
    if nav_guarded(widget_id):
        pass
    elif widget_id == ids.ALL_TO_SETTING:
        pass
    elif widget_id == ids.INTERNET_REFRESH:
        log.debug("################## refresh button pressed")
        wifi.scan_ssid_and_show()
        log.debug("Waiting 3s...")
        time.sleep(3)
        wifi.scan_ssid_and_show()
    elif widget_id == ids.INTERNET_TO_WIFI:
        pass
    elif widget_id == ids.INTERNET_TO_SETTING:
        page_to(ids.COMMON_SETTING)


def wifi_list(page_id, widget_id):
    if nav_guarded(widget_id):
        pass
    elif widget_id == ids.ALL_TO_SETTING:
        pass
    elif widget_id in (ids.WIFI_LIST_SSID_1, ids.WIFI_LIST_SSID_2, ids.WIFI_LIST_SSID_3,
                       ids.WIFI_LIST_SSID_4, ids.WIFI_LIST_SSID_5):
        index = widget_id - ids.WIFI_LIST_SSID_1
        if g.screen.wifi_ssid_button_enabled[index]:
            wifi.get_wifi_list_ssid(index)
            saved = connections.saved_by_ssid(g.net.get_wifi_name)
            if saved is not None:           # a known network: connect / change the password / forget, not the password again
                connections.open_detail(saved, "list")
            else:
                connections.open_keyboard(connections.KB_PSK_SCANNED, 8, g.net.get_wifi_name)
    elif widget_id == ids.WIFI_LIST_SAVED:
        connections.open_saved()
    elif widget_id == ids.WIFI_LIST_HIDDEN:
        connections.open_hidden()
    elif widget_id == ids.WIFI_LIST_REFRESH:
        log.debug("################## refresh button pressed")
        wifi.scan_ssid_and_show()
        # 4.4.1 CLL wifi refresh fix
    elif widget_id == ids.WIFI_LIST_PREVIOUS:
        if g.net.wifi_current_pages > 0:
            log.debug("page_wifi_current_pages = %s", g.net.wifi_current_pages)
            log.debug("page_wifi_ssid_list_pages = %s", g.net.wifi_ssid_list_pages)
            g.net.wifi_current_pages -= 1
            set_page_wifi_ssid_list(g.net.wifi_current_pages)
            wifi.refresh_wifi_list()
    elif widget_id == ids.WIFI_LIST_NEXT:
        if g.net.wifi_current_pages < g.net.wifi_ssid_list_pages - 1:
            log.debug("page_wifi_current_pages = %s", g.net.wifi_current_pages)
            log.debug("page_wifi_ssid_list_pages = %s", g.net.wifi_ssid_list_pages)
            g.net.wifi_current_pages += 1
            set_page_wifi_ssid_list(g.net.wifi_current_pages)
            wifi.refresh_wifi_list()
    elif widget_id == ids.WIFI_LIST_TO_WIFI:
        pass
    elif widget_id == ids.WIFI_LIST_TO_SETTING:
        connections.open_info()               # the network settings start with the network info


# 4.4.24: the timer of the page reports a connection that takes too long
def wifi_connect(page_id, widget_id):
    if widget_id == ids.WIFI_CONNECT_TIMEOUT:
        page_to(ids.WIFI_FAILED)


def wifi_success(page_id, widget_id):
    if widget_id == ids.WIFI_SUCCESS_YES:
        wifi.go_to_network()


def wifi_failed(page_id, widget_id):
    if widget_id == ids.WIFI_FAILED_YES:
        wifi.go_to_network()                  # 4.4.22 (was page_to(ids.WIFI_LIST))


def wifi_kb(page_id, widget_id):
    if widget_id == ids.WIFI_KB_BACK:
        connections.keyboard_back()


def net_saved_or_net_info(page_id, widget_id):
    if nav_guarded(widget_id):
        pass
    elif page_id == ids.NET_SAVED:
        connections.saved_clicked(widget_id)
    elif page_id == ids.NET_DETAIL:
        connections.detail_clicked(widget_id)
    elif page_id == ids.NET_CONFIRM:
        connections.confirm_clicked(widget_id)
    else:
        connections.info_clicked(widget_id)


def common_setting(page_id, widget_id):
    if nav_guarded(widget_id):
        pass
    elif widget_id == ids.ALL_TO_SETTING:
        pass
    elif widget_id == ids.COMMON_SETTING_LANGUAGE:
        page_to(ids.LANGUAGE)
    elif widget_id == ids.COMMON_SETTING_WIFI:
        connections.open_info()               # the network settings start with the network info (4.4.22 had the QR code page here)
    elif widget_id == ids.COMMON_SETTING_SYSTEM:
        klipper.go_to_reset()
    elif widget_id == ids.COMMON_SETTING_SCREEN_SLEEP:
        page_to(ids.SLEEP_MODE)
    elif widget_id == ids.COMMON_SETTING_RESTORE:
        page_to(ids.RESTORE_CONFIG)
    elif widget_id == ids.COMMON_SETTING_OOBE_OFF:
        settings.set_oobe_enabled(False)
        page_to(ids.COMMON_SETTING)
    elif widget_id == ids.COMMON_SETTING_OOBE_ON:
        settings.set_oobe_enabled(True)
    elif widget_id == ids.COMMON_SETTING_TO_LEVEL_MODE:
        page_to(ids.LEVEL_MODE)
        g.screen.set_mode = "Level_mode"


def language_or_sleep_mode(page_id, widget_id):
    if nav_guarded(widget_id):
        pass
    elif widget_id == ids.ALL_TO_SETTING:
        pass
    elif widget_id == ids.BACK_TO_COMMON_SETTING:
        page_to(ids.COMMON_SETTING)
    elif widget_id == ids.RESET_PRINT_LOG:
        file_list.print_log()
    elif widget_id == ids.RESET_RESTART_KLIPPER:
        klipper.reset_klipper()
    elif widget_id == ids.RESET_RESTART_FIRMWARE:
        klipper.reset_firmware()


def update_success(page_id, widget_id):
    if widget_id == ids.UPDATE_SUCCESS_YES:
        page_to(ids.MAIN)


def detect_error(page_id, widget_id):
    if widget_id == ids.DETECT_ERROR_YES:
        if g.screen.previous_page == ids.AUTO_MOVING:
            klipper.reset_klipper()
        page_to(ids.MAIN)
        job.clear_previous_data()


def gcode_error(page_id, widget_id):
    if widget_id == ids.GCODE_ERROR_YES:
        page_to(ids.MAIN)


# 4.4.2 CLL screen sleep feature
def screen_sleep(page_id, widget_id):
    if widget_id == ids.SCREEN_SLEEP_ENTER:
        page_to(ids.SCREEN_SLEEP)
    elif widget_id == ids.SCREEN_SLEEP_EXIT:
        if g.screen.previous_page == ids.FILE_LIST:
            file_list.go_to_file_list()
        else:
            page_to(g.screen.previous_page)
            klipper.get_object_status()


def restore_config(page_id, widget_id):
    if widget_id == ids.RESTORE_CONFIG_YES:
        settings.restore_config()
    elif widget_id == ids.RESTORE_CONFIG_NO:
        page_to(ids.COMMON_SETTING)


def memory_warning(page_id, widget_id):
    if widget_id == ids.MEMORY_WARNING_YES:
        page_to(ids.MAIN)


HANDLERS = {
    ids.INTERNET: internet,
    ids.WIFI_LIST: wifi_list,
    ids.WIFI_CONNECT: wifi_connect,
    ids.WIFI_SUCCESS: wifi_success,
    ids.WIFI_FAILED: wifi_failed,
    ids.WIFI_KB: wifi_kb,
    ids.NET_SAVED: net_saved_or_net_info,
    ids.NET_DETAIL: net_saved_or_net_info,
    ids.NET_CONFIRM: net_saved_or_net_info,
    ids.NET_INFO: net_saved_or_net_info,
    ids.COMMON_SETTING: common_setting,
    ids.LANGUAGE: language_or_sleep_mode,
    ids.SYS_OK: language_or_sleep_mode,
    ids.RESET: language_or_sleep_mode,
    ids.SLEEP_MODE: language_or_sleep_mode,
    ids.UPDATE_SUCCESS: update_success,
    ids.DETECT_ERROR: detect_error,
    ids.GCODE_ERROR: gcode_error,
    ids.SCREEN_SLEEP: screen_sleep,
    ids.RESTORE_CONFIG: restore_config,
    ids.MEMORY_WARNING: memory_warning,
}
