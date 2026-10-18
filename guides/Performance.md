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

Drawing uses the shared C gfx core, and presentation converts and sends only
changed rows through DMA. `draw.swap()` reports how many rows were sent.

The screen image lives in PSRAM by default. **System > Settings > Fast Drawing**
moves it to on-chip SRAM: drawing is about 2.5× faster, but the 102,400-byte
image comes out of the Python heap. Animated apps borrow SRAM only while open
by calling `view_manager.request_fast_drawing()` in `start`; the view manager
returns it when the view stops, including after a crash. Graph3D and Tetris do
this. If there is no free 100 KB block, the screen stays in PSRAM and the
Settings choice applies after a restart.

First device measurements (v1.1 performance test):

| | SRAM screen | PSRAM screen |
|---|---|---|
| Free heap | 266 KB | 366 KB |
| Whole screen sent | 23.2 ms | 25.4 ms |
| One text line changed | 0.46 ms | measured by the next benchmark |
| 150 shapes drawn | 11.4 ms | 27.8 ms |
| Python loop vs ulab (C) | 88× slower | |

The benchmark now measures sending and drawing in both modes, and restores
the mode it found.

Graph3D renders frames with `draw._mesh3d` (src/MicroPython/gfx/gfx_mesh.c):
projection, depth sort, clipping, shading and outlines in C. The simulator
test renders several views both ways and requires identical images when both
use the same 256-step colour table. The benchmark's "3-D plot frame" step
times the default surface with the Python and C renderers.

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

The built-in `picosolve` module provides the beam solver to Python (see
src/MicroPython/picosolve/README.md). The benchmark's "Beam solver" step builds
a 600-element continuous beam from Python and times solving it in double and
in single precision; those two numbers set the automatic precision threshold.

Plots compile the user's formula once with `picosolve.Formula` and evaluate
whole rows in C; their geometry is built in C too. Results are bit-identical
to Python's `eval` (tested on about 60,000 random evaluations and on every
Graph and Graph3D test plot); a formula the compiler cannot reproduce exactly
keeps using `eval`. The benchmark's "Formula compiler" step times three
formulas at 4096 points both ways, and its 3-D step builds an implicit sphere
in pure Python, with the C mesh builder, and with C mesh and formula.

Graph's curve, contour and shading loops run in C as well (`gfx/gfx_plot.c`,
`draw._plot_curve`, `_plot_segments`, `_stipple`), and the calculator's
integrals and equation solver use compiled formulas. The "Graph drawing" and
"Calculator" steps time each both ways. The benchmark also records the
processor clock (240 MHz in normal use, 200 MHz in the REPL and serial
terminal).

Full-screen benchmark samples now establish an untimed baseline and verify that
every timed swap sends all 320 rows. Each timing is paired with its own row
count. Earlier full-screen numbers may describe a partial initial update.
