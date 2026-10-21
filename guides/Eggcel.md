# Eggcel — keyboard spreadsheet

Open **Apps → PicoDESK → Eggcel** in the updated firmware/simulator.
The hierarchy and shared theme are included in the v1.2 and later UF2s; subsequent
spreadsheet changes are SD updates. Chrome follows system foreground, background
and accent colours, reserving the top 18 pixels for system indicators.

## Keyboard

| Key | Action |
|---|---|
| Arrows | Browse cells; the sheet scrolls to follow the selection |
| Enter | Edit existing contents; Enter again commits in the same cell |
| Typing | Start replacing the selected cell |
| Left / Right while editing | Move the text cursor |
| Escape while editing | Cancel; the original cell stays intact |
| Tab | Next column; while editing, commit and move right |
| Ctrl-Up / Ctrl-Down | Previous / next column when browsing |
| Back / Del | Clear cell or marked range; erase before cursor while editing |
| F1 | File menu |
| F2 | Actions: fill, convert to values, undo, formatting, recalculate, plot |
| F3 | Begin/end range marking; arrows or Go extend the rectangle |
| F4 / F5 | Copy / paste; formulas adjust relative references |
| F6 | Plot setup |
| F7 | Go to address; preserves the anchor while marking a range |
| F8 | Cycle selected column width: 48 / 72 / 96 / 120 pixels |
| F9 | Show/hide help; help starts hidden |
| F10 | Unused |
| Escape when browsing | Return; unsaved changes offer Save / Discard / Keep editing |

On PicoCalc, F6–F10 are Shift+F1–F5. While entering text, F4 copies the
whole entry and F5 inserts it at the cursor. Prefilled dialogs select their
contents for replacement: type to replace, or use arrows to edit. F9 help starts
hidden. F1 is Eggcel's File key; the system screenshot shortcut is Alt+S.

The current keyboard transport does not distinguish Shift-Tab. Ctrl-Up provides
the previous-column action. Firmware Home/reset/power-off shortcuts bypass the
app's Escape confirmation; explicitly save important work before using them.

## Cells and formulas

One logical sheet covers **A1:Z200**, storing only populated cells. The first
version allows **512 populated cells**, **256 characters per cell**, and a
shared **16 KiB cell-text budget**. These are deliberate bounds, not hardware
benchmark results. Up to 512 cells can be copied in one selection. A paste that
exceeds the sheet or budgets leaves the original data unchanged.

Examples:

```text
42
Resistor
=B2*C2
=SUM(D2:D4)
=AVERAGE(A1:A10)
=IF(D6<=15,"Within","Over")
=$B$2*A5
```

Supported functions: `SUM`, `AVERAGE`, `MIN`, `MAX`, `COUNT`, `IF`, `ABS`,
`SQRT`, `SIN`, `COS`, `TAN`, `ROUND`, and `PI()`. Trigonometry uses radians.
Arithmetic supports `+ - * / ^ %`, comparisons `= <> < > <= >=`, parentheses,
and `&` concatenation. Quoted strings escape a quote by doubling it. A leading
apostrophe stores literal text, including text beginning with `=`.

Operator precedence follows the supported part of Excel's
[documented ordering](https://support.microsoft.com/en-gb/excel/calculation-operators-and-precedence-in-excel):
unary negation precedes powers, and equal-precedence operators evaluate from
left to right. Thus `=-2^2` gives 4 and `=2^3^2` gives 64. This differs from the
scientific calculator's mathematical-expression convention.

Blank references contribute zero in arithmetic; aggregates ignore blank/text
cells. Text is not implicitly converted to a number inside formulas. IF
evaluates only the chosen branch. Cell references and function names are case
insensitive; `$` anchors survive copying. Named ranges, whole-column references,
multiple sheets, Excel's full coercion rules and complete function compatibility
are not implemented.

Errors appear in cells: `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, `#NUM!`,
`#ERROR!`, `#CYCLE!` or `#LIMIT!`. Formula token/nesting/work budgets bound
evaluation; aggregate ranges are limited to 2,048 cells with up to 512 active cell dependencies. Evaluation uses explicit work
stacks, with 16,000 steps per calculation and 4,096 queued tasks/results.
Recalculation runs in cancellable batches; Esc cancels it. Formulas use a restricted parser, never Python eval. Cached results
are invalidated on each cell change; targeted dependency recalculation is future
work. Numeric precision follows the existing MicroPython firmware; this is not
Excel's numerical engine.

General / 2-decimal / scientific formatting applies to the sheet and preserves
stored values. A narrower numeric font is used when needed; `###` means the
formatted value still does not fit. Text ending with `~` is visually clipped;
the formula bar/editor retains its full contents.

## Files

F1 offers New, Open, Save, Save as, Open CSV, Export CSV and Load example.
The example is a parts-cost worksheet and is **not automatically saved**.

Documents live in **`picoware/documents/eggcel/`**. `.egg` files are versioned
JSON containing raw cell contents/formulas, column widths and number format.
Workbook loading validates a new sheet before replacing the current one.
Files are limited to 48 KiB. Saves write and read-verify a temporary file before
replacing the target, with a temporary `.bak` of existing documents. If recovery
leaves a `.bak`, preserve/recover it before saving over that name again. This
does not guarantee survival of every possible power failure.

Open CSV opens the system's two-pane file browser, starting in `picoware` and
remembering the last browsed folder for this session. It shows directories and
CSV files anywhere on the SD card. Enter opens a folder or imports the selected
CSV; Esc cancels. Unsaved changes are checked first, and invalid files leave the
current workbook intact. Imported data opens as an unsaved workbook; Save creates
an `.egg` file without overwriting the source CSV. Beam view's **Export CSV
(Eggcel)** writes a sampled table in `picoware/engineering/exports` that fits
Eggcel's 512 populated cells and A1:Z200 limits; its full-resolution export is
intended for desktop spreadsheets.

CSV exports calculated values, not formulas or formatting. CSV imports treat
leading `=` as literal data, accept commas/doubled quotes/CRLF, and require
single-line cells. `.xlsx`/`.xls`, saved charts, sorting, row/column insertion
and external references are deferred.

## Ranges, filling and values

At B2 press **F3 → F7**, enter `D10`, then Enter to select B2:D10.
Arrows also extend the marked rectangle; F3 ends marking. An invalid or
cancelled Go leaves the selection intact.

To create 1–200 down column A:

1. Set A1 to `1` and A2 to `=A1+1`.
2. At A2 press F3, F7, enter `A200`, then Enter.
3. Press **F2 → Fill selection**.

Fill copies the top cell down a column or the left cell across a row, adjusting
relative references and retaining `$` anchors. It overwrites the other cells
inside the selection. For a rectangle, choose Down or Right explicitly; each
column uses its top cell, or each row uses its left cell. Limits are checked
before committing the edit. Fill does not infer sequences from literal numbers.

**F2 → Convert to values** replaces selected formulas with freshly calculated
results after confirmation. All results must succeed before any cell changes;
Esc cancels without modifying cells. Conversion preserves the available numeric
precision, stores text literally and retains boolean values. It removes formula
links: future source edits no longer affect the converted cells. It cannot
recover a result that fails to calculate. No automatic save occurs.

**F2 → Undo last edit** restores one prior cell operation (including a whole
fill, paste, clear or conversion) or a number-format change. There is no multi-step
undo or redo. Undo is held in memory, is not stored in the workbook, and does
not cover column widths or loading a different workbook.

## Plots

Mark a rectangle with F3 and the arrows or Go, then press **F6** or choose
**F2 → Plot selection**. The first selected column supplies X; the next up to
three columns supply Y. A single selected column uses worksheet row numbers
for X. The setup shows all inferred ranges before drawing; selections wider
than four columns initially use their first four columns.

Choose **XY lines**, **XY scatter**, **2D column** or **2D pie** using
Left/Right on the chart-type row. For XY, edit X/Y ranges with Enter, and toggle
the first-row-labels option with Enter or Left/Right. Ranges can be nonadjacent,
for example X `A2:A20`, Y1 `D2:D20`, Y2 `F2:F20`. Each must be a single vertical
range with the same number of cells. Blank X means worksheet row numbers;
blank Y fields disable those series. Header detection is a suggestion and can
be overridden. If enabled, the first entry in every range supplies its label
and is excluded from numeric data.

Select Draw plot. Charts use current calculated values, including formulas.
Blank, text, boolean and error-valued coordinate pairs become **gaps**, never
zeroes, and a gap count is shown. Each enabled series needs at least one valid
numeric pair. Up to three series of 200 rows are supported within the sheet's
existing cell budgets. Very large coordinates/spans must be scaled to fit the
shared graph engine's supported bounds.

In the plot: arrows pan, +/- zoom, **F fits all data** (including offscreen
points), G toggles the grid, W opens bounds/grid controls, and Enter opens
series visibility. Square/cross/diamond markers and separate colours identify
the three series. Graph labels, backgrounds and controls follow the system
theme; the first curve uses the theme colour. F9 opens plot help.

Esc from the plot restores the same sheet, selection, scroll, clipboard,
filename and unsaved state. Plotting does not save the workbook or change the
standalone Graph session. After editing cells, reopen the chart to refresh its
data. Setup options last for this sheet session, with a fresh marked selection
replacing the inferred ranges; they are not yet saved in `.egg` documents.
For **2D column**, X supplies category labels and Y1–Y3 supply grouped bars.
Negative values are supported with a visible zero baseline. Blank, text, boolean
and error values leave gaps. Up to 200 categories are supported. Left/Right
inspects and scrolls categories; Up/Down selects a series, +/- changes the
number visible, F resets the view and G toggles the grid.

For **2D pie**, X supplies labels and only Y1 supplies values. Positive numbers
form slices; zero values are omitted with a note. Negative, blank, text, boolean,
error and all-zero input are rejected. Choose at most 24 positive slices; extra
categories are never merged automatically. Arrows inspect slices and scroll the
legend, showing the selected value and percentage. F9 toggles chart help.

A blank label range uses worksheet row numbers. The First row headers setting
can be overridden in setup; categorical inference checks the value columns so
ordinary category labels do not remove the first data row. Charts are snapshots:
reopen after editing to refresh. Trendlines, error bars and persistent chart
definitions remain future work.

## Errors and recovery

Formula failures are shown in red cells and a red panel at the bottom. Recoverable
runtime/resource failures also leave the workbook open. **F2** opens recovery:
resume with recalculation paused, edit the first offending cell where known,
undo the last cell operation, retry calculation, convert the selection, or save
a recovery copy. **F1** opens File and Esc dismisses the panel. Calculation is
not retried on every frame after failure.

Recovery copies use the first free `Recovery-001.egg` through `Recovery-999.egg`
in the documents directory, storing raw formulas without evaluating them. This
does not rename the current workbook or mark its changes saved. Drawing failures
use a small native fallback screen with the same File/Recovery controls. Severe
memory exhaustion or power loss can still require a restart; save regularly.

## Development and installation

Sources: `builds/MicroPython/apps_unfrozen/desktopapps/eggcel/` and `Eggcel.py`.
Compile the current app sources with the matching `mpy-cross` using
`tools/compile-engineering-apps.py`; see [BUILD.md](../BUILD.md). Generated ZIPs
and `.mpy` files are local build outputs rather than tracked source. Merge the
compiled Eggcel entry and complete `desktopapps/eggcel/` package into an existing
GungOS v1.33 SD installation. Keep shared `engtools`/`desktopapps` dependencies,
exit apps and restart after replacement. Keep one `.py` or `.mpy` per module.
Documents/settings stay on the device. No UF2 change is required for this batch.

Checks:

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_eggcel.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_eggcel_plots.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_eggcel_revision.py
```

Preview through the PicoDESK launcher:

```sh
sh tools/run-micropython-desktop.sh --viewer --board picocalc-pico2w \
  --network offline --audio silent --app PicoDESK \
  --keys enter
```

Use F1 → Load example to populate the grid. The simulator checks navigation,
rendering and calculations; physical Pico testing is still needed for timing
and available heap on large workbooks.


## Planned: larger workbooks and CSV browsing

The current 200-row, 512-populated-cell, 16 KiB cell-text and 48 KiB file
limits are software safeguards, not measured Pico hardware ceilings. An
oversized CSV is rejected with an error; the current workbook is retained.
Import does not currently truncate, sample or page through the source file.

For a following update:

- Separate large CSV inspection from loading a complete editable workbook.
  Add a streaming SD-backed viewer with a bounded row window, navigation and
  explicit row/column selection for import. Preserve the original CSV.
- Offer deliberate sampling for large-data plots, showing the chosen range
  and sampling policy instead of silently discarding data.
- Evaluate a larger logical row range independently from the populated-cell,
  text, file, clipboard, formula-work and chart budgets. Sparse empty rows are
  cheap; populated cells, caches, undo state and calculation work use heap.
- Replace whole-file import reads with bounded parsing before substantially
  increasing supported CSV sizes. Keep cancellation and transactional errors.
- Measure peak heap, import time, recalculation and keyboard responsiveness
  on physical PicoCalc hardware before choosing new defaults. Update address
  validation, limit messages, chart limits and regression coverage together.

These are planned SD application changes. No limits are raised by this note.
