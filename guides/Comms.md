# Communications and service independence

This describes the maintained GungOS sources after the v1.1 connectivity
and service-removal passes. It is not a claim that every inherited tool has been
validated on physical PicoCalc hardware. See [Connectivity.md](Connectivity.md)
for the fixes, protocol tests, limits and device test steps.

## Current inventory

| Tool | Available behavior | Readiness / remaining work |
|---|---|---|
| Wi-Fi station | Scan/select SSID, save credentials, connect/disconnect, RSSI display | Source/simulator checks pass; test real reconnects, weak signal and coexistence |
| Wi-Fi AP / web server | Create a local AP or serve over an existing Wi-Fi connection; SD HTML/Python routes | Bounded nonblocking socket handling tested; physical AP/client testing remains; no HTTPS server or account login is implied |
| Clock sync | NTP from `pool.ntp.org` after Wi-Fi connects and the clock needs setting | Retained external time service; worker failures release state for another attempt |
| Bluetooth LE scan | Device list, full scan-response names and RSSI monitor | Virtual protocol tests pass; verify actual nearby devices and coexistence |
| Bluetooth LE UART | Central connects to a compatible Nordic UART peer; peripheral advertises/waits for a client; bounded UTF-8 chat | Discovery/subscription, packet fragmentation and cleanup fixed; physical interoperability remains |
| Bluetooth advertising / Beacon page | Simple UART-service advertising demonstrations | This is not an implementation of a standardized iBeacon/Eddystone payload |
| Bluetooth pairing | Clear unavailable message | Selected Pico 2 W native BTstack build does not expose the needed pairing API; secure pairing/bond persistence is not ready |
| USB | Keyboard, numpad, media-control keys, payload tools, alongside USB serial/REPL | Present; device enumeration and each app still need physical review |
| Infrared | Remote files, transmit, learn and pin/settings workflows | Requires suitable IR hardware/pins; needs a separate device review |
| Serial Terminal | UART input/output with port/baud/pin configuration | Present under Utils; requires an appropriate wired connection and hardware checks |
| SSH Terminal | User-specified remote host and credentials | Inherited code, not ready to call secure: key exchange parses the server host key/signature without verifying it or maintaining a trusted-host record; needs a separate review |
| HTTP / WebSocket libraries | Generic transports for scripts using caller-supplied URLs | No configured upstream account service; HTTP certificate verification is still disabled and needs its own fix |

Menus: **Comms → WiFi / Bluetooth / USB / Infrared**. Serial Terminal and SSH
Terminal remain under **Utils**.

## Removed upstream service integrations

The audit found executable FlipSocial and notification clients still present
outside the visible menus and included by the previous frozen-module manifest.
They contained account login/registration, feed, messages, profile/explore and
notification requests to the upstream author's service. Their presence does not
establish that the home screen was calling those services.

The maintained source now removes:

- `picoware/applications/applications/FlipSocial.py` and
  `picoware/applications/notifications.py`, including the notification bundle's
  weather/email polling.
- The upstream API-key field/property and account username/password editor,
  defaults, legacy per-field import and obsolete account-required decorator.
- Matching simulator login/game-stat responses and provider credential defaults.

The two removed clients are also excluded in the shared firmware/simulator
feature profile so an old application cannot silently restore the imports.
App Store and the upstream firmware updater remain removed/excluded.

Existing SD cards remain compatible. The settings loader ignores
`jblanked_api_key`, `server_username` and `server_password`; the next successful
settings save drops those fields while preserving Wi-Fi and unrelated settings.
It does not rewrite a card merely to load preferences. Old per-field account
JSON files are no longer read. Users may remove those unused files themselves.
The local web server's `picoware/wifi/server/server_info.json` is separate and is
retained.

The packaged SD settings template was checked and already contains none of those
retired account fields. Private
historical backups may still contain original sources/settings; backups are
ignored and excluded from the public source/build inputs.

Upstream copyright/license notices, project attribution and source links are
retained. A credits string or comment does not initiate a network connection.
The internal `picoware` Python package/SD paths remain for compatibility; service
independence does not require renaming every import.

## What still connects externally

Home reconnects to the saved access point and can request time from
`pool.ntp.org`. It does not check for firmware updates, log into the upstream
service, fetch social/notification data, or initialize an HTTP client. SSH and
generic network APIs use destinations explicitly supplied by the user/script.
Simulator offline fixtures do not use the physical radio.

This removal is not a firewall. User-installed SD scripts, manually entered URLs
and historical binaries are outside this source audit. Standard DNS/host network
behavior still applies. Build tools can fetch dependencies from their upstream
source hosts; those are build-time actions on the development computer.

## Checks and installation

```sh
python3 tools/check-service-independence.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_service_independence.py
```

The source guard checks maintained firmware/app/simulator Python literals for
retired service/download endpoints, preserves comments/docstrings as attribution,
and verifies that the removed clients stay absent/excluded. It is not a general
malware scanner, packet capture or audit of arbitrary user code/native libraries.
The native first-party source search found upstream source/credit links, not
additional service destinations.

Regression checks cover old-card settings migration, preservation of normal
preferences/Wi-Fi, retired import rejection, and home reconnect/time behavior
without creating an HTTP client. The existing preferences, trimmed-firmware,
Wi-Fi setup, menu/navigation and BLE/server checks passed as well. The new test
is included in the simulator's selected `--sim-check` profile.

**A new UF2 is required.** These clients/settings are frozen firmware modules.
The previous v1.0 UF2 has not been altered and still contains its previous frozen
contents. Replacing SD apps alone cannot remove those contents from the device.
No firmware has been built/flashed as part of this source-removal pass.
