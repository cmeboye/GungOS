# PicoCAD direct-versus-sampled comparison

**Historical comparison:** these figures were captured before the sampled
backend was removed. Current PicoCAD includes direct geometry only. The original
comparison code has also been removed; the current benchmark measures direct
construction across all curve quality settings.

Captured on 2026-10-19 using the desktop MicroPython simulator, with a 16 MiB
heap and native float32 ulab/picosolve. These are **host measurements**, not
on-device Pico benchmarks. The UI, camera controls and `.pcad` format are unchanged.

Identical input: a 40 x 30 x 10 mm box, minus a centred cylinder of radius
5 mm and height 16 mm. Both paths receive the same model and quality N.

## Build time

Median of nine warm runs per backend/quality. Includes construction validation,
geometry generation and, for sampled builds, edge extraction. Direct timings
include the app backend selector. Imports, drawing, camera fitting and I/O are
excluded. Normal garbage collection remains enabled.

| N | Sampled median (ms) | Direct median (ms) | Sampled triangles | Direct lines / circles |
|---|---:|---:|---:|---:|
| 6 | 22.792 | 0.189 | 672 | 12 / 2 |
| 8 | 64.841 | 0.186 | 1832 | 12 / 2 |
| 10 | 120.505 | 0.183 | 3240 | 12 / 2 |
| 12 | 196.387 | 0.181 | 5032 | 12 / 2 |

## Heap and display work

Memory is measured in separate passes so instrumentation does not affect the
timing results. Modules are preloaded; a collected baseline is subtracted.
“Observed peak” samples live MicroPython heap after collection at each builder
yield and after completion. It is a **lower bound**, not a native allocation
watermark: temporary allocations wholly inside a step can be missed. It also
excludes imported code, the surrounding UI, framebuffers and host process RSS.

“Retained wire” matches app installation: keep compact edges, flags and a cloned
model, then release builder/formulas and raw triangles and collect. Host heap
object sizes differ from the Pico, so these byte counts must not be treated as
predicted board heap requirements.

| N | Sampled observed peak (bytes) | Direct observed peak (bytes) | Sampled retained wire (bytes) | Direct retained wire (bytes) |
|---|---:|---:|---:|---:|
| 6 | 62080 | 4864 | 4256 | 1248 |
| 8 | 150464 | 4832 | 9056 | 1216 |
| 10 | 256256 | 4832 | 13184 | 1216 |
| 12 | 388192 | 4832 | 15936 | 1216 |

At default N8:

- Build time improves by about **349x** in this host run.
- Retained wire heap decreases by about **86.6%**.
- Sampled wire has **814 segments**; direct geometry draws **44 segments** at the default fitted camera.
- Packed boundary payload decreases from **6512 to 368 bytes** (both use 32-bit array elements).
- Direct build storage does not grow with volume-grid N. Higher quality/zoom can increase display subdivision.

## Benchmark current direct-only PicoCAD

From the repository root:

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/benchmark_picocad.py
```

The script emits JSON with current direct-only timings, memory readings and
geometry counts; it does not recreate the removed sampled baseline.
Run it on an otherwise idle host for more stable timing. Measure on the physical
Pico before making a board-specific speed or memory claim.

After removing the legacy backend and compatibility buffers, a fresh default N8
run measured 0.141 ms median build time, 4,768 bytes observed live peak and
1,184 bytes retained wire heap. The same host-only and peak-sampling caveats
apply. The model still stores 12 lines and two circles in 368 packed bytes.


## Expanded analytic kernel

After adding four primitive renderers, analytic silhouettes, operation planning
and typed validation, the same N8 example measured **0.585 ms** median (nine
warm desktop runs), **8,064 bytes observed live peak** and **1,344 bytes retained
wire/model heap**. It stores 12 lines, two rims and one analytic cylindrical
surface: **460 packed bytes**, drawing 46 segments in the fitted perspective
view. The added two segments are the bore-wall silhouettes. The original
sampler remains removed. These measurements retain the host/GC caveats above.
