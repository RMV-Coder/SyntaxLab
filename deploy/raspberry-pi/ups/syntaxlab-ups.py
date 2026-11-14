#!/usr/bin/env python3
"""Watch a Waveshare UPS HAT (E) and shut the Pi down cleanly before its batteries run out.

Registers (I2C address 0x2D) are from Waveshare's register manual:
https://docs.waveshare.com/UPS-HAT-E-Tutorials-Register. Each value is 16 bits, low byte first.

    0x10  USB-C input voltage (mV)          0x20  battery voltage (mV)
    0x22  battery current (mA, signed: + charging, - discharging)
    0x24  battery remaining (%)             0x28  remaining discharge time (min)
    0x30, 0x32, 0x34, 0x36  cell 1-4 voltage (mV)
    0x01  write 0x55: the HAT cuts the Pi's power about 30 s later, then powers it on again
          when charging power returns (with auto-start, register 0x40 bit 0, on by default)

    syntaxlab-ups.py status    print one reading as JSON
    syntaxlab-ups.py monitor   run as the service does

The shutdown needs every condition at once, on CONFIRMATIONS readings in a row, so one bad read
cannot power the Pi off: no input power, battery discharging, and the battery at or below
SHUTDOWN_PERCENT. Readings that make no physical sense are logged and never acted on.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

ADDRESS = 0x2D
BUS = 1
INPUT_PRESENT_MV = 4500  # USB-C input above this means the charger is connected
POLL_S = int(os.environ.get("UPS_POLL_SECONDS", "10"))
SHUTDOWN_PERCENT = int(os.environ.get("UPS_SHUTDOWN_PERCENT", "10"))
CONFIRMATIONS = int(os.environ.get("UPS_CONFIRMATIONS", "3"))
SUMMARY_EVERY_S = int(os.environ.get("UPS_SUMMARY_SECONDS", "900"))
DRY_RUN = os.environ.get("UPS_DRY_RUN", "0") == "1"


def word(bus, register: int, *, signed: bool = False) -> int:
    value = bus.read_word_data(ADDRESS, register)  # SMBus words are low byte first
    return value - 0x10000 if signed and value >= 0x8000 else value


def read(bus) -> dict[str, object]:
    return {
        "input_mv": word(bus, 0x10),
        "battery_mv": word(bus, 0x20),
        "battery_ma": word(bus, 0x22, signed=True),
        "percent": word(bus, 0x24),
        "minutes_left": word(bus, 0x28),
        "cells_mv": [word(bus, r) for r in (0x30, 0x32, 0x34, 0x36)],
    }


def plausible(r: dict[str, object]) -> bool:
    return (
        0 <= int(r["percent"]) <= 100  # type: ignore[call-overload]
        and 2000 <= int(r["battery_mv"]) <= 20000  # type: ignore[call-overload]
        and 0 <= int(r["input_mv"]) <= 25000  # type: ignore[call-overload]
    )


def should_shut_down(r: dict[str, object]) -> bool:
    return (
        int(r["input_mv"]) < INPUT_PRESENT_MV  # type: ignore[call-overload]
        and int(r["battery_ma"]) < 0  # type: ignore[call-overload]
        and int(r["percent"]) <= SHUTDOWN_PERCENT  # type: ignore[call-overload]
    )


def log(message: str) -> None:
    print(message, flush=True)  # journald keeps it: journalctl -u syntaxlab-ups


def shut_down(bus) -> None:
    log("Battery low and no input power: arming the HAT power cycle and shutting down.")
    if DRY_RUN:
        log("UPS_DRY_RUN=1: not shutting down.")
        return
    # The HAT cuts power about 30 s after this, and restores it when charging power returns.
    bus.write_byte_data(ADDRESS, 0x01, 0x55)
    subprocess.run(["systemctl", "poweroff"], check=False)


def open_bus():
    import smbus  # Debian package python3-smbus

    return smbus.SMBus(BUS)


def monitor() -> int:
    bus = open_bus()
    strikes = 0
    on_battery = None
    last_summary = 0.0
    last_problem = None  # log a problem once, not on every poll (SD card wear)
    log(
        f"Watching the UPS: shutdown at {SHUTDOWN_PERCENT}% on battery, after {CONFIRMATIONS} "
        f"readings {POLL_S} s apart{' (dry run)' if DRY_RUN else ''}."
    )
    while True:
        try:
            r = read(bus)
        except OSError as error:
            problem = f"Cannot read the UPS: {error}"
            if problem != last_problem:
                log(problem + " (logged once until it changes)")
                last_problem = problem
            strikes = 0
            time.sleep(POLL_S)
            continue
        if not plausible(r):
            problem = "implausible readings"
            if problem != last_problem:
                log(f"Ignoring an implausible reading: {json.dumps(r)}")
                last_problem = problem
            strikes = 0
            time.sleep(POLL_S)
            continue
        if last_problem is not None:
            log("UPS readings are back.")
            last_problem = None
        now_on_battery = int(r["input_mv"]) < INPUT_PRESENT_MV  # type: ignore[call-overload]
        if now_on_battery != on_battery:
            state = "ON BATTERY" if now_on_battery else "on input power"
            log(f"{state}: {json.dumps(r)}")
            on_battery = now_on_battery
            last_summary = time.monotonic()
        elif time.monotonic() - last_summary >= SUMMARY_EVERY_S:
            log(json.dumps(r))
            last_summary = time.monotonic()
        strikes = strikes + 1 if should_shut_down(r) else 0
        if strikes >= CONFIRMATIONS:
            shut_down(bus)
            if not DRY_RUN:
                return 0
            strikes = 0
        time.sleep(POLL_S)


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "status"
    if command == "status":
        reading = read(open_bus())
        reading["plausible"] = plausible(reading)
        reading["would_shut_down"] = should_shut_down(reading)
        print(json.dumps(reading, indent=2))
        return 0
    if command == "monitor":
        return monitor()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
