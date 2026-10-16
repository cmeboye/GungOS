# Public repository review — 2026-10-16

The first public source push can use the tracked/unignored source tree after
`python3 tools/check-public-repo.py` passes. This review did not create a remote,
commit or push. There was no Git repository/history at the start of the review.

## Changes

- Stronger Git exclusions protect local SD snapshots, credentials/documents in
  private backups, host executables, compiled MPYs/UF2s, generated ZIPs and logs.
- Original recordings, old SD archives, generated checksum inventories and raw
  build reports are preserved under ignored `local-backup/` paths.
- Original Game Boy Tetris recordings have no redistribution license recorded
  here. They and their converted WAVs are excluded from the public source and
  default packages. Local sound files remain available; opt-in packaging requires
  the user to have suitable permissions.
- Audio tests generate their own waveforms. Tetris remains usable without
  optional sound files, and clean builds disable sound when no audio is packaged.
- README, build/development instructions, contribution notes, changelog and a
  simulator screenshot describe the source project. Artwork is grouped in assets.
- GPLv3, upstream credits and third-party source/license notices are preserved.
  Third-party dependencies remain pinned for offline builds.

## Credential findings

No unresolved common credential signatures were found in the Git candidate
files. Test passwords in simulator tests are synthetic. The pinned Mbed TLS and
Pico SDK sources contain upstream public test/example keys and PEM-header
constants; these are documented fixtures, not device signing keys. The audit
reports locations/categories and never prints matched credential values.

The checker also catches an ignored file if it has already been added to Git.
It rejects private/generated candidate paths, common service-token signatures,
unreviewed first-party audio/binaries, missing license provenance and files over
the project's 50 MiB review limit.

## Validation and limits

A clean export of only Git candidate files was used to compile all 60 apps
without private recordings. The audio test, Eggcel revision test and game/demo
checks run against that export. Default generated app archives contain no Tetris
recordings; explicit local-audio opt-in retains the ten-file package.

This is a source/packaging review and common-pattern scan. It does not establish
hardware behaviour, audit a future Git history, catch every possible secret, or
grant rights to third-party media or trademarks. Preserve the component notices
and review any future release binaries/archives separately. Do not publish an
unfiltered ZIP of the local working directory: ignored files are still on disk.

GPLv3 source/notice terms: https://www.gnu.org/licenses/gpl-3.0.html
