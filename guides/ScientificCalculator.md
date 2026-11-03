# PicoLAB scientific calculator preview

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
| F7 | Mathematical template catalogue |
| F9 | Scrollable help; Esc/F9 closes it |

Alt+S is the system screenshot shortcut and Home remains its home shortcut.
The current keyboard transport does not distinguish Shift-Tab, so Ctrl-Up is
the previous-slot shortcut in this preview. Shift-minus enters `_` normally.

Type `2^` and press Space to create an empty exponent slot, then type `3`.
Right exits that slot; Enter evaluates to 8. The other shorthands include
`x_`, `sqrt()`, `frac()`, `int()`, `log()`, `log_`, `logb()`, and `pi`. Press Space after
each. Filled arguments also expand, for example `sqrt(9)` followed by Space.
`log()` is base 10; `ln()` is natural log; `logb()` has base and argument slots.

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
1/3. This requires the configured native ulab firmware; copying SD files alone
does not install that library. Nested integrals are not supported yet.

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
cmath. Errors retain the expression for correction and leave stored values
unchanged.

## Current limits

Expressions use a bounded editable tree, not Python eval. Up to 384 items and
10 template levels are allowed; evaluator nesting and operation budgets are
also bounded. Drawing clips to each panel and follows the active cursor.
Mathematical symbols use small drawn glyphs rather than a new font dependency.

The current numerical configuration is float32 (roughly seven significant
decimal digits). Fractions display in textbook form but calculate numerically;
exact rational arithmetic and symbolic results have not been implemented.
Native integration compares two bounded subdivision depths for convergence;
this is an approximate numerical check, not a guaranteed error bound. It is
synchronous, so Escape cannot interrupt an individual native calculation.

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
equation. Polynomials return approximate real/complex roots. Linear systems use
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

The desktop Calculate widget reads its native box dimensions and shows answer,
structured prompt and options/variable/math menus. It keeps no history and exposes
Calculate mode only. F3 first enters widget focus; subsequent F3 opens its Options.

## Preview and deployment

`builds/MicroPython/PicoLAB-update.zip` contains the compiled PicoLAB entry,
Calculator Widget and complete shared `engtools` package for the calculator UI
update. Merge its `picoware` folder onto the SD card and replace matching files,
then restart GungOS to reload cached modules. Keep one `.py` or `.mpy` copy per
module. This update needs no UF2 flash on GungOS v2.1. The existing v2.1 release
directory remains the original firmware/source snapshot.

```sh
sh tools/run-micropython-desktop.sh --viewer --board picocalc-pico2w \
  --network offline --audio silent --app PicoLAB \
  --keys down,down,enter
```

Sources are in `builds/MicroPython/apps_unfrozen/engtools/calculator/`.
`tools/compile-engineering-apps.py` includes this package in
`builds/MicroPython/engineering-preview.zip`, alongside the shared plotting apps.
Basic calculator operations do not require a new UF2; integrals require ulab.

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_calculator.py
```

The checks exercise nested templates, known arithmetic/integral answers,
assignment, rejected expressions, physical key routing, all six mode routes,
history recall, panel clipping and return/reopen cleanup. The full selected
firmware simulator suite includes this check.
