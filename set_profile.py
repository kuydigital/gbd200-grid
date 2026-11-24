#!/usr/bin/env python3
# G-Shock Grid — Casio GBD-200 BLE console. Copyright (c) 2026 KUYDIGITAL.
# MIT License (see LICENSE). https://github.com/kuydigital/gbd200-grid
"""
Set GBD-200 profile bits (wrist / gender) in feature 0x45.
Read-modify-write: only byte[1] bits change; all personal bytes are preserved.

  python set_profile.py --address <uuid> --wrist right
  python set_profile.py --address <uuid> --gender female
"""
from __future__ import annotations
import argparse
import asyncio
from bleak import BleakClient

REQ = "26eb002c-b012-49a8-b1f8-394fb2032b0f"
ALL = "26eb002d-b012-49a8-b1f8-394fb2032b0f"


class Dev:
    def __init__(self, c): self.c = c; self.q = asyncio.Queue()
    def _cb(self, _h, d): self.q.put_nowait(bytes(d))
    async def start(self): await self.c.start_notify(ALL, self._cb)
    async def rd(self, req, t=3.0):
        while not self.q.empty(): self.q.get_nowait()
        await self.c.write_gatt_char(REQ, bytes(req), response=False)
        return await asyncio.wait_for(self.q.get(), t)
    async def wr(self, b): await self.c.write_gatt_char(ALL, bytes(b), response=True)


def describe(b1): return ("female" if b1 & 0x01 else "male") + " / " + ("right" if b1 & 0x02 else "left") + " wrist"


async def run(address, wrist, gender):
    async with BleakClient(address, timeout=20.0) as client:
        d = Dev(client); await d.start()
        cur = bytearray(await d.rd([0x45]))
        print("current:", describe(cur[1]))
        if wrist == "right": cur[1] |= 0x02
        elif wrist == "left": cur[1] &= ~0x02
        if gender == "female": cur[1] |= 0x01
        elif gender == "male": cur[1] &= ~0x01
        await d.wr(bytes(cur)); await asyncio.sleep(0.3)
        back = await d.rd([0x45])
        print("now:    ", describe(back[1]), "(OK)" if back[1] == cur[1] else "(no change)")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", required=True)
    ap.add_argument("--wrist", choices=["left", "right"])
    ap.add_argument("--gender", choices=["male", "female"])
    args = ap.parse_args()
    if not args.wrist and not args.gender:
        raise SystemExit("Nothing to set: pass --wrist and/or --gender.")
    await run(args.address, args.wrist, args.gender)


if __name__ == "__main__":
    asyncio.run(main())
