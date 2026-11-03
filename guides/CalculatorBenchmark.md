# Calculator device check

Install the combined calculator/reader preview once, then open:

**PicoLAB → Checks → Calculator check → Enter**

A standalone **Calculator Check** entry is also supplied under the SD `misc`
apps folder. The test runs a small fixed set, shows the report on screen and
saves the complete text to **`picoware/calculator-check.txt`**. Send that text
back, including its header and END line. Enter/F6 runs it again; Escape cancels
or returns to PicoLAB. A rerun replaces only the previous benchmark report.

Protocol v2 includes the additional scientific-function pass.

The check does not change calculator sessions, documents, settings, CPU speed
or display mode. It uses the current firmware's native Formula acceleration
where supported. Running it once with Fast Drawing off and once on is useful;
the report identifies the screen mode. Save the first report elsewhere before
rerunning if you want to keep both.

## What the text contains

- Firmware/runtime, machine, CPU frequency, drawing mode and Formula availability.
- Arithmetic, 1024-term/nested sums, combinations and complex inverse/square-root
  checks, with three compute timings and their median for each scalar case.
- Smooth/narrow/split-point integrals with numerical results, estimated error
  and sample counts.
- Exact repeated factors, complex repeated roots, ordinary quartics, coefficient
  scaling and widely separated quadratic roots, with compute times.
- Matrix-local sum/integral checks, expected domain errors and transactional
  assignment checks.
- Additional angle/polar, integer gcd/lcm, inverse hyperbolic, stable increment,
  scaled norm, rounding and gamma/error-function checks.
- Correct subnormal output text and complete scalar catalogue coverage, with
  catalogue retained heap and whether it was already loaded.
- After-GC retained heap differences, sampled minimum free heap and a 12-cycle
  cleanup check. Sampled memory can miss short allocation peaks and does not
  measure external PSRAM or native static storage. Timing excludes report-screen
  drawing and SD saving, but includes normal GC inside a measured computation.
  This is not a cold app-launch/import benchmark.

`RESULT passed=28 failed=0` means the fixed cases met their stated tolerances;
it is not comprehensive hardware or numerical qualification. A failed case is
kept in the text so the remaining cases can still run. An interrupted/stopped
check may have no END line. Expected domain refusals are labelled `OK
expected_error`, not failed calculations.

## Optional REPL script

The combined SD update includes a small `calculator_check.py` at the SD root.
With `/sd` already accessible in the Python console:

```python
exec(open('/sd/calculator_check.py').read())
```

It prints the same report and writes the same text file. The script mounts the
SD through the existing Storage API if it is not yet mounted; use the menu path
above when the console cannot open `/sd` in the first place. The underlying
module can also be called after adding `/sd/picoware/apps` to `sys.path`:

```python
from engtools.bench.calculator import run_report
run_report('/sd/picoware/calculator-check.txt')
```

Source: `tools/device/calculator_check.py`; runner and UI:
`builds/MicroPython/apps_unfrozen/engtools/bench/calculator.py`.

## Host checks

After compiling the matching SD snapshot, run:

```sh
python3 tools/tests/test_calculator_numerics.py
builds/MicroPython/desktop/micropython -X heapsize=24M simulator/test_calculator_numerics_ui.py
builds/MicroPython/desktop/micropython -X heapsize=24M simulator/test_calculator_numerics_ui.py .build/calculator-numerics-2026-11-03/sd-app-staging
```

The numerical suite includes an independent 80-digit Decimal polynomial oracle,
integration cases and a 128 KiB MPY numeric-core heap check. Those results do not
replace device timings or full-UI heap measurements.
