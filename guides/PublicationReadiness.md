# Publication preparation — 6 November 2026

This record follows the [comparison audit](RepositoryAudit-2026-11-06.md) of
source commit `c25ae786f7627f3f1b38e92914ae89ab730bed45`. That audit is a dated
baseline; its failing-check results describe the pre-cleanup source.

## Changes

- Label the working source `1.36-dev`; retain the existing v1.35 tag unchanged.
- Align dashboard modal-help, PicoLAB hierarchy and StressStrain tab checks with current behavior,
  including Calculator check launch/return and focus preservation.
- Refresh the README, build/data preparation instructions, contributor workflow,
  Picoware attribution and earlier LofiFren-based legacy lineage.
- Index the pinned PNGdec inflater/zlib notices and classify imported/generated
  source for GitHub's code view. Preserve bundled build dependencies.
- Validate external dictionary data before compilation or replacement of SD
  output; keep generated firmware checksum sidecars outside tracked source.
- Use a standard app compilation stage for fixture-driven reader/calculator
  checks and include the additional checks in `tools/check-source.py` and CI.
- Fix a compressed-chapter replay allocation failure exposed by the existing
  160 KiB compiled-reader test: release optional RAM pages before reopening the
  inflater. The displayed page and SD cache remain intact; the heap limit was
  not raised. The standalone source/compiled replay check passes after the fix.
- Keep the legacy whole-chapter sample test at its 128/256 KiB heaps while
  releasing the preceding caller-owned text result before loading another one.
  Measure metadata retention after one warm-up load so compiled-module lazy
  initialization is not counted as a repeated-load leak; retain the 160 KiB heap
  and the existing growth threshold.

## Validation and publication status

The complete local source check passes: **54 validation steps**, covering all
90 simulator test scripts either directly or through their generated-fixture
drivers. This includes the 45-test canonical selected profile, source/compiled
reader and calculator checks, native graphics/solver/SD checks, artwork,
publication exclusions and device-only C syntax. The matching compiler and host
simulator were built from the pinned source before validation. A fresh Arm
firmware-only build also passes with Arm GNU Toolchain 15.3.Rel2 and CMake 4.4.4.

The GitHub [Source checks workflow](https://github.com/cmeboye/GungOS/actions/workflows/source-checks.yml)
uses macOS and the same entry point with `--build`, so it builds its own tools
from each checked-out source revision. Consult the workflow run for the latest
hosted result; a local result is not presented as a hosted result.

Physical-device qualification and a new stable binary release remain separate.
Keep firmware and SD apps together at the exact qualified source revision.

## History and provenance

The cleanup preserves development history and the existing v1.35 release tag.
The exact original Picoware import revision remains unrecorded; the dated
upstream comparison is not represented as a verified fork point.
Commit author identities in existing history are retained. New preparation
commits use the owner's GitHub noreply address.

The existing public project is preserved at original commit
`96ec62bf2304f73a7d3b62e77d3fdc398d622fe3`. A complete Git mirror and verified
restorable bundle were made before remote changes; the legacy tag is
[`legacy-2025-12-12`](https://github.com/cmeboye/GungOS/tree/legacy-2025-12-12).
The [legacy branch](https://github.com/cmeboye/GungOS/tree/legacy/lofifren) adds only
a short explanatory README; `master` and the tagged source are unchanged. The main source profile keeps its GPLv3/component notices,
while the earlier project's notices remain with that source.
