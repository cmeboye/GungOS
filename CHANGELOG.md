# Changelog

## v1.1 performance hardware test — 2026-10-18

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
