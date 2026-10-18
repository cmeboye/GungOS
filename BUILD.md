# Building GungOS v1.1

The release vendors its source dependencies. Building does not fetch from the
network. Use the pinned sources in `vendor/`; no `git submodule update` is needed.

## Host requirements

- Python 3, Make, CMake, a host C/C++ compiler and **Arm GNU Toolchain**
  (`arm-none-eabi-gcc`, `arm-none-eabi-g++`, binutils).
- The shipped build was made on Apple Silicon with Arm GNU Toolchain 15.3.Rel2
  (GCC 15.3.1) and CMake 4.4.4. The toolchain itself is installed separately.
- Optional: SDL2 to show the simulator and hear sound; ffmpeg to reconvert the
  original sound recordings. Neither is required for the firmware build.

## Firmware and SD build

Add your Arm toolchain's `bin` directory to PATH, open a terminal at this
directory, and run:

```sh
sh tools/build-gungos-release.sh
```

The script builds a matching `mpy-cross`, host picotool and the RP2350 firmware,
compiles the shipped applications, regenerates clean SD contents and records
checksums. Output:

- `firmware/GungOS-v1.1-PicoCalc-Pico2W.uf2`
- `sd-card/` and `GungOS-v1.1-SD.zip`
- `verification/build-info.json`, firmware ELF/map and `SHA256SUMS.txt`

Intermediate files live in `.build/` and can be deleted after building. To place
them elsewhere, set `GUNGOS_BUILD_DIR` to an absolute directory. Build parallelism
defaults to eight jobs; set `PICOWARE_BUILD_JOBS` to change it.

The RP2350 flash layout reserves 2,048,000 bytes for the internal MicroPython
filesystem within the Pico 2 W's 4 MiB flash. Application MPY files and optional licensed Tetris
WAVs live on SD. The selected native ulab uses float32 and the dedicated PCM
module drives PicoCalc speakers with PWM/DMA.

`vendor/revisions.json` identifies upstream revisions. Any local MicroPython
adaptation is recorded in `vendor/micropython-local.patch` and already applied
to the vendored source. Firmware build date defaults to 2026-10-18 UTC through
`SOURCE_DATE_EPOCH`; toolchain changes can change the firmware checksum.

The PicoCalc CMake adapter keeps GCC 15's array-bounds diagnostic for the
upstream Mbed TLS fixed-length XOR tail as a warning for `aes.c` and `gcm.c` only.
The library source is unchanged; other firmware warnings retain `-Werror`.

## Public and local audio

The default build omits audio recordings. Tetris remains playable without sound;
new clean SD settings disable sound when no WAV assets are packaged. Local audio
files and host executables are not part of a Git clone. See
[optional audio](guides/TetrisAudio.md) for an explicit audio-enabled app build.

## Verification

```sh
python3 tools/verify-gungos-release.py
```

To build and check the host simulator using the same vendored MicroPython:

```sh
MICROPYTHON_DIR="$PWD/vendor/micropython" \
PICOWARE_DESKTOP_SOURCE_ALIAS="$PWD/.build/desktop-source" \
  sh tools/micropython-desktop.sh
sh tools/run-micropython-desktop.sh --sim-check --network offline --audio silent
sh tools/run-micropython-desktop.sh --viewer --board picocalc-pico2w
```

Create `.build/` first if running the simulator build without a firmware build.
The simulator's initial SD tree uses synthetic network/settings fixtures. It is
for development and should never be copied to a device instead of `sd-card/`.

The source tree is checked separately with:

```sh
python3 tools/check-public-repo.py
```

Native code has host tests, and device-only C can be type-checked against the
real pico-sdk headers without the Arm toolchain:

```sh
sh src/MicroPython/gfx/tests/run-tests.sh
sh src/MicroPython/picosolve/tests/run-tests.sh
sh tools/check-device-syntax.sh
```

Release checksum generation covers `firmware/`, `sd-card/` and `verification/`;
it excludes local backups, personal SD trees and the Git database.

## Editing applications

Edit `builds/MicroPython/apps_unfrozen/`, then rerun the build script or compile
with the matching `.build/mpy-cross/mpy-cross`. Copy changed `.mpy` files and
their shared dependencies to the SD card. Firmware Python/native changes require
a new UF2. Ordinary app edits can be tested in the simulator first.

## v1.1 performance hardware test

The working source combines the final released v1.1 dashboard (238 × 238
widget canvas, centered logo and theme/status features) with native gfx,
SRAM/PSRAM image storage and dirty-row DMA presentation. The version stays 1.1;
keep hardware-test packages separate from the previous stable v1.1 release.

Use a fresh absolute build directory for this integration:

```sh
GUNGOS_BUILD_DIR="$PWD/.build/performance" sh tools/build-gungos-release.sh
python3 tools/verify-gungos-release.py
```

The build uses the bundled MicroPython/Pico SDK and picotool sources, an
installed Arm GNU compiler for the Pico 2 W, and a matching host mpy-cross for
SD apps. The macOS simulator is a separate native host build. A simulator
binary cannot be converted to the device UF2.

Default panel transfers remain 16-bit. The Benchmark SD app can temporarily
try 12-bit transfers and asks for a colour verdict. Device results are written
to `picoware/benchmark.txt`. The picosolve C kernel is preserved as source but
has no MicroPython binding and is not linked into this firmware.
