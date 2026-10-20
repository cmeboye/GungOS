# Public repository review — 2026-10-18

This pass reviewed the local Git source repository and the history reachable
from its local refs. It did not add a remote, publish a release, rewrite history
or push anything. Generated device packages under `releases/` remain separate,
ignored build snapshots; the current source includes newer menu artwork.

## Source and repository layout

- Firmware/native source lives in `src/MicroPython/`; editable SD apps live in
  `builds/MicroPython/apps_unfrozen/`. Pinned dependencies and notices remain in
  `vendor/`. Builds use this checkout rather than another local GungOS copy.
- Current logos and the simulator screenshot are in `assets/logos/` and
  `assets/screenshots/`. Retired artwork is preserved in `assets/legacy/`.
  The current README preview uses synthetic status/resource values.
- Build outputs, release archives, private backups, host executables, SD/flash
  snapshots and locally supplied recordings stay outside Git. The public checker
  rejects these paths even when someone force-adds an ignored file.
- Binary attributes cover media, firmware and vendored binary fixtures so Git
  does not apply text line-ending conversion to those formats. Upstream sources
  and license notices are retained; this pass does not prune dependencies.
- Setup, simulator and installation guides describe v1.2 and the custom native
  desktop interpreter. A stock MicroPython executable is insufficient.

## Credential and history findings

The current Git-candidate scan found no unresolved common credential signatures.
A separate scan checked all **26 commits** reachable from local branches/tags
at the start of this pass, reading **17,006 unique blobs** (317,841,414 bytes).
It found no unresolved common token/key/literal-credential signatures or
private/generated paths. The scan enumerated every commit tree and read blob
contents through `git cat-file --batch`; reports contain paths/categories,
never matched credential values.

Public Mbed TLS/Pico SDK test keys, PEM-header constants and synthetic simulator
credentials remain documented fixtures. They are not device or release keys.
No history rewrite was necessary on the basis of these checks.

`python3 tools/check-public-repo.py` scans current tracked/unignored files; it
**does not audit history**. The history findings above are a dated review, not
an automatic guarantee for subsequent commits. Git reflogs, unreachable objects,
remote-only refs and secret formats outside the checked signatures were not
covered. Ignored private files remain on disk and were not scanned for publishing.

## Validation

From the repository root:

```sh
python3 tools/check-public-repo.py
python3 tools/tests/test_public_repo.py
```

The host-only public-check regressions cover ignored files, force-tracked private
paths, flash snapshots, generated SD settings, Finder metadata, permitted public
templates, missing tracked files, credential redaction and upstream test fixtures.
First-party Markdown links and packed logo/source consistency were also checked.

This source/packaging review does not establish hardware behaviour, certify all
third-party licenses or detect every possible secret. Existing UF2/SD packages
were not rebuilt. Review new release artifacts separately and keep their matching
source revision and notices. Do not upload an unfiltered ZIP of the local working
directory: ignored backups, personal data and local media are still present.

## Licenses and optional media

The Picoware-derived software remains GPLv3; component-specific licenses and
notices are retained in `LICENSE`, `CREDITS.md` and `THIRD_PARTY_NOTICES.md`.
The root license does not override a dependency's own terms.

Original Game Boy Tetris recordings have no redistribution grant recorded here.
They remain excluded from Git and default generated packages; optional sound
requires the user's own appropriately licensed assets. Code attribution is
preserved. This review does not grant rights to media or trademarks.
