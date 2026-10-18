# Retained system and connectivity tools

This is the current menu inventory for the v2.1 review. Keeping a tool in this
list does not imply that every operation has been tested on the physical PicoCalc.

| Tool | Current purpose | Next review |
|---|---|---|
| Settings | Theme, brightness, keys, time and widget choice | Physical reboot/persistence and input consistency |
| About | GungOS version, features, credits and GPL notice | Final release wording |
| System Info / F1 panel | Board and memory counters | Unify full-page counters with the measured desktop snapshot |
| Bootloader / Restart / Shutdown / Stop | Device/runtime control | Confirm PicoCalc behaviour and return paths |
| Bluetooth | BLE scan, advertise, pairing, UART chat, beacon and RSSI pages | Radio behaviour, cleanup and whether each page is useful |
| WiFi | Scan/connect and saved credentials | Cold boot reconnect and NTP on the device |
| USB | Keyboard, numpad, media keys and payload tools | Which HID tools belong in the bare release |
| Infrared | External IR transmit/receive functionality | Hardware requirements and whether to keep it |
| File Manager | Browse/copy/edit/manage SD files | Editing and app launch paths with the release bundle |
| PicoIDE | Python source editing and development; compiled `.mpy` open/save blocked | Execution and error recovery |
| Python REPL | Interactive Python | Keyboard routing and exit/recovery |
| Serial Terminal | UART communication | Pin/settings workflow and cleanup |
| SSH Terminal | Remote shell via Wi-Fi | Connection setup, terminal behaviour and failure recovery |

Agent/AI, its setup page, Email and ESP Flasher are excluded from the frozen
profile. The launcher exposes Graph, Graph3D and PicoLAB directly. Games lists
only Tetris, and the full-screen Screensavers menu lists only Lorenz. Existing
user SD files are not deleted by those menu restrictions.

Review these tools one at a time before expanding the release scope. Email,
a spreadsheet-style editor and online updates are deferred to later versions.

PicoIDE edits readable `.py` source; `.mpy` files contain compiled MicroPython
bytecode. Use the corresponding source from `builds/MicroPython/apps_unfrozen/`
to modify an app. Renaming `.mpy` to `.py` does not turn it into source.
Opening a file no longer writes an empty/new file to SD. Failed binary/text
reads leave the original unchanged, and Save As cannot target `.mpy` files.
These protections are in the frozen firmware, so existing devices need a new
UF2 to receive them; the calculator SD update does not include this change.

Check with `builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_pico_ide.py`.

The [connectivity review](Connectivity.md) records the v1.1 Wi-Fi/BLE
fixes, test coverage and remaining hardware/native limitations. In particular,
Pair Device requires native support absent from the selected Pico 2 W build;
the simulator now reports that limitation too.
