#!/usr/bin/env python3
"""
Read today's step/calorie totals from a GBD-200 (convoy channel). Read-only.

  python read_activity.py --address <uuid>

Protocol: enable notify on 0x0023 + 0x0024, write `00 11 00 00 00` to 0x0023,
the watch echoes the length on 0x0023 and streams a bitwise-inverted payload on
0x0024 whose header holds today's totals.
"""
from __future__ import annotations
import argparse
import asyncio
from bleak import BleakClient

C23 = "26eb0023-b012-49a8-b1f8-394fb2032b0f"
C24 = "26eb0024-b012-49a8-b1f8-394fb2032b0f"


async def run(address):
    buf = bytearray()
    async with BleakClient(address, timeout=20.0) as client:
        await client.start_notify(C23, lambda _h, _d: None)
        await client.start_notify(C24, lambda _h, d: buf.extend(d))
        await client.write_gatt_char(C23, bytes([0x00, 0x11, 0x00, 0x00, 0x00]), response=True)
        await asyncio.sleep(3.0)
    if len(buf) < 13:
        print("No activity payload received.")
        return
    raw = bytes((~b) & 0xff for b in buf)
    steps = raw[7] | (raw[8] << 8) | (raw[9] << 16) | (raw[10] << 24)
    cals = raw[11] | (raw[12] << 8)
    if steps == 0xfffffffe: steps = 0
    if cals == 0xfffe: cals = 0
    print("date (UTC): %04d-%02d-%02d %02d:%02d" % (2000 + raw[2], raw[3], raw[4], raw[5], raw[6]))
    print("steps:     ", steps)
    print("calories:  ", cals)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", required=True)
    args = ap.parse_args()
    await run(args.address)


if __name__ == "__main__":
    asyncio.run(main())
