#!/usr/bin/env python3
# G-Shock Grid — Casio GBD-200 BLE console. Copyright (c) 2026 KUYDIGITAL.
# MIT License (see LICENSE). https://github.com/kuydigital/gbd200-grid
"""
Read-modify-write-verify GBD-200 alarms.

  # alarm 1 lives in feature 0x15 (single slot)
  # alarms 2-5 live in feature 0x16 (one frame, four 4-byte slots)

  python set_alarm.py --address <uuid> --alarm 2 --hour 6 --minute 45  # set & enable
  python set_alarm.py --address <uuid> --alarm 3 --off                 # disable alarm 3
  python set_alarm.py --address <uuid> --restore                       # revert all we changed

Slot layout (4 bytes):
  [0] 0x40 enabled (0x50 = enabled+snooze), 0x00 disabled
  [1] 0x40 (watch normalizes this to 0x00 on read)
  [2] hour   (plain byte)
  [3] minute (plain byte)
"""
from __future__ import annotations

import argparse
import asyncio
import os

from bleak import BleakClient

REQ = "26eb002c-b012-49a8-b1f8-394fb2032b0f"
ALL = "26eb002d-b012-49a8-b1f8-394fb2032b0f"
FEATURE_ALARM1 = 0x15     # alarm 1
FEATURE_ALARMS = 0x16     # alarms 2-5 (slots 0..3)
HERE = os.path.dirname(__file__)
ORIG_15 = os.path.join(HERE, "orig_alarm15.bin")
ORIG_16 = os.path.join(HERE, "orig_alarm16.bin")


def fmt(d: bytes) -> str:
    a = "".join(chr(b) if 32 <= b < 127 else "." for b in d)
    return f"{d.hex(' ')}   |{a}|"


def describe_slot(en: int, hh: int, mm: int) -> str:
    state = "ON" if (en & 0x40) else "off"
    snooze = " +snooze" if (en & 0x10) else ""
    return f"{hh:02d}:{mm:02d} {state}{snooze}"


def describe(code: int, frame: bytes) -> str:
    if code == FEATURE_ALARM1:
        return "alarm1 = " + describe_slot(frame[1], frame[3], frame[4])
    parts = []
    for i in range(4):
        o = 1 + i * 4
        if o + 3 < len(frame):
            parts.append(f"alarm{i + 2}=" + describe_slot(frame[o], frame[o + 2], frame[o + 3]))
    return "  ".join(parts)


class Casio:
    def __init__(self, client):
        self.client = client
        self.q: asyncio.Queue = asyncio.Queue()

    def _cb(self, _c, data: bytearray):
        self.q.put_nowait(bytes(data))

    async def start(self):
        await self.client.start_notify(ALL, self._cb)

    async def read_feature(self, code: int, timeout=4.0):
        while not self.q.empty():
            self.q.get_nowait()
        await self.client.write_gatt_char(REQ, bytes([code]), response=False)
        return await asyncio.wait_for(self.q.get(), timeout)

    async def write_feature(self, frame: bytes):
        await self.client.write_gatt_char(ALL, frame, response=True)


def save_once(path: str, data: bytes):
    if not os.path.exists(path):
        open(path, "wb").write(data)
        print(f"Saved original to {os.path.basename(path)}")


async def do_restore(c: Casio):
    did = False
    for code, path in ((FEATURE_ALARM1, ORIG_15), (FEATURE_ALARMS, ORIG_16)):
        if os.path.exists(path):
            orig = open(path, "rb").read()
            print(f"Restoring 0x{code:02x}: {fmt(orig)}")
            await c.write_feature(orig)
            did = True
    if not did:
        raise SystemExit("Nothing saved to restore.")
    await asyncio.sleep(0.4)


async def set_alarm1(c: Casio, hour, minute, off):
    cur = await c.read_feature(FEATURE_ALARM1)
    print(f"Current:  {fmt(cur)}  -> {describe(FEATURE_ALARM1, cur)}")
    save_once(ORIG_15, cur)
    en = 0x00 if off else 0x40
    hh = cur[3] if off else hour
    mm = cur[4] if off else minute
    new = bytes([FEATURE_ALARM1, en, 0x40, hh, mm])
    print(f"Writing:  {fmt(new)}  -> {describe(FEATURE_ALARM1, new)}")
    await c.write_feature(new)
    await asyncio.sleep(0.4)
    after = await c.read_feature(FEATURE_ALARM1)
    print(f"Read-back:{fmt(after)}  -> {describe(FEATURE_ALARM1, after)}")


async def set_alarm_n(c: Casio, n, hour, minute, off):
    """n in 2..5 -> slot (n-2) inside the 0x16 frame."""
    cur = await c.read_feature(FEATURE_ALARMS)
    print(f"Current:  {fmt(cur)}\n          -> {describe(FEATURE_ALARMS, cur)}")
    save_once(ORIG_16, cur)
    frame = bytearray(cur)
    o = 1 + (n - 2) * 4
    if o + 3 >= len(frame):
        raise SystemExit(f"Alarm {n} slot not present in this frame.")
    frame[o] = 0x00 if off else 0x40
    frame[o + 1] = 0x40
    if not off:
        frame[o + 2] = hour
        frame[o + 3] = minute
    new = bytes(frame)
    print(f"Writing:  {fmt(new)}\n          -> {describe(FEATURE_ALARMS, new)}")
    await c.write_feature(new)
    await asyncio.sleep(0.4)
    after = await c.read_feature(FEATURE_ALARMS)
    print(f"Read-back:{fmt(after)}\n          -> {describe(FEATURE_ALARMS, after)}")


async def run(address, alarm, hour, minute, off, restore):
    async with BleakClient(address, timeout=20.0) as client:
        print("Connected.\n")
        c = Casio(client)
        await c.start()
        if restore:
            await do_restore(c)
        elif alarm == 1:
            await set_alarm1(c, hour, minute, off)
        else:
            await set_alarm_n(c, alarm, hour, minute, off)
        print("\nDone.")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", required=True)
    ap.add_argument("--alarm", type=int, default=1, choices=[1, 2, 3, 4, 5],
                    help="which alarm (1 uses 0x15; 2-5 use 0x16)")
    ap.add_argument("--hour", type=int, default=7)
    ap.add_argument("--minute", type=int, default=30)
    ap.add_argument("--off", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    await run(args.address, args.alarm, args.hour, args.minute, args.off, args.restore)


if __name__ == "__main__":
    asyncio.run(main())
