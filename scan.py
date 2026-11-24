#!/usr/bin/env python3
# G-Shock Grid — Casio GBD-200 BLE console. Copyright (c) 2026 KUYDIGITAL.
# MIT License (see LICENSE). https://github.com/kuydigital/gbd200-grid
"""
GBD-200 BLE explorer — step 1.

Usage:
    python scan.py                 # scan ~8s, list all BLE devices
    python scan.py --name CASIO    # scan, then connect to first match and dump GATT
    python scan.py --address XX:XX  # connect to a specific address and dump GATT

On macOS, --address is actually a CoreBluetooth UUID (printed by the scan),
not a real MAC — that's normal, the OS hides MACs.
"""
import argparse
import asyncio

from bleak import BleakClient, BleakScanner

SCAN_SECONDS = 8.0


# Casio's 128-bit service UUIDs (older + GBX/GBD family), used to spot the watch
# when it advertises no readable name.
CASIO_HINTS = ("26eb", "casio")


def looks_like_casio(name, svc_uuids, mfg_data):
    blob = " ".join(svc_uuids).lower() + " " + name.lower()
    if any(h in blob for h in CASIO_HINTS):
        return True
    # Casio Computer Co. Bluetooth SIG company id = 0x0063 (99)
    if 0x0063 in (mfg_data or {}):
        return True
    return False


async def scan():
    print(f"Scanning for {SCAN_SECONDS:.0f}s ...\n")
    devices = await BleakScanner.discover(timeout=SCAN_SECONDS, return_adv=True)
    if not devices:
        print("No BLE devices found. Is Bluetooth on? Is the watch advertising?")
        return []
    rows = []
    for addr, (dev, adv) in devices.items():
        name = adv.local_name or dev.name or "(no name)"
        svc = list(adv.service_uuids or [])
        mfg = adv.manufacturer_data or {}
        rows.append((adv.rssi, name, addr, svc, mfg))
    rows.sort(key=lambda r: r[0], reverse=True)  # strongest signal first

    print("Likely CASIO devices:")
    hits = [r for r in rows if looks_like_casio(r[1], r[3], r[4])]
    if hits:
        for rssi, name, addr, svc, mfg in hits:
            print(f"  >>> {rssi:>4}  {name:<22}  {addr}")
            print(f"          services={svc}")
            print(f"          mfg={{ {', '.join(f'0x{k:04x}:{v.hex()}' for k,v in mfg.items())} }}")
    else:
        print("  (none matched by service/name/manufacturer heuristics)")

    named = [r for r in rows if r[1] != "(no name)"]
    if named:
        print("\nAll NAMED devices:")
        for rssi, name, addr, svc, mfg in named:
            flag = "  <-- CASIO?" if "casio" in name.lower() else ""
            print(f"{rssi:>5}  {name:<24}  {addr}{flag}")

    print(f"\nTotal devices seen: {len(rows)}  "
          f"(named: {len(named)}, no-name: {len(rows) - len(named)})")
    # return name-less-friendly rows for the --name matcher
    return [(r[0], r[1], r[2]) for r in rows]


async def dump_gatt(client: BleakClient):
    print("\nConnected. Dumping GATT table:\n")
    for service in client.services:
        print(f"[service] {service.uuid}  ({service.description})")
        for ch in service.characteristics:
            props = ",".join(ch.properties)
            print(f"    [char] {ch.uuid}  handle={ch.handle}  props={props}")
            if "read" in ch.properties:
                try:
                    val = await client.read_gatt_char(ch.uuid)
                    print(f"           value = {val.hex(' ')}  {val!r}")
                except Exception as e:
                    print(f"           (read failed: {e})")
            for desc in ch.descriptors:
                print(f"        [desc] {desc.uuid}  handle={desc.handle}")
    print("\nDone.")


async def connect_and_dump(target):
    print(f"Connecting to {target} ...")
    async with BleakClient(target, timeout=20.0) as client:
        await dump_gatt(client)


async def main():
    global SCAN_SECONDS
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", help="connect to first device whose name contains this")
    ap.add_argument("--address", help="connect to this exact address/UUID")
    ap.add_argument("--seconds", type=float, default=SCAN_SECONDS, help="scan duration")
    args = ap.parse_args()
    SCAN_SECONDS = args.seconds

    if args.address:
        await connect_and_dump(args.address)
        return

    rows = await scan()
    if args.name:
        match = next(
            (addr for _, name, addr in rows if args.name.lower() in name.lower()),
            None,
        )
        if not match:
            print(f"\nNo device matched name containing {args.name!r}.")
            return
        await connect_and_dump(match)


if __name__ == "__main__":
    asyncio.run(main())
