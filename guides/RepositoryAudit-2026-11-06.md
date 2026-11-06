# GungOS: Picoware comparison and publication audit

**Audit date:** 6 November 2026 (Europe/Rome)

**Scope:** the current local Git source, its reachable history, two pinned Picoware snapshots, and the existing public GungOS repository. This is an audit and publication plan; it does not publish or rewrite either repository.

This is the **pre-cleanup baseline** at the pinned source revision below.
Subsequent fixes, validation and publication are recorded in
[PublicationReadiness.md](PublicationReadiness.md).

## 1. Assessment

GungOS is a substantial PicoCalc engineering-focused derivative of Picoware. It retains Picoware's MicroPython/device foundation while replacing much of the desktop, application selection, numerical tooling and release workflow. The existing GitHub GungOS project is the earlier, separate LofiFren-based project described by the owner; it should be preserved explicitly as legacy.

The current source already has useful publication hygiene: GPL text and credits, component notices, pinned dependencies, source/build separation, private-data exclusions, a publication checker and extensive host checks. No unresolved common credential signatures or private/generated publication paths were found in the checked current source or reachable local history.

**Recommended status: publication candidate, with a small corrective pass before calling it a clean release.** Two selected simulator tests fail on a fresh source export. Both conflict with newer behavior already visible in the source or controls guide. They need reconciliation and a complete rerun. The principal documentation gaps are an unrecorded exact Picoware fork point, incomplete top-level PNG dependency attribution, and development changes still carrying the v1.35 identity.

No source cleanup, deletion, history rewrite, remote reconfiguration, commit, tag, push or GitHub branch change was performed. The report itself is the only intended addition to the working project. Build and test activity used a disposable export of tracked source.

## 2. Pinned comparison points and ancestry limits

| Project / reference | Exact commit | Meaning |
|---|---|---|
| Local GungOS `main` | `c25ae786f7627f3f1b38e92914ae89ab730bed45` | Audited source; commit dated 3 November 2026 |
| Local initial recorded snapshot | `3b5c3b512729d7e4169ece79760aff8f639cb166` | Root commit dated 16 October 2026; already a customized GungOS snapshot |
| Local `v1.35` peeled tag | `bff86370f8f1fc54f182ca918e27ef91c2f87529` | Earlier matching firmware/SD device-test release |
| [Picoware current `main`](https://github.com/jblanked/Picoware/commit/8915fbe7b68059f96e4f99730ad3383da7a77a38) | `8915fbe7b68059f96e4f99730ad3383da7a77a38` | Public upstream tip observed on audit day; commit dated 4 November 2026 |
| [Picoware dated reference](https://github.com/jblanked/Picoware/commit/c2d229340102abc7013e7cc0d2d8f6466bee1b97) | `c2d229340102abc7013e7cc0d2d8f6466bee1b97` | Latest upstream commit returned by GitHub's commit API before the local root commit timestamp; 16 October 2026 |
| [Existing public GungOS `master`](https://github.com/cmeboye/GungOS/commit/96ec62bf2304f73a7d3b62e77d3fdc398d622fe3) | `96ec62bf2304f73a7d3b62e77d3fdc398d622fe3` | Legacy project; one root commit, dated 12 December 2025 |

The local repository has **62 reachable commits**, local tags `v1.0` and `v1.35`, a clean working tree at the start of this audit, and **no configured remote**. Picoware's original history is not retained as ancestry: the local root is a standalone snapshot. Neither a merge base nor an exact original Picoware import revision can be established from that history. The dated reference above is a comparison anchor, **not a verified fork point**.

Consequently, differences against current Picoware include both GungOS customization and upstream work after the import. A missing upstream path does not prove it was deleted locally; it could have appeared upstream later. A GungOS-only path does not prove original authorship: bundled dependencies and reorganized files also appear that way. The initial local snapshot does not establish when all customization began.

The existing public GungOS repository currently exposes only `master`, with no tags. Its 37 tracked files include `boot.py`, `modules/`, `picocalcdisplay/`, `vtterminal/`, `sd/` and `Client_Code/`. It has no root README or LICENSE. No file has byte-identical content to a tracked file in the current local project; that observation does not exclude adaptation or shared third-party ancestry. The owner's stated earlier lineage is [LofiFren/PicoCalc](https://github.com/LofiFren/PicoCalc).

## 3. Quantitative differences

Counts below compare recursive Git trees by exact repository-relative path and Git blob identity. Ignored working files are excluded. Content changes and path presence are counted separately; similarity-based rename detection is not used.

| Metric | Current Picoware | Dated Picoware reference | Current GungOS |
|---|---:|---:|---:|
| Tracked files | 4,074 | 3,949 | 17,888 |
| Uncompressed tracked blob bytes | 271,710,112 | 264,367,242 | 326,584,998 |
| Approximate uncompressed size | 259.12 MiB | 252.12 MiB | 311.46 MiB |

| Relationship to GungOS | Current Picoware | Dated Picoware reference |
|---|---:|---:|
| Same path, identical content | 131 | 137 |
| Same path, different content | 127 | 123 |
| Paths present only in GungOS | 17,630 | 17,628 |
| Paths present only in Picoware | 3,816 | 3,689 |

The apparent increase is dominated by **17,012 files / 318,227,167 bytes in `vendor/`**: 95.1% of tracked paths and 97.4% of tracked bytes. Outside `vendor/`, GungOS has **876 files / 7.97 MiB**. Against current Picoware, **618 GungOS-only paths are outside `vendor/`**; some of those are also imported libraries or generated source tables. These numbers are not a measure of newly authored code.

Since the initial local GungOS snapshot, 202 shared paths have different content, 401 paths have been added and 88 old paths are absent. Another 17,285 paths are byte-identical. This local-history comparison captures later development, but not the customization already present in the root snapshot.

Both upstream snapshots contain `GroceryCompanion.py` and `groceryCompanion.py` in the same directory. These collide on the audit machine's case-insensitive filesystem. Comparisons therefore use Git objects, not the checked-out upstream files. The local GungOS tree has no case-folded path collisions, symlinks or Git submodule entries.

## 4. What changed from Picoware

| Area | Observed GungOS difference | Main evidence in the local tree |
|---|---|---|
| Hardware and product scope | A selected PicoCalc + Raspberry Pi Pico 2 W profile instead of upstream's broad board collection. The host simulator remains supported. Other hardware targets and CircuitPython/SDK application trees are absent from this source profile. | `README.md`, `src/MicroPython/picoware/system/boards.py`, `src/MicroPython/PicoCalc/picoware_modules.cmake` |
| Desktop and branding | GungOS artwork, compact resource header, category sidebar, 238 × 238 widget area, theme/accent settings and modal help. Original fonts are preserved alongside the Spleen replacement workflow. | `src/MicroPython/picoware/gui/dashboard.py`, `style.py`, `status_bar.py`; `assets/`; `tools/convert-spleen-fonts.py` |
| Application selection | PicoDESK and PicoLAB organize the shipped apps. Upstream's OTA updater, app store, AI agent, email, USB video, Game Boy engine and C/JavaScript/MMBasic support are excluded from this selected firmware. Wi-Fi, Bluetooth, USB tools, file management and PicoIDE remain. Compatibility with arbitrary upstream apps should not be implied. | `src/MicroPython/picoware/system/features.py`, `picoware/applications/library.py`, `simulator/test_trimmed_firmware.py` |
| Scientific calculation | Shared calculator workspaces for Calculate, Statistics, Solver, Complex, Base-N and Matrix; structured expressions, reductions, scientific functions, numerical reliability work and a device report. | `builds/MicroPython/apps_unfrozen/engtools/calculator/`, `engtools/numerics/`, `engtools/bench/calculator.py` |
| Engineering tools | BeamView with beams/plane frames, Mohr circles, shrink fit, stress/strain, buckling, section properties, 2D heat transfer, direct-geometry PicoCAD, unit conversion and PicoSpice circuits. Dynamics/Fluids menu entries are explicitly planned placeholders. | `builds/MicroPython/apps_unfrozen/PicoLAB.py`, `engtools/`, `guides/PicoLAB.md` |
| Native numerical kernel | A 32-file `picosolve` source subtree supplies beam/frame solving, circuit analysis, expression evaluation and plotting geometry. Float32 ulab is separately bundled and configured. | `src/MicroPython/picosolve/`, `src/MicroPython/ulab/`, `vendor/revisions.json` |
| Plotting and graphics | Graph/Graph3D are heavily revised and fronted by a shared Grapher. Native drawing, plot/mesh work, framebuffer memory modes and changed-row LCD transfers support the selected apps. | `Graph.py`, `Graph3D.py`, `Grapher.py`, `engtools/plots/`, `src/MicroPython/gfx/`, PicoCalc LCD/PSRAM source |
| PicoDESK | Eggcel spreadsheet/formulas/charts, PicoWord notes/equations, PicoPaint, offline English/Italian PicoDict and EPUB/TXT PicoReader. Reader source includes bounded streaming, chapter navigation, images and MathML layout with documented limits. | `builds/MicroPython/apps_unfrozen/desktopapps/` (29 files), top-level app launchers, corresponding guides |
| Images and reader support | New native PNG parsing/compositing with a pinned PNGdec inflater fork; revised JPEG output/lifecycle and bounded compressed reads. These changes include firmware code, not just SD apps. | `src/MicroPython/png/`, `src/MicroPython/jpeg/`, `src/MicroPython/picoware/gui/jpeg.py`, `gui/png.py` |
| Games and screensavers | A selected Tetris game, Lorenz/Lenia screensavers and calculator widget. Optional supplied Tetris recordings are excluded from tracked source/default packages; PCM software and conversion tools remain. | `games/Tetris.py`, `misc/screensavers/`, `src/MicroPython/pcm/`, `guides/TetrisAudio.md` |
| Lifecycle, data and reliability | SD-app unloading, resource reporting, crash reporting, internal-flash credential storage and FAT32/SD changes with host regressions. Internal flash storage is not encryption and remains readable through device access. | `system/app_loader.py`, `system/secrets.py`, `system/resource_info.py`, `src/MicroPython/sd/`, relevant simulator tests |
| Build and testing | Bundled pinned MicroPython/Pico SDK/picotool dependencies, a recorded MicroPython patch, matching app compilation, clean SD packaging, release verification, native checks and a specialized simulator. | `vendor/`, `BUILD.md`, `tools/build-gungos-release.sh`, `tools/verify-gungos-release.py`, `simulator/` |

The complete local application source comprises 154 Python modules compiled successfully during this audit. `engtools/` contains 109 tracked files. The tree also includes 90 `simulator/test_*.py` files and 11 files under `tools/tests/`; file counts do not imply that every test was run.

### What remains recognizably upstream

The MicroPython/PicoCalc hardware foundation, keyboard/display/PSRAM interfaces, view/app-loading architecture, storage/network utilities and many GUI/native components remain Picoware-derived, even when modified. Examples of exact unchanged upstream content include the root GPL license, native `response`, `vector` and `vt` files, numerous simulator hardware adapters and most of the bundled JPEGDEC source. GungOS attribution should describe it as based on Picoware, credit jblanked prominently, and preserve component/source notices.

## 5. Publication hygiene findings and recommended actions

### Resolve before presenting the next build as a clean release

1. **Reconcile two reproducible selected-profile test failures.** The documented `--sim-check` stops at `simulator/test_dashboard_layout.py:122`. Its F9 → Escape sequence expects `home.focus == 'menu'`, while `guides/Keys.md:90` says closing help restores focus and the calculator closes its own modal help first. A standalone rerun fails at the same assertion. Separately, `simulator/test_picolab_hierarchy.py:38` expects only Numerics check and Plot previews, but `PicoLAB.py` now also contains Calculator check. These are evidenced expectation mismatches; the audit did not change app behavior or tests. Update the expectations and any dependent indices, verify the intended interactions, then rerun the full canonical self-check rather than skipping failures.

2. **Separate unreleased source from the v1.35 release.** HEAD differs from the peeled `v1.35` tag in 110 files, with 13,724 insertions and 755 deletions in Git's diff summary. It includes native PNG/JPEG/PSRAM work, new reader navigation/math and calculator changes. `features.py` still reports 1.35; `README.md` and the main build guide lead with that version. Keep the existing v1.35 tag fixed, clearly label the current branch as development, and choose a distinct next release identity when qualifying it. A current-source build cannot be assumed to match existing v1.35 artifacts or to require only an SD update. `CHANGELOG.md` already has an Unreleased section to build on.

3. **Complete the top-level provenance index.** `src/MicroPython/png/upstream/SOURCE.md` already pins PNGdec commit `2855e785bc1a80763c89a2afd808faf6156d35c6`, records its local inflater change, and preserves its repository license and per-file zlib notices. Add this component and those notice locations to `THIRD_PARTY_NOTICES.md`; it is currently absent there and from the central revisions index. Preserve both the repository license and the notices in the actual inflater sources. Record Picoware's exact original import revision if reliable evidence can be recovered; otherwise retain the explicit uncertainty and dated reference in this audit. Do not substitute a guessed fork commit.

4. **Refresh the dated publication evidence.** `verification/public-review.md` is a review dated 18 October and refers to 26 commits and older release/setup text. It correctly says its history result is dated, but it should link to this 62-commit audit and the next successful validation pass. Avoid a new blanket "all checks passed" statement while the two failures remain.

### Improve before the first public source handoff

| Finding | Evidence / implication | Recommended bounded change |
|---|---|---|
| Dictionary input is external to Git | `BUILD.md` discloses the requirement; `finalize-gungos-release.py` opens the ignored `PicoDict-data.zip` whenever PicoDict source exists. A plain clone cannot produce the full SD package without preparing that data. | Present "obtain dictionary inputs" then "offline build" as two explicit phases. Fail early with a clear missing-input message before compiling firmware; optionally support a documented app-only/data-free package. Preserve WikDict source/output hashes and CC BY-SA attribution. |
| No project-owned CI workflow | No root `.github/` workflow is tracked. Existing check scripts require manual invocation. | Add a small CI job for the public checker and its six regressions, source app compilation and native tests; add simulator checks after resolving the two known failures. Ensure recent reader/calculator tests have an explicit validation route: the selected profile's 45-test list does not include all 90 simulator test files. |
| Commit author metadata warrants an owner decision | Four of the 62 commits use a local-host author email rather than a public identity. This is metadata, not a discovered credential. | Inspect author/committer identities before the first push. Keeping them is valid; if privacy changes are desired, decide before public history is established and preserve backups. No rewrite is justified merely by the signature scan. |
| Documentation mixes historical and current instructions | `BUILD.md` contains a v1.2 performance section that still says the release version is 1.2. The README carries several paragraphs of old release narrative. `guides/Release-v1.35.md` is useful historical release documentation but does not describe every HEAD feature. | Keep one current quick start and development status near the top. Move or label historical build/performance material and link old release notes instead of repeating them in the landing page. |
| Isolated generated checksum in the source tree | `firmware/GungOS-v1.34-Spleen-PicoCalc-Pico2W-2026-11-03.sha256` is tracked, while the matching UF2 is ignored. | Move the checksum with its matching reviewed release asset, or explicitly explain why this historical checksum belongs in source. Do not silently regenerate or pair it with a different binary. |
| Large bundled dependency surface | `vendor/` accounts for 97.4% of bytes, including other-board examples, test keys and binary/tool documentation. The largest tracked blob is about 16.77 MiB. | Keep the pinned dependency closure for the first publish. Explain it in the README. Treat pruning as a separate build-verified project; do not delete public test fixtures or license files merely to make the tree smaller. |
| GitHub code presentation | Imported code also exists outside the conventional `vendor/` directory. The current attributes handle binary/text conversion but have no explicit Linguist overrides. | Optionally mark JPEGDEC, ulab upstream and PNGdec upstream paths as vendored, and committed generated font/logo tables as generated where appropriate. Keep handwritten wrappers visible. See [Linguist's official override documentation](https://github.com/github-linguist/linguist/blob/main/docs/overrides.md). |
| Legacy identity is not yet documented in the public repo | The public legacy tree has no README or root LICENSE. The current local `CREDITS.md` explains Picoware, but not the earlier project's place in the history. | Add a concise lineage/legacy explanation during migration, credit LofiFren for the earlier project, preserve existing notices, and keep the new Picoware-derived project's licensing distinct. Do not infer licensing rights from the shared GungOS name. |

### Existing hygiene to retain

- Keep `LICENSE`, `CREDITS.md`, `THIRD_PARTY_NOTICES.md`, component notices and `vendor/revisions.json`.
- Keep current private/generated exclusions: `.build/`, `local-backup/`, `SD contents/`, simulator SD/flash state, generated MPY/UF2/ZIP files, local releases, editor state and optional recordings. Their on-disk presence is not itself a Git publication defect.
- Publish tracked Git contents or specifically reviewed release assets. The raw working directory contains ignored private files and is not a suitable upload bundle.
- Keep application source at `builds/MicroPython/apps_unfrozen/` for this pass. Its name can be explained; renaming it now would touch build, simulator and packaging paths without helping the provenance audit.
- Preserve the distinction between working source, dated release packages, host simulation and physical-device qualification. Existing hardware milestone notes are not a new qualification result for the audited HEAD.

## 6. Checks performed and their limits

| Check | Result |
|---|---|
| Current tracked/unignored publication candidates | PASS: 17,888 files; official checker reports no issues and recognizes 9 upstream/synthetic fixture paths |
| Public-check regression tests | PASS: 6 tests |
| Reachable local history | 62 commits; 17,827 unique blobs; 328,712,083 bytes read; no private/generated paths or blobs above the project's 50 MiB threshold |
| History credential signatures | Two literal-credential matches in removed `simulator/test_ai_setup.py`, blob `bff8dab8e42a475b52c84138a46e49ff39deb83b`, line 38; both exact synthetic values from the current checker's test-value set, manually confirmed as simulator key-masking fixtures. No unresolved findings after review |
| First-party Markdown links | 69 Markdown files checked; no missing tracked targets in the inline links examined, and no user-machine paths found. External URLs and heading anchors were not comprehensively validated |
| Git-tree portability | No local case-folded path collisions, symlinks or submodule entries |
| Source-only export | Tracked HEAD exported separately; official checker passes there too; ignored device state and release artifacts are unnecessary for the checks below |
| Recorded MicroPython patch | Reverse-apply check passes against the exported vendored source; no patch application was performed |
| Fresh `mpy-cross` and application compilation | PASS: compiler built from exported pinned MicroPython; all 154 application modules compiled |
| Fresh host simulator build | PASS: built using only exported vendored/project source and installed host tools |
| Native graphics | PASS: 6,018 checks |
| Native solver | PASS: 1,254 structural/core checks, 1,373 circuit checks and 100 formula checks |
| Native SD/FAT32 | PASS: 2,532 checks |
| Canonical simulator `--sim-check` | FAIL: stops at `test_dashboard_layout.py:122`, after its first dashboard check passes |
| All 45 selected-profile tests, individually completed | 43 PASS, 2 FAIL: `test_dashboard_layout.py` and `test_picolab_hierarchy.py`. Remaining tests were run individually to avoid the canonical runner's early stop; this is not a passing canonical self-check |
| Firmware/physical/release qualification | Not performed: no fresh Arm UF2 build, hardware flashing, device benchmark, full SD release build, audit of existing ignored release archives, or complete legal/security review |

The signature scan reuses the current public checker's token, private-key and literal-assignment patterns and its fixture rules, with explicit manual review of the historical test above. It reads all blobs reachable from local branch/tag commits. It does not inspect ignored private working files, reflogs, unreachable objects, GitHub-only history, unknown secret formats or every possible credential assignment. Known public test keys are not release-signing keys. Findings are reported without credential values.

## 7. Preserve legacy and publish the current project

Recommended migration for the existing `cmeboye/GungOS` repository:

1. **Re-read the remote refs immediately before migration.** The observed legacy tip is `96ec62bf2304f73a7d3b62e77d3fdc398d622fe3`; the audit's shallow comparison clone is not a full backup.
2. **Create a complete backup of the existing remote.** Use a full mirror or equivalent repository backup and retain it locally. Preserve the old source and notices unchanged in that backup.
3. **Create explicit legacy refs before changing the default branch.** Suggested names are branch `legacy/lofifren` and annotated tag `legacy-2025-12-12`, initially pointing to the exact observed old tip. Leave `master` intact during the transition. Verify the preserved refs on GitHub.
4. **Finish the bounded cleanup and validation described above.** Keep the existing local development history; there is no credential finding here that calls for replacing it with a new single commit. Review identity metadata separately if desired.
5. **Configure the current local checkout's `origin` as the existing public GungOS repository and publish its `main` as a new branch.** At audit time that remote has no `main`, so preserving `master` and adding `main` does not require overwriting the legacy branch or merging unrelated histories. Recheck before execution. Publish tags deliberately after checking for conflicts; do not use a blanket force push or mirror push from the new project.
6. **Verify `main` on GitHub, then make it the default.** Its landing page should explain the PicoCalc/Pico 2 W target, Picoware/jblanked credit, build/install path, current development status and a clear link to the older LofiFren-based legacy branch. A later legacy-branch README can explain its status without changing the preserved legacy tag.
7. **Publish reviewed binary assets separately.** Use a release identity matching the chosen source commit, preserve the existing v1.35 tag, include correct license/data notices and checksums, and distinguish device-test artifacts from a qualified stable release.

Keeping a legacy branch/tag is different from archiving the entire GitHub repository. The repository should remain active for the new GungOS work. Picoware can be added as a separately named upstream reference for future comparison, but its history should not be merged blindly into this snapshot-based development history.

## Appendix A. Directory comparison against current Picoware

"Same" means an identical blob at the same path. "Changed" means a different blob at the same path. Presence-only columns do not establish origin or authorship. Paths are grouped for readability; the `src` row covers source outside `src/MicroPython/`.

| Area | Same | Changed | GungOS only | Picoware only |
|---|---:|---:|---:|---:|
| `(root files)` | 1 | 3 | 7 | 0 |
| `app` | 0 | 0 | 0 | 9 |
| `assets` | 0 | 0 | 37 | 0 |
| `builds` | 0 | 0 | 0 | 147 |
| `builds/MicroPython` | 0 | 3 | 154 | 817 |
| `drafts` | 0 | 0 | 5 | 0 |
| `firmware` | 0 | 0 | 2 | 0 |
| `guides` | 0 | 2 | 47 | 19 |
| `images` | 0 | 0 | 0 | 1 |
| `sd-card` | 0 | 0 | 1 | 0 |
| `simulator` | 26 | 13 | 103 | 26 |
| `src` | 0 | 0 | 0 | 491 |
| `src/MicroPython (root)` | 0 | 1 | 0 | 0 |
| `src/MicroPython/Cardputer` | 0 | 0 | 0 | 28 |
| `src/MicroPython/CrowPanel` | 0 | 0 | 0 | 50 |
| `src/MicroPython/Desktop` | 15 | 5 | 35 | 33 |
| `src/MicroPython/Flipper` | 0 | 0 | 0 | 42 |
| `src/MicroPython/JPEGDEC` | 17 | 1 | 0 | 0 |
| `src/MicroPython/Pancake` | 0 | 0 | 0 | 29 |
| `src/MicroPython/PicoCalc` | 13 | 13 | 7 | 1,133 |
| `src/MicroPython/PicoDuo` | 0 | 0 | 0 | 5 |
| `src/MicroPython/Poom` | 0 | 0 | 0 | 22 |
| `src/MicroPython/V8` | 0 | 0 | 0 | 29 |
| `src/MicroPython/Waveshare` | 0 | 0 | 0 | 149 |
| `src/MicroPython/audio` | 0 | 0 | 0 | 11 |
| `src/MicroPython/auto_complete` | 0 | 0 | 0 | 8 |
| `src/MicroPython/boards` | 0 | 0 | 0 | 20 |
| `src/MicroPython/c` | 0 | 0 | 0 | 26 |
| `src/MicroPython/engine` | 0 | 0 | 0 | 48 |
| `src/MicroPython/font` | 4 | 6 | 0 | 0 |
| `src/MicroPython/gameboy` | 0 | 0 | 0 | 45 |
| `src/MicroPython/gfx` | 0 | 0 | 18 | 0 |
| `src/MicroPython/ghouls` | 0 | 0 | 0 | 94 |
| `src/MicroPython/http` | 0 | 0 | 0 | 3 |
| `src/MicroPython/jpeg` | 3 | 2 | 3 | 0 |
| `src/MicroPython/jsmn` | 0 | 0 | 0 | 7 |
| `src/MicroPython/lcd` | 1 | 3 | 0 | 0 |
| `src/MicroPython/log` | 3 | 2 | 0 | 0 |
| `src/MicroPython/mjs` | 0 | 0 | 0 | 280 |
| `src/MicroPython/mmbasic` | 0 | 0 | 0 | 27 |
| `src/MicroPython/pcm` | 0 | 0 | 2 | 0 |
| `src/MicroPython/picosolve` | 0 | 0 | 32 | 0 |
| `src/MicroPython/picoware` | 22 | 65 | 20 | 75 |
| `src/MicroPython/picoware_boards` | 0 | 0 | 0 | 4 |
| `src/MicroPython/png` | 0 | 0 | 21 | 0 |
| `src/MicroPython/response` | 4 | 0 | 0 | 0 |
| `src/MicroPython/sd` | 9 | 4 | 5 | 0 |
| `src/MicroPython/textbox` | 2 | 1 | 0 | 0 |
| `src/MicroPython/uf2loader` | 3 | 1 | 0 | 0 |
| `src/MicroPython/ulab` | 0 | 0 | 73 | 0 |
| `src/MicroPython/usb_video` | 0 | 0 | 0 | 4 |
| `src/MicroPython/vector` | 4 | 0 | 0 | 0 |
| `src/MicroPython/video` | 0 | 0 | 0 | 3 |
| `src/MicroPython/vt` | 4 | 0 | 0 | 0 |
| `src/MicroPython/websocket` | 0 | 0 | 0 | 3 |
| `tests` | 0 | 0 | 0 | 72 |
| `tools` | 0 | 2 | 44 | 56 |
| `vendor` | 0 | 0 | 17,012 | 0 |
| `verification` | 0 | 0 | 2 | 0 |
| **Total** | **131** | **127** | **17,630** | **3,816** |

## Appendix B. All 127 changed shared paths against current Picoware

This inventory lists every same-path content difference. New GungOS-only areas and absent upstream features are described above and summarized by directory in Appendix A. Entire bundled dependency trees are not repeated as thousands of filenames.

<details>
<summary>Expand the complete changed-path inventory</summary>

```text
.gitattributes
.gitignore
README.md
builds/MicroPython/apps_unfrozen/Graph.py
builds/MicroPython/apps_unfrozen/Graph3D.py
builds/MicroPython/apps_unfrozen/games/Tetris.py
guides/Infrared.md
guides/Simulator.md
simulator/build.sh
simulator/hardware/jpegdec.py
simulator/hardware/machine.py
simulator/hardware/network.py
simulator/hardware/picoware_psram.py
simulator/hardware/picoware_southbridge.py
simulator/hardware/sd_mp.py
simulator/hardware/sim_runtime.py
simulator/hardware/sim_usocket.py
simulator/hardware/ubluetooth.py
simulator/jpeg/sim_jpeg_decode.cpp
simulator/run.py
simulator/viewer/sdl_fb_viewer.c
src/MicroPython/Desktop/desktop_bridge.c
src/MicroPython/Desktop/desktop_bridge.h
src/MicroPython/Desktop/desktop_mp.c
src/MicroPython/Desktop/modules/desktop/micropython.mk
src/MicroPython/Desktop/variant/mpconfigvariant.h
src/MicroPython/JPEGDEC/src/JPEGDEC.h
src/MicroPython/PicoCalc/picoware_keyboard/keyboard.c
src/MicroPython/PicoCalc/picoware_keyboard/keyboard.h
src/MicroPython/PicoCalc/picoware_lcd/lcd.c
src/MicroPython/PicoCalc/picoware_lcd/lcd.h
src/MicroPython/PicoCalc/picoware_lcd/micropython.cmake
src/MicroPython/PicoCalc/picoware_lcd/picoware_lcd.c
src/MicroPython/PicoCalc/picoware_lcd/picoware_lcd.h
src/MicroPython/PicoCalc/picoware_modules.cmake
src/MicroPython/PicoCalc/picoware_psram/micropython.cmake
src/MicroPython/PicoCalc/picoware_psram/picoware_psram.c
src/MicroPython/PicoCalc/picoware_psram/picoware_psram.h
src/MicroPython/PicoCalc/picoware_psram/picoware_psram_shared.h
src/MicroPython/PicoCalc/picoware_psram/psram_qspi.c
src/MicroPython/font/font12.c
src/MicroPython/font/font16.c
src/MicroPython/font/font20.c
src/MicroPython/font/font24.c
src/MicroPython/font/font8.c
src/MicroPython/font/font_mp.h
src/MicroPython/jpeg/jpegdec_mp.c
src/MicroPython/jpeg/jpegdec_mp.h
src/MicroPython/lcd/lcd_config.h
src/MicroPython/lcd/lcd_mp.c
src/MicroPython/lcd/lcd_mp.h
src/MicroPython/log/log_config.h
src/MicroPython/log/storage.h
src/MicroPython/main.py
src/MicroPython/picoware/applications/applications/custom.py
src/MicroPython/picoware/applications/applications/games/games.py
src/MicroPython/picoware/applications/applications/screensavers.py
src/MicroPython/picoware/applications/bluetooth/advertise.py
src/MicroPython/picoware/applications/bluetooth/beacon.py
src/MicroPython/picoware/applications/bluetooth/bluetooth.py
src/MicroPython/picoware/applications/bluetooth/pair.py
src/MicroPython/picoware/applications/bluetooth/rssi_monitor.py
src/MicroPython/picoware/applications/bluetooth/scan.py
src/MicroPython/picoware/applications/bluetooth/uart_chat.py
src/MicroPython/picoware/applications/desktop.py
src/MicroPython/picoware/applications/library.py
src/MicroPython/picoware/applications/settings.py
src/MicroPython/picoware/applications/system/system.py
src/MicroPython/picoware/applications/system/system_info.py
src/MicroPython/picoware/applications/usb/keyboard.py
src/MicroPython/picoware/applications/usb/media_keys.py
src/MicroPython/picoware/applications/usb/numpad.py
src/MicroPython/picoware/applications/usb/payload.py
src/MicroPython/picoware/applications/usb/usb.py
src/MicroPython/picoware/applications/utilities/file_manager.py
src/MicroPython/picoware/applications/utilities/pico_ide.py
src/MicroPython/picoware/applications/utilities/repl.py
src/MicroPython/picoware/applications/utilities/serial.py
src/MicroPython/picoware/applications/utilities/ssh.py
src/MicroPython/picoware/applications/wifi/connect.py
src/MicroPython/picoware/applications/wifi/password.py
src/MicroPython/picoware/applications/wifi/rssi_monitor.py
src/MicroPython/picoware/applications/wifi/scan.py
src/MicroPython/picoware/applications/wifi/server.py
src/MicroPython/picoware/applications/wifi/settings.py
src/MicroPython/picoware/applications/wifi/ssid.py
src/MicroPython/picoware/applications/wifi/utils.py
src/MicroPython/picoware/applications/wifi/wifi.py
src/MicroPython/picoware/gui/choice.py
src/MicroPython/picoware/gui/date_picker.py
src/MicroPython/picoware/gui/draw.py
src/MicroPython/picoware/gui/file_browser.py
src/MicroPython/picoware/gui/jpeg.py
src/MicroPython/picoware/gui/keyboard.py
src/MicroPython/picoware/gui/loading.py
src/MicroPython/picoware/gui/menu.py
src/MicroPython/picoware/gui/text_editor.py
src/MicroPython/picoware/gui/textbox.py
src/MicroPython/picoware/system/app_loader.py
src/MicroPython/picoware/system/battery.py
src/MicroPython/picoware/system/bluetooth.py
src/MicroPython/picoware/system/boards.py
src/MicroPython/picoware/system/buttons.py
src/MicroPython/picoware/system/decorator.py
src/MicroPython/picoware/system/drivers/pye.py
src/MicroPython/picoware/system/drivers/vt.py
src/MicroPython/picoware/system/ducky.py
src/MicroPython/picoware/system/http.py
src/MicroPython/picoware/system/input.py
src/MicroPython/picoware/system/settings.py
src/MicroPython/picoware/system/storage.py
src/MicroPython/picoware/system/system.py
src/MicroPython/picoware/system/thread.py
src/MicroPython/picoware/system/time.py
src/MicroPython/picoware/system/uart.py
src/MicroPython/picoware/system/usb.py
src/MicroPython/picoware/system/view.py
src/MicroPython/picoware/system/view_manager.py
src/MicroPython/picoware/system/wifi.py
src/MicroPython/sd/fat32.c
src/MicroPython/sd/fat32.h
src/MicroPython/sd/sd_config.h
src/MicroPython/sd/sdcard.c
src/MicroPython/textbox/textbox_mp.c
src/MicroPython/uf2loader/uf2loader_mp.c
tools/micropython-desktop.sh
tools/run-micropython-desktop.sh
```

</details>

## Audit method

Upstream and legacy repositories were downloaded into the audit workspace without altering the development checkout. Picoware's dated commit was fetched separately. Recursive `git ls-tree` records and blob IDs were used for both upstream comparisons and the initial-local-snapshot comparison. All reachable local commit trees were enumerated and unique blobs read with `git cat-file --batch`; matched values were not included in reports. A separate tracked-source export was used to build and check the host tools, compile applications and run the selected regressions. The audit report was then added as documentation; the measured source revision remains the pre-report HEAD listed above.
