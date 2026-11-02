# xindi

Screen backend for the QIDI Q1 Pro: drives the printer's TJC touch display
over its serial port from any Klipper + Moonraker installation (Armbian,
KIAUH, …). LAN only.

## Requirements

Python ≥ 3.9, Pillow ≥ 9.1, NetworkManager. The service user needs `dialout`
(the serial port) and `netdev` (nmcli).

## Installation

```sh
sudo mkdir -p /opt/xindi && sudo cp -r main.py xindi /opt/xindi/
sudo -u mks install -D -m 644 contrib/xindi.ini.example ~mks/.config/xindi/xindi.ini  # optional, every key has a default
sudo install -m 644 contrib/systemd/xindi.service /etc/systemd/system/  # edit User= first
sudo install -m 644 contrib/systemd/50-xindi.rules /etc/polkit-1/rules.d/  # edit mks in it to match User=
sudo install -m 755 contrib/usb-automount/xindi-usb-mount /usr/local/sbin/
sudo install -m 644 contrib/usb-automount/xindi-usb-mount@.service /etc/systemd/system/
sudo install -m 644 contrib/usb-automount/99-xindi-usb.rules /etc/udev/rules.d/
sudo install -m 644 contrib/usb-automount/xindi-usb.default /etc/default/xindi-usb  # edit XINDI_USER in it
sudo systemctl daemon-reload && sudo udevadm control --reload && sudo systemctl enable --now xindi
```

Run by hand: `python3 main.py [--config FILE] [moonraker_host]`. A USB drive
is expected mounted at `<gcodes>/sda1`.

## Screen firmware

Built in `display_firmware/` (generators → `.HMI`); the `.tft` is compiled
from the `.HMI` in the USART HMI editor. Host and `.tft` must be the same
version (`VERSION` in `xindi/screen/navigation.py`).

Stop the service, then:

```sh
python3 main.py --flash-screen FILE.tft
```

Exit status: `0` ok, `1` UART/transfer failure, `2` bad file or baud, `130`
interrupted. An interrupted transfer leaves the screen stuck in download mode
until a power cycle (it then shows `Data ERROR`); flash again after that.
`contrib/flash-screen.sh` stops the service, flashes, starts the service.

## Origin

A port of QIDI's C++ backend
([QIDI_Q1_Pro](https://github.com/QIDITECH/QIDI_Q1_Pro) @ `8aaa970c`) to the
behaviour of screen firmware V4.4.24, since refactored into a standalone
project with a new screen design. QIDI cloud, updates and factory mode are
removed, so page numbers differ from QIDI's. Golden traces in `tests/e2e`
check everything the host sends to the screen.

## Tests

```sh
python3 tests/run_unit.py           # pure logic
python3 tests/e2e/golden.py check   # simulated printer in docker, golden traces
```

## License

AGPLv3, like the original QIDI program. See [LICENSE](LICENSE).
