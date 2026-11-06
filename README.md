# GungOS

[![Source checks](https://github.com/cmeboye/GungOS/actions/workflows/source-checks.yml/badge.svg?branch=main)](https://github.com/cmeboye/GungOS/actions/workflows/source-checks.yml)

A handheld engineering computer for **PicoCalc with Raspberry Pi Pico 2 W**.
By Cem Gungor, based on [Picoware by jblanked](https://github.com/jblanked/Picoware).

![GungOS desktop in the simulator](assets/screenshots/desktop.png)

*Simulator preview; status and resource figures are simulated.*

## Development status

The current source is **1.36-dev**, an unreleased development version. It includes
reader, image-decoding and calculator changes beyond the tagged
[v1.35 device-test release](guides/Release-v1.35.md). Physical qualification of a
new matching firmware/SD build is pending. See the [changelog](CHANGELOG.md) for
changes and the [publication record](guides/PublicationReadiness.md) for validation.

## What it includes

- **PicoLAB:** a scientific calculator with statistics, solvers, complex/Base-N/matrix
  modes, 2D/3D Grapher, PicoCAD, BeamView, Mohr circles, shrink fit, stress/strain,
  buckling, section properties, Heat transfer 2D and PicoSpice. Native picosolve
  and float32 ulab support the numerical tools. Dynamics and Fluids are planned.
- **PicoDESK:** Eggcel spreadsheets and charts, PicoWord notes/equations, PicoPaint,
  offline English/Italian PicoDict and EPUB/TXT PicoReader. Reader image, MathML
  and navigation support has documented limits in the [reader guide](guides/PicoReader.md).
- **Desktop and system:** themes, resource indicators, a calculator widget,
  Lorenz/Lenia screensavers, Tetris, SD file management, PicoIDE, Wi-Fi, Bluetooth
  and USB tools.

This source profile targets PicoCalc with **Pico 2 W**. Other Picoware boards,
its app store/OTA updater and several other upstream features are outside this
profile; arbitrary upstream applications are not guaranteed compatible.

## Build and install

Start with [BUILD.md](BUILD.md). It covers host requirements, the optional-data
preparation step, firmware/SD builds and source checks. [START-HERE.md](START-HERE.md)
explains the source layout and application workflow.

Build dependencies are pinned and bundled in `vendor/` so compilation works
offline. They account for most repository size and retain their upstream notices.
The full SD package also needs separately prepared PicoDict data; the build
checks for it before compiling. Generated UF2/MPY files, SD ZIPs and local backups
are excluded from Git. Reviewed binaries belong in GitHub Releases with their
matching source revision.

After building a matching firmware/SD set:

1. Back up the SD card. Copy the generated `sd-card/` contents onto a fresh
   writable FAT32 card, or merge updated app files while retaining user data.
2. Put the **Pico 2 W** into BOOTSEL mode and copy the generated
   `firmware/GungOS-v1.36-dev-PicoCalc-Pico2W.uf2` onto its bootloader drive.
3. Insert the SD and reboot. Configure Wi-Fi under Comms → Wi-Fi → Scan.

Ordinary SD app changes can use matching `.mpy` replacements. Native code,
firmware Python and font changes require a new UF2.

## Simulator and checks

Build the custom host interpreter as described in [BUILD.md](BUILD.md), then run:

```sh
sh tools/run-micropython-desktop.sh --viewer --board picocalc-pico2w
```

`Start Simulator.command` is a macOS convenience launcher. SDL2 enables viewer
and audio support; tests run offline with silent/dummy audio. The GitHub source
workflow uses the same entry point as local validation:

```sh
python3 tools/check-source.py --build
```

Host checks do not establish physical-device speed, available heap or keyboard behavior.

## Controls and guides

Escape closes the innermost help/edit/view. Back and Del erase before the cursor.
F6–F10 use Shift+F1–F5 on PicoCalc. Alt+S saves a screenshot.

[Desktop](guides/Desktop.md) · [Controls](guides/Keys.md) · [Themes](guides/Themes.md) ·
[PicoLAB](guides/PicoLAB.md) · [Calculator](guides/ScientificCalculator.md) ·
[Grapher](guides/Grapher.md) · [PicoCAD](guides/PicoCAD.md) ·
[PicoDESK](guides/DesktopApps.md) · [Eggcel](guides/Eggcel.md) ·
[PicoReader](guides/PicoReader.md) · [PicoDict](guides/PicoDict.md) ·
[Tetris](guides/Tetris.md) · [Comms](guides/Comms.md) ·
[Performance testing](guides/Performance.md)

## Origins, license and legacy

The current firmware is based on **Picoware by jblanked** and retains its **GPLv3**
license and source notices. See [credits](CREDITS.md), [LICENSE](LICENSE) and
[third-party notices](THIRD_PARTY_NOTICES.md). The exact initial Picoware import
commit was not recorded; the [comparison audit](guides/RepositoryAudit-2026-11-06.md)
identifies verified reference snapshots and explains the uncertainty.

The earlier GungOS project was based on [LofiFren/PicoCalc](https://github.com/LofiFren/PicoCalc).
It is preserved separately on the [legacy branch](https://github.com/cmeboye/GungOS/tree/legacy/lofifren).

Original Game Boy Tetris recordings are excluded from public source and default
packages. Tetris works without them; optional sound requires suitably licensed
assets. See [audio setup](guides/TetrisAudio.md).

[Contributing](CONTRIBUTING.md) · [Public repository review](verification/public-review.md)
