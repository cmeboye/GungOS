# Selected ulab configuration

Upstream: [micropython-ulab](https://github.com/v923z/micropython-ulab), version
6.12.1, commit `15e999747079205b2415e71a6aa2840b8f85f9dc`.
`upstream/` contains the unmodified C sources and MIT license. `source.json`
records the revision and original source checksums; no network fetch is needed
to build this checked-in dependency.

`picoware_ulab_config.h` is the common configuration for the PicoCalc CMake
adapter and the desktop make adapter. The PicoCalc adapter explicitly selects
MicroPython float32; the desktop variant selects the same precision. This is a
firmware-wide floating-point setting, not a per-array precision switch.

## Included

- One- and two-dimensional arrays, indexing/slicing, reshaping, transpose,
  copying, buffer conversion, arithmetic/comparisons and in-place arithmetic.
- Complex array arithmetic, conjugate and real/imaginary components.
- Array creation, common real maths, `out=` for supported math functions,
  finite-value checks, reductions/statistics, interpolation, dot products,
  polynomial evaluation and sampled-data trapezoidal integration.
- Native `numpy.sort` for bounded statistics/quantile calculations. In-place
  ndarray sorting, argsort and numpy.median remain excluded.
- QR, Cholesky and norms; Cholesky and triangular equation solves.
- Bisection and Newton roots; adaptive quadrature (`quad`).
- FFT/IFFT and second-order-section filtering (`sosfilt`).

Fast direct-loop implementations remain enabled; the smaller/slower function
iterator and binary-operation function-pointer options are disabled.

FFT uses **separate real and imaginary arrays**, even though complex array
arithmetic is available. This avoids the additional complex-output copy:

```python
from ulab import numpy as np
real, imag = np.fft.fft(signal)
reconstructed, imaginary = np.fft.ifft(real, imag)
```

FFT lengths must be powers of two. `sosfilt(..., zi=state)` returns output and
updated state for processing successive blocks.

## Excluded

Higher-dimensional tensors, random numbers, special functions, generic Python
callback `vectorize`, matrix inversion/determinants/eigenvalues, general
minimisation, the incomplete nonlinear curve fitter, duplicate quadrature
algorithms, spectrograms and NumPy file loaders/savers. Polynomial fitting will
use guarded QR and triangular solves instead of the upstream `polyfit` normal
equations/inversion path. CSV storage remains in the engineering package.

No ODE solver or complete engineering model has been added by this integration.
Those numerical/model modules remain placeholders until implemented separately.

The calculator's shared `engtools/numerics/statistics.py` now implements bounded
frequency statistics and centred linear regression. It uses compact arrays,
native sort, reductions and dot products; quartiles use Type-7 interpolation
without expanding repeated observations. See
[Statistics.md](../../../guides/Statistics.md) for workflows and limits.

## Engineering wrapper and checks

`builds/MicroPython/apps_unfrozen/engtools/numerics/backend.py` imports ulab
lazily, verifies the required capabilities and provides `guarded_qr`.
There is no CPython NumPy or simulated numerical fallback.

The pinned QR implementation creates full temporary Q/R matrices before reducing
its output. The wrapper accepts only finite real float32 matrices with rows >=
columns, at most 64 rows and 16 columns, a conservative 64 KiB workspace budget,
and an 80 KiB free-heap reserve. These limits protect memory and keep initial
models small; they are not a measured execution-time guarantee. Raw ulab calls
bypass the wrapper. Complex and wide QR inputs are rejected before entering
the upstream C routine. Large datasets need a future fitter that works in blocks.

Always specify the triangle when solving, for example:

```python
solution = scipy.linalg.solve_triangular(R, rhs, lower=False)
```

The pinned implementation defaults `lower` to true, unlike the documented SciPy
default. The checks verify upper-triangular QR fitting explicitly.

Engineering Lab now has a **Numerics checks** entry. It runs eight small
known-answer checks, one per UI iteration, covering arrays/statistics, complex
arithmetic, QR fitting, Cholesky solving, roots, integration, FFT reconstruction
and filtering. Enter reruns them; Back cancels between checks and returns.

Timings cover each complete check, including setup/validation. Allocation deltas
are free-heap snapshots before/after the check, **not peak workspace**. Desktop
timings describe the host, not Pico speed; display refresh is outside the timed
check. Native calls finish before cancellation can be handled.

The existing device UF2 does not contain ulab. Its check page displays a useful
missing-library message; ordinary plot previews and apps still work. Flash the
new selected firmware once the lab work is ready to enable device checks.

## Verification and packaging

```sh
MICROPYTHON_DIR=/path/to/micropython sh tools/micropython-desktop.sh
sh tools/run-micropython-desktop.sh --sim-check --network offline --audio silent
python3 tools/compile-engineering-apps.py --mpy-cross /path/to/mpy-cross
```

`simulator/test_ulab.py` verifies the actual included/excluded native APIs,
float32/complex storage sizes, numerical answers, invalid inputs, workspace
limits and check-page lifecycle. The regular app/plot regressions also run at
float32. Simulator precision now matches the selected RP2 firmware, but its
heap size, CPU and radio/storage behaviour still differ.

The PicoCalc native CMake includes this adapter for the next device build.
The device UF2 has not been rebuilt or flashed by this step; target flash size
and hardware performance will be measured when that build is made.
