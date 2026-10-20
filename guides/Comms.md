# Communications

This describes the maintained GungOS sources after the v1.1 connectivity
passes. It is not a claim that every inherited tool has been
validated on physical PicoCalc hardware. See [Connectivity.md](Connectivity.md)
for the Wi-Fi/BLE fixes, protocol tests, limits and device test steps.
The [wired/SSH review](CommsReview.md) covers the remaining modules.

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
| USB | Keyboard, numpad, media-control keys and SD macro playback, alongside native USB serial/REPL | Use the Pico’s own USB connector; key mapping, transfer backpressure and cleanup need work; physical enumeration unverified |
| Serial Terminal | Line-oriented UART0 text exchange, fixed GP0/GP1 at 115200 baud | No port/baud/pin settings UI. Burst loss, lost local echo, blocking startup and unbounded text confirmed; refactor before relying on it |
| SSH Terminal | Password-authenticated SSH command execution to a user-specified host | Not an interactive shell; no host-key signature/trust verification. Parser/MAC defects and unbounded/blocking output confirmed; not ready for credentials |
| HTTP / WebSocket libraries | Generic transports for scripts using caller-supplied URLs | HTTP certificate verification is still disabled and needs its own fix |

Menus: **Comms → Bluetooth / USB / WiFi**. Infrared and its frozen drivers are
excluded from this release. Serial Terminal and SSH
Terminal remain under **Utils**.

## What still connects externally

Home reconnects to the saved access point and can request time from
`pool.ntp.org`. It does not check for firmware updates or initialize an HTTP
client. SSH and
generic network APIs use destinations explicitly supplied by the user/script.
Simulator offline fixtures do not use the physical radio.

This is not a firewall. User-installed SD scripts, manually entered URLs
and historical binaries are outside this source audit. Standard DNS/host network
behavior still applies. Build tools can fetch dependencies from their upstream
source hosts; those are build-time actions on the development computer.

See [ConnectivityRoadmap.md](ConnectivityRoadmap.md) for the deferred GPIO/serial
configuration tool and usable SSH client. The complete SSH profile now lives in
internal flash; old SD profile files migrate before being removed.
