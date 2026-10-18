# Connectivity work for following releases

These are planned features, not a claim that the current inherited terminals
are ready. The current release keeps Bluetooth, USB and Wi-Fi; Infrared is
excluded. System retains Restart and Shutdown, with Bootloader and Stop hidden.
Settings exposes brightness, theme, time and screensaver selection.

## GPIO and Serial configuration

Rework the existing Serial Terminal into a configurable GPIO/communications
settings tool. Keep the current terminal for this release; postpone its UI
and I/O refactor until a following release.

Planned scope:

- Select permitted GPIO functions and UART port, TX/RX pins, baud, data bits,
  parity, stop bits and line endings.
- Protect board-owned display, PSRAM, SD, keyboard, audio and wireless pins;
  check bridge wiring and pin ownership before applying changes.
- Apply/restore configurations safely and persist user choices deliberately.
- Provide buffered, bounded serial receive/transmit, reliable local echo,
  scrollback and responsive cancellation before expanding terminal emulation.

The concrete current defects are recorded in [CommsReview.md](CommsReview.md).

## Usable SSH client

Keep the current SSH entry for later development. It currently runs separate
commands and does not implement an interactive shell. Do not treat it as a
secure client until the following work is complete:

1. Verify server signatures and implement host-key trust/pinning, bounded
   packet parsing and correct per-direction crypto negotiation.
2. Bound output and receive windows, fix line/UTF-8 reassembly, and add
   nonblocking operations, operation deadlines and cancellation.
3. Decide the supported command-runner/interactive-shell UI. A real shell
   needs persistent PTY/session handling and terminal control-sequence support.
4. Evaluate a maintained embedded SSH implementation and test interoperability
   and memory use on the Pico 2 W before relying on the client.

Credential storage requirement: keep connection profiles and authentication
material on the Pico's internal flash, not the removable SD card. The complete
host/port/username/password profile now follows that rule via `/secrets.json`.
Legacy SD fields are removed after verified migration; failed writes keep the
originals for recovery. Command history still lives on SD and is separate from
the saved login profile.

The current store is unencrypted JSON, readable through a device REPL. Encryption
at rest is a separate future design requiring meaningful key storage/access
control; text encoding or an embedded fixed key must not be presented as secure
encryption. Future private keys and trusted-host records should also stay on-chip.

Infrared extensions can be contributed separately when suitable external
hardware is available; they are outside the release baseline.
