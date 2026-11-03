# App roadmap

The plan for every PicoLAB and PicoDESK app covers four things:

- what exists today;
- what each new app does;
- how apps pass data to each other;
- the order to build them in.

Wi-Fi, Bluetooth, serial and SSH are in the separate
[connectivity roadmap](ConnectivityRoadmap.md).

Status: **done** means accepted for the current app scope (release packaging
is tracked separately); **partial** means usable but with work
remaining; **new** means not started. Size compares an app with ones that
exist: **S** is about Mohr circle, **M** about Shrink fit or Heat transfer 2D,
**L** about BeamView or PicoSpice.

## Where things stand

Updated **30 October 2026**. There are **37 apps: 8 done, 9 partial and
20 new**. PicoReader is the app previously planned as PicoBook; PicoDict is
an additional PicoDESK app.

The committed baseline is **GungOS v1.34**. PicoDict and PicoReader are local,
uncommitted additions with simulator checks and compiled preview app bundles;
they are not yet part of a committed release. Physical PicoCalc SD latency,
peak memory and responsiveness checks remain pending for both.

Overall, Phase 0 cleanup and Phase 1 foundations remain open. PicoReader's
standalone first pass was brought forward from Phase 2. Later-phase first
passes do not mean their shared-library or exchange dependencies are complete.

| Folder | App | Status | Today |
|---|---|---|---|
| Structural | BeamView | done | BeamView: beams and frames, sections, diagrams |
| | Mohr's circle | done | Mohr circle: 2D/3D stress, rotation, principal stresses |
| | ShrinkFit | done | Shrink fit: rotating discs, thick cylinders, press fits |
| | StressStrain | partial | Section loads, stress maps and critical points, 3D/plane stress/plane strain, thermal strain, materials, cases and SI exports; rosettes and material curves remain |
| | Buckling | partial | First pass: both axes, end conditions/custom K, six section types, yield screen, plots, cases and SI CSV; BeamView handoff remains |
| | Section Properties | partial | Standalone first pass: six shape templates, live section/material editing, centroids, inertias, moduli, gyration, cases and reports; connections to other apps deferred |
| | FatigueLife, FractureLife | new | |
| Machine design | PicoCAD | partial | Analytic primitives, Booleans, `.pcad` projects; under Modules → Machine design |
| | MeshGen, GearGen, WeldCalc, Materialprop | new | |
| Dynamics | ModalHarmonics, TransientSolve, Multibody, TransferFunc | new | |
| Fluids | FlowRegimes, PipeLoss, BoundaryDrag, 1DNetSolve | new | |
| Thermal | ThermalField | partial | Heat transfer 2D: a rectangular plate of one material, steady or transient |
| | HeatExchanger, Cycles, PropTable | new | |
| Electrical | PicoSpice | partial | First pass committed in v1.34: operating point, DC sweep and transient; AC and second-pass features remain |
| | SmithChart | new | |
| Tools | SciCalc | done | Scientific calculator |
| | Grapher | partial | Unified 2D/3D workspace and versioned shared API; isolated fixtures first, solver migrations and data/field extensions pending |
| | UnitConvert | done | UnitConverter accepted: 49 categories, 322 units, search, cases, favorites, history and SI CSV. Shared input parsing and exchange are separate follow-ups |
| PicoDESK | EggCel, PicoWord, PicoPaint | done | `.egg`, `.pword`, `.ppaint` files; CSV in and out, TXT and BMP out |
| | PicoDict | partial | Offline English/Italian single-word lookup, separate SD dictionary data, bounded reads and simulator checks; local first pass, device checks and release pending |
| | PicoReader | partial | EPUB and TXT library, text reflow, pages and chapters, saved position, bookmarks, font choice, incremental SD page index and sample books; physical-device checks and release remain |
| | PicoPlayer, PicoMail | new | |

### Next milestone: finish the PicoDESK first passes

1. PicoReader's reading essentials are implemented locally: persistent last
   position, bookmarks, an incremental SD page index, selectable font sizes
   and TXT support, with extra-small as the default. See
   [PicoReader.md](PicoReader.md) for formats and size limits.
2. Check PicoReader and [PicoDict](PicoDict.md) on physical PicoCalc hardware:
   SD access, peak memory, navigation responsiveness and exit cleanup.
   Simulator results do not establish device performance.
3. Commit the reviewed PicoDESK additions and produce the matching SD app
   update, with PicoDict data kept as a separate package. The current apps
   use existing firmware capabilities; no new native module is required.

The next shared foundation is Phase 1's exchange layer, streaming CSV reader,
clipboard and reports. Materialprop and PropTable remain unstarted; the
standalone reader and dictionary do not depend on those libraries.

## Ground rules

These follow from the hardware and from what already works.

1. **One tool in memory.** About 366 KB of heap is free at idle, and an open
   tool keeps 30–160 KB of it. PicoLAB already unloads a tool's code when the
   tool closes. Apps never share memory. They pass data through files on the
   SD card and a small clipboard.
2. **Flash is for kernels.** Python apps live on the SD card and use no flash.
   Native C goes in only where Python is too slow or too large, as in solvers
   and decoders. About 668 KB of the firmware partition is free after
   `ps.Circuit`. This plan uses an estimated 60–90 KB of it and keeps the rest
   in reserve.
3. **Same screens, same keys.** New PicoLAB tools follow
   [PicoLAB keys](Keys.md): F1 Add, F2 Remove, F3 Options, F4 Plots,
   F5 Results, F6 Build/Calculate/Evaluate and F9 Help. Arrows navigate
   inputs; Tab switches input/preview focus; preview arrows navigate,
   Space changes navigation mode and +/− zooms. Use the shared
   `engtools/ui/lab.py` and `ui/tool.py` parts. The key guide records
   the local control alignment and deliberate editing exceptions. PicoDESK apps
   keep their own menus.
   UnitConverter, StressStrain and Buckling now follow BeamView's tabbed
   layout: Left/Right selects a section, Up/Down its fields. F9 presents
   equations through the scientific calculator's math renderer first.
4. **SI inside.** Models and exchange files store SI. Units change only at
   the screen and at input.
5. **Shared libraries first.** A library that several apps need is built
   before those apps, so none of them has to be changed later. Examples are
   materials, fluid properties and the exchange layer.
6. **Each app ships complete**, with:
   - saved cases (versioned JSON);
   - CSV export and at least one **Send to**;
   - a guide in `guides/`;
   - a model test and a test driven by keys in `simulator/`;
   - memory figures from the device benchmark.

## How apps exchange data

This section describes the **planned shared exchange layer**. The registry,
Send to/Import flow, shared clipboard and generated PicoWord reports are not
implemented yet; existing app-specific files and CSV exports remain in use.

Apps don't convert data pair by pair. Every app reads and writes a few
shared **exchange kinds**. An app supports the kinds that make sense for it
and can then work with every other app that uses them.

### Exchange kinds

| Kind | File | Holds | Written by | Read by |
|---|---|---|---|---|
| Table | `.csv` | Columns headed `name [unit]`, values in SI | every solver, Eggcel, SciCalc statistics, PropTable, Materialprop | Eggcel, Grapher, SciCalc statistics, PipeLoss (pump curves) |
| Signal | `.csv`, time in the first column | A load or response history | PicoSpice, TransientSolve, Multibody, Eggcel | FatigueLife, FractureLife, TransientSolve (forcing), PicoSpice (PWL sources), Grapher |
| Stress state | `.json` | σ and τ components (plane or 3D) and the point they belong to | StressStrain, BeamView (a point in a section), Shrink fit (a radius), MeshGen results | Mohr's circle, FatigueLife, FractureLife, WeldCalc |
| Material | `.json` record | E, ν, ρ, strengths, endurance limit, K_Ic, Paris C and m, k, cp, α | Materialprop | BeamView, Shrink fit, StressStrain, Buckling, FatigueLife, FractureLife, WeldCalc, GearGen, PicoCAD, ThermalField, HeatExchanger |
| Section | `.json` | A, I, centroid, extreme fibres and the outline | PicoCAD (a 2D profile), BeamView's section list | BeamView, Buckling, StressStrain |
| Geometry | `.pcad` | A part or a 2D profile | PicoCAD, GearGen | PicoCAD, MeshGen |
| Mesh | `.pmesh` | Nodes, triangles, boundary groups and results at the nodes | MeshGen | StressStrain, ThermalField, ModalHarmonics |
| Linear model | `.json` | A transfer function (polynomials, or poles, zeros and gain), or a frequency response | TransferFunc, PicoSpice AC, ModalHarmonics | TransferFunc, SmithChart, TransientSolve, Grapher |
| Report | `.pword` | Inputs, equations and results as a document | every PicoLAB tool | PicoWord, PicoMail |
| Image | `.bmp` | A screen or a drawing | PicoPaint, the Alt+S screenshot | PicoPaint, PicoMail; PicoWord later |
| Value | clipboard text | A number with its unit, an expression or a small range of cells | any field, SciCalc, Eggcel | any field, SciCalc, Grapher, Eggcel |

Outside formats are used only at the edges:

- STL out of PicoCAD and MeshGen;
- MP3 and WAV in PicoPlayer;
- EPUB and TXT in PicoReader;
- attachments in PicoMail.

Every JSON kind carries `kind`, `version`, `from` (the tool that wrote it)
and SI values, the same as saved cases do today in `engtools/cases.py`.

### Moving data between apps

- **Send to** (F3 options) works in four steps:
  1. The source writes the exchange file.
  2. The source keeps its own state in `session.kept`, then closes to free
     its memory.
  3. The target opens with the file as a new, unsaved item. It never
     overwrites anything.
  4. Esc in the target returns to the source as it was.
- **Import** (F3 options) opens the system file browser in
  `picoware/exchange/` and shows only the kinds the app reads.
- **Clipboard:** copy the value under the cursor, or a range of cells in
  Eggcel, and paste it into any field. It holds up to 4 KB of text. It is kept
  in RAM and also written to the SD card, so it survives switching between
  PicoLAB and PicoDESK.
- **Registry:** one small table lists the kinds each app reads and writes.
  Send to menus are built from it without loading any app's code, the same
  way PicoLAB's `MENUS` works.

Both launchers use the exchange layer, so it lives in a small top-level
package beside `engtools/` and `desktopapps/` (proposed name: `exchange/`).
PicoLAB keeps it loaded when a tool closes.

### Where files go

| Folder | Holds |
|---|---|
| `picoware/exchange/` | The files Send to writes, one per kind, each replaced by the next send. Import starts here |
| `picoware/engineering/cases/`, `exports/`, `cad/` | Unchanged |
| `picoware/documents/<app>/` | Unchanged |
| `picoware/pictures/` | Numbered Alt+S screenshots. Today there is a single `screenshot.bmp` at the root, overwritten each time |
| `picoware/library/` | Materialprop and PropTable data, plus the user's own materials |
| `picoware/documents/picoreader/` | PicoReader EPUB and TXT books |
| `picoware/settings/picoreader/` | PicoReader position, bookmarks, font and page index |
| `picoware/dictionary/` | PicoDict English/Italian lookup data, installed separately from app code |
| `picoware/music/`, `mail/` | Planned PicoPlayer and PicoMail storage |

## Shared kernels and libraries

| Part | Language | Used by | Phase | Flash, estimated |
|---|---|---|---|---|
| Exchange layer, clipboard, CSV reader that streams rows | Python | every app | 1 | none |
| Units library (extending `units.py`) | Python | UnitConvert and every number field | 1 | none |
| Material library and picker | Python, data on the SD card | 11 apps | 2 | none |
| Fluid property library | Python, data on the SD card | Fluids, Thermal | 2 | none |
| Complex sparse LU and AC analysis | C, in `sparse.c` and `circuit.c` | PicoSpice, SmithChart, TransferFunc | 3 | about 6 KB |
| Rainflow counting and damage sums | Python | FatigueLife, FractureLife | 4 | none |
| MP3 decoder (minimp3, public domain) feeding `pcm` | C | PicoPlayer | 4 | about 25–35 KB |
| Hydraulic elements in the network kernel | C, in `circuit.c` | 1DNetSolve | 5 | about 3 KB |
| Eigensolver on skyline matrices | C | ModalHarmonics, frame buckling | 7 | about 8 KB |
| ODE integrator (explicit, plus implicit for stiff systems) using `Formula` | C | TransientSolve, Multibody | 7 | about 6 KB |
| Plane triangle elements for stress and heat | C | StressStrain, ThermalField and ModalHarmonics on meshes | 8 | about 12–15 KB |
| 2D mesher | Python; C for slow loops if measurement says so | MeshGen | 8 | 0–8 KB |

## Phases

Phases 0–2 establish the shared foundations for later integrations. Standalone
first passes can be built earlier where those foundations are not required,
as with PicoReader and PicoDict. The remaining fixed orders are:

- Electrical before Dynamics, so TransferFunc can read PicoSpice's AC results;
- Fluids before Thermal, for the heat transfer correlations;
- Phase 8's mesh modes last.

Every phase ends in a release. Phases 0, 3, 4, 5, 7 and 8 change native code
and need a new UF2. Phases 1, 2 and 6 are SD card updates.

### Phase 0: close the open work

**Partial.** The circuit kernel and PicoSpice first pass are committed in the
v1.34 baseline, and a v1.34 UF2 has been built. Control alignment is implemented
locally with simulator regressions. Folder reorganization is also implemented
locally; the remaining first-pass PicoSpice UI review is still open. This
status does not claim fresh physical-device qualification.

- Local control alignment covers the [key contract](Keys.md#current-alignment),
  including all calculator modes, preview focus, help and shared plot viewers.
  App help, guides and simulator checks follow the revised bindings. Changes
  remain uncommitted; physical Shift+F and device validation are pending.
- Completed in the v1.34 baseline: commit the circuit kernel and PicoSpice
  and build the UF2, including the fix for transients started from zero.
- Settle the open PicoSpice first-pass items:
  - symbol art;
  - where transistors and the op-amp are drawn;
  - how a new element picks its nodes.
- Local folder organization keeps Checks and Tools at the top level and
  orders Modules as Structural, Machine design, Dynamics, Fluids, Thermal
  and Electrical.
  - PicoCAD is under Machine design; its project files and formats are unchanged.
  - Dynamics and Fluids list their planned apps as muted informational rows,
    with no launch action.
  - Simulator routes and app breadcrumbs follow the moved tool, and the former
    simulator shortcut remains accepted. See [PicoLAB.md](PicoLAB.md).

Done when everything is committed, the menu test follows the new folders and
the release is out.

### Phase 1: exchange layer and tools

**Partial.** UnitConverter's first pass is accepted and Grapher has a shared
workspace/API foundation. The exchange layer, shared clipboard, streaming
CSV reader, report generation and end-to-end app handoffs remain pending.

- **Exchange layer** (M):
  - the kinds, the registry, Send to and Import;
  - the clipboard and `picoware/exchange/`;
  - `guides/Exchange.md`, documenting each format.
- **CSV:**
  - A reader that streams a window of rows, which is the large-CSV work
    already planned for Eggcel.
  - The `name [unit]` header convention in every CSV export.
- **Reports** (S): F5 results of any PicoLAB tool become a `.pword` document.
  It holds the inputs, the main equations (in the renderer PicoWord and the
  calculator already share) and the results.
- **Links between existing apps:**
  - BeamView and Shrink fit send a stress state to Mohr's circle.
  - Mohr's circle saves cases; today it only keeps its state in memory.
  - Every solver's CSV opens in Eggcel and Grapher.
  - SciCalc sends an expression to Grapher, and a value comes back.
  - PicoPaint imports BMP.
  - Alt+S saves numbered screenshots in `picoware/pictures/`.
- **Grapher** (M): Graph and Graph3D merge into one tool with 2D and 3D
  modes. It adds plots of tables and signals, with several series, log axes
  and a cursor readout, and it receives every plot sent from another app.
  - Foundation first: one workspace, a versioned sources/layers/axes/view API,
    lazy renderer ownership and isolated tests. See [Grapher.md](Grapher.md).
    Existing solver apps keep their plotting paths until the shared contract
    and device budgets are verified. Log axes, probes, streaming, sampled
    fields and exchange integration follow as independently tested capabilities.
- **UnitConvert** (S): categories, prefixes, temperature offsets and compound
  units. Its library also serves every number field, so `2 in` typed into a
  length becomes 0.0508 m. PicoSpice keeps SPICE suffixes, where `m` means
  milli.
  - First pass accepted as done: **UnitConverter** under Tools; see
    [UnitConverter.md](UnitConverter.md). Device benchmarks, compound-unit
    parsing and integration with shared number fields/exchange are pending.

Done when every existing app sends or receives at least one kind, and one
test drives BeamView → Mohr's circle → report → PicoWord by keys.

### Phase 2: data libraries

**Started through PicoReader.** The reader first pass is available locally;
Materialprop, PropTable and their shared pickers remain planned.

- **Materialprop** (M), typical values for many material classes:
  steels, cast irons, aluminium, titanium, copper alloys, polymers, timber,
  concrete and more.
  - The data is one CSV per class on the SD card, plus a user file for the
    user's own materials.
  - A picker serves every material field in every app.
  - The booklet itself is a menu of class, then material, then a page of
    properties. Each class also opens in Eggcel.
  - Values are marked typical, with their sources.
- **PropTable** (M), properties of four groups of fluids:
  - water and steam from the IAPWS-IF97 equations, which are published
    openly;
  - air and ideal gases from cp(T) fits;
  - refrigerants from saturation and superheat tables, generated on a
    computer with CoolProp (MIT licence) and interpolated from the SD card.

  The viewer finds a state from any two properties, and tables open in
  Eggcel.
- **Existing apps:** BeamView sections, Shrink fit and Heat transfer 2D take
  their materials from the picker.
- **PicoReader** (M), previously called PicoBook in this plan, is the
  PicoDESK EPUB/TXT reader. See [PicoReader.md](PicoReader.md).
  - Available: SD library, stored/DEFLATE EPUB reading using the firmware's
    `deflate` module, XHTML text reflow, page turning and chapter navigation.
    UTF-8 TXT files are split into bounded parts at line breaks.
  - Position, bookmarks (24 per book) and the reading font (extra small,
    small, medium) persist in `picoware/settings/picoreader/state.json`.
    The saved position and bookmarks store word offsets, so they survive a
    font change. An incremental page index caches per-chapter page counts and
    drives the whole-book progress display; it is rebuilt when the file size
    or font changes.
  - Extra-small system text is the default; colours follow the system theme.
    Three original dummy EPUBs and one TXT sample exercise reading, chapter
    boundaries, wrapping, bookmarks and accented text. Generate them with
    `tools/build-reader-samples.py`.
  - Simulator checks cover archive and TXT parsing, bounds, malformed/corrupt
    books, reading order, library opening, navigation, fonts, bookmarks,
    position/index restore, corrupt saved state, help and file cleanup. The
    app compiles with the firmware-compatible MicroPython compiler.
  - Current scope is UTF-8, text-only, DRM-free EPUB. Images, CSS layout and
    encrypted resources are unsupported. Physical SD/display/memory checks
    and a committed release remain pending.
  - All Python, using existing firmware capabilities; no firmware change.
- **PicoDict**, an additional standalone PicoDESK first pass, provides offline
  English/Italian single-word lookup. See [PicoDict.md](PicoDict.md).
  - Available: direction switching, input editing, normalization and bounded
    binary-search lookup in separately installed SD dictionary data.
  - Model/data and keyboard-driven simulator checks pass. Device SD latency,
    available heap and release integration remain pending.
  - Suggestions, stemming, conjugation tables and sentence translation are
    deferred; they are not part of the implemented first pass.

### Phase 3: Electrical

- **PicoSpice, second pass** (M):
  - AC analysis, with a Bode plot of any probe;
  - op-amp output limits at the supply rails, and junction capacitances;
  - renaming elements;
  - a readout at the cursor on the schematic after a transient;
  - probe colours checked in the light theme.

  It sends frequency responses as a linear model and waveforms as signals.
- **SmithChart** (M):
  - impedance and admittance charts;
  - reflection coefficient and VSWR;
  - moving along a line;
  - L-section and single-stub matching, with each step drawn on the chart.

  It reads impedance against frequency from PicoSpice's AC analysis.
- **Firmware:** complex LU and the AC analysis.

### Phase 4: Structural

- **StressStrain** (M) gives the stress at a point from combined loads on a
  section: axial force, bending about two axes, torsion and shear.
  - It also covers Hooke's law in 3D (stress to strain and back), plane
    stress and plane strain, thermal strain and strain-gauge rosettes.
  - It draws a stress–strain curve (Ramberg–Osgood) from the material.
  - It sends the stress state to Mohr's circle and FatigueLife.
  - A mode for plane finite elements comes in Phase 8.
  - Available: [StressStrain.md](StressStrain.md). Section loads, stress maps,
    a shared section/material editor, exact normal extrema,
    sampled shear/von Mises maxima and isotropic
    stress/strain conversion are ready for simulator feedback;
    rosettes, Ramberg–Osgood curves and shared material/exchange integration
    are pending.
- **Buckling** (S) is Euler buckling.
  - It covers end conditions (the effective length factor), slenderness,
    critical load and stress, and the safety factor.
  - It warns when a member is short enough that yielding comes first.
  - It takes a member from BeamView (length, section, axial force) and the
    material from the picker.
  - Whole frames wait for the eigensolver in Phase 7.
  - First pass available: [Buckling.md](Buckling.md). F9 starts with Euler's
    equation; direct BeamView/member exchange remains pending.
    Section and material editing now use BeamView's shared cross-section
    preview, including live drafts, in a dedicated editor.
- **FatigueLife** (M):
  - S–N curves from the material (Basquin), with surface, size and
    reliability factors;
  - mean stress corrections (Goodman, Gerber, Smith–Watson–Topper);
  - rainflow counting of a load history and Miner's sum;
  - life and safety factor.

  It reads stress states and signals.
- **FractureLife** (M):
  - stress intensity for standard cracks (centre, edge, surface, at a hole);
  - critical crack length from K_Ic;
  - crack growth by the Paris law over rainflow cycles;
  - cycles to failure and an a–N curve.

  It is built alongside FatigueLife, sharing the history import and the cycle
  counting.
- **WeldCalc** (S), in the Machine design folder:
  - fillet and butt welds;
  - weld groups treated as lines, with centroid and polar moment;
  - direct and torsional shear;
  - allowable stress and safety factor;
  - fatigue classes of welds.

  Each calculation comes with a short practical note.
- **PicoPlayer** (M), on the PicoDESK side, plays MP3 and WAV files from
  `picoware/music/`.
  - It browses by folder and by ID3 tags, with a playlist, shuffle and
    repeat.
  - It has volume, progress and a small level display.
  - The decoder streams into `pcm` through two alternating buffers.
  - Playing in the background of other apps is a later decision, because it
    costs memory and processor time in every app.
- **Firmware:** the MP3 decoder.

### Phase 5: Fluids

- **FlowRegimes** (S):
  - Reynolds, Froude and Mach numbers for pipes, channels, plates and
    bodies;
  - laminar, transitional or turbulent flow;
  - friction factor (laminar, Colebrook, Haaland), with the Moody chart in
    Grapher.

  Properties come from PropTable.
- **PipeLoss** (M):
  - Darcy–Weisbach losses along pipes in series;
  - fittings from a catalogue of K values;
  - changes of height;
  - the system curve, and the operating point on a pump curve imported as a
    table.
- **BoundaryDrag** (S):
  - flat-plate boundary layers (Blasius when laminar, power law when
    turbulent, and the transition);
  - thickness and skin friction along the plate;
  - drag coefficients of standard shapes against Reynolds number;
  - terminal velocity.
- **1DNetSolve** (L) draws pipe networks in PicoSpice's editor: nodes on a
  grid, with elements between them.
  - Elements are pipes, pumps with curves, valves, reservoirs at a fixed
    head, and demands at nodes.
  - The circuit kernel solves it: head is the voltage, flow is the current,
    and a pipe is a nonlinear resistor, h = K·Q·|Q|.
  - Probes, plots, results and cases work as in PicoSpice.
  - The editor first moves out of `engtools/spice` into a shared network
    editor driven by a catalogue of elements.
- **Firmware:** hydraulic elements in `circuit.c`.

### Phase 6: Thermal

- **HeatExchanger** (M):
  - LMTD and ε–NTU for parallel flow, counterflow, shell-and-tube and
    crossflow;
  - rating (outlet temperatures of a given exchanger) and sizing (the area
    for a duty);
  - U from the wall and two film coefficients, using the correlations from
    the fluids work (Dittus–Boelter, Gnielinski) and properties from
    PropTable.
- **Cycles** (M):
  - Rankine with reheat, Brayton, Otto, Diesel and vapour-compression
    refrigeration;
  - a table of states, with work, heat, efficiency or COP;
  - T–s and P–h diagrams in Grapher.
- **ThermalField** (M), which is Heat transfer 2D today:
  - regions of different materials from the picker;
  - contact resistances;
  - temperatures sent as thermal loads to StressStrain.

  Shapes other than rectangles wait for MeshGen.

### Phase 7: Dynamics

- **Firmware:** the eigensolver and the ODE integrator.
- **ModalHarmonics** (L) finds natural frequencies and mode shapes.
  - It covers spring–mass chains, shear buildings and frames imported from
    BeamView.
  - Modes are animated, and harmonic response with damping is plotted.
  - It sends modal data as a linear model.
  - Buckling then also covers frames.
- **TransferFunc** (M):
  - transfer functions typed as polynomials or as poles, zeros and gain, or
    imported from PicoSpice AC or ModalHarmonics;
  - Bode and Nyquist plots, step and impulse responses, poles and zeros,
    gain and phase margins;
  - root locus later.
- **TransientSolve** (M) solves linear and nonlinear transients:
  - ODE systems typed as formulas, x' = f(t, x);
  - M, C, K systems of several degrees of freedom with forcing (Newmark),
    where the forcing can be an imported signal.

  It sends signals to FatigueLife and Grapher.
- **Multibody** (L) simulates planar rigid bodies.
  - Bodies connect with pin and slider joints, springs, dampers and gravity.
  - It covers four-bars, slider-cranks and pendulums, with the motion
    animated and joint forces plotted.
  - It comes last in the phase.
- **PicoMail** (L), on the PicoDESK side, reads mail over IMAP and sends it
  over SMTP, both over TLS.
  - It has folders, plain-text reading (HTML reduced to text), compose and
    reply.
  - Attachments come from and go to the SD card, so any export can leave the
    device and CSV, EPUB and MP3 files can arrive.
  - Passwords stay on the Pico's internal flash, following the rule in the
    connectivity roadmap.
  - The risk is memory, because a TLS session takes tens of KB. PicoMail
    therefore runs with everything else unloaded.
  - Certificates are checked against a CA bundle, which needs the clock set
    by NTP.
  - It starts with providers that allow app passwords (Gmail does);
    sign-in through OAuth only is out of scope at first.

### Phase 8: Machine design and meshes

- **PicoCAD** (L), which is partial today, gains:
  - 2D profiles of lines and arcs, extruded or revolved;
  - section properties of a profile, sent to BeamView as a section;
  - mass properties with a material;
  - STL export;
  - fillets and chamfers, later.
- **GearGen** (M) generates involute spur gears; helical gears come later.
  - The profile comes from module, tooth count and pressure angle.
  - It reports the mesh: contact ratio, centre distance and backlash.
  - It gives Lewis bending stress and contact stress.
  - Gear trains show speed and torque on every shaft, with a 2D drawing of
    the gears in mesh.
  - Profiles go to PicoCAD and stresses to FatigueLife.
- **MeshGen** (L) builds triangle meshes of PicoCAD's 2D profiles.
  - It uses constrained Delaunay triangulation, with sizes set by the user
    and refinement near holes.
  - Boundary groups carry loads and supports.
  - It writes `.pmesh` files, and STL for a computer.
  - 3D tetrahedral meshing is out of scope.
- **Firmware:** plane triangle elements. With them, StressStrain gets a mode
  for plane finite elements (with a von Mises field), ThermalField solves any
  meshed shape, and ModalHarmonics gets 2D modes.

## What each new app needs first

Section Properties has a standalone first pass; see
[SectionProperties.md](SectionProperties.md). Its UI/utility review comes
before connecting it to BeamView, Buckling, StressStrain or PicoCAD.

| App | Needs |
|---|---|
| app-to-app handoffs and shared reports | the exchange layer; standalone PicoReader and PicoDict first passes do not require it |
| StressStrain, Buckling, FatigueLife, FractureLife, WeldCalc, GearGen | Materialprop |
| FlowRegimes, PipeLoss, BoundaryDrag, HeatExchanger, Cycles | PropTable |
| SmithChart, TransferFunc imports | PicoSpice AC |
| FatigueLife, FractureLife | rainflow counting |
| 1DNetSolve | the shared network editor and hydraulic elements |
| HeatExchanger | the correlations from FlowRegimes and PipeLoss |
| ModalHarmonics, Buckling of frames | the eigensolver |
| TransientSolve, Multibody | the ODE integrator |
| MeshGen | PicoCAD profiles |
| StressStrain, ThermalField and ModalHarmonics on meshes | MeshGen and plane elements |
| GearGen to PicoCAD | PicoCAD profiles |

## Budgets for each app

Measure these with the device benchmark before each release.

- **Code:** about 50 KB of `.mpy` or less for a calculator-style app, and
  about 85 KB or less for an editor (BeamView is 82 KB, PicoSpice 48 KB).
- **Heap:** at least 150 KB free with the app open and a case solved, so
  that saving, exporting and Send to never run out of memory.
- **Files:** case and exchange files of 32 KB or less, the same as today.
  Anything larger, such as long signals or meshes, is streamed to and from
  the SD card.

## Open questions

1. Your list places Machine design without a number between Structural and
   Dynamics, and skips 6. This plan treats Machine design as its own folder.
   Is something else meant to be 6?
2. Should menu labels use the list's names (BeamView, ThermalField) or stay
   as they are now (BeamView, Heat transfer 2D)?
3. Should PicoPlayer play in the background while other apps run?
4. Which mail providers does PicoMail need to support first?
