#!/usr/bin/env python3
"""Virtual SW_LID switch: lets us test lid-close behaviour without touching the real lid.

Creates a uinput device that reports EV_SW/SW_LID, emits closed, waits, emits open.
Prints the logind LidClosed property so the caller can confirm the event was seen.
"""
import ctypes, fcntl, os, struct, subprocess, sys, time

UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
UI_SET_EVBIT = 0x40045564
UI_SET_SWBIT = 0x4004556D
EV_SYN, EV_SW, SYN_REPORT = 0x00, 0x05, 0x00
SW_LID = 0x00


class UinputUserDev(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * 80),
        ("input_id", ctypes.c_uint16 * 4),  # bustype, vendor, product, version
        ("ff_effects_max", ctypes.c_uint32),
        ("absmax", ctypes.c_int32 * 64),
        ("absmin", ctypes.c_int32 * 64),
        ("absfuzz", ctypes.c_int32 * 64),
        ("absflat", ctypes.c_int32 * 64),
    ]


def lid_closed():
    out = subprocess.run(
        ["busctl", "get-property", "org.freedesktop.login1", "/org/freedesktop/login1",
         "org.freedesktop.login1.Manager", "LidClosed"],
        capture_output=True, text=True).stdout.strip()
    return out


def main():
    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_SW)
    fcntl.ioctl(fd, UI_SET_SWBIT, SW_LID)
    dev = UinputUserDev()
    dev.name = b"pi-lid-probe"
    dev.input_id[0] = 0x19  # BUS_HOST
    dev.input_id[1] = 0x1
    dev.input_id[2] = 0x1
    dev.input_id[3] = 0x1
    os.write(fd, bytes(dev))
    fcntl.ioctl(fd, UI_DEV_CREATE)
    time.sleep(2.5)  # let udev+logind pick the device up
    print("LidClosed before:", lid_closed(), flush=True)

    def emit(value):
        ev = struct.pack("qqHHi", 0, 0, EV_SW, SW_LID, value)
        os.write(fd, ev)
        os.write(fd, struct.pack("qqHHi", 0, 0, EV_SYN, SYN_REPORT, 0))
        time.sleep(0.2)

    emit(1)
    for i in range(12):
        time.sleep(1)
        print(f"t+{i+1}s LidClosed:", lid_closed(), flush=True)
    emit(0)
    time.sleep(1)
    print("LidClosed after reopen:", lid_closed(), flush=True)
    fcntl.ioctl(fd, UI_DEV_DESTROY)
    os.close(fd)


main()
