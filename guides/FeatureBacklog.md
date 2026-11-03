# Feature backlog

A task-level view of [Roadmap.md](Roadmap.md) and
[ConnectivityRoadmap.md](ConnectivityRoadmap.md), reviewed on 26 October 2026
against the v1.34 baseline and the local PicoReader/PicoDict additions.

Sizes in **bold** come from the roadmap; `est.` marks an estimate made while
reviewing. Status: **done** is in the v1.34 baseline (or an accepted first
pass), **partial** is usable with work remaining, **new** is not started.

Verified gaps at review time: no `exchange/` package, material or fluid
library, streaming CSV reader, report generation, AC analysis, Mohr case
saving, numbered screenshots or shared material picker.

## PicoReader follow-up — 3 November 2026

Device feedback: the metadata SD patch now opens the supplied complex textbook
on PicoCalc. The following requested work remains open; see
[PicoReader device feedback and plan](PicoReader.md#device-feedback-and-next-work--3-november-2026)
for detail and validation boundaries.

| ID | Remaining feature | Status |
|---|---|---|
| R1 | Correct structured MathML/equation display, including wide-equation viewing | F8 and mixed-page device tests passed; six alignment cases remain |
| R2 | Chapter list, fast selection, Go to chapter/page and clear page-number semantics | implemented locally; device acceptance pending |
| R3 | Previous/next page on `[` / `]`; arrow-key panning in image views | reading bracket keys implemented; image panning still open |
| R4 | Persistent indexed text chunks for efficient jumping/reopening | new |
| R5 | Full-resolution image viewport, bounded decoding/storage and access to every chapter image | new |
| R6 | Fullscreen reading/image mode | new |
| R7 | Low-light mode: pitch-black background and reddish-gray text | new |

## Next milestone: finish the PicoDESK first passes

| ID | Feature | Area | Size | Status | Depends on |
|---|---|---|---|---|---|
| N1 | PicoReader: persistent last position and bookmarks | PicoDESK | **M** | done (local) | — |
| N2 | PicoReader: incremental SD page index | PicoDESK | **M** | done (local) | N1 |
| N3 | PicoReader: selectable font sizes | PicoDESK | **S** | done (local) | — |
| N4 | PicoReader: TXT reading | PicoDESK | **S** | done (local) | N1 |
| N5 | Device qualification for PicoReader + PicoDict (SD latency, peak heap, navigation, exit cleanup) | Verification | est. S | pending | N1–N4 |
| N6 | Commit PicoDESK additions and ship matching SD update, dictionary data separate | Release | est. S | pending | N1–N5 |

Control alignment and folder organization were implemented locally on
30 October 2026; packaging,
physical-device checks and committing wait until the current five-item batch
is reviewed. See [Keys.md](Keys.md#current-alignment) for the bindings and
intentional editing exceptions.

## Phase 0: close the open work (new UF2)

| ID | Feature | Area | Size | Status | Depends on |
|---|---|---|---|---|---|
| P0-1 | Align existing PicoLAB controls to `Keys.md` | UX | est. M | done (local; simulator checked) | — |
| P0-2 | PicoSpice UI: symbol art, transistor/op-amp placement, node picker | App | est. S | partial | — |
| P0-3 | Reorganize PicoLAB folders; move PicoCAD; list planned apps | UX | **S** | done (local; simulator checked) | — |
| P0-4 | Update menu regression test and ship release | Release | est. S | new | P0-1…P0-3 |

## Phase 1: exchange layer and tools (SD update)

| ID | Feature | Area | Size | Status | Depends on |
|---|---|---|---|---|---|
| P1-1 | `exchange/` package: kinds, registry, Send to, Import | Library | **M** | new | — |
| P1-2 | Shared clipboard (4 KB, RAM + SD) | Library | **S** | new | P1-1 |
| P1-3 | Streaming CSV reader | Library | **M** | new | — |
| P1-4 | `name [unit]` CSV headers in every export | Library | **S** | partial | P1-3 |
| P1-5 | F5 results → `.pword` report | Library | **S** | new | P1-1 |
| P1-6 | `guides/Exchange.md` | Docs | **S** | new | P1-1 |
| P1-7 | Handoffs: BeamView/Shrink fit → Mohr, Mohr cases, CSV → Eggcel/Grapher, SciCalc ↔ Grapher, BMP import | Apps | est. M | partial | P1-1…P1-5 |
| P1-8 | Numbered screenshots in `picoware/pictures/` | UX | **S** | new | — |
| P1-9 | Grapher: multi-series tables/signals, log axes, cursor readout, solver plot migration | App | **M** | partial | P1-1, P1-3 |
| P1-10 | UnitConverter: compound units, shared number-field parsing, device benchmark | App + Library | **S** | partial | — |
| P1-11 | Key-driven BeamView → Mohr → report → PicoWord test | Verification | est. S | new | P1-1…P1-7 |

## Phase 2: data libraries (SD update)

| ID | Feature | Area | Size | Status | Depends on |
|---|---|---|---|---|---|
| P2-1 | Materialprop: class CSVs, user file, booklet, Eggcel opening | App | **M** | new | P1-3 |
| P2-2 | Shared material picker | Library | **M** | new | P2-1 |
| P2-3 | PropTable: IAPWS-IF97, cp(T) gases, refrigerant tables, state solver | App | **M** | new | P1-3 |
| P2-4 | Adopt material picker in existing apps | Apps | est. M | new | P2-2 |
| P2-5 | PicoDict: suggestions, stemming, conjugation, sentence translation | App | est. L | deferred | — |

## Phase 3: Electrical (new UF2)

| ID | Feature | Area | Size | Status | Depends on |
|---|---|---|---|---|---|
| P3-1 | PicoSpice AC analysis with Bode plot | App | **M** | new | P3-5 |
| P3-2 | Op-amp supply limits; junction capacitances | App | **M** | new | — |
| P3-3 | Element renaming, transient cursor readout, light-theme probe colours | App | **S** | new | — |
| P3-4 | SmithChart | App | **M** | new | P3-1 |
| P3-5 | Firmware: complex sparse LU + AC analysis (~6 KB) | Firmware | **S** | new | — |

## Phase 4: Structural (new UF2)

| ID | Feature | Area | Size | Status | Depends on |
|---|---|---|---|---|---|
| P4-1 | StressStrain: rosettes | App | est. S | new | — |
| P4-2 | StressStrain: Ramberg–Osgood curve | App | est. S | new | P2-2 |
| P4-3 | StressStrain: material/exchange integration | App | est. S | new | P1-1, P2-2 |
| P4-4 | Buckling: BeamView handoff and material picker | App | **S** | partial | P1-1, P2-2 |
| P4-5 | FatigueLife | App | **M** | new | P1-1, P2-2 |
| P4-6 | FractureLife | App | **M** | new | P1-1, P2-2, P4-8 |
| P4-7 | WeldCalc | App | **S** | new | P2-2 |
| P4-8 | Rainflow counting and damage sums | Library | est. S | new | — |
| P4-9 | PicoPlayer | App | **M** | new | P4-10 |
| P4-10 | Firmware: MP3 decoder (~25–35 KB) | Firmware | **L** | new | — |

## Phase 5: Fluids (new UF2)

| ID | Feature | Area | Size | Status | Depends on |
|---|---|---|---|---|---|
| P5-1 | FlowRegimes | App | **S** | new | P2-3 |
| P5-2 | PipeLoss | App | **M** | new | P2-3 |
| P5-3 | BoundaryDrag | App | **S** | new | P2-3 |
| P5-4 | Shared network editor extracted from PicoSpice | Library | est. M | new | — |
| P5-5 | 1DNetSolve | App | **L** | new | P5-4, P5-6 |
| P5-6 | Firmware: hydraulic elements (~3 KB) | Firmware | **S** | new | — |

## Phase 6: Thermal (SD update)

| ID | Feature | Area | Size | Status | Depends on |
|---|---|---|---|---|---|
| P6-1 | Heat-transfer correlations | Library | est. M | new | P5-1, P5-2 |
| P6-2 | HeatExchanger | App | **M** | new | P2-3, P6-1 |
| P6-3 | Cycles | App | **M** | new | P2-3 |
| P6-4 | ThermalField: multi-material, contact resistance, thermal loads | App | **M** | partial | P1-1, P2-2 |

## Phase 7: Dynamics (new UF2)

| ID | Feature | Area | Size | Status | Depends on |
|---|---|---|---|---|---|
| P7-1 | Firmware: skyline eigensolver (~8 KB) | Firmware | **M** | new | — |
| P7-2 | ModalHarmonics | App | **L** | new | P7-1, P1-1 |
| P7-3 | Buckling for frames | App | est. M | new | P7-1 |
| P7-4 | Firmware: ODE integrator (~6 KB) | Firmware | **M** | new | — |
| P7-5 | TransferFunc | App | **M** | new | P3-1, P7-2 |
| P7-6 | TransientSolve | App | **M** | new | P7-4 |
| P7-7 | Multibody | App | **L** | new | P7-4 |
| P7-8 | PicoMail | App | **L** | new | P0-1 |

## Phase 8: Machine design and meshes (new UF2)

| ID | Feature | Area | Size | Status | Depends on |
|---|---|---|---|---|---|
| P8-1 | PicoCAD: 2D profiles, extrude/revolve | App | **L** | partial | — |
| P8-2 | PicoCAD: section/mass properties, STL, fillets later | App | est. M | partial | P8-1, P1-1 |
| P8-3 | GearGen | App | **M** | new | P8-1 |
| P8-4 | MeshGen | App | **L** | new | P8-1 |
| P8-5 | Firmware: plane triangle elements (~12–15 KB) | Firmware | **L** | new | — |
| P8-6 | Mesh modes in StressStrain, ThermalField, ModalHarmonics | Apps | est. M | new | P8-4, P8-5 |

## Connectivity

| ID | Feature | Area | Size | Status | Depends on |
|---|---|---|---|---|---|
| C1 | GPIO/UART settings tool replacing the Serial Terminal | Comms | est. M | new | C2 |
| C2 | Board-pin protection and safe apply/restore | Comms | est. S | new | — |
| C3 | Buffered bounded serial I/O, echo, scrollback, cancellation | Comms | est. M | new | — |
| C4 | SSH host-key trust, signature verification, bounded parsing | Comms | **L** | new | — |
| C5 | SSH nonblocking I/O, deadlines, UTF-8 reassembly | Comms | est. M | new | C4 |
| C6 | SSH PTY and interactive shell | Comms | **L** | new | C5 |
| C7 | Evaluate a maintained embedded SSH implementation | Comms | est. M | new | — |
| C8 | Credential encryption at rest | Security | est. L | new | — |
| C9 | Infrared support | Comms | — | out of scope | external hardware |

## Cross-cutting requirement for every new app

| Requirement | Detail |
|---|---|
| Saved cases | Versioned JSON with `kind`, `version`, `from`, SI values |
| Export/handoff | CSV export plus at least one Send to |
| Documentation | Guide in `guides/` |
| Tests | Model test and keyboard-driven simulator test |
| Budgets | ≤50 KB code (calculator), ≤85 KB (editor), ≥150 KB free heap, ≤32 KB files |

## Deferred or out of scope

3D tetrahedral meshing · EPUB images/CSS/DRM · helical gears · TransferFunc
root locus · background PicoPlayer · OAuth-only mail · infrared ·
credential encryption design.
