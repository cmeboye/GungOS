# PicoCalc wired and terminal review

Reviewed the maintained PicoCalc/Pico 2 W source tree. Menu cleanup, infrared removal and
on-chip SSH profile storage below are implemented; the inherited Serial,
USB and SSH findings are a review backlog, not completed terminal rewrites.
No physical peripheral or external SSH server was used during this pass.

## Changes made

- System now lists Settings, About, System Info, Restart and Shutdown.
  Bootloader and Stop are removed from the dashboard/library and legacy menus.
  Shutdown keeps its confirmation dialog. Low-level control APIs remain.
- Settings lists Screen Brightness, Theme Color, Time and Screensaver.
  Debug, Onscreen Keyboard and Fast Drawing entries/toggle UI are removed.
  Existing drawing/keyboard preferences and application APIs still work.
- Infrared is excluded from the release: its menu route, application, facade
  and all protocol drivers are removed from the maintained frozen source tree.
  The simulator no longer tries to import/test those modules. Compatibility
  decorators explicitly report unsupported IR for old SD applications.
- The complete SSH profile (host, port, username, password) is saved only to
  internal flash. Legacy SD profile files migrate in one verified flash update
  before deletion. Failed writes preserve originals for recovery/retry; existing
  on-chip values take priority over stale SD copies. New edits apply only after
  saving succeeds. This is not encryption and does not fix SSH authentication.
- Future serial/GPIO configuration and SSH work is recorded in
  [ConnectivityRoadmap.md](ConnectivityRoadmap.md).

These are frozen firmware sources: a future UF2 build is needed to install
these changes on the PicoCalc. No UF2 or live SD update was made in this pass.

## Hardware and connector facts

The RP2350/Pico 2 W has a USB 1.1 controller supporting device and host roles.
The selected firmware enables MicroPython runtime USB **device** functions
and USB CDC. It does not implement a general USB-host UI or host drivers.
A USB stick or external USB keyboard will therefore not start working just
because this menu exists.

Use the Pico module's own Micro-USB connector for native USB HID and CDC.
ClockworkPi's V2.0 mainboard schematic routes the case USB-C data through a
switch to the CH340C serial bridge or the keyboard MCU's USB pins; it does not
show a direct path to the Pico USB controller. The default USB-C serial path
therefore serves UART0, rather than the Pico's HID interface. Mainboard
revision and switch settings must be checked before physical testing.

PicoCalc has no built-in infrared emitter or receiver. GP28 is exposed on its
expansion header and can drive an external IR transmitter circuit. Use a
suitable IR LED, current limiting and driver, plus common ground. A receiver
would need its own compatible interface and software configuration; the
current board flag/decorator and capture API assume no receiver is present.

Primary references:

- [Raspberry Pi Pico-series hardware](https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html)
- [ClockworkPi PicoCalc mainboard V2.0 schematic](https://github.com/clockworkpi/PicoCalc/blob/master/clockwork_Mainboard_V2.0_Schematic.pdf)
- [MicroPython USBDevice API and lifecycle](https://docs.micropython.org/en/latest/library/machine.USBDevice.html)
- [MicroPython RP2 UART reference](https://micropython.org/resources/docs/en/latest/rp2/quickref.html#uart-serial-bus)

## Infrared: excluded

The earlier review found that the stock PicoCalc lacks IR hardware and that
some inherited TX choices overlapped PSRAM/UART wiring. The complete IR
feature has now been removed for this release. Contributors with external
hardware can restore an implementation from Git history and add board-specific
pin ownership checks, transmitter/receiver configuration and physical tests.
See [Infrared.md](Infrared.md) for the removal scope.

## USB

**Purpose:** turn PicoCalc into a peripheral for another computer:

- Keyboard: translate typed characters into USB HID reports.
- Numpad: send numeric-keypad digits and arithmetic keys.
- Media Keys: volume, mute, play/pause and track navigation.
- Payload: play keyboard macro files (`.txt`/`.duck`) from `picoware/usb/`.

The low-level code appends a HID interface to native CDC so the MicroPython
serial interface can coexist with it. This is separate from the CH340C bridge.

**Confirmed problems:**

1. Keyboard's `button_to_char()` path sends Enter, but ignores arrows,
   Backspace, Tab and function keys. It does not map Ctrl/Alt combinations.
2. Both HID wrappers ignore `_wait()` failure and `submit_xfer()` rejection.
   A rejected report can leave `_xfer_done` false and cause repeated 500 ms
   waits, notably before host configuration or after cable removal.
3. App stop deletes its reference but never deinitializes the singleton USB
   device. Its callbacks retain the HID object and the runtime interface
   remains active. Changing modes needs an explicit ownership/cleanup policy.
4. USB payload execution is synchronous; long macros/delays block navigation.
   The browser/payload objects also lack complete exit cleanup.

**Recommended improvement:** one shared HID lifecycle, a bounded event queue,
proper transfer acceptance/completion handling, reconnect/error UI and full
key/modifier mapping. Restore a clean CDC configuration on exit rather than
leaving runtime callbacks behind. Then test enumeration, key release,
repeated mode switching and unplug/replug on the real Pico USB connector.
The simulator records reports but cannot certify host enumeration.

## Serial Terminal

**Purpose:** a line-oriented wired chat/console using UART0 at **115200 baud,
GP0 TX / GP1 RX**, with native UART defaults (8 data bits, no parity, 1 stop
bit). It is not a USB-host terminal or an ANSI/VT100 terminal. Despite an older
inventory description, the app has no port, baud or pin configuration page.
The wrapper API supports configuration, but this UI never exposes it.

The case USB-C bridge is one possible PC connection. For an external UART
peer use compatible 3.3 V signalling, cross TX/RX and share ground; account
for the board's bridge wiring before attaching a second device to these pins.

**Confirmed problems:**

1. Each receive callback overwrites one global message, dropping earlier
   bursts before the UI consumes them.
2. Incoming bytes are formatted as Python `b'...'` literals and receive
   labels are added twice in the viewing path.
3. Sending immediately clears its local-echo string; data arriving while
   composing can also be discarded by that shared variable.
4. `start()` blocks waiting for a key; receive string allocation happens in
   the UART callback instead of a bounded foreground queue/poll loop.
5. Text accumulation is unbounded. The app only sends LF and provides no
   useful serial settings, raw control-key mode or proper terminal emulation.

**Recommended improvement:** refactor this first. Use nonblocking startup,
bounded receive polling/queueing and scrollback, separate TX/RX state, safe
byte/UTF-8 handling, and reliable local echo. Add baud and LF/CRLF settings
before attempting a larger terminal-emulation feature set. Test with a PC
bridge session or a known UART peer, including bursts while typing and
repeated open/close.

The shared UART wrapper also has a busy-loop line reader with non-wrap-safe
tick subtraction and can merge multiple received lines; its `write()` discards
the native byte count. Review those APIs when introducing queued I/O.

## SSH Terminal

**Purpose:** password-authenticated SSH command execution over Wi-Fi to a
user-entered host. Each command opens a new `session` channel and uses SSH
`exec`. There is no persistent interactive shell or PTY request: `cd` does not
persist across commands, and tools such as `nano`, interactive `sudo` or `top`
are not supported terminal workflows.

**Status: not ready for real credentials.** This is an inherited Python SSH
implementation, not a wrapper around a complete native SSH client.

**Confirmed problems:**

1. All key-exchange paths parse the server host key and signature but never
   verify the signature or establish host trust. Algorithm negotiation alone
   does not authenticate a server. A fingerprint prompt alone would not fix
   the missing signature verification. [RFC 4253, section 8](https://www.rfc-editor.org/rfc/rfc4253#section-8)
   requires both server-key acceptance and signature verification.
2. String parsing accepts declared lengths beyond the available packet.
   Packet padding/minimum-size checks are incomplete.
3. Both MAC directions use the client-to-server algorithm and length even
   though negotiation permits different algorithms per direction. SHA-1
   outbound/SHA-256 inbound derives a 20-byte inbound key instead of 32 bytes.
4. Connect/key exchange/command collection run synchronously in the UI loop.
   Per-socket 15-second timeouts do not provide a responsive cancel path or a
   whole-operation deadline; a continuously sending peer can run much longer.
5. Output and packet-split lines are collected without a memory bound.
   The code advertises a 2 MB receive window and never calls its window-adjust
   helper. Large output can exhaust heap or stall. UTF-8/lines split across
   packets are not reassembled properly.
6. Password authentication is the only login method. History is written to SD
   for every command. The full connection profile now lives in internal-flash
   secrets; storing it there does not supply missing server authentication.

**Recommended improvement:** settle whether the goal is a small remote-command
client or a true interactive shell before rebuilding the UI. First establish
signature verification plus host-key trust/pinning, bounded parsers and correct
per-direction crypto. Prefer evaluating a maintained embedded SSH core against
Pico memory/CPU limits to expanding handwritten cryptography. Next add bounded,
nonblocking I/O and output with cancellation. PTY/shell, ANSI handling and
public-key login would be separate later features. None of these fixes was
silently treated as complete by this review.

## Reproduce the review

From the repository root:

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/audit_comms.py
```

This is a diagnostic characterization, not a passing security/interoperability
test: it prints the current defects without asserting that they should remain.
It uses local simulated UART/USB; Infrared is no longer part of the audit. SSH packet
fixtures are in memory; ECDH and AES are replaced only for the signature/MAC
control-flow probes. It does not connect to any host, use a password, enumerate
real USB hardware or validate cryptographic interoperability.

Regression checks for the implemented changes: `test_trimmed_firmware.py`,
`test_preferences.py`, `test_fast_drawing.py`, `test_theme_picker.py`,
`test_menu.py`, `test_choice_dialogs.py` and `test_secrets.py`, run with the same interpreter.
