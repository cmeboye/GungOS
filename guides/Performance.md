# v1.1 performance hardware test

This build combines the final v1.1 desktop with the native display performance
changes. The device still reports v1.1; the hardware-test package has a separate
filename and directory so it cannot be mistaken for the previous stable build.

## Build on the development Mac

The build runs locally. Arm GNU GCC compiles C/C++ for the Pico 2 W's RP2350;
MicroPython freezes the firmware Python modules, CMake links the image, and
picotool produces the UF2. The matching host mpy-cross compiles the SD apps.
The macOS simulator is compiled separately and never converted into a UF2.

From the project root, with an Arm GNU Toolchain `bin` directory on PATH:

```sh
SOURCE_DATE_EPOCH=1792281600 GUNGOS_BUILD_DIR="$PWD/.build/performance" \
  sh tools/build-gungos-release.sh
python3 tools/verify-gungos-release.py
```

The script uses the pinned source dependencies already in `vendor/`. It produces
`firmware/GungOS-v1.1-PicoCalc-Pico2W.uf2`, `GungOS-v1.1-SD.zip`, clean `sd-card/`
contents and verification/checksum files. The version comes from
`src/MicroPython/picoware/system/features.py`. Use a fresh build directory when
changing source checkout or compiler installation.

## What to test

1. Back up the SD card. Merge the Apps Update archive's `picoware/` folder into
   the SD root, replacing matching app files. The update has no preferences,
   credentials, documents or audio; existing Tetris recordings are retained.
2. Flash the Performance Test UF2 through Pico 2 W BOOTSEL.
3. Check the logo, 238 × 238 widget, theme, saved Wi-Fi, app switching and Tetris.
4. Open **Apps > Misc > Benchmark**, press Enter. The 12-bit experiment is disabled
   by default; F2 on the start screen enables it explicitly. Results are saved to `picoware/benchmark.txt`.
5. Exercise the calculator, graphs and Lorenz widget, then restart the device
   and check settings persistence.

The default image lives in on-chip SRAM and costs 102,400 bytes. PSRAM mode can
release that buffer for larger workloads, at slower drawing speed. Drawing uses
the shared C gfx core, and presentation converts and sends only changed rows
through DMA. `draw.swap()` reports how many rows were sent.

Panel transfers default to 16 bits. The benchmark saves partial measurements between stages. If an enabled colour
test stops updating the display, press N to restore 16-bit mode. An unanswered
Y/N prompt also restores the format after 20 seconds, provided the app loop is
still running. The benchmark's 12-bit experiment sends 25%
less pixel data if the panel supports the format; its appearance and speed must
be judged on the physical device. Simulator timings do not measure Pico speed.

Recent connectivity work moves saved passwords from SD settings into the Pico's
internal flash. This is storage separation, not encryption; moving an SD card
to another device or returning to older firmware may require entering passwords
again. Existing settings, documents and audio should be retained during upgrade.

The picosolve C solver sources and host tests are preserved. They are not linked
into this UF2 because the MicroPython binding has not been implemented.

Full-screen benchmark samples now establish an untimed baseline and verify that
every timed swap sends all 320 rows. Each timing is paired with its own row
count. Earlier full-screen numbers may describe a partial initial update.
