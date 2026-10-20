# EngTool render benchmark (v1.32)

Open **Apps → Misc → EngTool render benchmark**. This is the `misc/Benchmark.mpy`
entry on the SD. The old display/CPU suite remains available with F4.

## Hardware test

Install the matching v1.33 UF2 and complete SD app update. Restart first so the
run begins with a predictable heap. For a short smoke test, press F2 to choose
Quick, leave F3 at Both, then Enter. Restart again, leave the default Full stress
and Both choices, and press Enter for the stress ladder. Full can take several
minutes on the Pico. The app does not write your engineering models or appearance
settings. Existing cases are neither loaded into the test nor replaced.

| Key | Action |
| --- | --- |
| Enter | Start |
| F2 before starting | Full stress / Quick |
| F3 before starting | Both / PSRAM / SRAM framebuffer |
| F4 before starting | Original display/CPU benchmark |
| F6 before starting | Core benchmark (whole firmware) |
| F5 during a run | Skip the current case |
| F9 | Scrollable help; Up/Down scroll |
| Esc | Close help, or cancel and retain partial results |

The report is **`picoware/engtool-render-benchmark.txt`**. Send that file after the
hardware run, including if the run stops. Each line is a JSON record so a partial
file remains readable. A new run overwrites this report only when Enter starts it;
copy a previous report first if comparing profiles. The F4 baseline uses the
separate original `picoware/benchmark.txt`.

## Workloads

Full runs 37 cases in each framebuffer mode: **74 total**. Quick runs nine per
mode. Only the current synthetic model is allocated.

- Beam: 1, 4, 8 and 16 connected members; a 16-member six-load-case/six-combination
  case; portal frames with 1, 3 and 7 bays. Each draws the model preview,
  individual-member diagrams and whole-model overview. Three frames change
  preview zoom, cursor or overview quantity, including the first cold frame.
- Synthetic Beam: 32, 64 and 128 members and 15/31-bay portal frames. These use
  the real model/solver/render API above the editor's 16-member/48-item limits.
  They do not expand the limits of the normal editor; `synthetic: true` labels
  them. A large native solve is a single call.
- PicoCAD: box, sphere and cone; 1, 2, 4 and 8 separate cylinders at curve
  qualities 6, 12 and 24; two/four/seven through-bores; an open side notch.
  The normal adaptive analytic curve/silhouette renderer draws perspective
  and parallel/isometric projection paths at 1×, 4× and 16× camera zoom.
- Five-cycle build/render/release tests repeat an eight-member Beam and an
  eight-cylinder CAD model. Their post-cleanup free-heap samples help reveal
  retention across identical iterations.
- Expected refusals: a ninth CAD feature, a zero-radius cutter and an unsupported
  corner breakout. These should say `expected refusal`, not `error`. A current
  algorithm/editor limit is distinct from exhausting the Pico's resources.

## Measurements

Each case records its actual screen mode, model size, status and free heap.
Times are in microseconds with normal automatic garbage collection enabled.

- `model_us`: synthetic input construction.
- `solve_prepare_us`: each Beam solve plus its normal diagram preparation.
  `native_info` contains the solver's byte count, precision and conditioning.
- `build_active_us`: CAD constructor plus active analytic-builder steps, excluding
  time spent yielding to the benchmark loop and its GC instrumentation.
  `build_wall_us` additionally includes that scheduling/GC overhead. For a
  repeated CAD case these two timings describe the last cycle.
- `fit_us`, `segments` and `packed_bytes`: CAD camera fit, projected segment count
  at the fitted view and packed analytic boundary payload. Segment count is
  before viewport clipping and before the later zoom changes.
- `pages`: first/median/max frame time, median drawing time excluding swap,
  median swap time and actual dirty-row counts for all three frames. Frame and
  drawing timings include the ordinary cache/GC work those frames require.
- `sampled_live_gc_bytes`: largest observed live GC-heap increase after collection
  at yield/frame boundaries. It is a lower bound, **not** a transient allocation
  peak or a count of all native memory. `native_info.bytes` is reported separately;
  do not assume those two counts are disjoint or add them together.
- `cycle_free_bytes`: free GC heap after each build/release cycle. Small changes
  can include result bookkeeping and cache warming, not necessarily a leak.

Only one engine's SD modules are retained between families, so inactive Beam
code does not consume CAD's benchmark heap. Imports occur outside model/build
timings. The report's free-heap baseline includes the benchmark, shared modules,
current framebuffer and any other state that is still live.

## Finding the boundary

Before every case and risky phase, the benchmark closes an appended SD checkpoint.
If the board hangs or resets, the final `START`/`phase` record identifies the
attempted workload. Completed measurements above it are retained.

The benchmark stops a case if free GC heap falls below its 32 KiB reserve, a
MemoryError occurs, or measured work exceeds 30 seconds between calls. Native
solver calls, imports, drawing calls and SD I/O cannot be preempted from Python;
the soft deadline and Esc cannot rescue a native hard lock. No watchdog is added.
After a resource failure or unexpected error, remaining cases in that engine
family/screen mode are skipped; the other family/mode and refusal probes continue.
F5 skips just one case. Screen storage is restored on exit, cancel and cleanup.

`slow_frame: true` marks a frame above 200 ms; it does not stop the ladder. A run
that reaches every planned case has reached the planned workload ceiling, not
proved an unlimited hardware capacity. Simulator results validate the harness
and recovery paths; only the physical run establishes Pico performance.

The normal 16-bit panel transfer format is retained. F4's separate display suite
still offers its explicitly enabled experimental 12-bit test.

Both reports name the firmware build (`build` in the render report, `Firmware
build` in `benchmark.txt`), so runs on different UF2s of the same version can be
told apart. The F4 suite ends with a read-only SD stage: listing the apps folder,
the app-folder scan menus used to run, file lookups, reading the largest app module
in 512-byte and import-sized pieces, and the saved Wi-Fi lookup. It writes nothing
except its report, so it is safe to compare on an older firmware's SD driver.
On the F4 suite's first screen, F5 runs only the memory and SD stages. A stage that
runs out of memory is reported as `ran out of memory` with the heap left after
cleanup, keeping what it had measured, and the later stages still run.

## Core benchmark (F6)

F6 on the first screen opens a suite that times every part of the firmware
core the same way on each build, so the reports of two UF2s compare line by
line. Restart first. F2 sets the rounds (10, 3 or 1; ten take about 16
minutes), F3 turns the SD write tests on, and Enter starts. The report is
**`picoware/core-benchmark.txt`**, saved after every step. Within a round each
value is the fastest of several runs. The timing steps repeat every round, and
each report line gives the mean with its minimum, maximum and spread (standard
deviation as a percentage of the mean). System runs once at the start and
Memory afterwards once at the end.

| Step | What it measures |
| --- | --- |
| System and memory | Build, reported clock, heap total/free, largest free block, modules, PSRAM free |
| Processor clock check | The real clock: Cortex-M33 cycle counter against the crystal-driven µs timer |
| Python interpreter | Cost per operation of loops, arithmetic, calls, attributes, dicts, allocation, formatting, generators, exceptions; full garbage collection |
| Imports | Frozen and SD module imports, a cached import and a missing-module search |
| Drawing, SRAM / PSRAM screen | Every C drawing primitive, text in three fonts, the Python `Draw` wrappers, and swaps of a whole screen, a quarter, one text line and nothing |
| Screens | Menu, list, text box, alert, status bar, on-screen keyboard and the home screen (open, full draw, idle frame) |
| System services | Input, keyboard and battery reads over I2C, RTC, the home screen's 5 s resource snapshot, settings load, thread manager and Wi-Fi polling |
| PSRAM | Write, read, fill and copy throughput; 8-bit access; drawing from PSRAM |
| SD card | Free-space query; 64 KB writes, appends and reads through the driver and `open()`; small-file create, look-up, rename, delete; JSON save/load |
| Memory afterwards | Heap held after all steps and the largest free block (fragmentation) |

The PSRAM step uses only a block it allocates. The SD write tests are off by
default; switched on, they run once, after the first round, in
`picoware/core-benchmark-tmp`, which they remove afterwards. Back up the card
first. Modules re-imported for timing are put back, so the running system keeps
its own copies. A step that fails or runs out of memory is recorded and the
next step still runs.

To compare two reports, for example a baseline and a candidate build:

```sh
python3 tools/compare-benchmark.py core-baseline.txt core-candidate.txt
```

It lists the lines that changed by at least 5% and marks each better or worse
(`--all` lists every line). A change smaller than the spread of either report
is noise.
