# Calculator Statistics

Open PicoLAB → Scientific Calculator → F2 → Statistics. Choose
1-variable or 2-variable data. Probability distributions are deferred and hidden
from the release menu.

The 320×320 layout retains the 18-pixel system-indicator gap, status strip,
answer box, data/results area, mathematical prompt and shortcut bar.

## Table and input

- One-variable data uses X; two-variable data uses paired X/Y columns.
- Optional Freq is enabled in F6 Options and defaults to 1. Its integer range
  is 0..9999; zero excludes a row from calculations while frequencies are on.
- Arrow keys browse cells. Typing replaces the selected cell; Enter begins
  editing its existing value. The full float32 round-trip value is loaded into
  the editor, even when the table displays fewer digits.
- Expressions such as `a/3`, `sqrt()` + Space, `2/` + Space and `log_` + Space
  work in cells. Enter commits and advances down the column. Tab navigates
  mathematical slots when inside a template; at the main row it commits and
  advances across the table. Right exits a filled mathematical slot.
- Escape cancels an unfinished edit. Backspace clears a cell while browsing;
  Delete removes its row. Insert/delete/clear actions also appear in Options.
  Clearing the whole dataset requires confirmation in the app.
- F7 opens templates; F8 inserts calculator variables into the cell editor.
  Assign variables from the calculator prompt rather than inside a cell.

Up to **128 rows** are stored in each dataset. Enter on the last editable row
adds a new blank row until that limit. Blank rows are excluded from analysis;
an incomplete nonzero-frequency X/Y pair blocks analysis with its row number.
Incomplete edits and invalid values leave committed measurements unchanged.

One-/two-variable datasets are separate and remain in RAM while switching data
types or calculator modes. Toggling frequency visibility retains the stored
frequencies; when off, every complete row counts once. Exiting the calculator
ends the RAM session. Nothing is automatically written to SD.

## Results and commands

F3 Data, F4 Summary, F5 Fit and F6 Options switch views while browsing.
During editing, F5 clears the input and Enter/Tab commit it. F2 opens the main
calculator mode grid. Escape from the table/results returns to the statistics
type selector; Escape there opens the Statistics calculator prompt.

Summary provides count, sums/squared sums, mean, median, minimum/maximum/range,
quartiles/IQR, and explicitly labelled sample/population variance and standard
deviation for each column. Paired results also include sample/population
covariance and Pearson correlation. Select a result and Enter to use it as
**Ans** in the calculator prompt. F3 there returns to the data table.

Commands accept the active dataset, including from Calculate/Complex after
one has been opened:

```text
a=mean(X)+2*std(X)
pstd(X)
var(Y)
pvar(Y)
median(X)
q1(X)
q3(X)
iqr(X)
sum(X)
sum2(X)
n(X)
min(X)
max(Y)
cov(X,Y)
pcov(X,Y)
corr(X,Y)
slope()
intercept()
r2()
predict(4)
```

`std` and `var` are **sample** values (n−1); `pstd` and `pvar` are population
values (n). Sample values require at least two effective observations.

Quartiles use **Type 7 linear interpolation**: position `(n−1)*p` in the
ordered observations, with interpolation between adjacent values. Frequencies
behave exactly like repeating each observation, without allocating the expanded
dataset. This convention is explicit; other calculators/software may choose a
different quartile convention.

Fit provides `Y=a+bX`, intercept, slope, r, R², residual sum of squares,
residual standard deviation and a Predict Y form. It treats frequencies as
repeated pairs. At least two distinct X values are required; residual SD needs
at least three effective observations (n−2). Correlation/R² are undefined for
constant Y. Covariance remains available for constant X; correlation does not.
Plotting, nonlinear fits and distributions are deferred.

## CSV files

F6 Options → Save CSV writes a **new numbered file**, for example:

`picoware/engineering/statistics/statistics-1var-001.csv`

Save verifies the write by reading it back before reporting success. Failed
verification attempts to remove that new file and preserves RAM data. It does
not overwrite an existing numbered CSV. Save/load reports unavailable SD cards.

Load CSV lists this directory. Selecting a file replaces the corresponding
one-/two-variable RAM dataset only after validation; the other dataset remains.
Files are limited to 32 KiB and 128 rows. Headers are case-insensitive and can
be `X`, `X,Freq`, `X,Y`, or `X,Y,Freq`. Export includes a comment recording the
frequency setting and retains stored frequencies even when hidden:

```csv
# Picoware statistics v1; frequency=1
X,Y,Freq
1,3,2
2,5,1
3,7,1
```

The comment is optional when importing ordinary CSV files; a Freq column then
enables frequency mode. Empty measurements represent blank cells, and an empty
Freq defaults to 1. Mathematical expressions are accepted in the interactive
editor; CSV measurement fields must contain finite numbers.

## Numerical backend and deployment

The shared numerical module is `engtools/numerics/statistics.py`; calculator
table/rendering/storage handling is in `engtools/calculator/statistics.py`.
Native ulab supplies float32 arrays, sorting, reductions and dot products.
Quartile rank selection, input validation and result metadata are Python.
Computed results are cached until data/frequency settings change. Variance and
fits use centred values, with scaling for the regression products, to reduce
cancellation and overflow. Large/small values remain subject to float32's
roughly seven-digit precision; input rounding cannot be recovered afterwards.
Undefined/out-of-range statistics are identified instead of shown as valid numbers.

Statistics requires the selected native ulab build **with numpy.sort**. The
desktop interpreter is rebuilt for this feature. On-device support arrives with
the planned custom UF2; updating only the SD package cannot install native ulab.
The current device UF2 has not been rebuilt as part of this preview.

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_statistics.py
python3 tools/compile-engineering-apps.py --mpy-cross /path/to/mpy-cross
```

Deploy the generated `builds/MicroPython/engineering-preview.zip` package as a
whole. Known-answer and simulator tests cover weighted quartiles, centred
regression, invalid/undefined cases, row bounds, cell math/navigation, mode
retention, CSV round trips/failures and missing firmware support. Desktop tests
verify functionality, not Pico execution speed or exact available heap.
