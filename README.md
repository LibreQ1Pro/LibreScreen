# xindi – screen backend for the QIDI Q1 Pro on Klipper and Moonraker

xindi drives the TJC (USART HMI) touch screen of the QIDI Q1 Pro (272 × 480) from any Klipper + Moonraker installation:
Armbian and KIAUH, no QIDI system image needed. It shows the printer (temperatures, the file list with thumbnails, printing,
filament, movement, levelling, Wi-Fi and LAN) and takes the touches. LAN only: no cloud, no accounts.

The repository has two parts:

* **the host program** (`xindi/`, Python, no packages except Pillow): the serial port of the screen, Moonraker's websocket and
  HTTP API, NetworkManager (`nmcli`);
* **the screen firmware** (`display_firmware/`): the project of the screen with a new design (mockup in HTML, 13 languages), made by
  generators and built into a `.HMI` file; the `.tft` is made from it in the USART HMI editor (see `RELEASING.md`).

Status: 0.1.0. See `CHANGELOG.md`; what is not yet checked on a real screen is listed there too.

## Origin

xindi began as a line-by-line Python port of QIDI's C++ screen backend,
[QIDI_Q1_Pro](https://github.com/QIDITECH/QIDI_Q1_Pro) at commit
[`8aaa970c1a7175d0ffc0ca5a29cac92617d5733c`](https://github.com/QIDITECH/QIDI_Q1_Pro/tree/8aaa970c1a7175d0ffc0ca5a29cac92617d5733c)
(the later commits of that repository removed the source code), brought to the behaviour of QIDI's screen firmware **V4.4.24**
(QIDI's xindi 4.4.22 binary has no sources; it was decompiled, and the functions changed in it are marked "4.4.22" in the code).
It has been refactored since: the code is organised by what it does (see Structure) and the screen has a new design.
The result is a separate project and keeps no compatibility with QIDI's system image, files or names.

Not part of xindi: QIDI Link (accounts, QR code login, device binding, the frpc tunnel), updates from a USB drive or online,
the factory mode, QIDI's recovery files. The pages for them are removed from the screen firmware, so its page numbers differ from QIDI's.
What the screen is sent is checked by the golden traces of `tests/e2e`.

## Installation (Armbian, KIAUH)

Requirements: Python ≥ 3.9 and Pillow ≥ 9.1 (`requirements.txt`; tested with Python 3.11 and Pillow 9.4 on Armbian bookworm)
and NetworkManager (`nmcli`, for Wi-Fi and LAN). Nothing else; the websocket and HTTP
clients are built in. The screen is on a serial port (`/dev/ttyS1` by default); the user that runs xindi needs the group
`dialout` (or whatever owns the port) and the right to change connections with `nmcli` (NetworkManager's polkit rules).

```sh
sudo mkdir -p /opt/xindi && sudo cp -r main.py xindi /opt/xindi/
sudo install -D -m 644 contrib/xindi.ini.example /etc/xindi/xindi.ini     # optional, every key has a default
sudo install -m 644 contrib/systemd/xindi.service /etc/systemd/system/    # edit User= first
sudo systemctl daemon-reload && sudo systemctl enable --now xindi
```

Run by hand: `python3 main.py [--config FILE] [moonraker_host]` (or `python3 -m xindi`).

**Configuration.** An ini file, looked up in `--config`, `$XINDI_CONFIG`, `~/.config/xindi/xindi.ini`, `/etc/xindi/xindi.ini`
(`contrib/xindi.ini.example` lists all keys; the defaults suit a usual KIAUH installation). It sets the serial port and
speeds, Moonraker's address, the data directory (`settings.ini`, the settings the screen saves; default
`~/.local/share/xindi`) and, when Moonraker's own answer is not wanted, the gcode, config and log directories.

**Screen firmware.** `.tft` files are built in `display_firmware/`. With the service stopped:
`python3 main.py --flash-screen out/firmware.tft`.
The command waits for an acknowledgement of every block, including the last. UART writes (including `tcdrain`) and
acknowledgement waits have 10-second deadlines (with wire time added for data blocks). The previous sender's baud-switch
sequence, 2048-byte drains and transfer pauses are retained. Exit status (also for `python3 -m xindi`):
`0` — the entire download was acknowledged, `1` — UART / transfer failure, `2` — invalid file or baud rate, `130` — interrupted.
Acknowledgements do not verify firmware integrity or a successful reboot: wait for the normal screen UI before starting
the service. A reply to `sendme` alone is not a successful boot check.

**USB drive.** xindi expects the drive mounted in the gcode directory as `sda1`; `contrib/usb-automount` has the udev rule,
systemd unit and mount script (see its README). Without it the USB tab of the file list stays empty.

**Settings reset** (Settings → Reset) clears the print history of Moonraker, writes the default `settings.ini` (the setup
guide stays off; Settings has a switch to run it again) and sets the z offset to 0.

## Helper binaries that are now built in

| Original | Replacement | Notes |
|---|---|---|
| `/root/uart` (aarch64 ELF, built from `uart.cpp`) | `xindi/screen/flash.py` | The protocol was reverse engineered from the disassembly and checked against a development copy of `uart.cpp`. Sends `whmi-wri <size>,<transfer_baud>,0`, then blocks of up to 4096 bytes in writes of up to 2048 bytes, with bounded I/O and an ACK for every block, including the last. `main.py --flash-screen FILE` reports transfer errors through its exit status. |
| `/home/mks/gene4.py` | `xindi/screen/colpic.py` | The same Pillow code (resize, `ImageOps.pad`, RGB565). It is called directly instead of through `python3 …`, and the result stays in memory instead of `/home/mks/tjc`. |
| `/home/mks/libColPic.so` (aarch64) | `xindi/screen/colpic.py` (`col_pic_encode_str` …) | Reverse engineered (`ad_list0`, `byte8bit_encode`, `col_pic_encode`, `col_pic_encode_str`). Output is byte-identical to the original library, including its quirks. |
| wpa_supplicant control socket (`mks_wpa_cli.cpp`, libwpa_client) | `xindi/system/network.py` | Not ported: Wi-Fi scan / connect / status and the addresses of the Wi-Fi and LAN interfaces go through NetworkManager (`nmcli`), so the screen, KlipperScreen and `nmcli` share one state. The interfaces are looked up, not assumed to be `wlan0` / `eth0`. The status keeps the wpa_supplicant words the screen code uses (`wpa_state` is `COMPLETED` when connected). |
| websocketpp | `xindi/moonraker/ws_client.py` | Minimal RFC 6455 client with the same connection-state semantics. |
| HTTPRequest.hpp | `xindi/moonraker/http_client.py` | Includes the library's quirk of returning an empty body when the first `recv()` does not contain the whole header. |

The shell commands of the original (`cp`, `mv`, `mkdir`, `curl`, `sync`, `systemctl` for the USB drive) are replaced by Python
(`shutil`, `os`, `urllib`); the port starts no shell command of its own, only `nmcli`.

## Structure

```
xindi/
  main.py            start-up sequence and the main loop
  state.py           the shared state, one object per area (g.screen, g.klippy, g.files, ...)
  screen/            the TJC screen: tx.py (instructions, g.port), rx.py (frames), serial.py, events.py (touches,
                     values, keyboard), navigation.py (page_to), pageids.py, faces.py (looks of the widgets), transfer.py (pictures),
                     colpic.py, thumbnail.py, flash.py (firmware download)
  moonraker/         ws_client.py, http_client.py, rpc_requests.py (JSON-RPC builders), rpc_messages.py (dispatch of
                     what Moonraker sends), printer_status.py, gcode_responses.py, gcode_files.py, gcodes.py
  printer/           what the user can ask: heating.py, motion.py, job.py, calibration.py, klipper.py
  pages/             what every page shows: refresh.py (the page that is open), home.py, printing.py, preview.py,
                     move.py, filament.py, leveling.py, guide.py, system.py, file_list.py, wifi.py, connections.py
  clicks/            what a touch does: a table of handlers per page
  config/            inifile.py (settings.ini), settings.py
  system/            network.py (NetworkManager)
  util/              cpp.py (C/C++ semantics), paths.py, netstrings.py
```

* `xindi/state.py` holds the shared state, one object per area: `g.screen` (what the screen
  shows, page flags), `g.klippy` (the printer as Klipper reports it), `g.shown` (values last sent
  to the screen), `g.levelling`, `g.files`, `g.net`, `g.config`, `g.update`, `g.pictures` and
  `g.rpc` (the Moonraker queue). The two connections are `g.port` (the screen's serial port:
  `g.port.page(...)`, `g.port.txt(...)`, …) and `g.ep` (Moonraker).
* `xindi/util/cpp.py` reproduces the C/C++ semantics the code depends on:
  * 32-bit `float` rounding (`f32`) and `std::to_string`
  * `std::string::substr` / `npos` arithmetic and integer division / `%` truncating toward zero
  * C `round()`, `strtol` / `atof` / `std::stof` / stream parsing
  * nlohmann::json style access and type errors (`jget`, `jstr`, `jint`, …)
  * `pthread_create` that aborts the process on an uncaught exception, like `std::terminate`
* The page ids are in `xindi/screen/pageids.py`. Fall-through `switch` cases (missing `break`) of the C++ code are
  reproduced and marked with a `NOTE`.

## Deliberate deviations

The port follows the original including its bugs. It only differs where the C++
code has undefined behaviour that cannot be reproduced in a meaningful way:

* `page_wifi_list_ssid_button_enabled` is `bool[3]` in C++ but indexed 0..4. The
  port uses five entries.
* `std::stack::top()` on an empty stack and iterating past `std::set::end()` in
  the file list are guarded and yield an empty string / no entry.
* `send_cmd_click()` writes `sizeof(std::string)` bytes of object memory in C++.
  It is unused; the port writes the command padded to 32 bytes.
* `mks_set_psk()` uses `sprintf` into a 64 byte buffer. The port does not
  reproduce the overflow for long passwords. SSIDs are truncated at 62 bytes
  like the `snprintf` in `mks_set_ssid()`.
* The uninitialised default of `recevice_progress_handle()` is 0 / "".
* The busy loop of `recevice_progress_handle()` yields the GIL (`time.sleep(0)`)
  so that the other threads keep running.
* Converted thumbnails are kept in memory (`g.tjc_data`) instead of being
  written to `/home/mks/tjc` and read back. A failed conversion leaves no
  picture; the original keeps the unchanged file and shows the picture of the
  previous file.
* Thumbnails are read from the gcode files themselves (`xindi/screen/thumbnail.py`):
  the start of the file is downloaded from Moonraker
  (`/server/files/gcodes/<path>` with a Range header) and the embedded
  `; thumbnail[_JPG|_QOI] begin WxH` blocks are decoded in memory. The original
  only works with QIDI's own slicer and Moonraker: it reads
  `/home/mks/gcode_files/<dir>/.thumbs/<name>-160x160.png` for the preview and
  sends `<name>-112x112_QD.jpg` to the screen for the file list. The port picks
  the best embedded size instead, and makes a 112×112 baseline JPEG for the list. The screen
  is mounted rotated, so the pictures are turned 90° counterclockwise first
  (QIDI's `.thumbs` pictures are stored turned already). When a print is started from the web UI the original
  only looks at the `.cache` copy of the file; the port falls back to the file
  itself. Transparent parts of the thumbnails are shown black (gene4.py drops
  the alpha channel and shows the colour the slicer left under it). Only the
  header of the file is read: the search stops at the first gcode command. The
  list JPEG is made before the touch is disabled for the transfer.
* `json_parse()` does not poll `is_get_message` every 50 µs (about 10% CPU in
  Python). The websocket thread puts the messages into a queue and
  `json_parse()` waits for the next one. In the original a message that
  arrives while the previous one is parsed overwrites it or is dropped when the
  flag is reset; the port handles every message.
* The directories of the gcode files, the Klipper configuration and the logs
  are not fixed to QIDI's `/home/mks/gcode_files`, `/home/mks/klipper_config`
  and `/home/mks/klipper_logs` (`xindi/util/paths.py`). They are given in the
  configuration file or asked from Moonraker (`/server/files/roots`); while it
  does not answer, `~/printer_data/{gcodes,config,logs}` are used. USB drives are
  expected at `<gcodes>/sda1` (`contrib/usb-automount`).
* `settings.ini` lives in the data directory of the configuration (not in
  `/root` or the Klipper configuration), and is created with the defaults of
  the program when it does not exist.
* `sent_jpg_to_tjc()` closes the file when the screen reports a full buffer
  (0x24); the original leaks it.
* For tiny thumbnails `libColPic.so` writes past the end of its output buffer.
  The port uses a larger scratch buffer and produces the same file content.

## Tests

`tests/unit/` has the tests of the pure logic (no printer, no network): `PYTHONPATH=. python3 -I -m unittest discover -s tests/unit -t .`
(the splitting of the screen's byte stream into frames, `xindi/screen/rx.py`).

`tests/e2e/` runs the port in a simulated printer in docker and compares everything it does with golden traces,
to check refactorings (`tests/e2e/golden.py check`). See `tests/e2e/README.md`.

## License

Copyright (C) 2024 QIDI Technology — original C++ program
([QIDI_Q1_Pro](https://github.com/QIDITECH/QIDI_Q1_Pro/tree/8aaa970c1a7175d0ffc0ca5a29cac92617d5733c);
`MoonrakerAPI` by Kenneth Lin, 2022).

The original program is licensed under the GNU Affero General Public License
v3.0, so this port, as a derived work, is distributed under the same license.
See [LICENSE](LICENSE).

Ported third-party code keeps its own copyright and license:

* `xindi/moonraker/http_client.py`: port of HTTPRequest by Elviss Strazdins, public domain (Unlicense).
