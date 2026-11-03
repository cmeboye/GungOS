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
- [ ] Complex inverse trig: native `cmath` lacks asin/acos/atan; a validated
  implementation is still needed.
- [x] Reject adjacent numeric literals (`1 2` previously returned 2), retaining
  intentional implicit multiplication such as `2pi` and `2(x+1)`.
- [x] Apply the same reserved-variable rules in Base-N and Calculate modes.
- [x] Delegate scalar-only Matrix expression subtrees with their original scope
  (integrals/sums and combinations such as `MatA*sum(k,1,3,k)`).
- [ ] Bound scalar functions containing matrix operations in their bodies, such as
  `sum(k,1,3,k*trace(MatA))`, need further evaluator integration.
- [x] Focused numerical/editor/rendering regression tests and simulator preview.
- [ ] Physical PicoCalc key, layout, heap and responsiveness checks.

## Numerical reliability follow-ups

- [ ] Repeated/clustered polynomial roots: `(x-1)^4` yielded roots near
  0.967+0.005i through 1.039-0.004i. Improve conditioning/convergence diagnostics;
  a small polynomial residual does not establish accurate root locations.
- [ ] Integration refinement, user interval splits/tolerances and diagnostics:
  `int(0,1,exp(-((x-0.12345)/0.0001)^2))` returned 0 instead of about 0.000177245.
  Agreement between two sampled approximations cannot guarantee accuracy.
- [ ] Cancellation/progress for longer reductions and native integration;
  current single native calls are synchronous.
- [ ] Define tangent-pole behavior: `tan(90)` in DEG currently returns a large
  finite value. Avoid indiscriminately rejecting legitimate nearby values.
- [ ] Make float32 precision/underflow visible. `16777217-16777216` and
  `100000000+1-100000000` return 0; extremely small products underflow to zero.
- [ ] Review exact rational/integer arithmetic separately from float32; current
  textbook fractions are numerical and factorial is limited to 0..34.
- [ ] Investigate polynomial coefficient scaling and root polishing.

## Additional scientific functions

- [ ] Combinations/permutations: ncr/npr with domain and overflow checks.
- [ ] Real cube/nth roots, including odd roots of negative real values.
- [ ] atan2, complex phase, rectangular/polar conversions.
- [ ] Numerical derivative with step/error controls; existing shared calculus
  module is a placeholder, while calculator integration is implemented separately.
- [ ] gcd/lcm and integer validation.
- [ ] Inverse hyperbolic functions.
- [ ] Numerically stable log1p/expm1/hypot helpers.
- [ ] Round to decimal places/significant digits; truncation.
- [ ] Normal/binomial/Poisson distributions and inverse normal.
- [ ] Gamma/log-gamma/erf, subject to available native functions or validated algorithms.
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

- [ ] Categorized function catalogue with signatures/examples; the original F7
  menu exposed only 11 templates despite a larger evaluator function set.
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
