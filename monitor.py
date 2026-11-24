#!/usr/bin/env python3
# G-Shock Grid — Casio GBD-200 BLE console. Copyright (c) 2026 KUYDIGITAL.
# MIT License (see LICENSE). https://github.com/kuydigital/gbd200-grid
"""
Live BLE monitor — prints each device the moment it is FIRST seen.

Run this, then trigger pairing mode on the watch. The device that appears
right as you start pairing (usually strong RSSI, often no name on macOS)
is the GBD-200. Note its ADDRESS, then:

    python scan.py --address <that-address>

Ctrl-C to stop.
"""
import asyncio
import time

from bleak import BleakScanner

seen = {}
start = time.monotonic()


def cb(device, adv):
    if device.address in seen:
        return
    seen[device.address] = True
    t = time.monotonic() - start
    name = adv.local_name or device.name or "(no name)"
    svc = list(adv.service_uuids or [])
    mfg = adv.manufacturer_data or {}
    note = ""
    if "casio" in name.lower() or any("26eb" in s.lower() for s in svc):
        note = "   <<<<< CASIO!"
    print(f"[{t:5.1f}s] RSSI={adv.rssi:>4}  {name:<22}  {device.address}{note}")
    if svc:
        print(f"           services={svc}")
    if mfg:
        print(f"           mfg={{ {', '.join(f'0x{k:04x}:{v.hex()}' for k,v in mfg.items())} }}")


async def main():
    print("Monitoring new BLE devices. Trigger pairing mode NOW.")
    print("Watch for a NEW device appearing as you start pairing. Ctrl-C to stop.\n")
    scanner = BleakScanner(detection_callback=cb)
    await scanner.start()
    try:
        await asyncio.sleep(30)
    finally:
        await scanner.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
