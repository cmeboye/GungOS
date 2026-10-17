# Picoware MicroPython Simulator
Run Picoware on your desktop. The simulator uses a native SDL2 window for display and input, while Picoware itself runs inside MicroPython.

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
and uses float32, matching the current PicoCalc numeric profile. Engineering
Lab's Numerics checks page shows known-answer checks and host timings; its heap
deltas are allocation snapshots rather than peak memory measurements.

### macOS

```sh
brew install micropython sdl2
```

### Linux

```sh
# Debian / Ubuntu
sudo apt install micropython libsdl2-dev ffmpeg

# Fedora
sudo dnf install micropython SDL2-devel ffmpeg

# Arch
sudo pacman -S micropython sdl2 ffmpeg
```

### Windows

Not supported. The simulator relies on Unix process spawning and file-pipe IPC
that have no direct equivalent on Windows. Use WSL2 or a Linux VM.

## Usage

Build the selected desktop interpreter and SDL viewer, then launch. Set
`MICROPYTHON_DIR` to your MicroPython source checkout when building:

```sh
sh tools/micropython-desktop.sh
sh simulator/build.sh viewer
sh tools/run-micropython-desktop.sh --viewer --board picocalc-pico2w
```

Apps contains Graph, Graph3D, PicoLAB, Games and Screensavers. Games lists only
Tetris; Screensavers lists the Lorenz demonstration. Use `--app PicoLAB`,
`--app Graph`, `--app Graph3D` or `--game Tetris` to launch directly. The older
Agent/Python Apps menu routes are no longer exposed.

On the 320 × 320 PicoCalc desktop, Left/Right selects the category and
Up/Down selects its menu items. F1 focuses the scrollable resource panel,
F3 focuses the optional widget, and H shows help. See
[Engineering desktop](Desktop.md) for layout, memory counters and widget setup.

Run checks for the selected profile with:

```sh
sh tools/run-micropython-desktop.sh --sim-check --network offline --audio silent
```

This builds only the desktop interpreter. The device UF2 is built separately
after the lab/numerics work is ready.

Tetris music and effects can be heard with `--viewer --game Tetris --audio real`.
Its dedicated PCM helper streams the supplied WAVs; `--audio silent` disables the
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
app Calculator
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
