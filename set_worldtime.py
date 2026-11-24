#!/usr/bin/env python3
# G-Shock Grid — Casio GBD-200 BLE console. Copyright (c) 2026 KUYDIGITAL.
# MIT License (see LICENSE). https://github.com/kuydigital/gbd200-grid
"""
Set a GBD-200 world-time city (home slot 0 or world slot 1). Uses the real
multi-frame session reverse-engineered from a capture of the official app.

  python set_worldtime.py --address <uuid> --city TOKYO          # world slot
  python set_worldtime.py --address <uuid> --city LONDON --slot 0  # home slot
  python set_worldtime.py --address <uuid> --list

City timezone bytes are from the Gadgetbridge CasioTimeZone table (plus LAS VEGAS
from a capture). Each entry is (A, B, offset, dstOffset, dstRules); offset/dstOffset
are signed 15-minute units.
"""
from __future__ import annotations
import argparse
import asyncio
from bleak import BleakClient

REQ = "26eb002c-b012-49a8-b1f8-394fb2032b0f"
ALL = "26eb002d-b012-49a8-b1f8-394fb2032b0f"

CITIES = {
    "PAGO PAGO": (0xd7,0x00,0xd4,0x04,0x00), "HONOLULU": (0x7b,0x00,0xd8,0x04,0x00),
    "ANCHORAGE": (0x0c,0x00,0xdc,0x04,0x01), "LAS VEGAS": (0x9c,0x00,0xe0,0x04,0x01),
    "LOS ANGELES": (0xa1,0x00,0xe0,0x04,0x01), "DENVER": (0x54,0x00,0xe4,0x04,0x01),
    "CHICAGO": (0x42,0x00,0xe8,0x04,0x01), "NEW YORK": (0xca,0x00,0xec,0x04,0x01),
    "HALIFAX": (0x71,0x00,0xf0,0x04,0x01), "ST.JOHN'S": (0x0c,0x01,0xf2,0x04,0x01),
    "RIO DE JANEIRO": (0xf1,0x00,0xf4,0x04,0x00), "PRAIA": (0xe9,0x00,0xfc,0x04,0x00),
    "UTC": (0x00,0x00,0x00,0x00,0x00), "LONDON": (0xa0,0x00,0x00,0x04,0x02),
    "PARIS": (0xdc,0x00,0x04,0x04,0x02), "ATHENS": (0x13,0x00,0x08,0x04,0x02),
    "JEDDAH": (0x85,0x00,0x0c,0x04,0x00), "TEHRAN": (0x16,0x01,0x0e,0x04,0x2b),
    "DUBAI": (0x5b,0x00,0x10,0x04,0x00), "KABUL": (0x88,0x00,0x12,0x04,0x00),
    "KARACHI": (0x8b,0x00,0x14,0x04,0x00), "DELHI": (0x52,0x00,0x16,0x04,0x00),
    "KATHMANDU": (0x8c,0x00,0x17,0x04,0x00), "DHAKA": (0x56,0x00,0x18,0x04,0x00),
    "YANGON": (0x2f,0x01,0x1a,0x04,0x00), "BANGKOK": (0x1c,0x00,0x1c,0x04,0x00),
    "HONG KONG": (0x7a,0x00,0x20,0x04,0x00), "PYONGYANG": (0xea,0x00,0x24,0x04,0x00),
    "TOKYO": (0x19,0x01,0x24,0x04,0x00), "ADELAIDE": (0x05,0x00,0x26,0x04,0x04),
    "SYDNEY": (0x0f,0x01,0x28,0x04,0x04), "NOUMEA": (0xcd,0x00,0x2c,0x04,0x00),
    "WELLINGTON": (0x2b,0x01,0x30,0x04,0x05), "NUKUALOFA": (0xd0,0x00,0x34,0x04,0x00),
    "KIRITIMATI": (0x93,0x00,0x38,0x04,0x00),
}


class Dev:
    def __init__(self, c): self.c = c; self.q = asyncio.Queue()
    def _cb(self, _h, d): self.q.put_nowait(bytes(d))
    async def start(self): await self.c.start_notify(ALL, self._cb)
    async def rd(self, req, t=3.0):
        while not self.q.empty(): self.q.get_nowait()
        await self.c.write_gatt_char(REQ, bytes(req), response=False)
        try: return await asyncio.wait_for(self.q.get(), t)
        except asyncio.TimeoutError: return None
    async def wr(self, b): await self.c.write_gatt_char(ALL, bytes(b), response=True)


def name_frame(slot, name):
    f = bytes([0x1f, slot]) + name.encode("ascii"); return f + bytes(20 - len(f))


async def run(address, city, slot):
    A, B, off, doff, rules = CITIES[city]
    async with BleakClient(address, timeout=20.0) as client:
        d = Dev(client); await d.start()
        pair = bytearray(await d.rd([0x1d, 0]))
        e = [bytearray(await d.rd([0x1e, 0])), bytearray(await d.rd([0x1e, 1]))]
        f = [bytes(await d.rd([0x1f, 0])), bytes(await d.rd([0x1f, 1]))]
        other = 1 - slot
        print("before: slot0=%s slot1=%s" % (
            bytes(f[0][2:]).split(b"\0")[0].decode("ascii", "replace"),
            bytes(f[1][2:]).split(b"\0")[0].decode("ascii", "replace")))

        # update the 0x1d pair for the changed slot (dstSetting AUTO = 0x02)
        if slot == 0: pair[3] = 0x02; pair[5] = A; pair[6] = B
        else:         pair[4] = 0x02; pair[7] = A; pair[8] = B
        e[slot] = bytes([0x1e, slot, A, B, off, doff, rules])
        f[slot] = name_frame(slot, city)

        frames = [bytes([0x21,0x00,0x01]), bytes(pair),
                  bytes(e[0]), bytes(e[1]), bytes(f[0]), bytes(f[1]),
                  bytes([0x2f,0x0e,0x04,0x00,0x1e,0x00]), bytes([0x21,0x01,0x01])]
        for fr in frames:
            await d.wr(fr); await asyncio.sleep(0.08)
        await asyncio.sleep(0.5)
        after = await d.rd([0x1f, slot])
        nm = bytes(after[2:]).split(b"\0")[0].decode("ascii", "replace").strip()
        print("slot%d now: %s  %s" % (slot, nm, "OK" if nm == city else "(FAILED)"))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--address")
    ap.add_argument("--city")
    ap.add_argument("--slot", type=int, default=1, choices=[0, 1])
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        print("\n".join(sorted(CITIES))); return
    if not args.address or not args.city:
        raise SystemExit("need --address and --city (or --list)")
    city = args.city.upper()
    if city not in CITIES:
        raise SystemExit("unknown city; use --list")
    await run(args.address, city, args.slot)


if __name__ == "__main__":
    asyncio.run(main())
