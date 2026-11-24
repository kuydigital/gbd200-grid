#!/usr/bin/env python3
"""
GBD-200 "All Features" client (read-only by default).

Protocol (Casio 2C/2D, per Gadgetbridge):
  - service  26eb000d-b012-49a8-b1f8-394fb2032b0f
  - write a feature-request byte to 26eb002c  (write-without-response)
  - responses arrive as notifications on      26eb002d
  - settings/time writes also go to           26eb002d

Usage:
  python casio.py --address <uuid>            # read a safe set of features
  python casio.py --address <uuid> --feat 23  # read one feature code (hex)
"""
from __future__ import annotations

import argparse
import asyncio

from bleak import BleakClient

SVC = "26eb000d-b012-49a8-b1f8-394fb2032b0f"
REQ = "26eb002c-b012-49a8-b1f8-394fb2032b0f"  # write feature requests here
ALL = "26eb002d-b012-49a8-b1f8-394fb2032b0f"  # notify + write settings/time

# feature code -> human label (from Gadgetbridge; some vary on GBD-200)
FEATURES = {
    0x23: "watch name",
    0x28: "watch condition (battery/level)",
    0x20: "version information",
    0x26: "module id",
    0x1f: "world city",
    0x1d: "DST watch state",
    0x1e: "DST setting",
    0x15: "alarm block 1",
    0x16: "alarm blocks 2-4",
    0x11: "setting for BLE",
    0x13: "setting for basic",
}

# A conservative read order (name/version/condition first).
DEFAULT_READ = [0x23, 0x20, 0x26, 0x28, 0x1f, 0x1d, 0x1e, 0x15, 0x16, 0x13]


def fmt(data: bytes) -> str:
    ascii_ = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
    return f"{data.hex(' ')}   |{ascii_}|"


class Casio:
    def __init__(self, client: BleakClient):
        self.client = client
        self.queue: asyncio.Queue = asyncio.Queue()

    def _on_notify(self, _char, data: bytearray):
        self.queue.put_nowait(bytes(data))

    async def start(self):
        await self.client.start_notify(ALL, self._on_notify)

    async def request(self, feature_bytes: bytes, timeout=4.0) -> bytes | None:
        # drain any stale notifications
        while not self.queue.empty():
            self.queue.get_nowait()
        await self.client.write_gatt_char(REQ, feature_bytes, response=False)
        try:
            return await asyncio.wait_for(self.queue.get(), timeout)
        except asyncio.TimeoutError:
            return None


async def connect_with_retry(address, wait_seconds):
    """Retry connecting until the watch next advertises (no pairing mode needed)."""
    import time
    deadline = time.monotonic() + wait_seconds
    attempt = 0
    while True:
        attempt += 1
        try:
            client = BleakClient(address, timeout=10.0)
            await client.connect()
            print(f"Connected (attempt {attempt}).")
            return client
        except Exception as e:
            if time.monotonic() >= deadline:
                raise SystemExit(f"Gave up after {wait_seconds}s: {e}")
            print(f"  attempt {attempt} failed ({type(e).__name__}); retrying...")
            await asyncio.sleep(2.0)


async def run(address, feats, wait_seconds):
    print(f"Connecting to {address} (retrying up to {wait_seconds}s) ...")
    client = await connect_with_retry(address, wait_seconds)
    try:
        print("Connected. Enabling notifications on 26eb002d.\n")
        casio = Casio(client)
        await casio.start()
        for code in feats:
            label = FEATURES.get(code, "unknown")
            resp = await casio.request(bytes([code]))
            tag = f"0x{code:02x}  {label}"
            if resp is None:
                print(f"[{tag}] -> (no response / not supported)")
            else:
                print(f"[{tag}]")
                print(f"    {fmt(resp)}")
        print("\nDone (read-only, nothing was changed).")
    finally:
        await client.disconnect()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", required=True)
    ap.add_argument("--feat", help="feature code(s) in hex, comma-separated, e.g. 11,3a,3b")
    ap.add_argument("--wait", type=float, default=30.0,
                    help="seconds to keep retrying the connection (default 30)")
    args = ap.parse_args()
    feats = [int(x, 16) for x in args.feat.split(",")] if args.feat else DEFAULT_READ
    await run(args.address, feats, args.wait)


if __name__ == "__main__":
    asyncio.run(main())
