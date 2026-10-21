# GungOS MicroPython simulator

Run GungOS on your desktop. A native SDL2 window handles display and input,
while the firmware runs inside the project's custom MicroPython interpreter.

## Features
- The firmware's own C drawing code (`src/MicroPython/gfx`), so the screen
  matches the device pixel for pixel, including its 256-colour palette
- A display summary at exit: how many rows the device would have sent to
  the panel, since `swap()` sends only rows that changed
- Real network access via host DNS/TCP/TLS (or `--network offline` for fixtures)
- The GungOS firmware for PicoCalc with Pico 2 W, with virtual Bluetooth
- Simulated SD card at `simulator/sdcard` (auto-seeded on first run)
- Headless mode for automated testing (`--headless`)

## Installation

The simulator models only the PicoCalc with a Raspberry Pi Pico 2 W, the one
board GungOS supports. The home clock still supports NTP. JPEG viewing, USB
HID, Bluetooth, Wi-Fi, SD editing and PicoLAB are available.

The desktop interpreter includes the [selected ulab build](../src/MicroPython/ulab/README.md)
and uses float32, matching the current PicoCalc numeric profile. PicoLAB's
Numerics checks page shows known-answer checks and host timings; its heap deltas
are allocation snapshots rather than peak memory measurements.

### macOS and Linux

Install Python 3, Make and a host C/C++ compiler. SDL2 development headers and
libraries enable the viewer and audio; ffmpeg is optional for local sound
conversion. The simulator's native modules and float32 ulab profile require the
custom interpreter built from `vendor/micropython`; a stock MicroPython binary
is insufficient. See [BUILD.md](../BUILD.md) for the pinned-source build.

### Windows

Not supported. The simulator relies on Unix process spawning and file-pipe IPC
that have no direct equivalent on Windows. Use WSL2 or a Linux VM.

## Usage

From the repository root, build the custom desktop interpreter and SDL viewer,
then launch. Use the bundled MicroPython revision:

```sh
mkdir -p .build
MICROPYTHON_DIR="$PWD/vendor/micropython" \
PICOWARE_DESKTOP_SOURCE_ALIAS="$PWD/.build/desktop-source" \
  sh tools/micropython-desktop.sh
sh simulator/build.sh viewer
sh tools/run-micropython-desktop.sh --viewer --board picocalc-pico2w
```

Apps contains PicoDESK, PicoLAB, Games and Misc. Graph and Graph3D live under
PicoLAB; Screensavers and Benchmark live under Misc. Games lists Tetris. Use
`--app PicoDESK`, `--app PicoLAB`, `--app Graph`, `--app Graph3D` or
`--game Tetris` to launch directly.

On the 320 × 320 PicoCalc desktop, Left/Right selects the category and
Up/Down selects its menu items. F1 focuses the scrollable resource panel,
F3 focuses the optional widget, and F9 shows help. See
[Engineering desktop](Desktop.md) for layout, memory counters and widget setup.

Run checks for the selected profile with:

```sh
sh tools/run-micropython-desktop.sh --sim-check --network offline --audio silent
```

These commands use the desktop interpreter. Build the device UF2 separately
with `tools/build-gungos-release.sh`; the host binary cannot be flashed to PicoCalc.

Tetris music and effects can be heard with `--viewer --game Tetris --audio real`.
Its dedicated PCM helper streams your optional local WAVs; `--audio silent` disables the
audible helper for checks. See [Tetris audio](TetrisAudio.md).

### Keyboard shortcuts (viewer window)

| Shortcut | Action |
|---|---|
| `Ctrl+Q` | Quit |
| `Ctrl+D` | Toggle debug HUD |
| `Ctrl+S` | Save BMP screenshot |
| `Alt+A..Z` | PicoCalc Alt+letter (Alt+S takes a device screenshot) |
| `Ctrl+M` | Toggle audio mute |
| `Ctrl+R` | Restart simulator |
| `Ctrl+Shift+R` | Reset SD card and restart |
| `Ctrl+1..4` | Change window scale |


`--board` accepts only `picocalc-pico2w` (the default).

### Script input

Simulator scripts support queued key/text input plus simulator state changes:

```text
app PicoLAB
keys down,enter
text hello
battery 42
```

`battery N` sets the battery percentage reported by the simulated southbridge.

`wait`, `sleep`, or `frames` in a script delays later queued input. This is useful
when launching directly into an app and waiting for lazy imports or loading
screens before sending keys.

### Rebuilding

Native binaries are built automatically on first use. To rebuild manually:

```sh
cd simulator

./build.sh --force    # rebuild all
./build.sh --clean    # remove binaries
./build.sh --check    # report missing/stale binaries without rebuilding
./build.sh viewer     # rebuild only the viewer
./build.sh audio      # rebuild the Tetris PCM helper (alias: tetris-audio)
./build.sh jpeg
```
