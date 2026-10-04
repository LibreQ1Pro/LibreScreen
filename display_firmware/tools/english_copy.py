#!/usr/bin/env python3
"""The English copy of the screen firmware (what the editor shows and what ``lang==2`` displays) and the Russian one (``lang==1``).

    python3 tools/english_copy.py            apply (run from display_firmware/)
    python3 tools/english_copy.py --check    only report problems (a line wider than its component, too many lines)

QIDI's English was machine-translated and in places wrong or unrelated to the original (``Load`` on the button that
unloads, ``Confirm`` on a Yes/No question, ``Heat Chamber`` as the title of the nozzle keyboard); this table was written
from the Chinese originals, which are kept in the ``lang==0`` branches. Every text is written once, without line
breaks: the line breaks (``\\r``) are computed from the real glyph widths of the font of the component.

``COPY[(page, component)]``    one text, or a list for a component that gets several texts one after another
                               (a keyboard title, a step label): the first is the editor text, the list is the ``lang==2``
                               lines in the order they are written in ``codesload``.
``BUTTON_COPY``                the short words of buttons (OK, Yes, No, Back ...), by what the Chinese stock text meant.
``COPY_RU``                    the same for the Russian branch (``lang==1``); a button takes the Russian of its English word
                               from ``RU_WORDS``.
``wifi()``                     writes "Wi-Fi" in every language (the stock has WiFi, Wifi, wifi).
"""
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_hmi   # noqa: E402
import translations   # noqa: E402

sys.path.insert(0, os.path.join(build_hmi.find_builder(), "tools"))   # hmi_font

# short words of buttons: the Chinese text of the component in the stock project is in the comment
BUTTON_COPY = {
    ('auto_finish', 'ok'): 'Done',
    ('auto_unload', 'load_btn'): 'Load',
    ('auto_unload', 'ok'): 'OK',
    ('auto_warning', 'ok'): 'OK',
    ('bed_finish', 'ok'): 'Done',
    ('cal_warning', 'next_btn'): 'Continue',
    ('cal_warning', 'back_btn'): 'Back',
    ('detect_error', 'ok'): 'OK',
    ('filament', 'load_btn'): 'Load',
    ('filament_pop_1', 'ok'): 'OK',
    ('filament_pop_2', 'done_btn'): 'Done',
    ('filament_pop_2', 'alt_btn'): 'Unload',
    ('filament_pop_2', 'next_btn'): 'Next',
    ('filament_pop_2', 'back_btn'): 'Back',
    ('filament_pop_3', 'done_btn'): 'Done',
    ('filament_pop_3', 'alt_btn'): 'Load',
    ('filament_pop_3', 'next_btn'): 'Next',
    ('filament_pop_3', 'back_btn'): 'Back',
    ('gcode_error', 'ok'): 'OK',
    ('level_error', 'ok'): 'OK',
    ('memory_warning', 'ok'): 'OK',
    ('move_pop_1', 'ok'): 'OK',
    ('move_pop_2', 'ok'): 'Yes',
    ('move_pop_2', 'cancel'): 'No',
    ('open_language', 'next'): 'Next',
    ('open_language', 'skip'): 'Skip',
    ('open_language2', 'next'): 'Next',
    ('open_language2', 'skip'): 'Skip',
    ('open_pop', 'ok'): 'Yes',
    ('open_pop', 'cancel'): 'No',
    ('pre_heat', 'next_btn'): 'Next',
    ('pre_heat', 'back_btn'): 'Back',
    ('preview_pop_1', 'ok'): 'OK',
    ('preview_pop_2', 'ok'): 'OK',
    ('print_finish', 'ok'): 'OK',
    ('print_log_f', 'ok'): 'OK',
    ('print_log_s', 'ok'): 'OK',
    ('print_lowtemp', 'ok'): 'OK',
    ('print_no_fil', 'ok'): 'OK',
    ('print_no_fil2', 'ok'): 'OK',
    ('print_stop', 'ok'): 'Yes',
    ('print_stop', 'cancel'): 'No',
    ('restore_config', 'ok'): 'Yes',
    ('restore_config', 'cancel'): 'No',
    ('resume_print', 'ok'): 'Yes',
    ('resume_print', 'cancel'): 'No',
    ('stop_confirm', 'ok'): 'Yes',
    ('stop_confirm', 'cancel'): 'No',
    ('syntony_finish', 'ok'): 'Done',
    ('unload_finish', 'ok'): 'OK',
    ('unload_mode', 'back_btn'): 'Back',
    ('update_success', 'ok'): 'OK',
    ('wifi_fail', 'ok'): 'OK',
    ('wifi_success', 'ok'): 'OK',
}

NOZZLE_LOW = "The nozzle temperature is too low. Please try again after it reaches the set temperature."

COPY = {
    ("auto_finish", "msg"): "Auto leveling completed.",
    ("auto_heaterbed", "msg"): "Preheat the bed to the printing temperature of the filament before leveling for a more "
                               "accurate result.",
    ("auto_moving", "step1_txt"): "Initializing the platform and nozzle position.",
    ("auto_moving", "step2_txt"): "Heating and cleaning the nozzle.",
    ("auto_moving", "step3_txt"): "Waiting for the nozzle to cool down.",
    ("auto_moving", "step4_txt"): "Collecting the compensation values.",
    ("auto_moving", "bed_lbl"): "Bed Temp:",
    ("auto_unload", "step1_txt"): "Heating up.",
    ("auto_unload", "step2_txt"): "Unloading filament.",
    ("auto_unload", "step3_txt"): "Done.",
    ("auto_warning", "msg"): "Please set the temperature to 35℃ or higher.",
    ("bed_calibrate", "msg"): "Following the picture, adjust the nut under the metal sheet of the platform at the "
                              "marked position until the calibration feeler gauge moves between the nozzle and the platform with "
                              "slight friction. Then tap “>” to continue the calibration.",
    ("bed_calibrate", "step_txt"): ["Adjusting nut 1.", "Adjusting nut 2.", "Adjusting nut 3.", "Adjusting nut 4."],
    ("bed_finish", "msg"): "Select a nut above to move to its position and adjust it again.",
    ("bed_finish", "screw1"): "Nut 1",
    ("bed_finish", "screw2"): "Nut 2",
    ("bed_finish", "screw3"): "Nut 3",
    ("bed_finish", "z_tilt"): "Tilt Calibration",
    ("bed_moving", "msg"): "Moving to the adjustment point, please wait...",
    ("cal_warning", "msg"): "Please make sure the PEI plate is properly placed and there is no debris on the platform or on the "
                            "chamber floor below it.",
    ("common_set", "tab_settings"): "General",
    ("common_set", "tab_calib"): "Calibration",
    ("common_set", "lang_lbl"): "Language",
    ("common_set", "network_lbl"): "Network",
    ("common_set", "sysinfo_lbl"): "Klipper Status",
    ("common_set", "sleep_lbl"): "Screen",
    ("common_set", "reset_lbl"): "Restore Factory Settings",
    ("detect_error", "msg"): "Error Message",
    ("filament", "tab_manual"): "Move",
    ("filament", "tab_load"): "Filament",
    ("filament", "replace_btn"): "Replace Filament",
    ("filamentVideo0", "title"): "Load Filament (3/3)",
    ("filamentVideo0", "msg"): "Please install the filament holder.",
    ("filamentVideo1", "title"): "Load Filament (3/3)",
    ("filamentVideo1", "msg"): "Insert the filament into the filament inlet and keep pushing it until it reaches the nozzle.",
    ("filamentVideo2", "title"): "Load Filament (3/3)",
    ("filamentVideo2", "msg_heat"): "Tap the “-” or “+” button above to start heating and set the nozzle temperature.",
    ("filamentVideo2", "msg_wait"): "Waiting for the temperature to reach the set value.",
    ("filamentVideo3", "title"): "Load Filament (3/3)",
    ("filamentVideo3", "msg"): "Make sure the filament has entered the nozzle, then tap “↓” until filament flows out of "
                               "the nozzle.",
    ("filament_kb", "title"): ["Nozzle Temp", "Bed Temp", "Chamber Temp"],
    ("filament_pop_1", "msg"): NOZZLE_LOW,
    ("filament_pop_2", "step1_txt"): "Heating up.",
    ("filament_pop_2", "step2_txt"): "Unloading filament.",
    ("filament_pop_2", "step3_txt"): "Done.",
    ("filament_pop_2", "done_btn"): "OK",
    ("filament_pop_2", "alt_btn"): "Load",
    ("filament_pop_3", "alt_btn"): "Retry",
    ("filament_pop_2", "hint"): "Please cut the filament, then tap “Next”.",
    ("filament_pop_3", "step1_txt"): "Heating up.",
    ("filament_pop_3", "step2_txt"): "Loading filament.",
    ("filament_pop_3", "step3_txt"): "Done. Check that filament comes out.",
    ("filament_pop_3", "hint"): "Please load the filament, then tap “Next”.",
    ("filelist", "usb_tab"): "USB Files",
    ("filelist", "local_tab"): "Local Files",
    ("filelist", "empty_msg"): "Empty",
    ("gcode_error", "msg"): "G-code Error",
    ("internet", "title"): "Wi-Fi Connection",
    ("internet", "msg"): "No network detected.",
    ("internet_page", "title"): "Network",
    ("internet_page", "wifi_btn"): "Wi-Fi",
    ("keybdB", "title"): ["Nozzle Temp", "Bed Temp", "Print Speed", "Flow Rate", "Cooling Fan", "Auxiliary Cooling Fan",
                          "Chamber Circulation Fan", "Chamber Temp"],
    ("keybdB", "mute_btn"): "Mute",
    ("language", "title"): "Language",
    ("language2", "title"): "Language",
    ("level_error", "msg"): "Leveling error.",
    ("level_mode", "tab_settings"): "General",
    ("level_mode", "tab_calib"): "Calibration",
    ("level_mode", "auto_level"): "Auto Bed Leveling",
    ("level_mode", "shaping"): "Input Shaping",
    ("level_mode", "bed_calib"): "Platform Calibration",
    ("level_mode", "msg"): "Please make sure the nozzle is clean and there are no foreign objects on the bed.",
    ("main", "ver_warning"): "The UI version does not match the firmware. Please check for updates or contact support!",
    ("memory_warning", "msg"): "Memory is full. Please free up some space.",
    ("move", "tab_manual"): "Move",
    ("move", "tab_load"): "Filament",
    ("move_pop_1", "msg"): "The movement is out of range.",
    ("move_pop_2", "msg"): "The axes must be homed before they can be moved manually. Home them now?",
    ("open_finish", "msg"): "Congratulations! The setup guide is finished.",
    ("open_finish", "msg_level"): "Please perform leveling and input shaping before printing.",
    ("open_finish", "finish"): "Finish",
    ("open_language", "title"): "Language (1/3)",
    ("open_language2", "title"): "Language (1/3)",
    ("open_moving", "title"): "Unboxing (2/3)",
    ("open_moving", "msg"): "Please wait for the platform and nozzle to finish initializing.",
    ("open_pop", "msg"): "Skip the setup guide?",
    ("open_video_1", "title"): "Unboxing (2/3)",
    ("open_video_1", "msg"): "Remove all cable ties.",
    ("open_video_2", "title"): "Unboxing (2/3)",
    ("open_video_2", "msg"): "Remove the four screws that secure the heated bed.",
    ("open_warning", "title"): "Unboxing (2/3)",
    ("open_warning", "msg"): "The platform is about to move. Please make sure it is unlocked and nothing is on it.",
    ("pre_bed_cal", "title"): "Adjusting the platform reference point.",
    ("pre_bed_cal", "msg"): "Select a number and adjust it with the up and down arrow buttons until the calibration feeler gauge moves "
                            "between the nozzle and the platform with slight friction.",
    ("pre_heat", "msg"): "Please select the nozzle temperature.",
    ("preview", "level_lbl"): "Bed Leveling",
    ("preview", "timelapse_lbl"): "Timelapse",
    ("preview", "err_msg"): "Failed to open the file, please go back.",
    ("preview_pop_1", "msg"): "Printing PLA or PETG in a closed chamber may overheat and soften the filament too early, "
                              "which can jam the hotend. Please open the top cover and keep the machine ventilated.",
    ("preview_pop_1", "no_more"): "Don't Show Again",
    ("preview_pop_2", "msg"): "Please make sure the top cover and front door are closed. The chamber temperature "
                              "should not exceed 55℃.",
    ("preview_pop_2", "no_more"): "Don't Show Again",
    ("print_filament", "title"): "Load Filament",
    ("print_filament", "replace_btn"): "Replace Filament",
    ("print_finish", "msg"): "Print complete! Time spent:",
    ("print_log_f", "msg"): "Failed to export the logs. Please make sure the USB drive is inserted.",
    ("print_log_s", "msg"): "Logs exported successfully.",
    ("print_lowtemp", "msg"): NOZZLE_LOW,
    ("print_no_fil", "msg"): "No filament detected. Please reload the filament.",
    ("print_no_fil2", "msg"): "Filament tangle detected. Please reload the filament.",
    ("print_stop", "msg"): "Stop printing?",
    ("print_stopping", "msg"): "The machine is stopping, please wait...",
    ("re_printing", "msg"): "Resuming the print...",
    ("reset", "export_logs"): "Export Logs",
    ("reset", "title"): "Klipper Status",
    ("reset", "err_msg"): "Error message",
    ("restore_config", "msg"): "Restore the factory settings?",
    ("resume_print", "msg"): "The last print was interrupted. Resume printing?",
    ("sleep_mode", "opt_5min_lbl"): "5 minutes",
    ("sleep_mode", "opt_15min_lbl"): "15 minutes",
    ("sleep_mode", "opt_30min_lbl"): "30 minutes",
    ("sleep_mode", "opt_never_lbl"): "Never",
    ("sleep_mode", "title"): "Screen",
    ("stop_confirm", "msg"): "Are you sure you want to do an emergency stop?",
    ("syntony_finish", "msg"): "Input shaping completed.",
    ("syntony_move", "msg"): "Input shaping in progress, please wait...",
    ("sys_ok", "msg"): "Klipper is ready.",
    ("sys_ok", "export_logs"): "Export Logs",
    ("sys_ok", "title"): "Klipper Status",
    ("unload_finish", "msg"): "Filament unloading completed.",
    ("unload_mode", "msg"): "Please select an unloading method.",
    ("unload_mode", "hint"): "Recommended.",
    ("unload_mode", "warn"): "Note: The filament may get stuck during automatic unloading and block the extruder.",
    ("unload_mode", "manual_btn"): "Manual Unload",
    ("unload_mode", "auto_btn"): "Automatic Unload",
    ("update_success", "msg"): "Update complete.",
    ("wifi_connect", "msg"): "Connecting to Wi-Fi...",
    ("wifi_fail", "msg"): "Connection failed.",
    ("wifi_kb", "title"): "Enter Password",
    ("wifi_success", "msg"): "Connected successfully.",
}

RU_WORDS = {"OK": "ОК", "Yes": "Да", "No": "Нет", "Cancel": "Отмена", "Back": "Назад", "Next": "Далее", "Done": "Готово",
            "Continue": "Продолжить", "Skip": "Пропустить", "Add": "Добавить", "Refresh": "Обновить",
            "Retry": "Повторить", "Load": "Загрузить", "Unload": "Выгрузить"}
NOZZLE_LOW_RU = "Температура сопла слишком низкая. Повторите попытку, когда она достигнет заданной."
FILAMENT_TABS_RU = "Филамент"

COPY_RU = {
    ("auto_finish", "msg"): "Автоматическое выравнивание стола завершено.",
    ("auto_heaterbed", "msg"): "Перед выравниванием рекомендуется прогреть стол до температуры печати используемого "
                               "филамента: так результат будет точнее.",
    ("auto_moving", "step1_txt"): "Инициализация положения платформы и сопла.",
    ("auto_moving", "step2_txt"): "Нагрев и очистка сопла.",
    ("auto_moving", "step3_txt"): "Ожидание остывания сопла.",
    ("auto_moving", "step4_txt"): "Сбор значений компенсации.",
    ("auto_moving", "bed_lbl"): "Стол:",
    ("auto_unload", "step1_txt"): "Нагрев.",
    ("auto_unload", "step2_txt"): "Выгрузка филамента.",
    ("auto_unload", "step3_txt"): "Готово.",
    ("auto_warning", "msg"): "Установите температуру выше 35℃.",
    ("bed_calibrate", "msg"): "По рисунку отрегулируйте гайку под металлическим листом платформы, пока калибровочный щуп "
                              "не станет двигаться между соплом и платформой с лёгким трением. Затем нажмите «>».",
    ("bed_calibrate", "step_txt"): ["Регулировка гайки 1.", "Регулировка гайки 2.", "Регулировка гайки 3.",
                                   "Регулировка гайки 4."],
    ("bed_finish", "msg"): "Выберите гайку выше, чтобы перейти к её положению и отрегулировать её заново.",
    ("bed_finish", "screw1"): "Гайка 1",
    ("bed_finish", "screw2"): "Гайка 2",
    ("bed_finish", "screw3"): "Гайка 3",
    ("bed_finish", "z_tilt"): "Калибровка наклона",
    ("bed_moving", "msg"): "Перемещение к точке регулировки, подождите...",
    ("cal_warning", "msg"): "Убедитесь, что пластина PEI установлена правильно, а на платформе и на дне камеры под ней нет "
                            "посторонних предметов.",
    ("common_set", "tab_settings"): "Общие",
    ("common_set", "tab_calib"): "Калибровка",
    ("common_set", "lang_lbl"): "Язык",
    ("common_set", "network_lbl"): "Сеть",
    ("common_set", "sysinfo_lbl"): "Статус Klipper",
    ("common_set", "sleep_lbl"): "Экран",
    ("common_set", "reset_lbl"): "Сброс к заводским настройкам",
    ("filament", "tab_manual"): "Движение",
    ("filament", "tab_load"): FILAMENT_TABS_RU,
    ("filament", "replace_btn"): "Заменить филамент",
    ("filamentVideo0", "title"): "Загрузка (3/3)",
    ("filamentVideo0", "msg"): "Установите держатель филамента.",
    ("filamentVideo1", "title"): "Загрузка (3/3)",
    ("filamentVideo1", "msg"): "Вставьте филамент во вход филамента и проталкивайте его до самого сопла.",
    ("filamentVideo2", "title"): "Загрузка (3/3)",
    ("filamentVideo2", "msg_heat"): "Нажмите «-» или «+» выше, чтобы начать нагрев и задать температуру сопла.",
    ("filamentVideo2", "msg_wait"): "Ожидание достижения заданной температуры.",
    ("filamentVideo3", "title"): "Загрузка (3/3)",
    ("filamentVideo3", "msg"): "Убедитесь, что филамент вошёл в сопло, затем нажимайте «↓», пока филамент не "
                               "потечёт из сопла.",
    ("filament_kb", "title"): ["Темп. сопла", "Темп. стола", "Темп. камеры"],
    ("filament_pop_1", "msg"): NOZZLE_LOW_RU,
    ("cal_warning", "next_btn"): "Далее",
    ("filament_pop_2", "step1_txt"): "Нагрев.",
    ("filament_pop_2", "step2_txt"): "Выгрузка филамента.",
    ("filament_pop_2", "step3_txt"): "Готово.",
    ("filament_pop_2", "done_btn"): "ОК",
    ("filament_pop_2", "alt_btn"): "Загрузить",
    ("filament_pop_2", "hint"): "Отрежьте филамент и нажмите «Далее».",
    ("filament_pop_3", "step1_txt"): "Нагрев.",
    ("filament_pop_3", "step2_txt"): "Загрузка филамента.",
    ("filament_pop_3", "step3_txt"): "Готово. Проверьте, выходит ли филамент.",
    ("filament_pop_3", "alt_btn"): "Повторить",
    ("filament_pop_3", "hint"): "Загрузите филамент и нажмите «Далее».",
    ("filelist", "usb_tab"): "Файлы USB",
    ("filelist", "local_tab"): "Локальные",
    ("filelist", "empty_msg"): "Пусто",
    ("internet", "title"): "Подключение Wi-Fi",
    ("internet", "msg"): "Сеть не обнаружена.",
    ("keybdB", "title"): ["Температура сопла", "Температура стола", "Скорость печати", "Скорость потока",
                          "Охлаждающий вентилятор", "Вспомогательный вентилятор", "Циркуляционный вентилятор камеры",
                          "Температура камеры"],
    ("keybdB", "mute_btn"): "Тихий режим",
    ("language", "title"): "Язык",
    ("language2", "title"): "Язык",
    ("level_error", "msg"): "Ошибка выравнивания.",
    ("level_mode", "tab_settings"): "Общие",
    ("level_mode", "tab_calib"): "Калибровка",
    ("level_mode", "auto_level"): "Автовыравнивание стола",
    ("level_mode", "shaping"): "Input Shaping",
    ("level_mode", "bed_calib"): "Калибровка платформы",
    ("level_mode", "msg"): "Убедитесь, что сопло чистое и на столе нет посторонних предметов.",
    ("main", "ver_warning"): "Версия интерфейса не соответствует прошивке. Проверьте обновления или обратитесь в "
                             "поддержку!",
    ("memory_warning", "msg"): "Память заполнена. Освободите место.",
    ("move", "tab_manual"): "Движение",
    ("move", "tab_load"): FILAMENT_TABS_RU,
    ("move_pop_1", "msg"): "Движение за пределами допустимого диапазона.",
    ("move_pop_2", "msg"): "Перед ручным перемещением нужно выполнить парковку осей. Выполнить её сейчас?",
    ("open_finish", "msg"): "Поздравляем! Руководство по настройке завершено.",
    ("open_finish", "msg_level"): "Перед печатью выполните выравнивание стола и Input Shaping.",
    ("open_finish", "finish"): "Завершить",
    ("open_language", "title"): "Язык (1/3)",
    ("open_language2", "title"): "Язык (1/3)",
    ("open_moving", "title"): "Распаковка (2/3)",
    ("open_moving", "msg"): "Дождитесь завершения инициализации платформы и сопла.",
    ("open_pop", "msg"): "Пропустить руководство по настройке?",
    ("open_video_1", "title"): "Распаковка (2/3)",
    ("open_video_1", "msg"): "Снимите все кабельные стяжки.",
    ("open_video_2", "title"): "Распаковка (2/3)",
    ("open_video_2", "msg"): "Выкрутите четыре винта, фиксирующих нагревательный стол.",
    ("open_warning", "title"): "Распаковка (2/3)",
    ("open_warning", "msg"): "Сейчас платформа начнёт движение. Убедитесь, что она разблокирована и на ней нет "
                             "посторонних предметов.",
    ("pre_bed_cal", "title"): "Регулировка опорной точки платформы.",
    ("pre_bed_cal", "msg"): "Выберите число и регулируйте кнопками со стрелками вверх и вниз, пока калибровочный щуп не начнёт "
                            "двигаться между соплом и платформой с лёгким трением.",
    ("pre_heat", "msg"): "Выберите температуру сопла.",
    ("preview", "level_lbl"): "Выравнивание стола",
    ("preview", "timelapse_lbl"): "Таймлапс",
    ("preview_pop_1", "msg"): "Печать PLA или PETG в закрытой камере может привести к перегреву: филамент размягчается "
                              "слишком рано и может заклинить хотэнд. Откройте верхнюю крышку и обеспечьте вентиляцию.",
    ("preview_pop_1", "no_more"): "Больше не показывать",
    ("preview_pop_2", "msg"): "Убедитесь, что верхняя крышка и передняя дверца закрыты. Температура камеры не должна "
                              "превышать 55℃.",
    ("preview_pop_2", "no_more"): "Больше не показывать",
    ("print_filament", "title"): "Загрузка филамента",
    ("print_filament", "replace_btn"): "Заменить филамент",
    ("print_finish", "msg"): "Печать завершена! Затраченное время:",
    ("print_log_f", "msg"): "Не удалось экспортировать журналы. Убедитесь, что USB-накопитель вставлен.",
    ("print_log_s", "msg"): "Журналы успешно экспортированы.",
    ("print_lowtemp", "msg"): NOZZLE_LOW_RU,
    ("print_no_fil", "msg"): "Филамент закончился. Загрузите филамент заново.",
    ("print_no_fil2", "msg"): "Обнаружено запутывание филамента. Загрузите филамент заново.",
    ("print_stop", "msg"): "Остановить печать?",
    ("print_stopping", "msg"): "Принтер останавливается, подождите...",
    ("re_printing", "msg"): "Возобновление печати...",
    ("reset", "export_logs"): "Экспорт журналов",
    ("reset", "title"): "Статус Klipper",
    ("restore_config", "msg"): "Восстановить заводские настройки?",
    ("resume_print", "msg"): "Прошлая печать была прервана. Продолжить печать?",
    ("sleep_mode", "opt_5min_lbl"): "5 минут",
    ("sleep_mode", "opt_15min_lbl"): "15 минут",
    ("sleep_mode", "opt_30min_lbl"): "30 минут",
    ("sleep_mode", "opt_never_lbl"): "Никогда",
    ("sleep_mode", "title"): "Экран",
    ("stop_confirm", "msg"): "Выполнить аварийную остановку?",
    ("syntony_finish", "msg"): "Input Shaping завершён.",
    ("syntony_move", "msg"): "Выполняется Input Shaping, подождите...",
    ("sys_ok", "msg"): "Klipper готов к работе.",
    ("sys_ok", "export_logs"): "Экспорт журналов",
    ("sys_ok", "title"): "Статус Klipper",
    ("unload_finish", "msg"): "Выгрузка филамента завершена.",
    ("unload_mode", "msg"): "Выберите способ выгрузки.",
    ("unload_mode", "hint"): "Рекомендуется.",
    ("unload_mode", "warn"): "Внимание: при автоматической выгрузке филамент может застрять и заблокировать экструдер.",
    ("unload_mode", "manual_btn"): "Выгрузка вручную",
    ("unload_mode", "auto_btn"): "Автоматическая выгрузка",
    ("update_success", "msg"): "Обновление завершено.",
    ("wifi_connect", "msg"): "Подключение к Wi-Fi...",
    ("wifi_fail", "msg"): "Не удалось подключиться.",
    ("wifi_kb", "title"): "Введите пароль",
    ("wifi_success", "msg"): "Подключение выполнено.",
}

# Japanese has no spaces to break at, Arabic and Hebrew run right to left: the screen wraps these itself
NO_WRAP = (3, 10, 12)

# shorter texts where a translation does not fit its component: (page, component, English text, screen language) -> text
SHORT = {}


def _short(page, comps, english, texts):
    """SHORT[...] for several components at once: texts = {language: text}."""
    for comp in comps:
        for lang, text in texts.items():
            SHORT[(page, comp, english, lang)] = text


_short("filament_kb", ("title",), "Chamber Temp", {9: "Temp. câmara"})
_short("filament_pop_3", ("alt_btn",), "Retry", {9: "Repetir"})
_short("internet", ("msg",), "No network detected.", {3: "ネットワーク未検出。"})
_short("server_set", ("title",), "Connection Settings", {5: "Verbindung"})
_short("update_mode", ("msg_failed",), "Failed to get the online version information.",
       {5: "Online-Version konnte nicht abgerufen werden."})
_short("unload_mode", ("auto_btn",), "Automatic Unload", {9: "Descarga automática"})
_short("unload_mode", ("manual_btn",), "Manual Unload", {9: "Descarga manual"})
_short("reset_account", ("pass2_lbl",), "Confirm Password:", {4: "Confirmation :"})
_short("auto_unload", ("step2_txt",), "Unloading filament.", {4: "Déchargement.", 5: "Entladen.", 6: "Scaricamento.",
                                                                7: "Descargando.", 8: "언로드 중입니다.", 9: "Descarregando."})
_short("common_set", ("reset_lbl",), "Restore Factory Settings", {6: "Ripristino di fabbrica", 9: "Restaurar de fábrica"})
_short("filamentVideo2", ("msg_heat",), "Tap the “-” or “+” button above to start heating and set the nozzle temperature.",
       {5: "Tippen Sie oben auf „-“ oder „+“, um zu heizen und die Temperatur einzustellen."})
_short("filament_pop_2", ("hint",), "Please cut the filament, then tap “Next”.", {5: "Filament abschneiden, dann „Weiter“ tippen."})
_short("filament_pop_3", ("hint",), "Please load the filament, then tap “Next”.", {5: "Filament laden, dann „Weiter“ tippen."})
_short("filelist", ("local_tab",), "Local Files", {4: "Locaux", 5: "Lokal", 7: "Locales", 9: "Locais", 10: "المحلية"})
for _lang, _text in {4: "Ventilateur auxiliaire", 6: "Ventola ausiliaria"}.items():
    _short("keybdB", ("title",), "Auxiliary Cooling Fan", {_lang: _text})
for _lang, _text in {4: "Ventilateur de la chambre", 7: "Ventilador de la cámara"}.items():
    _short("keybdB", ("title",), "Chamber Circulation Fan", {_lang: _text})
_short("online_update", ("msg",), "Online update file found. Update now?", {
    4: "Mise à jour en ligne trouvée. Installer ?", 5: "Online-Update gefunden. Jetzt starten?",
    6: "Aggiornamento online trovato. Aggiornare?", 7: "Actualización en línea encontrada. ¿Actualizar?",
    8: "온라인 업데이트를 찾았습니다. 업데이트할까요?", 9: "Atualização online encontrada. Atualizar?",
    11: "Çevrimiçi güncelleme bulundu. Güncellensin mi?"})
_short("pre_bed_cal", ("title",), "Adjusting the platform reference point.", {6: "Regolazione punto di riferimento.",
                                                                              7: "Ajuste del punto de referencia."})
for _page in ("preview_pop_1", "preview_pop_2"):
    _short(_page, ("no_more",), "Don't Show Again", {6: "Non ripetere", 9: "Não repetir"})

TXT_LINE = re.compile(r'^(\s*)([\w.]+)\.txt="(.*)"(\s*//.*)?$')
WIFI = re.compile(r"(?<![A-Za-z_])[Ww]i-?[Ff]i(?![a-z_])")
_fonts = {}


def width_of(font_key, text):
    """Pixel width of a line in the screen font (the width field of every glyph in the .zi)."""
    import hmi_font
    if font_key not in _fonts:
        data = open(os.path.join(ROOT, "fonts", font_key + ".zi"), "rb").read()
        _fonts[font_key] = (data, hmi_font._header_from_bytes(data), hmi_font)
    data, header, mod = _fonts[font_key]
    total = 0
    for ch in text:
        entry = mod._entry_info(data, header, ord(ch))
        total += entry["width"] if entry else 10
    return total


def wrap(text, font_key, limit):
    """Greedy word wrap into lines no wider than ``limit`` pixels."""
    lines, cur = [], ""
    for word in text.split(" "):
        trial = word if not cur else cur + " " + word
        if cur and width_of(font_key, trial) > limit:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def layout(text, comp, wrap_lines=True):
    """``text`` broken into lines for the component (a list); one line for a component that cannot wrap."""
    a = comp["attributes"]
    font = a["font"]["$ref"].split(":", 1)[1] if isinstance(a.get("font"), dict) else "font_title18"
    if not a.get("isbr") or not wrap_lines:
        return [text], font
    return wrap(text, font, a["w"] - 12), font


def fit_problems(page, comp, lines, font, lang=2):
    a = comp["attributes"]
    out = []
    widest = max(width_of(font, l) for l in lines)
    if widest > a["w"] - 2:
        out.append("%s.%s[%s]: line %r is %d px, the component is %d px wide" % (page, comp["key"], lang, max(lines, key=len), widest, a["w"]))
    if len(lines) > 1 and len(lines) * 19 > a["h"]:
        out.append("%s.%s[%s]: %d lines do not fit the height %d: %s" % (page, comp["key"], lang, len(lines), a["h"], " / ".join(lines)))
    return out


def process(page, data):
    """Applies the tables to a loaded page (English: editor text and ``lang==2``; Russian: ``lang==1``)."""
    problems = []
    comps = {o["key"]: o for o in data["objects"]}
    english = {}                                 # component -> list of texts
    for (p, name), value in COPY.items():
        if p == page:
            english[name] = value if isinstance(value, list) else [value]
    for (p, name), word in BUTTON_COPY.items():
        if p == page and name not in english:
            english[name] = [word]
    tables = {2: english}
    russian = {}
    for (p, name), value in COPY_RU.items():
        if p == page:
            russian[name] = value if isinstance(value, list) else [value]
    for name, values in english.items():
        if name not in comps:
            problems.append("%s: no component %s" % (page, name))
        elif name not in russian and values[0] in RU_WORDS and len(values) == 1:
            russian[name] = [RU_WORDS[values[0]]]
    tables[1] = russian
    for i, lang_name in enumerate(translations.LANGS):      # ja ... he: translations of the English copy
        tables[translations.FIRST + i] = {
            name: [SHORT.get((page, name, v, translations.FIRST + i), translations.TRANS[v][i]) for v in values]
            for name, values in english.items()}
    for name, values in english.items():         # editor text
        if name in comps:
            lines, font = layout(values[0], comps[name])
            comps[name]["attributes"]["txt"] = "\r\n".join(lines)
            problems += fit_problems(page, comps[name], lines, font, 2)
    # the lang==2 / lang==1 branch of every event that sets a text (codesload, and a few components set their own text)
    lists = [(data["root"]["events"], "codesload")] + [(o["events"], ev) for o in data["objects"] for ev in o["events"]]
    for events, ev in lists:
        cur, out, used = None, [], {}
        for line in events.get(ev, []):
            s = line.strip()
            m = re.match(r"(?:\}\s*)?(?:else\s+)?if\(\s*lang\s*==\s*(\d+)\s*\)", s)
            if m:
                cur = int(m.group(1))
            elif s == "}else":
                cur = "else"
            m = TXT_LINE.match(line)
            table = tables.get(cur)
            if m and table is not None and m.group(2) in table and m.group(2) in comps:
                name = m.group(2)
                i = used.get((cur, name), 0)
                used[(cur, name)] = i + 1
                values = table[name]
                if i >= len(values):
                    problems.append("%s.%s: %d lines of lang==%s, %d texts in the table" % (page, name, i + 1, cur, len(values)))
                    out.append(line)
                    continue
                lines, font = layout(values[i], comps[name], cur not in NO_WRAP)
                if (i or cur != 2) and (cur not in NO_WRAP or not comps[name]["attributes"].get("isbr")):
                    problems += fit_problems(page, comps[name], lines, font, cur)
                out.append('%s%s.txt="%s"%s' % (m.group(1), name, "\\r".join(lines), m.group(4) or ""))
                continue
            out.append(line)
        events[ev] = out
        for (lang, name), n in used.items():
            want = len(tables[lang][name])
            if n != want:
                problems.append("%s.%s: %d lines of lang==%s, %d texts in the table" % (page, name, n, lang, want))
    return problems


def wifi(data):
    """Wi-Fi in every language, in editor texts and codesload."""
    for o in data["objects"]:
        t = o["attributes"].get("txt")
        if t:
            o["attributes"]["txt"] = WIFI.sub("Wi-Fi", t)
    events = data["root"]["events"]
    for name, lines in events.items():
        events[name] = [TXT_LINE.sub(lambda m: m.group(0), l) if not TXT_LINE.match(l) else
                        re.sub(r'(\.txt=")(.*)(")', lambda m: m.group(1) + WIFI.sub("Wi-Fi", m.group(2)) + m.group(3), l)
                        for l in lines]


def main():
    check = "--check" in sys.argv
    project = json.load(open(os.path.join(ROOT, "project.json")))
    problems, changed = [], 0
    for p in project["pages"]:
        path = os.path.join(ROOT, p["content"]["path"])
        data = json.load(open(path, encoding="utf-8"))
        before = json.dumps(data, sort_keys=True)
        problems += process(p["key"], data)
        wifi(data)
        if json.dumps(data, sort_keys=True) != before:
            changed += 1
            if not check:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.write("\n")
    print("\n".join(problems))
    print("%d pages %s, %d problems" % (changed, "would change" if check else "written", len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
