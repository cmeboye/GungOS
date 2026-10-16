# Picoware MicroPython Simulator
Run Picoware on your desktop. The simulator uses a native SDL2 window for display and input, while Picoware itself runs inside MicroPython.

## Features
- Custom Picoware UI with framebuffer and keyboard input
- Scripted/viewer touch input for supported touch-board profiles
- Real network access via host DNS/TCP/TLS (or `--network offline` for fixtures)
- Selected Python/engineering profile with Agent/AI and virtual Bluetooth
- Simulated SD card at `simulator/sdcard` (auto-seeded on first run)
- Headless mode for automated testing (`--headless`)

## Installation

The current desktop build omits Agent/AI, Email, ESP Flasher, LVGL,
C/JavaScript/MMBasic, native game engines, media playback/streaming, App Store
and the upstream firmware updater. The home clock still supports NTP. JPEG
viewing, USB HID, Bluetooth, Wi-Fi, SD editing and PicoLAB remain available.
Unsupported native APIs are also blocked
in simulator shims so the preview reflects the selected firmware.

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
| Left mouse click | Send a touch point to touch-board profiles |


Useful board names include `picocalc-pico2w`, `waveshare-1.28-rp2350`,
`waveshare-1.43-rp2350`, `waveshare-1.69-rp2350`, `waveshare-3.49-rp2350`,
`crowpanel-10.1`, and `cardputer`.

### Game Boy controls

The simulator runs Game Boy ROMs through the native Walnut-CGB helper when it
is available, with a placeholder fallback if the helper cannot build or start.
Firmware/PicoCalc controls still work, and the simulator also accepts a
QWERTY-friendly keymap:

| Key | Game Boy button |
|---|---|
| Arrow keys | D-pad |
| `X` or `]` | A |
| `Z` or `[` | B |
| `Enter` or `=` | Start |
| `Space` or `-` | Select |

### Script input

Simulator scripts support queued key/text input plus simulator state changes:

```text
app Calculator
keys down,enter
text hello
touch 440 200
gesture 6 160 160
battery 42
```

`touch X Y [GESTURE]` and left-clicks in the viewer update the simulated touch
controller. `battery N` sets the battery percentage reported by simulator board
shims.

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
./build.sh audio      # rebuild local audio, radio and Tetris PCM helpers
./build.sh audio-player
./build.sh tetris-audio # streamed PCM music/effects preview
./build.sh radio-player
./build.sh jpeg
./build.sh gameboy    # rebuild only the Game Boy helper
```
