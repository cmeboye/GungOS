# Working on GungOS

This is the GungOS v1.33 source tree with the matching firmware and SD application updates.
Use this checkout as the project root. The source and pinned dependencies do
not require another GungOS copy or a sibling MicroPython checkout.

| Location | Purpose |
|---|---|
| `src/MicroPython/` | Firmware Python and native modules |
| `builds/MicroPython/apps_unfrozen/` | Editable application sources |
| `vendor/` | Pinned upstream sources and their notices |
| `simulator/`, `tools/`, `guides/` | Development tools, checks and documentation |
| `assets/logos/`, `assets/screenshots/` | Current branding and simulator preview |
| `assets/legacy/` | Retired artwork retained for reference |
| `releases/` | Ignored, versioned local release snapshots |
| `drafts/engineering-tools/` | Planned modules, outside the shipped app set |
| `firmware/`, `sd-card/` | Generated device files after a build |

`local-backup/`, host executables, compiled apps and generated archives are local
only and ignored by Git. The original recordings are preserved under
`local-backup/audio-originals/`. Existing local SD audio is unchanged.

## Develop an application

Edit the `.py` files under `builds/MicroPython/apps_unfrozen/`. Run the simulator
through `Start Simulator.command` on macOS, or see [BUILD.md](BUILD.md) to build
the custom host interpreter on macOS or Linux.

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

Git tracks the source; generated releases and private backups remain ignored.
Check `git status` before committing and `git remote -v` before pushing. The
checker scans current tracked/unignored files; it does not inspect commit history
or certify every third-party asset. The dated [public review](verification/public-review.md)
records the separate history scan and its limits.

Do not upload the local directory as an unfiltered ZIP: it contains ignored
private backups and locally supplied media. Publish Git contents or a reviewed
release. Existing files under `releases/` are build snapshots; source commits
do not update them. Rebuild after firmware, font or branding changes and keep
the resulting UF2, SD package and source revision together.
