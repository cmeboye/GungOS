# Building GungOS

This branch builds **1.36-dev**, an unreleased development version. The existing
v1.35 tag and its [device-test notes](guides/Release-v1.35.md) describe an earlier
snapshot. Current native/image changes require rebuilding firmware as well as
the SD apps. Physical qualification of the resulting set remains pending.

## Host requirements

- Python 3, Make, CMake, a host C/C++ compiler and Arm GNU Toolchain
  (`arm-none-eabi-gcc`, `arm-none-eabi-g++`, binutils).
- The historical v1.35 build used Apple Silicon, Arm GNU Toolchain 15.3.Rel2
  (GCC 15.3.1) and CMake 4.4.4. Install the toolchain separately and put its
  `bin` directory on PATH.
- SDL2 for simulator viewer/audio and the full host check suite; Pillow for
  artwork checks and generated image test fixtures. Firmware compilation does
  not require them. ffmpeg is only needed to prepare optional local recordings.
- Clang for `tools/check-device-syntax.sh` (type checking against real SDK headers).

## 1. Prepare dictionary data for a full SD package

The source includes PicoDict code but not its generated dictionary data or raw
SQLite inputs. Obtain the two WikDict developer databases and follow
[PicoDict.md](guides/PicoDict.md), including its attribution and license terms:

```sh
python3 tools/build-dictionary.py --en-it /path/en-it.sqlite3 --it-en /path/it-en.sqlite3
python3 tools/check-build-inputs.py
```

This creates the ignored `builds/MicroPython/PicoDict-data.zip`. The input hashes,
converted-data hashes and CC BY-SA 4.0 attribution are retained in its manifest
and notice. Once prepared, compilation and packaging use local files and do not
fetch dependencies. Original reader samples are generated during packaging.
The full build validates dictionary contents before compiling; direct packaging
validates them before replacing any generated SD output.

## 2. Build firmware and the clean SD package

```sh
sh tools/build-gungos-release.sh
python3 tools/verify-gungos-release.py
```

Outputs for the current development identity:

- `firmware/GungOS-v1.36-dev-PicoCalc-Pico2W.uf2`
- `sd-card/` and `GungOS-v1.36-dev-SD.zip`
- `verification/build-info.json`, firmware ELF/map and `SHA256SUMS.txt`

The RP2350 build targets Pico 2 W's 4 MiB flash and reserves 2,048,000 bytes for
the internal filesystem. Editable applications compile to SD `.mpy` files.
Intermediates live in `.build/`; set `GUNGOS_BUILD_DIR` to an absolute path for
a separate build and `PICOWARE_BUILD_JOBS` to control parallelism (default eight).

For a firmware-only build that does not require dictionary data:

```sh
GUNGOS_SKIP_PACKAGE=1 sh tools/build-gungos-release.sh
```

That stops after the native build; its UF2 is under `.build/rp2/firmware.uf2`
(or the selected build directory). It does not produce a clean SD package.

Pinned source identities are in `vendor/revisions.json`; the recorded MicroPython
patch is already applied in `vendor/micropython-local.patch`. No submodule fetch
is needed. `SOURCE_DATE_EPOCH` defaults to 3 November 2026 UTC for reproducible
build timestamps; compiler/toolchain changes can still change checksums.
The adapter keeps a known GCC 15 Mbed TLS array-bounds diagnostic as a warning
for `aes.c`/`gcm.c` only; it does not relax firmware-wide `-Werror`.

## 3. Build and run the simulator

```sh
mkdir -p .build
MICROPYTHON_DIR="$PWD/vendor/micropython" \
PICOWARE_DESKTOP_SOURCE_ALIAS="$PWD/.build/desktop-source" \
  sh tools/micropython-desktop.sh
sh tools/run-micropython-desktop.sh --viewer --board picocalc-pico2w
```

Use the bundled source and this custom interpreter; stock MicroPython lacks the
native modules. The simulator's SD/flash data is synthetic development state and
is not a deployment package. The simulator build is separate from an Arm UF2.

## 4. Validate source before publishing

Install SDL2 and Pillow in the host environment, then run:

```sh
python3 tools/check-source.py --build
```

The same command runs in GitHub Actions on macOS. It builds a fresh matching
compiler and simulator, compiles every shipped application, checks publication
candidates/artwork/native code, runs the canonical simulator self-check and
dispatches the additional calculator/reader tests through their fixture drivers.
The tests include source and compiled application paths. Each step is logged
under `.build/source-checks/`; a failing step stops the run. Dictionary data,
personal books and original audio recordings are not needed for source checks.
Some legacy test outputs use `/private/tmp`, so the complete suite currently
expects the macOS temporary-directory layout. Firmware/simulator builds also
support Linux; a Linux CI job is not claimed by this workflow.

The quick publication checks remain:

```sh
python3 tools/check-public-repo.py
python3 tools/tests/test_public_repo.py
```

These inspect current Git candidates, not all history. See the dated
[publication audit](guides/RepositoryAudit-2026-11-06.md) and
[current validation record](guides/PublicationReadiness.md).

## Application edits, release files and device checks

Edit `builds/MicroPython/apps_unfrozen/`, then compile with the matching
`.build/mpy-cross/mpy-cross`. Replace changed `.mpy` files and shared dependencies
on the SD card; preserve documents/settings. Firmware Python, native and font
changes need a new UF2. Default packages omit optional Tetris recordings; see
[audio setup](guides/TetrisAudio.md) for preparation of suitably licensed files.

Publish reviewed artifacts with their source revision, notices and checksums.
Existing ignored `releases/` snapshots do not update when source changes. Keep
the v1.35 tag fixed and choose a final new release identity before qualification.
Host validation does not replace testing that exact firmware/SD set on PicoCalc.

Historical rendering/core benchmarks and the optional 12-bit display experiment
are described in [Performance.md](guides/Performance.md) and
[EngToolBenchmark.md](guides/EngToolBenchmark.md). They are not new measurements
of this development build; default panel transfers remain 16-bit.
