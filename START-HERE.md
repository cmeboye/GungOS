# Working on GungOS

This is the GungOS v1.1 source tree with the latest SD-only Eggcel revision.
The complete source and pinned dependencies stand independently of Picoware-main.

| Location | Purpose |
|---|---|
| `src/MicroPython/` | Firmware Python and native modules |
| `builds/MicroPython/apps_unfrozen/` | Editable application sources |
| `vendor/` | Pinned upstream sources and their notices |
| `simulator/`, `tools/`, `guides/` | Development tools, checks and documentation |
| `assets/` | GungOS artwork and desktop screenshot |
| `drafts/engineering-tools/` | Planned modules, outside the shipped app set |
| `firmware/`, `sd-card/` | Generated device files after a build |

`local-backup/`, host executables, compiled apps and generated archives are local
only and ignored by Git. The original recordings are preserved under
`local-backup/audio-originals/`. Existing local SD audio is unchanged.

## Develop an application

Edit the `.py` files under `builds/MicroPython/apps_unfrozen/`. Run the simulator
through `Start Simulator.command` on this Mac, or see [BUILD.md](BUILD.md) to build
a host interpreter on another computer.

Compile the SD apps with a matching `mpy-cross`:

```sh
python3 tools/compile-engineering-apps.py \
  --mpy-cross "$PWD/.build/mpy-cross/mpy-cross" \
  --snapshot "$PWD/sd-card/picoware/apps"
```

This creates app ZIPs under `builds/MicroPython/`. The local macOS compiler may
also be available at `host-tools/macos-arm64/mpy-cross`. Exit apps and restart
GungOS after replacing `.mpy` files to unload cached modules. Preserve device
documents and settings when merging app updates.

Default packaging omits optional audio. `--include-local-audio` is an explicit
opt-in for files you are entitled to redistribute; [audio notes](guides/TetrisAudio.md)
explain preparation. Firmware, native modules, fonts and global menus require
[rebuilding the UF2](BUILD.md).

## Before publishing

Run `python3 tools/check-public-repo.py`. It checks the Git candidate files, not
just whether local files exist. It also checks tracked files if a repository has
been initialized, so a newly ignored tracked file is still reported.

There is no Git history or remote in this prepared directory. The checker does
not inspect future commits or certify every third-party asset. Do not upload
the entire local directory as an unfiltered ZIP: it includes ignored private
backups and locally supplied media. Publish the Git contents or a reviewed release.
