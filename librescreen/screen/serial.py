"""Configuration of the screen's serial port."""

import termios


# Values of the termios constants on Linux (same on x86 and aarch64)
_CREAD = termios.CREAD
_CSIZE = termios.CSIZE
_CS7 = termios.CS7
_CS8 = termios.CS8
_PARENB = termios.PARENB
_PARODD = termios.PARODD
_INPCK = termios.INPCK
_CSTOPB = termios.CSTOPB
_VTIME = termios.VTIME
_VMIN = termios.VMIN

_BAUDRATES = {
    1200: termios.B1200,
    1800: termios.B1800,
    2400: termios.B2400,
    4800: termios.B4800,
    9600: termios.B9600,
    19200: termios.B19200,
    38400: termios.B38400,
    57600: termios.B57600,
    115200: termios.B115200,
    230400: termios.B230400,
    460800: termios.B460800,
    500000: termios.B500000,
    921600: termios.B921600,
}


def cfmakeraw_zeroed():
    """memset(&newtio, 0, sizeof newtio); cfmakeraw(&newtio);"""
    iflag = 0
    oflag = 0
    lflag = 0
    cflag = _CS8
    cc = [0] * 32
    cc[_VMIN] = 1
    cc[_VTIME] = 0
    return iflag, oflag, cflag, lflag, cc


def set_option(fd, baudrate, bits, parity, stopbit):
    if isinstance(parity, str):
        parity = ord(parity)
    try:
        termios.tcgetattr(fd)
    except (termios.error, OSError, ValueError):
        # error while reading the serial port parameters
        return -1

    iflag, oflag, cflag, lflag, cc = cfmakeraw_zeroed()      # raw mode

    # enable the receiver
    cflag |= _CREAD

    # clear the data bits
    cflag &= ~_CSIZE

    if bits == 7:
        cflag |= _CS7
    elif bits == 8:
        cflag |= _CS8
    else:
        cflag |= _CS8

    if parity in (ord('O'), ord('o')):
        cflag |= (_PARENB | _PARODD)
        cflag |= _INPCK                    # (sic) INPCK is an input flag, kept as in the original
    elif parity in (ord('E'), ord('e')):
        cflag |= _PARENB
        cflag &= ~_PARODD
        iflag |= _INPCK
    else:
        cflag &= ~_PARENB
        iflag &= ~_INPCK

    # baud rate
    speed = _BAUDRATES.get(baudrate, termios.B115200)
    if baudrate == 9600:
        print("Baud rate is 9600")
    elif baudrate == 921600:
        print("Baud rate is 921600")

    # stop bits
    if stopbit == 2:
        cflag |= _CSTOPB
    else:
        cflag &= ~_CSTOPB

    # MIN and TIME set to 0
    cc[_VTIME] = 0
    cc[_VMIN] = 0

    # flush the buffers
    try:
        termios.tcflush(fd, termios.TCIOFLUSH)
    except (termios.error, OSError):
        return -1

    # apply the configuration
    try:
        termios.tcsetattr(fd, termios.TCSANOW, [iflag, oflag, cflag, lflag, speed, speed, cc])
    except (termios.error, OSError):
        return -1

    return 0
