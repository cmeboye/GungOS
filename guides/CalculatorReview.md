# Scientific calculator review and implementation tracker

Reviewed 3 November 2026. Baseline: `2ee9dd84` (Spleen fonts in `ff38abbb`).
Checkboxes mean implemented and checked on the host unless explicitly labelled
as device qualification. They do not imply physical PicoCalc validation.

## First pass: correctness and rendered sums/products

User requirement: **typing `sum()` then Space must create a fully rendered
Sigma (Σ) expression**, like `int()` + Space and `^` + Space. Limits, index,
operand, nested expressions and active slots must all render and remain editable.
`prod()` + Space must similarly create a Pi (Π) product template. Plain function
text is not a substitute for the rendered templates.

- [x] Indexed `sum(k,lower,upper,expression)` and `prod(k,lower,upper,expression)`.
- [x] Σ/Π templates, shorthand expansion, F7 entries, cursor/Tab/arrows,
  missing-slot handling, nesting, history and widget rendering.
- [x] Preserve `sum(X)`/`sum(Y)`; add dataset products with frequency semantics.
- [x] Scalar argument sums/products; documented inclusive integer bounds,
  empty ranges, scoped indices, overflow and bounded evaluation work.
- [x] Compensated summation and shared work budgets for nested reductions.
- [x] Fix false root acceptance: `1e-12*(x-3)=0` previously returned x=0;
  `1e-12=0` incorrectly reported a solution.
- [x] Preserve small imaginary results: `1e-8*i` previously displayed zero;
  propagate engineering formatting to both complex components.
- [x] Complex base logarithms.
- [x] Complex inverse trig: application-side principal asin/acos/atan, scaled
  Cartesian algorithms, signed-zero branch sides and DEG/RAD conversion.
- [x] Scaled complex sqrt/log/log10/base-log and magnitude: avoid the native
  squared-magnitude underflow/overflow discovered during inverse-trig testing.
- [x] Reject adjacent numeric literals (`1 2` previously returned 2), retaining
  intentional implicit multiplication such as `2pi` and `2(x+1)`.
- [x] Apply the same reserved-variable rules in Base-N and Calculate modes.
- [x] Delegate scalar-only Matrix expression subtrees with their original scope
  (integrals/sums and combinations such as `MatA*sum(k,1,3,k)`).
- [x] Bound scalar functions containing matrix operations: one evaluator carries
  local k/x, nested scope and work budgets through sums/products/integrals.
  Matrix-valued reduction terms and integrands are rejected explicitly.
- [x] Focused numerical/editor/rendering regression tests and simulator preview.
- [ ] Physical PicoCalc key, layout, heap and responsiveness checks.

## Numerical reliability follow-ups

- [x] Repeated/clustered polynomial roots: exact stored-binary-coefficient
  square-free factors, exact Horner/Newton residuals, location checks and
  repeated/clustered coefficient-sensitivity warnings. `(x-1)^4` now returns
  four roots at 1. Near-multiple input conditioning remains a fundamental limit.
- [x] Integration refinement, interval splits/tolerances and diagnostics: adaptive
  Gauss/Kronrod, broad initial sampling and concentrated-feature refinement;
  the reviewed peak now returns about 0.000177247. Finite samples still cannot
  guarantee discovery of arbitrary features; estimated errors are labelled.
- [x] Progress and Escape cancellation between bounded evaluator/integration
  batches; preserve draft, answer, history and variables when cancelled.
  Native Formula evaluations remain individually atomic.
- [x] Define tangent-pole behavior: reject exact represented DEG poles and
  canonical odd multiples of pi/2 in RAD; retain neighbouring representable
  angles. Tangent-containing expressions use Python evaluation until the native
  Formula path can enforce the same policy.
- [ ] Make float32 precision/underflow visible. `16777217-16777216` and
  `100000000+1-100000000` return 0; extremely small products underflow to zero.
- [ ] Review exact rational/integer arithmetic separately from float32; current
  textbook fractions are numerical and factorial is limited to 0..34.
- [x] Power-of-two polynomial coefficient/variable scaling and checked Newton polishing.

## Additional scientific functions

- [x] Combinations/permutations: ncr/npr with domain, overflow and shared work checks.
- [x] Real cube/nth roots, including odd roots of negative real values.
- [x] atan2, complex phase, rectangular/polar conversions via radius/phase and rect.
- [ ] Numerical derivative with step/error controls; existing shared calculus
  module is a placeholder, while calculator integration is implemented separately.
- [x] gcd/lcm with checked integer domains, exact results and shared work limits.
- [x] Real/principal-complex inverse hyperbolic functions.
- [x] Numerically stable real log1p/expm1/hypot helpers.
- [x] Exact-tie decimal/significant-digit rounding and truncation.
- [ ] Normal/binomial/Poisson distributions and inverse normal.
- [x] Real gamma/lgamma/erf/erfc, checked against reference values and matching firmware symbols.
- [ ] Generated sequences/reusable lists and user-defined functions.
- [ ] Decide contextual percentage semantics; `%` currently means remainder.

## Other calculator modes

- [ ] Statistics: nonlinear regression, arbitrary percentiles, plots and
  probability workflows. Keep the existing 128-row bound until device profiling.
- [ ] Solver: interval-wide root search and nonlinear systems; current general
  solve finds one real root, polynomial degrees are 2..4, systems are 2..4.
- [ ] Matrix: rank/RREF, vectors, eigenvalues and complex matrices. Current
  MatA..MatD are real and limited to 4x4; review size increases after profiling.
- [ ] Base-N: rotates, bit fields and visual inspection; review 64-bit support.
- [ ] Widget: consider optional history; currently Calculate-only.

## Editing, discovery, persistence and documentation

- [x] Lazy categorized F7 catalogue with signatures/examples covering every
  registered scalar function, dataset defaults and context-only Matrix entries.
- [ ] Function/argument-specific errors; consider error positions in the editor.
- [ ] Undo/redo for structured expressions.
- [ ] Optional session persistence: history, variables, mode, angle and format.
- [ ] Explain history recall uses the current angle/mode, or offer metadata restore.
- [ ] F4 plotting handoff to Grapher.
- [x] Remove obsolete v2.1 deployment references and help claiming unavailable
  distributions; distinguish SD application updates from native firmware needs.
- [x] Keep bounded expression/history/variable limits explicit (384 editor items,
  10 template levels, 24 history entries, 24 scalar variables).

## Validation log

- Review baseline: `test_calculator.py`, `test_calculator_modes.py`,
  `test_calculator_native.py`, and `test_statistics.py` passed. Extra probes
  exposed the failures recorded above; passing baseline tests do not cover them.
- First pass: `test_calculator_reductions.py`, `test_calculator.py`,
  `test_calculator_modes.py`, `test_calculator_native.py`, `test_statistics.py`,
  and `test_picolab_controls.py` passed in desktop MicroPython.
- Compiled 139 modules and regenerated `engineering-preview.zip` and
  `DesktopApps-preview.zip`. `check_compiled_calculator.py` passed with the
  current F9 help behavior, rendered Sigma entry/evaluation and widget checks.
- Visual inspection: [Sigma preview](../assets/screenshots/calculator-sum.png)
  and [Pi preview](../assets/screenshots/calculator-prod.png). Nested fractions,
  all font levels, clipping, missing slots and history were also exercised.
- New limits: 1024 terms per reduction and shared 60000 evaluator operations;
  scalar sums are compensated; detected product underflow is an error.
- Changes are application-side and do not need a UF2 rebuild on the matching
  v1.34 native firmware. Physical PicoCalc checks remain pending.

## Second pass — scalar correctness and bound Matrix expressions

Implemented 3 November 2026, after the v1.35 device/reader preview work.

- F7 exposes `ncr(n,r)`, `npr(n,r)`, `cbrt(x)` and `root(n,x)`. These four use
  ordinary function text with signatures; the existing structured Σ/Π/radical/
  integral templates are retained. A full categorized catalogue is still open.
- Combinatorics use exact bounded integer intermediates/results: n/r within
  0..16777216, r<=n, at most 1024 factors after nCr symmetry, result <=float32
  maximum. Every factor is charged to the 60000-operation evaluator budget.
  This does not make other calculator arithmetic exact.
- `root(n,x)` accepts nonzero integer degrees -1024..1024 and real x; negative
  arguments require odd n. Negative degrees mean reciprocal roots; zero is
  rejected with a negative degree. These helpers deliberately choose real roots.
- Complex inverse functions follow principal values and signed-zero branch
  sides, using [Python's conventions](https://docs.python.org/3/library/cmath.html)
  and [NIST's inverse-trig definitions](https://dlmf.nist.gov/4.23). Scaling avoids
  squaring large/tiny magnitudes; small components are checked separately.
  `atan(+i)` and `atan(-i)` are singular and report an error.
- The same scaled components repair complex sqrt/log/magnitude. Previously
  `sqrt(1e-30*i)` became zero in native cmath, and logs of sufficiently small
  nonzero complex values could fail. Other native elementary functions retain
  their existing supported domains; complex tan and hyperbolic functions remain
  limited by the available cmath functions and have not been added here.
- Matrix bound expressions share one scalar evaluator. Trace is cheap and uses
  the shared work budget; at most 512 heavier matrix operations (arithmetic,
  determinant/inverse/transpose/identity) are allowed per evaluation. Repeated
  expensive operations inside quadrature may reach that limit; hoisting matrix
  expressions constant in the integration variable is future optimization work.
- Tangent has no epsilon exclusion zone. Float32 cannot recover distinctions
  already lost when an input rounds exactly to a pole. RAD canonical pole
  detection is limited to distinguishable half-pi multiples within +/-16777216.
  Tangent acceleration is disabled on existing native Formula firmware to avoid
  conflicting interpreted/compiled results. Other native compilation remains.

Validation:

- `python3 tools/tests/test_calculator_scientific.py`: 1564 complex-function
  reference cases generated with CPython cmath from float32 inputs, including
  signed zeros, branch cuts, +/-1 and +/-i, small components, near-zero and very
  large magnitudes; direct helpers and evaluator DEG/RAD paths checked.
- Same suite: exact combinatorics/domain/work limits, real roots, tangent poles
  and their representable neighbours, Matrix-local scopes/nesting/budgets,
  state preservation on failure, F7 entry/evaluation inside structured slots,
  help/draft preservation, size rejection and compact widget routing.
- Existing calculator, mode, reduction, native parity, statistics, PicoLAB
  controls and compiled SD checks passed. The scientific suite also runs against
  compiled MPY modules; native parity is checked on source and compiled code.
  Compiled checks exposed host-folded pi constants rounding a float32 ULP
  differently on load; runtime pi/e now keep source/MPY policies consistent.
- Compiled 141 modules and refreshed `engineering-preview.zip` and
  `DesktopApps-preview.zip`; original release/reader preview archives are intact.
- Application changes only: no new native firmware module or UF2 is required
  for this calculator pass on the matching v1.35 firmware. Physical keypad,
  float32 display, performance and heap checks remain pending.

The third pass below addresses repeated/clustered roots, scaling/polishing and
integration controls/diagnostics. General integration accuracy and recovery of
input precision lost to float32 remain outside what finite sampling can prove.

## Third pass — polynomial reliability, adaptive integration and device report

Implemented 3 November 2026; source and MPY host checks passed.

### Polynomial degree 2..4

The old Durand–Kerner path accepted roots based on a float32 polynomial
residual. Near a repeated root, cancellation makes that residual unreliable.
The new solver converts stored finite float32 coefficients to proportional
integers, finds exact common factors with the derivative, and handles their
multiplicities before finding locations. Exactness refers to **stored binary
coefficients**, not an intended decimal/factored expression lost during input
rounding. This uses bounded big integers for degree <=4, not a general symbolic
or exact rational calculator.

Quadratics use an exact discriminant and stable paired roots. Cubic/quartic
factors use power-of-two variable scaling and Aberth iterations, with exact
Gaussian-integer Horner/Newton residuals. Final correction/location checks and
distinct-root checks replace residual-only acceptance. Nonconvergence, underflow,
range and unresolved clusters are errors. Iterations remain bounded at 192,
with progress/cancellation between batches. Exact polynomial-factor intermediate
coefficients are capped at 8192 bits.

Solver results now include multiplicities and coefficient-sensitivity warnings
for repeated roots or roots separated by less than 5% of their magnitude.
That threshold is a conservative discovery warning, not a quantified condition
number/error bound. Roots are still approximate float32 locations. They may
change substantially if near-multiple coefficients round or are perturbed.
Small imaginary components are no longer suppressed by a broad UI threshold.

### Adaptive finite-interval integration

The mathematical quadrature rule uses the Gauss 7/Kronrod 15 nodes and weights
in [QUADPACK qk15](https://www.netlib.org/quadpack/qk15.f). The application driver
is bounded and independent of ulab's synchronous quadrature. Native Formula
still accelerates supported single-point evaluations; the validated Python
path is available otherwise. Existing split/tolerance conventions are similar
to the [QUADPACK controls documented by SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.quad.html).

`int(lower,upper,expr[,atol,rtol,split1,...])` accepts up to eight interior,
distinct split points. Defaults: atol=1e-7, rtol=2e-5; atol>=0 and
2e-6<=rtol<=0.1. Three-argument integrals retain their rendered template;
controlled calls remain complete ordinary function text. Bounds are finite,
may be reversed and use the existing DEG/RAD function semantics.

The driver starts with at least 32 panels, reconstructs a global compensated
sum/error estimate, refines the largest errors, probes endpoints and refines
concentrated sampled features before accepting a small absolute integral.
It caps work at 8192 evaluations and 256 intervals and checks float32 interval
resolution. The UI retains the last integral's estimated error and sample count.
Progress and Escape are checked between evaluator/panel batches; cancellation
commits no answer, assignment or history. A constant body uses its single
finite value times interval width instead of sampling it repeatedly.

There is no proof of a general integrand's accuracy from finite samples.
A dependent expression whose samples are all zero is refused with guidance
instead of silently returning zero; `int(0,1,0)` is known constant zero, while
`int(0,1,x-x)` currently gets the conservative zero-sample refusal. Finite
endpoint values are required; improper endpoint integrals are not added.
Features missed by every sample, aliasing and severe float32 cancellation
remain limitations. Supply splits around known narrow features and inspect
the diagnostic. Very narrow features can reach coordinate resolution and
require reformulating the variable/interval rather than tighter tolerances.

### Validation and device work

- 85 independently referenced polynomial cases, using known exact factors and
  an independent 80-digit Decimal root solver on stored float32 coefficients.
- Narrow peak, split-point peak, smooth/cusped/reversed/constant/degenerate
  integrals; domain/limit checks, estimated-error metadata and cancellation.
- Source and compiled UI checks for retained drafts/state, repeated-root
  warnings and the actual PicoLAB benchmark route with SD report saving.
- Fifteen polynomial/integral cycles in a 128 KiB numeric-core MPY heap:
  96-byte retained drift after warm-up in the host run. UI/framework/device
  overhead is excluded. This is not a device free-heap claim.
- Device script/menu and result-text instructions:
  [CalculatorBenchmark.md](CalculatorBenchmark.md). Host report passed 19 fixed
  checks; actual device timings and sampled heap remain pending user testing.

This pass remains an SD application update on matching v1.35 firmware. Earlier
release archives stay unchanged. Other unchecked functions/modes/editor items
above remain work to do; this is the numerical-reliability batch.

## Fourth pass — additional scientific functions and discovery

Implemented 3 November 2026. The additions are `atan2`, `phase`, `radius`, `rect`,
`gcd`, `lcm`, `asinh`, `acosh`, `atanh`, `log1p`, `expm1`, `hypot`, `sigfig`,
`trunc`, `gamma`, `lgamma`, `erf` and `erfc`, plus the two-argument round overload.
Their signatures, examples and input/angle rules are in
[ScientificCalculator.md](ScientificCalculator.md#additional-scientific-functions-and-f7-families).

- All real-only paths reject complex/nonfinite inputs explicitly. Integer helpers
  accept up to 32 arguments in ±2^24, use exact integer arithmetic, charge
  Euclidean work to the shared budget and reject out-of-range LCM results.
- Inverse hyperbolic complex extensions rotate the validated principal inverse
  trig paths while preserving signed branch sides. Hyperbolic functions are
  independent of the angle setting. Forward complex hyperbolic functions still
  depend on the original native cmath support and are not added by this pass.
- Polar conversion uses separate radius/phase scalars and a complex rect output;
  it does not introduce tuple-valued results. Rect preserves canonical quadrant
  axes and reduces degree angles before conversion.
- Rounding uses exact dyadic fractions, decimal half-even ties and exact float32
  quantization. Significant-digit decade selection is corrected with integer
  comparisons when float32 log10 rounds across a decade. Digits are bounded;
  no large float scale multiplication is used. This is not general rational
  arithmetic, and requested decimal places are not retained as display metadata.
- Subnormal `%g` text was incorrect on the tested MicroPython build despite
  correct numeric bits. Those values/components now use exact decimal formatting.
  Silent input rounding and generic arithmetic underflow remain open above.
- Special functions use matching native math exports, verified in the PicoCalc
  firmware image, and reject poles/range failures. Their numerical domains follow
  the [math API](https://docs.python.org/3/library/math.html); complex branch-side
  conventions follow [cmath](https://docs.python.org/3/library/cmath.html).
  Conjugation now retains negative-zero imaginary sides for composed branch-cut
  expressions, rather than losing them through the native complex constructor.
- F7 is grouped by family, loaded on demand, with signatures/examples, two-level
  back navigation, an explicit selection marker, draft/help preservation,
  dataset X/XY defaults and Matrix-only entries. The compact widget is checked.

Validation:

- 3196 independent math/cmath/Decimal reference cases, including exact rounding
  bits, branch cuts/signed zeros, extreme magnitudes, real domains and tiny
  increments. Source and MPY paths passed.
- UI routing/evaluation for all 18 new names and round, every scalar function's
  catalogue coverage, Matrix expression versus cell routing, Statistics defaults,
  nested draft/help/back behavior and compact widget rendering.
- Existing 1564 complex-function references, polynomial/integration checks,
  calculator/mode/native parity/statistics/controls and numeric-core heap checks
  remain in the regression set.
- Device report protocol is now v2 with 28 fixed checks. The added rows cover
  polar round-trip, gcd/lcm, complex inverse hyperbolic, stable increments/scaled
  norm, rounding, special functions, subnormal display and catalogue coverage.
  Catalogue retained heap/preloaded state is reported separately from sampled
  numeric heap. Physical device timing/heap qualification remains pending.

This pass adds no native module and requires no new UF2 for the calculator.
Probability distributions, numerical differentiation, reusable lists/functions,
other mode features and remaining editor/persistence items are still open.
