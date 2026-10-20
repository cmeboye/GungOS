# Changelog

## Unreleased

- The home screen's resource snapshot (every 5 s) walks the heap once
  instead of twice: `gc.mem_free()` and `gc.mem_alloc()` each walk the whole
  heap (5 ms on the device), and the heap total never changes. 11.1 → 6.3 ms.
  The core benchmark also times the snapshot's parts.
- The PSRAM screen image is written in 120-byte transfers instead of 64, each
  as one DMA transfer instead of two (command, then data). Clearing the
  screen went from 2.85 to 2.22 ms, lines and circles 17–29% faster, menus
  and the home screen about 10%. 128 bytes more RAM.
- Looking a name up by its text (imports, loading apps) searches the
  firmware's sorted names before the names loaded from SD apps; importing
  a module that is already loaded went from 154 to 65 µs. A local
  MicroPython option (`MICROPY_QSTR_FIND_SORTED_FIRST`).
- An alert updates the screen once instead of first sending a blank screen
  (no flash, 46 → 8 ms), and headers keep the decoded logo instead of
  decoding it on every draw (menus 26 → 14 ms).
- New strings (formatting, concatenation, slices) are no longer matched
  against every name loaded from SD apps before being created: `%d`
  formatting went from 57 to 10 µs on the device. A local MicroPython
  option (`MICROPY_STR_REUSE_QSTR`, see `vendor/micropython-local.patch`).
- The flash runs at 120 MHz instead of 60 MHz. MicroPython derived its
  limit from the 150 MHz default clock, so at 240 MHz the flash ran slower
  than on a stock Pico 2 W. Imports are about 20% faster, menus 16%.
- A core benchmark (F6 in the EngTool render benchmark) times the whole
  firmware core: clock (checked against the cycle counter), heap and
  fragmentation, the Python interpreter, imports, every drawing primitive and
  swap in both screen modes, the core screens and the home screen, system
  services, PSRAM and SD throughput. `tools/compare-benchmark.py` compares two
  reports.
- The on-screen keyboard no longer offers word suggestions. The
  `auto_complete` native module, its Python wrapper and the SD
  `picoware/keyboard` folder are gone. The last code for the upstream
  author's online service is removed too: the settings migration for its
  account fields, the endpoint guard script and its test.
- Fix SD directory corruption: a new entry whose slots crossed a cluster
  boundary overwrote the start of the directory ('.', '..' or other files).
  New directories are cleared in full, so old data in a reused cluster no
  longer hides or invents entries. Deleting a long name that crossed a
  cluster leaves no stray parts. Long names of 248–255 characters no longer
  overrun stack buffers; over-long paths are refused instead of being cut to
  another name. Clusters past the end of the volume are no longer counted.
- SD access reads far less: the driver keeps the last sector it read
  (directory scans, FAT lookups), whole-sector writes skip their read,
  seeks no longer restart at the file's first cluster, and short-name
  collisions are found in one directory pass (a measured workload went
  from 5.6 million block reads to 182 thousand). A host test now checks
  the driver against an in-memory card.
- Presenting the screen reads each changed PSRAM row once instead of twice;
  the panel's DMA buffers, the 12-bit palette and the SD read buffer are
  gone (8.9 KB more heap). Key and character lookup uses byte tables.
- The home screen retries saved Wi-Fi and the network clock every 10 s
  instead of every frame, and menus list the SD app folders only when
  something new was imported. Inverted image blits no longer modify the
  caller's buffer; ViewManager.remove keeps the other views; thread
  timeouts survive the tick counter wrapping. Remove the unused Picoware
  start-up animation.

- Allow point/moment load offsets from terminal nodes without resetting them
  to zero, including older saved cases. Explain missing member connections
  when adding a load; identify and select orphaned items on evaluation.

- Beam view uses Node / Member / Support / Load tabs, independent Rigid/Pinned
  nodes, live endpoint/section choices, degree expressions and Shift+E section
  editing. Node-relative supports/loads include branch selection, endpoint
  support locking and signed global X/Y settlement. Add a pinned bridge demo.
- F6 is now the only Beam evaluation command. Editing/Open/Undo clear results
  and displacement; navigation retains them. Plots/results/export require F6.
- Validate overlap, coincidence and unsplit used nodes in the solver API.
  Add explicit undoable Merge nodes, Split at node and previewed Resolve
  overlaps, preserving loads and refusing ambiguous conflicts. Keep crossing
  members separate even when interior load stations share coordinates.
- Save Beam schema 3 with migration of previous models and settlements.
  This revision updates SD apps; the v1.32 native solver is sufficient.
- Fix Beam max stress at a section change (the smaller section now governs
  at its joint), whole-frame plots drawn in the active member's colour,
  section names printed over a straight beam, section edits exceeding the
  12-step undo, removal of a load case still used by a settlement, and
  orphaned items or hinges moving on split/resolve or crashing a redraw.
- The evaluated preview, F5 Results and whole-frame plots are built once per
  view instead of on every key; remove the old editor's unused insert,
  length/angle and layout code.
- Remove the Blank beam template (Blank structure remains). Older models'
  downward settlement becomes Settlement Y when opened and is no longer saved.

## v1.32 — 2026-10-19

- Add the on-device EngTool render benchmark under Apps → Misc. It measures
  Beam model/diagram/overview drawing and direct PicoCAD geometry, camera and
  rendering across PSRAM and SRAM, including a Full stress ladder, repeated
  build/release cycles and explicitly labelled Beam cases beyond editor limits.
  SD checkpoints, cancel/skip, time/heap guards and expected CAD refusal probes
  help locate the hardware limit. F4 retains the display/CPU baseline suite.

- Expand Settings → Appearance with accent, background, text on dark and text on
  light colours; include 32 swatches, custom hex entry, a combined contrast
  preview, transactional Save/Cancel and a reset to GungOS defaults.
- Apply appearance roles across the dashboard/status bar, logo canvases, native
  selections and shipped app chrome, including all calculator modes and widget.

- PicoCAD in PicoLAB → Tools: direct analytic primitive wireframes, perspective
  and parallel projection, camera controls, an XYZ guide and verified `.pcad`
  project files. Supported Boolean cases include containment, box operations,
  cavities, angled/blind bores and trimmed one-side cylindrical through-notches.
  Typed diagnostics distinguish invalid input, unsupported operations, precision,
  topology and resource limits; empty and unchanged results remain successful.
  Includes geometry/UI regressions and a reproducible desktop benchmark.
- Shrink fit in PicoLAB → Modules → Structural: up to six concentric discs or
  cylinders (solid or bored) with rotation, inner and outer pressure and an
  interference fit at each interface (Lamé, plane stress or plane strain).
  Any N−1 of the speed, pressures, interferences and contact pressures can
  be marked Find (SPACE) and are solved from the rest, so it also finds the
  interference for a contact pressure or the speed at which a fit comes
  loose; a wrong count or an impossible combination is reported. Hatched
  cross-section or an orbiting 3D wireframe (F6 focuses the preview), stress
  plots through the radius (F4) and results (F5): peaks, von Mises safety,
  holding torque and axial force, assembly heating, loosening speed,
  inertia and kinetic energy. Beam view's F1–F5 keys. About 64 KB of heap
  while open. See [Shrink fit](guides/ShrinkFit.md).
- The F5 results list is shared (`engtools/ui/lab.py`); Beam view's run
  headings are no longer clipped at the left edge.
- Mohr circle in PicoLAB → Modules → Structural: a 2D plane-stress or 3D
  stress state typed in MPa, drawn as Mohr's circle(s) beside the element
  turned by theta. Left/Right turn the element 1 deg ([ / ] 15 deg), P and S
  jump to the principal and maximum-shear axes, and in 3D A picks the rotation
  axis (x, y or z). Shows rotated stresses, principal stresses and angle,
  maximum shear, von Mises and Tresca, and safety factors against a yield
  strength. F3 has worked examples. About 29 KB of heap while open, all
  returned at the PicoLAB menu. SD update only. See
  [Mohr circle](guides/MohrCircle.md).
- Beam view plots axial displacement u (along the member, positive toward its
  end) as a third diagram panel (`D`), with its peaks under Tab and in F5
  Results for frames, and for straight beams that carry axial load.
- Beam view's model preview is 184 pixels tall instead of 142: the tabs and
  property list move down and show three rows at a time, and the result
  summary is a box toggled with `I` (model problems always show).

## v1.31 — 2026-10-19

Fixes the v1.3 performance problem below; use v1.31 instead of v1.3. Tested on
hardware: Beam view runs without freezes.

- Closed SD apps give their heap back. Their modules used to stay loaded until
  reboot (after Beam view, Graph and Graph3D about 275 KB in the simulator);
  the firmware menus now unload SD app modules once no SD app is open, and
  PicoLAB unloads a tool's code when you return to its menu (Beam view alone
  is over 100 KB). Beam view keeps its model while PicoLAB is open, without
  the undo history; Graph3D saves its surface and ranges to SD. Beam view
  caches fewer diagram samples. The first load of a tool still interns its
  names once (about 35 KB for Beam view); repeated visits add nothing.

## v1.3 — 2026-10-19

> **Known issue, fixed in v1.31:** closed SD apps kept their code and data in
> RAM until reboot, so the heap climbed during use and stayed high after
> leaving Beam view, Graph or Graph3D, and performance degraded over a
> session. Do not use v1.3; flash v1.31.

- Graph and Graph3D share Beam view's screen parts (`engtools/ui/lab.py`): the
  PicoLAB title bar, panels, menus, one-line footer and F9 help. Window
  values, settings and equations are typed in place on the hardware keyboard;
  the on-screen keyboard is gone from both.
- Graph3D ranges: X, Y and Z minimum/maximum, Z Auto or Fixed (clips z=f, or
  bounds an implicit volume), Equal or Box aspect.
- Graph3D heat map: z = f(x, y) as colour with a colour bar, contours and a
  probe reading x, y, z; implicit surfaces refuse it with a reason.

- Beam Lab in PicoLAB: build a beam on its drawing (supports, springs,
  hinges, point, moment and distributed loads, section changes with material
  and shape presets), solved after every change by `picosolve`. Diagrams of
  shear, moment, deflection and slope with a cursor, peaks and pinned points;
  reactions with an equilibrium check; load cases and factored combinations;
  undo; save/open and CSV export. See [Beam Lab](guides/BeamLab.md).
- Beam Lab frames: members at any angle joined at joints (B adds a member,
  C splits one for a section change), loads acting down, normal to the member
  or horizontally, normal force and stress results, and a whole-frame view of
  moment (tension side), shear, normal force and the deflected shape. The
  sketch fits the whole structure at one scale and zooms with + and -.
- Beam Lab section editor: the cross-section drawn to scale with the edited
  size highlighted; I, T, rectangle, hollow rectangle, circle, tube or direct
  values; A, I, W, mass per metre and EI; a section library shared by
  members; optional self-weight. Beams saved by the first Beam Lab open
  unchanged.
- `picosolve.Frame`: plane frames with three DOFs per node, axial loads and
  results; the beam model is unchanged. Needs the new firmware UF2.
- `engtools.units`, `engtools.cases` and `engtools.ui.forms` are implemented
  (fixed engineering SI units, verified JSON cases, streamed CSV export,
  single-line input with arithmetic).

## v1.2 — 2026-10-18

- Refresh desktop/menu branding with native-resolution logos; PicoDESK and
  PicoLAB lettering and underlines follow the system accent. Archive old artwork.

- Consolidate the tested v1.1 performance work into a matching firmware and SD
  release: native graphics, changed-row DMA, built-in import caching, C formula
  and plot geometry paths, and the beam solver with lower working memory.
- Preserve the shared-PSRAM lifetime fix that resolved display blackouts.
- Reuse Graph's contour work arrays across rows; keep beam numbering scratch
  temporary and model inputs in float32, with double-precision solver arithmetic.
- Full-screen Lorenz now borrows the faster SRAM screen while open, restoring
  the user's preference on exit. If SRAM is unavailable it keeps drawing from
  PSRAM. The native-size widget keeps its own RAM surface and 8 FPS cap.
- Native-size widgets now take a direct row blit, avoiding redundant resampling
  and its temporary row allocation; arbitrary-size widgets still scale to fit.
- Report v1.2 in the desktop footer and About page; preserve existing SD settings,
  documents, credentials and optional audio when installing the app update.

## v1.1 performance hardware test — 2026-10-18

- Display recovery: native PSRAM interfaces share the bus and allocator.
  Constructing an interface for resource counters preserves existing allocations;
  collecting an interface no longer tears down hardware used by the LCD. Public
  methods remain available on the native type. A host regression runs the actual
  device binding with an emulated QSPI chip; physical blackout verification is pending.
- GungOS now targets only the PicoCalc with a Raspberry Pi Pico 2 W. Code for
  other boards (Flipper Zero, Cardputer, Waveshare, CrowPanel, Pancake, V8,
  PicoDuo, POOM, other PicoCalc Pico variants) is removed from the firmware,
  native modules and simulator; `picoware.system.boards` keeps the upstream
  board constants only so existing Picoware SD apps still import.
- Removed leftovers of retired features: LVGL, USB video, media playback,
  AI/MCP settings, C/JavaScript/MMBasic runners, Game Boy/Ghouls backends,
  ESP flasher, touch and round-display layouts, and the legacy desktop.
- Settings for retired features are dropped from `picoware.json` on load/save.
- Screenshots moved from F1 to **Alt+S** (any screen); F1 belongs to apps.
  The keyboard driver now reports Alt+letter as distinct keys.
- Simulator `--sim-check` runs eleven PicoCalc checks that were previously
  unreachable; all pass.
- App crashes show the exception with its file and line, and the full
  traceback is saved to `picoware/last_crash.txt` on SD. Alerts honour
  line breaks.
- Key-wait loops (alerts, yes/no dialogs, serial info) sleep between polls
  instead of spinning the CPU.
- A fatal error offers a restart (any key) or a stop at the REPL (Esc)
  instead of leaving the device stuck.
- Fixed: System > Shutdown and saving a scanned Wi-Fi network crashed.
- Wi-Fi, SSH and access point passwords are kept in the Pico's internal
  flash instead of in plain text on the SD card; existing SD copies are
  moved automatically.
- Display: `swap()` sends only the rows that changed, by DMA, and returns
  the number of rows sent; drawing writes whole row spans instead of single
  pixels. Measured on the device: a whole screen takes 23.2 ms (the panel
  link's limit is 21.8 ms), one changed text line 0.46 ms.
- The screen image stays in PSRAM by default, keeping 366 KB of heap free.
  **System > Settings > Fast Drawing** moves it to on-chip SRAM, about 2.5×
  faster drawing for 100 KB of RAM (266 KB free). Graph3D and Tetris borrow
  the SRAM screen while open (`view_manager.request_fast_drawing()`); it is
  returned when they close, also after a crash.
- Graph3D draws each frame with a C renderer (`gfx_mesh`: rotate, project,
  depth-sort, clip, shade and outline in one call). It produces exactly the
  Python renderer's image except that colours come from a 256-step table;
  firmware without it falls back to Python. The benchmark times one frame
  both ways.
- The built-in `picosolve` module (beam solver) is now part of the firmware:
  `picosolve.Beam` with supports, springs, hinges, settlement, point, moment
  and line loads, load cases, reactions, end forces, exact sections and
  diagram buffers. It can solve on the second core with progress and cancel,
  and picks single precision with refinement or double automatically.
  Problems raise `picosolve.SolveError` naming what is at fault. The
  benchmark times a 600-element beam in both precisions.
- Implicit plots build their geometry in C (`picosolve` geometry
  functions): Graph3D's surfaces and implicit isosurfaces (marching
  tetrahedra) and Graph's implicit curves (marching squares). Output is
  identical to the Python builders; implicit surfaces build 2–4× faster in
  the simulator, implicit curves 1.1–1.6× (their remaining time is formula
  evaluation).
- Formula compiler: `picosolve.Formula` compiles a plot formula once and
  evaluates it in C, a row or plane at a time. Graph and Graph3D use it for
  every curve, inequality, parametric pair and surface; results are
  bit-identical to Python's `eval` (60,000 random evaluations, and every test
  plot pixel for pixel), and a formula it cannot match exactly keeps using
  `eval`. In the simulator, formulas evaluate 23–74× faster and implicit plots
  draw 4–7× faster. The benchmark has a "Formula compiler" step.
- Graph's per-point drawing runs in C (`gfx/gfx_plot.c`): explicit and
  parametric curves with inequality shading, implicit-curve segments, and the
  dotted fill of inequality regions (`draw._stipple`). Pixel for pixel the
  same as the Python loops on 14 test plots; 5–20× faster in the simulator.
- Calculator integrals (`int(a,b,f)`) and the equation solver evaluate
  compiled formulas: identical results, integrals 10–20× faster in the
  simulator. Compiled integrands are no longer cut off by the 60,000-step
  work limit, which only guarded the slow evaluator.
- C code that copies Python's arithmetic (formulas, Graph drawing, the 3-D
  renderer) is built without fused multiply-add, which rounds differently.
- The benchmark records the processor clock and adds "Graph drawing" and
  "Calculator" steps (Python versus C).
- Beam solver memory: inputs (positions, springs, E, I, loads) are stored as
  float32, as they arrive from Python (all arithmetic stays double), and
  the equation-numbering scratch is freed right after numbering. A
  600-element beam needs 91 KB instead of 121 KB, with results unchanged.
- Graph's implicit curves reuse their per-row work arrays: 63% less memory
  allocated per plot, so fewer garbage collections.
- Imports: MicroPython does not cache "extensible" built-ins (array, time,
  json, os, struct, ...), so every import searches each sys.path directory
  on the SD card first: about 70 ms per import on the device. Startup now
  caches them in sys.modules (`main._cache_builtins`), and Graph and
  Graph3D import array once at module level. This was why Graph's C
  drawing measured no faster than Python on the device (one plot spent
  30 s in about 450 such imports) and much of a 3-D frame's time.
- Fixed (review): compiled formulas could give a wrong answer where whole
  numbers passed 2^24 (Python's ints are exact; float32 is not), e.g. an
  integral returning 0 instead of 1. Such points are now evaluated in
  Python; exact whole-number powers no longer use `powf`.
- Fixed (review): `Beam.free()` left the model usable on released memory,
  and a MemoryError while reallocating left a dangling block. A freed model
  now refuses every use, and blocks are never left pointing at freed memory.
- Fixed (review): a parametric plot whose y(t) could not be compiled while
  x(t) could lost t and drew nothing.
- Fixed drawing bugs: shapes and lines crossing the left or top edge no
  longer reappear at the far side; rounded rectangles keep their shape when
  clipped; JPEG and 16-bit images clipped at the right edge are no longer
  sheared; methods on a plain `lcd.LCD()` object are reachable.
- The simulator runs the firmware's own drawing code, so it shows the
  device's exact pixels and colours, and reports how many display rows the
  device would have sent.
- New **Apps > Misc > Benchmark** (SD app): times whole-screen, one-line
  and identical-redraw swaps, drawing in SRAM and PSRAM modes, free memory
  in each, an experimental 12-bit panel colour format (with a Y/N colour
  check) and interpreted Python against ulab's C code. Results are saved to
  `picoware/benchmark.txt`.
- Experimental: `draw.set_panel_bits(12)` sends 12 instead of 16 bits per
  pixel (a quarter less per frame) if the panel accepts it; it resets to 16
  on power-up.

These changes require a new UF2 and matching SD apps.

The final released v1.1 desktop, logo, status icons, themes and 238 × 238
widget canvas are retained. Release version remains 1.1.

## v1.1 — 2026-10-17

- Add the compact 320 × 320 desktop: native-size revised logo, black status bar,
  heap/PSRAM/SD usage bars and F1 resource details. A 238 × 238 widget fills the
  square panel; narrow-menu labels use the smallest font and wrap when needed.
  Center the new large logo, leave one-pixel panel margins and show v1.1 in the footer.
- Add 30 theme swatches and custom RGB hex colours, with preview, confirmed saves
  and readable text on bright accents.
- Smooth Lorenz with adjustable detail, trail capacity, FPS and performance stats.
  Keep the 8 FPS widget-host limit explicit and recover from SD/heap errors.
- Improve Eggcel keyboard shortcuts, range selection, fill down/right, conversion
  of formulas to values, undo and XY/column/pie plotting with local error recovery.
- Fix cooperative Wi-Fi joins, station/AP switching, saved settings, NTP recovery
  and bounded local HTTP serving. Improve BLE discovery, UART transfer and cleanup.
- Remove inherited upstream social/update/notification services and account fields.
- Preserve Esc-only navigation, Back/Del editing, PicoDESK, PicoLAB, Graph/Graph3D
  and Tetris. Keep selected float32 ulab and native PCM audio support.
- Package matching RP2350 UF2 and SD bytecode with checksums. Default public
  packages omit supplied recordings; optional personal audio is packaged separately.

Device validation is pending the first PicoCalc flash. Simulator timings and heap
sizes reflect the host. Secure Bluetooth pairing is unavailable in this native
backend; the existing HTTPS certificate and SSH host-verification limitations are
recorded in [Connectivity](guides/Connectivity.md) and [Comms](guides/Comms.md).

## v1.0

Previous GungOS release: dark desktop, PicoDESK/PicoLAB applications, scientific
calculator, plotting, Tetris and initial calculator/Lorenz widgets. Previous local
files are retained unchanged for rollback, including their legacy development filenames.
