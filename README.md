# G-Shock Grid

A Bluetooth control console for the **Casio GBD-200** (and likely other GBX-100 / GBD-family
G-Shocks). It reads and writes the watch's real settings over Bluetooth Low Energy — from a
web page (Chrome / Edge) or from Python on the command line.

> **The honest part:** a GBD-200's own display **cannot be reskinned or themed**. Its LCD is
> driven by fixed mask-ROM firmware, and Bluetooth only exposes *data* (time, alarms, timers,
> settings). So this is a **companion console** — a G-Shock-styled UI on your phone/computer
> that controls the watch. It does not change what the watch itself looks like.

Not affiliated with or endorsed by Casio. The BLE protocol was derived from the open-source
[Gadgetbridge](https://codeberg.org/Freeyourgadget/Gadgetbridge) project.

## Features

| Area | What you can do | Feature code |
|------|-----------------|--------------|
| **Time** | Sync the watch clock to your device | `0x09` |
| **Alarms** | Read/set all 5 alarms, enable/disable each | `0x15`, `0x16` |
| **Settings** | 24h/12h, button tone, auto-light, key vibration | `0x13` |
| **Timers** | 5 interval timers (name + mm:ss) with auto-repeat | `0x2a`, `0x44` |
| **Signal** | Push a notification to the watch (buzz + icon) | `0x30` |
| **Readout** | Module name, firmware, home city, status block | `0x23` `0x20` `0x1f` `0x28` |

**Planned (layout known, pending hardware verification):** world-city change (`0x1f`/`0x1e`/`0x1d`)
and fitness profile / step goal (`0x45`/`0x43`). These are intentionally left out of the UI until
confirmed on-device, because a bad write to the clock/timezone block is more disruptive than an alarm.

## Use it — web app (no install)

Open **`index.html`** in **Chrome or Edge** (Web Bluetooth isn't in Safari/Firefox):

- Hosted: `https://kuydigital.github.io/gbd200-grid/`
- Or just double-click the local `index.html`.

Then:

1. **Turn your phone's Bluetooth off** (so the watch isn't already connected to the G-SHOCK MOVE
   app — BLE allows only one connection). On iPhone use **Settings → Bluetooth**, not Control Center.
2. On the watch, hold the lower-left button to enter connect/pairing mode.
3. Click **Connect** and pick **CASIO GBD-200** in the browser's device chooser.
4. Edit alarms, settings, timers; sync time; send a notification. Changes are read back to confirm.

## Use it — Python CLI

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Find the watch and its address (macOS shows a CoreBluetooth UUID, not a MAC)
python scan.py
python monitor.py            # live "first-seen" detector while you trigger pairing

# Read settings
python casio.py --address <ADDRESS>

# Alarms (1 uses 0x15; 2-5 use 0x16)
python set_alarm.py --address <ADDRESS> --alarm 3 --hour 6 --minute 45
python set_alarm.py --address <ADDRESS> --alarm 2 --off
python set_alarm.py --address <ADDRESS> --restore
```

`scan.py` and `casio.py` take `--wait <seconds>` to keep retrying the connection, so you don't
have to race the watch's short pairing window.

## Compatibility

- **Confirmed:** Casio GBD-200.
- **Likely (same 2C/2D "All Features" protocol):** GBX-100, GBD-100, GBD-H1000, GG-B100 and
  similar. Feature codes can differ per model — `casio.py` prints raw frames so you can check.
  Reports welcome via issues.

## How it works

The watch exposes a GATT service `26eb000d-b012-49a8-b1f8-394fb2032b0f`:

- Write a one-byte **feature code** to `26eb002c` → the watch notifies the data back on `26eb002d`.
- Write settings/time frames to `26eb002d`.
- Push notifications to `26eb0030` (bytes transmitted bitwise-inverted).

See the table above for the per-feature codes.

## Safety

Everything here is read-modify-write and reversible: the tools read a setting, change one field,
write it back, and read it again to confirm. Nothing touches firmware. Still, this is unofficial —
use it on a watch you own, and if a write ever looks wrong, the watch's own menus always let you
reset a setting by hand.

## Contributing

Issues and PRs welcome — especially confirmations on other G-Shock models, the world-city index
map, and the fitness-profile layout. Keep writes reversible and read-back-verified.

## License

MIT — see [LICENSE](LICENSE).
