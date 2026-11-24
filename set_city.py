#!/usr/bin/env python3
# G-Shock Grid — Casio GBD-200 BLE console. Copyright (c) 2026 KUYDIGITAL.
# MIT License (see LICENSE). https://github.com/kuydigital/gbd200-grid
"""
Read-modify-write-verify the GBD-200 world-time city (feature 0x1f).

  python set_city.py --address <uuid> --city TOKYO     # change it
  python set_city.py --address <uuid> --restore        # write back saved original

Saves the original frame to orig_city.bin before the first change so it is
always reversible.
"""
from __future__ import annotations

import argparse
import asyncio
import os

from bleak import BleakClient

REQ = "26eb002c-b012-49a8-b1f8-394fb2032b0f"
ALL = "26eb002d-b012-49a8-b1f8-394fb2032b0f"
FEATURE_WORLD_CITY = 0x1f
ORIG_PATH = os.path.join(os.path.dirname(__file__), "orig_city.bin")


def fmt(data: bytes) -> str:
    a = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
    return f"{data.hex(' ')}   |{a}|"


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
        # settings are written to the ALL-FEATURES characteristic (26eb002d)
        await self.client.write_gatt_char(ALL, frame, response=True)


def build_city_frame(original: bytes, city: str) -> bytes:
    name = city.upper().encode("ascii")
    max_name = len(original) - 2  # [code][index] then name, padded
    if len(name) > max_name:
        raise SystemExit(f"City too long: max {max_name} chars for this frame.")
    frame = bytes([original[0], original[1]]) + name
    frame += bytes(len(original) - len(frame))  # pad with 0x00 to original length
    return frame


async def run(address, city, restore):
    async with BleakClient(address, timeout=20.0) as client:
        print("Connected.\n")
        casio = Casio(client)
        await casio.start()

        current = await casio.read_feature(FEATURE_WORLD_CITY)
        print(f"Current world-city frame:\n    {fmt(current)}\n")

        if restore:
            if not os.path.exists(ORIG_PATH):
                raise SystemExit("No orig_city.bin saved; nothing to restore.")
            with open(ORIG_PATH, "rb") as f:
                new = f.read()
            print(f"Restoring original:\n    {fmt(new)}\n")
        else:
            if not os.path.exists(ORIG_PATH):
                with open(ORIG_PATH, "wb") as f:
                    f.write(current)
                print(f"Saved original to {ORIG_PATH}")
            new = build_city_frame(current, city)
            print(f"Writing new frame ({city.upper()}):\n    {fmt(new)}\n")

        await casio.write_feature(new)
        await asyncio.sleep(0.4)

        after = await casio.read_feature(FEATURE_WORLD_CITY)
        print(f"Read-back after write:\n    {fmt(after)}\n")
        if after == new:
            print("✅ Change confirmed on the watch.")
        elif after == current:
            print("⚠️  No change took effect (watch rejected or ignored the write).")
        else:
            print("ℹ️  Frame changed but differs from what we wrote (watch normalized it).")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", required=True)
    ap.add_argument("--city", default="TOKYO")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    await run(args.address, args.city, args.restore)


if __name__ == "__main__":
    asyncio.run(main())
