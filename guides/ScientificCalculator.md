# PicoLAB scientific calculator preview

Implementation status and remaining review items: [CalculatorReview.md](CalculatorReview.md).

Open **PicoLAB → Tools → Scientific calculator**. The preview follows `test.png`:
18 pixels reserved for system indicators, calculator status, a separate answer
box and history above the `>>` prompt. **F9** opens scrollable help throughout the calculator, including its
desktop widget. Closing help restores the exact draft, slot or table selection.
A small `F9 Help` cue leaves room for input, history and tables. Errors and operation results remain visible.
The reserved area is currently blank. Indicators, answers, active slots and
cursors read the system theme colour when drawn.

**F3 → Mode** opens a three-column, two-row mode grid: Calculate / Statistics / Solver,
then Complex / Base-N / Matrix. All six modes have working numerical workflows.
Inline plotting is deferred. See [Statistics.md](Statistics.md)
for the Statistics table, summaries, regression and explicit CSV save/load.

## Keyboard

| Key | Action |
| --- | --- |
| Space | Expand the shorthand immediately before the cursor |
| Left / Right | Move through text; enter or exit a mathematical structure |
| Up / Down | Move between stacked slots; recall session history at the root |
| Tab | Next editable row, including the main row |
| Ctrl-Up / Ctrl-Down | Previous / next editable row |
| Enter | Calculate; highlight a missing slot if unfinished |
| Backspace / Delete | Erase before the cursor |
| Escape | Close the current menu, or return to the Lab |
| F1 / F2 | Statistics data: insert / remove a row; unused elsewhere |
| F3 | Options: mode, angle/format, history, variables and mode-specific tools |
| F8 | Variable list; Enter inserts a name, Delete removes a stored variable |
| F10 | Clear input without clearing the answer or history |
| F5 | Results; Calculate/Complex show session history |
| F6 | Calculate or accept the current cell edit |
| F7 | Mathematical templates and scientific functions |
| F9 | Scrollable help; Esc/F9 closes it |

Alt+S is the system screenshot shortcut and Home remains its home shortcut.
The current keyboard transport does not distinguish Shift-Tab, so Ctrl-Up is
the previous-slot shortcut in this preview. Shift-minus enters `_` normally.

Type `2^` and press Space to create an empty exponent slot, then type `3`.
Right exits that slot; Enter evaluates to 8. The other shorthands include
`x_`, `sqrt()`, `frac()`, `int()`, `log()`, `log_`, `logb()`, and `pi`. Press Space after
each. Filled arguments also expand, for example `sqrt(9)` followed by Space.
`log()` is base 10; `ln()` is natural log; `logb()` has base and argument slots.

### Rendered sums and products

Type **`sum()` then Space** to create a Sigma **Σ** template, or **`prod()` then
Space** to create a Pi **Π** product template. Both draw the upper bound above
the symbol and `k=lower` underneath, with the expression alongside. The index
starts as `k`, and the cursor starts in the lower bound. Fill the lower bound,
Tab to the upper bound, and Tab to the expression. Ctrl-Up/Tab and arrow keys
also reach the index and nested mathematical slots. F7 offers both templates.
Empty slots, history recall and widget rendering follow the integral editor.

Examples (filled forms also expand when followed by Space):

```text
sum(k,1,10,k^2)     = 385
prod(k,1,5,k)       = 120
sum(1,2,3)         = 6
prod(2,3,4)        = 24
```

Indexed bounds are inclusive integers within ±16777216. The step is +1; a
reversed interval is empty (sum 0, product 1). Empty scalar calls have the same
identities. Each reduction accepts at most 1024 terms and shares the evaluator's
60000-operation budget, including nested reductions. Indices have local scope:
stored variables are preserved and nested sums may use their own indices.
Reserved function/constant names cannot be indices. Sums use compensated
accumulation; products reject nonfinite results and detected underflow.
Reductions share the work bound and check Escape between evaluator batches;
cancellation preserves the expression, previous answer and stored variables.

`sum(X)`/`sum(Y)` retain their Statistics meanings; `prod(X)`/`prod(Y)` multiply
dataset observations, repeating them according to frequency when enabled. Dataset
products have the same 1024-term limit. Dataset calls and scalar-argument calls
stay ordinary text when Space is pressed; the indexed form uses the template.

Type `2/` and press Space to turn 2 into the numerator of a stacked fraction,
with the cursor in its empty denominator. Type 3 and Enter to calculate 2/3.
The numerator captures the preceding multiplicative term: `1+2/` captures 2,
`(1+2)/` captures the grouped sum, and `1/2/` captures the complete 1/2 term.
Within a typed function argument, parentheses and commas delimit the numerator.

Type `log_` then Space to create **two** slots, with the cursor in the base.
Type 2, Tab, 5, Enter to calculate log base 2 of 5. No extra `()` is needed.
`log_2()` followed by Space also works: the base is prefilled and the cursor
starts in the argument. Filled forms such as `log_2(5)` followed by Space
expand too. Ordinary `x_` still creates a variable subscript.

For an integral, type `int()` then Space. Enter the lower bound, Tab to the
upper bound, and Tab to the expression. The integration variable is **x**;
the display includes `dx`. For example, `int(0,1,x^2)` evaluates to approximately
1/3. Integration now uses the bounded application-side adaptive rule, with native
Formula acceleration where available. Nested integral bodies are unsupported.

Optional controls use ordinary text (do not expand into the three-slot template):

```text
int(0,1,exp(-((x-0.12345)/0.0001)^2))
int(0,1,exp(-((x-0.12345)/0.000001)^2),1e-9,2e-5,0.12345)
```

The optional order is absolute tolerance, relative tolerance, then up to eight
split points. Defaults are 1e-7 and 2e-5; relative tolerance must be 2e-6..0.1,
absolute tolerance nonnegative. Splits must be distinct interior points. The
last integral's estimated error and sample count remain visible. These are
estimates, not guaranteed accuracy. Endpoint values must be finite; improper
endpoint singularities are not handled. If all samples are zero, an expression
that depends on x reports a refusal; use explicit constant zero when appropriate.

Variables use `a=3` or a subscripted name such as `V_1=12`. Use `2a+1` or
`2V_1+1` afterwards. Names contain letters, digits and underscores, start with
a letter, and are limited to 16 characters; up to 24 names plus Ans are kept.
Function names, constants and Ans are reserved. `Ans` recalls the latest answer.
`X` and `Y` are reserved dataset column names; lowercase `x` and `y` remain
available as scalar variables.

Supported arithmetic includes +, -, *, /, %, right-associative powers,
parentheses, implicit multiplication and factorial for integers 0..34.
Functions include trig/inverse trig, hyperbolic trig, sqrt, logs, exp, abs,
floor, ceil, round, min/max and real/imaginary/conjugate helpers. Complex mode
accepts `i`, `j` and complex elementary functions supported by MicroPython's
cmath, with application-side principal complex asin/acos/atan, scaled sqrt/log
and complex base logarithms. Both components of inverse trig results use the
selected DEG/RAD unit. atan is singular at +i and -i. Nonzero imaginary parts
remain visible even below 1e-7; float32 rounding artifacts may also be visible. Errors retain the expression for correction and leave stored values
unchanged.

### Combinations, permutations and real roots

These functions are available by typing their names or through F7:

| Function | Example | Behavior |
| --- | --- | --- |
| `ncr(n,r)` | `ncr(5,2)` = 10 | Unordered choices |
| `npr(n,r)` | `npr(5,2)` = 20 | Ordered choices |
| `cbrt(x)` | `cbrt(-8)` = -2 | Real cube root |
| `root(n,x)` | `root(3,-27)` = -3 | Real nth root, degree first |

n/r must be integers within 0..16777216, with r<=n. nCr uses symmetry first;
up to 1024 factors are allowed. Integer results/intermediates are exact within
the float32 magnitude limit, and factors share the evaluator work budget.
Displayed answers still use the normal seven-significant-digit format; the
rest of the calculator is not an exact integer/rational engine.

Root degrees are nonzero integers from -1024 to 1024. Negative x needs an odd
degree; negative degrees give reciprocal roots, so `root(-3,-8)` = -0.5 and
`root(-2,0)` is an error. These helpers return real roots in Complex mode too;
use `sqrt` or powers for the complex workflow.

`tan(90)` in DEG and canonical represented odd multiples of pi/2 in RAD report
an undefined-angle error. Nearby representable angles still calculate: there
is no epsilon band around a pole. Inputs already rounded to a pole cannot be
distinguished in float32. Tangent expressions currently use the interpreted
path so numerical integration/solving enforce the same pole policy.

## Current limits

Expressions use a bounded editable tree, not Python eval. Up to 384 items and
10 template levels are allowed; evaluator nesting and operation budgets are
also bounded. Drawing clips to each panel and follows the active cursor.
Mathematical symbols use small drawn glyphs rather than a new font dependency.

The current numerical configuration is float32 (roughly seven significant
decimal digits). Fractions display in textbook form but calculate numerically;
exact rational arithmetic and symbolic results have not been implemented.
Adaptive integration uses a Gauss/Kronrod estimate with broad initial sampling,
endpoint probes and concentrated-feature checks. It is capped at 8192 samples
and 256 intervals. Arbitrary unsampled narrow features can still be missed;
use explicit splits and inspect diagnostics. Progress and Escape cancellation
work between bounded batches, preserving the draft/answer/variables on cancel.
An individual native Formula evaluation is atomic.

Up to 24 successful calculations and variables are held in RAM only. A shared
1536-item history budget retains fewer entries for large nested expressions.
No calculator history or preferences are written to SD. Help visibility is
session-only and starts hidden on reopening. Statistics datasets
can be saved/loaded explicitly as CSV; there is no automatic dataset saving.
Exiting the calculator
ends that session. Mode and angle metadata are retained with history entries;
recalling an expression evaluates it using the currently selected mode/angle.

## Solver, Base-N and Matrix

Solver offers a general equation in `x`, polynomials of degree 2..4, and linear
systems of 2..4 unknowns. Enter edits a field; F6 solves. F3 → Mode setup changes polynomial
degree or system size. Equation fields include lower/upper bounds and an initial
guess. A sign-changing interval uses bisection; otherwise bounded Newton steps
use the guess. Escape cancels between batches. A root is accepted after checking
its residual; this finds one approximate real root, not every root of a general
equation. Polynomials return approximate real/complex roots of the stored float32
coefficients. Exact repeated factors are separated before numerical iteration;
results include multiplicities and repeated/clustered coefficient-sensitivity
warnings. Very close roots can change greatly with tiny coefficient changes;
input rounding can split an intended repeated root. Unresolved/range-limited
cases fail explicitly. Linear systems use
native QR with scaling and rank/residual checks.

Base-N evaluates integers in BIN/OCT/DEC/HEX. F3 → Mode setup selects input base, 8/16/32-bit
word width and signed/unsigned interpretation; F7 lists bitwise operators.
`0b`, `0o` and `0x` prefixes override the input base. Arithmetic wraps modulo
the word width. Division truncates toward zero and remainder follows that
quotient. Right shift is arithmetic in signed mode and logical in unsigned mode.
Use `AND OR XOR NOT`, `& | ^ ~` and `<< >>`; `^` means XOR in this mode.
Floating numbers and scientific functions are rejected. Results retain exact
32-bit integer precision. For example, `0xFFFFFFFF+1` becomes zero at 32 bits.

Matrix stores MatA..MatD, each 1×1 through 4×4. F3 → Mode setup chooses a matrix and dimensions;
Left/Right changes dimensions, Enter applies them. The overlap is preserved when
resizing. Arrow keys select a cell, Enter edits, F10 clears its input, and Escape
cancels or returns to the expression prompt. Matrix entry accepts real scalar
expressions and the shared math templates.

Expressions include `MatA+MatB`, `MatA*MatB`, `2*MatA`, `MatA^2`, `inv(MatA)`,
`det(MatA)`, `trn(MatA)`, `trace(MatA)`, and `identity(3)`. Matrix multiplication
uses native dot; inverse uses native QR/triangular solves. Powers accept integers
-8..8. Assign a matrix with `MatB=inv(MatA)` and use `MatAns` for the latest matrix
result. Singular/ill-conditioned inputs and incompatible dimensions are rejected.
These matrices are real; Complex mode remains the scalar complex workflow.

Scalar matrix functions can appear inside bound expressions, for example
`sum(k,1,3,k*trace(MatA))`, `trace(sum(k,1,3,k)*MatA)` and
`int(0,1,x*trace(MatA))`. Local k/x does not overwrite stored variables. Sum/prod
terms and integrands must return scalars. The shared 60000-step budget applies,
plus a 512-operation cap on heavier matrix operations; cheap trace uses the
shared budget. Repeated matrix arithmetic/inverse/determinant calls within
quadrature can reach this limit.

The desktop Calculate widget reads its native box dimensions and shows answer,
structured prompt and options/variable/math menus. It keeps no history and exposes
Calculate mode only. F3 first enters widget focus; subsequent F3 opens its Options.

## Preview and deployment

After compiling, `builds/MicroPython/engineering-preview.zip` contains the compiled PicoLAB entry,
Calculator Widget and complete shared `engtools` package for the calculator UI
update. Merge its `picoware` folder onto the SD card and replace matching files,
then restart GungOS to reload cached modules. Keep one `.py` or `.mpy` copy per
module. On GungOS v1.34 firmware with the required native libraries, these
calculator application changes need no UF2 flash. Earlier release snapshots and
already generated ZIPs are not automatically updated by editing the source.

```sh
sh tools/run-micropython-desktop.sh --viewer --board picocalc-pico2w \
  --network offline --audio silent --app PicoLAB \
  --keys down,down,enter
```

Sources are in `builds/MicroPython/apps_unfrozen/engtools/calculator/`.
`tools/compile-engineering-apps.py` includes this package in
`builds/MicroPython/engineering-preview.zip`, alongside the shared plotting apps.
The calculator changes require no new UF2 on matching v1.35 firmware; native
Formula accelerates supported integrands. Statistics/Matrix still require ulab.
The on-device report is under **PicoLAB → Checks → Calculator check**; see
[CalculatorBenchmark.md](CalculatorBenchmark.md).

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_calculator.py
builds/MicroPython/desktop/micropython -X heapsize=32M simulator/test_calculator_reductions.py
python3 tools/tests/test_calculator_scientific.py
```

The checks exercise nested templates, known arithmetic/integral answers,
assignment, rejected expressions, physical key routing, all six mode routes,
history recall, panel clipping and return/reopen cleanup. The full selected
firmware simulator suite includes this check.

## Additional scientific functions and F7 families

F7 now opens families rather than a single template list. Enter/Right opens a
family; Up/Down selects a signature; Enter inserts it. Left/Esc returns to the
families, then Esc returns to the same input and active slot. F9 help preserves
the selected family. Existing Space shortcuts, rendered Sigma/Pi and mathematical
slots remain available under **Templates**. Typed expressions keep the same
syntax. Ordinary functions insert `name()` with the cursor inside the brackets.
Dataset entries insert complete X/XY calls, and Matrix entries appear only for
a Matrix expression, not a scalar matrix cell. The compact widget uses the same
families in its own dimensions.

| Family | Functions and conventions |
| --- | --- |
| Trig and angles | `atan2(y,x)` returns the quadrant-aware angle in selected DEG/RAD, including signed-axis conventions. Existing trig functions remain. |
| Complex and polar | `radius(z)` and `phase(z)` give the two polar components; `rect(r,angle)` creates the complex rectangular value. Angles use DEG/RAD; `rect` needs Complex mode. Signed radii are allowed. |
| Integers | `gcd(a,b,...)`, `lcm(a,b,...)`: 0..32 integer arguments within ±16777216. Results are nonnegative; `gcd()`=0, `lcm()`=1. `lcm` with a zero is zero after all arguments are checked. Exact integer results are bounded by float32's magnitude limit. |
| Hyperbolic | `asinh`, `acosh`, `atanh`: real functions and principal complex extensions. No DEG/RAD conversion. Real acosh needs x>=1; real atanh needs -1<x<1. Atanh is singular at ±1 even in Complex mode. |
| Stable math | `log1p(x)` computes ln(1+x) accurately near zero, x>-1; `expm1(x)` computes exp(x)-1 without subtractive cancellation; `hypot(x,y)` uses a scaled norm. These three take finite real inputs. Use `radius` for a complex norm. |
| Rounding and bounds | `round(x)` keeps its existing integer result; `round(x,digits)` adds decimal places, with negative digits rounding to tens/hundreds. Digits range -45..45. `sigfig(x,digits)` rounds to 1..7 significant digits. `trunc(x)` discards the fractional part toward zero. |
| Special functions | Real `gamma(x)`, `lgamma(x)`, `erf(x)` and `erfc(x)`. Lgamma is ln(abs(gamma(x))), including noninteger negative x. Gamma/lgamma reject nonpositive integer poles. Native float32 range and tail underflow limits apply. |

Rounding uses nearest with ties to even **on the stored binary value**, as in
[Python's rounding convention](https://docs.python.org/3/library/functions.html#round).
For example, `round(1.25,1)`=1.2 and `round(1250,-2)`=1200. Integers already
produced exactly by combinatorics retain integer results. Float inputs are
rounded with exact integer fraction/decimal arithmetic, then quantized back to
the nearest representable float32 value. This avoids multiplying by a huge or
tiny decimal scale in float32. It does not recover precision lost during input,
create an exact rational engine, or store a requested display precision.

Examples:

```text
atan2(1,-1)                    135 in DEG
phase(-1+i)                   135 in DEG, Complex mode
rect(radius(3+4i),phase(3+4i))  3+4i, Complex mode
gcd(-48,18,30)                6
lcm(12,18)                    36
asinh(i)                      1.570796i, independent of DEG/RAD
log1p(1e-8)                   about 1e-8
expm1(1e-8)                   about 1e-8
hypot(3e30,4e30)              about 5e30
sigfig(1.23456,4)             1.235
gamma(5)                      24
erfc(0)                       1
```

`rect` reduces represented degree angles before conversion, and returns exact
axis values for canonical represented quadrants, without a neighbourhood
snap tolerance. Input angle precision is still float32. Polar pairs are exposed
as the two scalar functions radius/phase rather than a tuple-valued `polar()`.
The calculator's complex display now formats subnormal components from their
exact binary fractions, avoiding the underlying `%g` formatting error for tiny
float32 values. Arithmetic underflow/rounding elsewhere remains a limit.
