# Connectivity debugging pass

This source revision fixes the built-in Wi-Fi/BLE modules after v2.2. These
modules are frozen into firmware: copying SD applications does not install the
fixes. The existing v2.2 UF2 is unchanged; build and flash a new UF2 when ready.
The simulator loads the revised sources directly.

## Confirmed issues and changes

| Area | Previous failure | Revised behavior |
|---|---|---|
| Wi-Fi joins | Switching SSIDs could report the previous connection as success; a worker ran a long connection loop | Disconnect before a new join; initiate the native join once and poll status/deadlines from the UI loop |
| Wi-Fi AP | AP configuration used the station interface | Use `WLAN(AP_IF)`, validate credentials, configure security/key, then activate; switching back uses `STA_IF` |
| Wi-Fi status | Tick-zero/wrap and missing start times could break elapsed time; failures were unclear | Wrap-safe deadlines, stable terminal states, driver failure reasons and cancellation |
| Wi-Fi scan | Display labels doubled as SSIDs; hidden/non-UTF-8 SSIDs were unsafe choices | Keep actual names separately; reject hidden-name joins and skip undecodable entries; bound results at 64 |
| RSSI | Repeated Wi-Fi scans on each half-second redraw | At most one scan every two seconds, a 64-network limit, and visible scan errors |
| Password entry | Network password displayed as ordinary text | Mask the Wi-Fi and AP password editors |
| Local HTTP server | Blocking client reads/writes could trap the app; Esc could leave the listener open | Nonblocking client work, partial writes, request limits/deadlines, and explicit cleanup through the actual app return path |
| Server settings | First-use/missing JSON failed; failed writes could look successful | Create on first save; verify temporary writes and preserve unreadable/existing settings; keep failed edits open |
| Server scripts | Imports were not visible inside the request handler | Share the script's execution globals and locals; return a generic 500 on execution/file errors |
| NTP | Worker failure could leave time sync permanently marked requested/running | Always release request/running flags so a subsequent sync can be requested |
| BLE advertising | Default UART names/service UUID could exceed the 31-byte advertisement limit | Fit service/short name in advertising and put the full name in the scan response |
| BLE discovery | String/UUID comparisons and a guessed CCCD handle prevented real UART setup | Compare UUID objects, discover descriptors, and wait for subscription acknowledgment before entering chat |
| BLE I/O | Long/UTF-8 text could exceed ATT packet limits or be split incorrectly | Queue and fragment packets by negotiated MTU; assemble bounded newline-framed UTF-8 messages |
| BLE lifecycle | Native IRQ data/UI callbacks, scan restarts and delayed cleanup caused fragile behavior | Copy transient IRQ data, process bounded events in `poll()`, and close the controller explicitly on exit/failure |
| Pairing | Device-name JSON implied a saved bond; simulator offered APIs absent from the device | Report unsupported firmware clearly; generic supported-stack path persists real keys and metadata once, with explicit passkey input/confirmation |

## Actual Pico 2 W pairing limitation

The pinned [Pico 2 W board configuration](../vendor/micropython/ports/rp2/boards/RPI_PICO2_W/mpconfigboard.cmake)
selects BTstack. Its build does not enable
`MICROPY_PY_BLUETOOTH_ENABLE_PAIRING_BONDING`; the default is zero in
[modbluetooth.h](../vendor/micropython/extmod/modbluetooth.h). The native
`gap_pair`/`gap_passkey` Python API is therefore absent. The pinned BTstack
implementation also returns unsupported for passkey replies and has no bridge
to Python GET_SECRET/SET_SECRET callbacks.

Enabling that compile flag alone will not provide complete secure pairing or
persistent bonds. Native backend integration is separate work. Scan, advertising
and compatible BLE UART peers can work without pairing; UART mode does not
promise an authenticated/encrypted connection.

The simulator now defaults to pairing unsupported. The new protocol tests
explicitly opt into a synthetic pairing-capable stack to exercise key storage
and passkey UI paths. Passing those tests does **not** establish pairing support
on the shipped Pico firmware.

## Storage and API details

- Passwords (Wi-Fi, SSH, the server's access point) are stored in the Pico's
  internal flash (`/secrets.json`, `picoware.system.secrets`), not on SD. The
  SSID and other settings stay in `picoware/settings/picoware.json`. Passwords
  that older releases wrote to the SD card move to flash the first time they
  are read and are then removed from the card. They stay with the device:
  moving the SD card to another PicoCalc means entering them again. Anyone
  holding the device can still read them over the USB REPL.
- Web-server settings/pages live in `picoware/wifi/server/server_info.json`.
- On a future supported pairing backend, actual key material lives in
  `picoware/bluetooth/bonds.json`; `paired_devices.json` holds names and key
  identifiers. These files are private device state. They belong on SD, not in
  source control. A device name alone is not proof of a saved bond.
- A leftover `.bak` file blocks another configuration/key replacement. Recover
  it deliberately rather than silently overwriting a potentially valid backup.
- `ViewManager.run()` polls Wi-Fi. Standalone `WiFi` callers must call `poll()`
  while a join is pending, or use the synchronous `connect()` compatibility API.
- BLE apps must call `Bluetooth.poll()` every frame and `close()` on exit.
  UI callbacks now run from `poll()`, not inside the native IRQ.
- BLE limits: 64 queued events, at most eight processed per poll, 1 KiB outgoing
  queue, 512-byte incoming chat line, 20 displayed messages. Connect/discovery
  timeout is 10 seconds, write acknowledgment timeout five seconds, pairing
  timeout 30 seconds on a supporting backend.
- HTTP server limits: one active client, 4 KiB headers/body each, 32 KiB response,
  1 KiB socket work per frame, and a five-second request/send budget. Request
  timeout replies have a separate five-second send deadline. Chunked requests
  are rejected. Local Python handlers still execute synchronously and must
  finish promptly; arbitrary user scripts are not preempted/sandboxed.

## Remaining issues / hardware verification

The generic HTTP client still sets `tls.CERT_NONE` in
[system/http.py](../src/MicroPython/picoware/system/http.py). It does not validate
server certificates. Provisioning trusted roots and verified TLS needs its own
change before using that client for sensitive services. This pass does not
change that policy.

Wi-Fi `WLAN.scan()` and native radio initialization are synchronous driver
operations. Scan throttling reduces repeated pauses; it does not make one scan
asynchronous. DNS timing, weak-signal reconnects, RF range, Wi-Fi/BLE coexistence
and sustained throughput remain physical-device checks. The simulator uses host
networking/virtual BLE and a larger heap; it cannot validate radio behavior,
actual Pico memory peaks, or SD power-loss durability.

## Tests

From the project root, using the selected desktop MicroPython build:

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_connectivity.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_connectivity_ui.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_wifi_setup.py
```

Both new tests are included in the selected simulator `--sim-check` profile.
They cover real protocol constraints, unsupported pairing, opt-in synthetic
bond/passkey behavior, cancellation/timeouts, partial HTTP reads/writes, settings
write failures, first-use/corrupt files, keyboard submission and app cleanup.
Existing preferences, menu/navigation, dashboard, release-demo and PicoIDE
regressions also passed during this pass. The demo test reported missing optional
audio in the isolated test tree and exercised its silent fallback.

After building a new UF2, check on PicoCalc:

1. Scan/join a known 2.4 GHz AP; verify saved credentials after power cycling.
   Switch to another AP; try a wrong password and an absent SSID, then retry.
2. Leave a pending join with Esc; verify the UI remains usable. Use Disconnect
   to cancel the join explicitly. Verify Wi-Fi stays available after BLE exits.
3. Configure server AP mode, find it from another device, load a page, send an
   incomplete request and press Esc; verify the listener/AP shut down. Rejoin
   station mode afterward. Confirm a failed time sync can be requested again.
4. Scan BLE peers; check full names. Test PicoCalc UART peripheral with a BLE
   UART client, and central mode with an actual Nordic UART-compatible peer.
   Exchange long/UTF-8 lines, disconnect either side, and reopen both roles.
5. Confirm Pair Device reports unsupported firmware rather than crashing.
   Secure pairing/reboot persistence is deferred until native support exists.
6. Run Wi-Fi and BLE together, then repeat open/close and longer transfers while
   watching actual free heap. This is required before claiming device readiness.

## Subsequent service-removal pass

The [Comms inventory and service audit](Comms.md) records removal of the inherited
social/notification clients and upstream account settings, while retaining local
connectivity and NTP. Run `python3 tools/check-service-independence.py` before
building to check for reintroduced endpoints.
