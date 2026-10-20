# Desktop apps: PicoPaint and PicoWord

Open **Apps → PicoDESK**, then choose Eggcel, PicoWord or PicoPaint.
PicoLAB is a separate engineering app, including Graph and Graph3D. The new
hierarchy, shared firmware theme and Esc-only navigation are included in v1.2 and later.
Review changes in the simulator before building/flashing firmware.

After installing the matching v1.33 UF2, merge the `picoware` folder from
the matching app update into the SD root and restart. For a fresh SD card, use
the complete clean SD package instead.
The bundle includes all dependencies. Keep one `.py` or `.mpy` copy per module.
Later app-only changes can be installed through the SD without rebuilding UF2.

Implementations live in `desktopapps/`, separate from PicoLAB's `engtools/`;
the equation renderer is shared with the calculator. `PicoDESK.mpy` is the
main productivity entry. `Apps.mpy` remains a compatibility entry, and
`Eggcel.mpy`, `PicoWord.mpy` and `PicoPaint.mpy` are standalone launch wrappers.

Back and Del both erase before the cursor; Esc alone returns/cancels.
F6–F10 use Shift+F1–F5 on the PicoCalc.

Both apps reserve the top 18 pixels for system indicators. Chrome follows the
current system foreground, background and accent colours. Press **F9** to
toggle help. **F2** opens New, Open, Save, Save as, Export and Load example.
Examples start unsaved. Escape returns, offering Save / Discard / Keep editing.
Save important work before the firmware Home/reset/power shortcuts, which can
bypass that confirmation. Nothing is automatically saved.

## PicoPaint

A **256 × 192** RGB332 canvas uses 48 KiB for pixels; the one-level undo adds
another 48 KiB. The image's colours stay fixed when the system theme changes.
This first release offers 16 palette swatches and a picker. Canvas dimensions
are fixed; resizing, arbitrary image import and layers are future additions.

| Key | Action |
|---|---|
| Arrows | Move the crosshair one pixel |
| Enter, Pencil/Eraser | Toggle pen down/up; arrows draw while down |
| Space, Pencil/Eraser | Stamp once |
| Enter, Line/Rectangle | Set first corner, move, Enter commits |
| Enter, Fill | Flood-fill connected pixels of the same colour |
| Enter, Picker | Sample the pixel under the crosshair |
| F3 | Tools: pencil, eraser, line, rectangle, fill, picker |
| F4 | Colour palette |
| F5 | Square brush size: 1, 3, 5, 9 or 15 pixels |
| F6 | Solid, dashes 25%, diagonal 50% or dots 25% |
| F7 | Undo the last stroke, shape, stamp or fill |
| Back / Del | Erase one square brush footprint, with undo |
| Escape | Cancel fill/shape or lift pen; otherwise return |

The square outline shows the brush footprint. Dashes, diagonal and dots mix the
selected colour with the canvas paper colour, producing lighter patterned
areas. Fill runs in small batches; Escape cancels and restores the pre-fill
canvas. A complexity limit also restores it instead of leaving half a fill.

Native `.ppaint` documents retain pixels in
`picoware/documents/picopaint/`. Export produces standard uncompressed indexed
`.bmp` files, readable on a computer. BMP/PNG import is not implemented.

## PicoWord

PicoWord edits paragraphs and separate structured equation blocks. Arrow keys
move the caret across wrapped lines and blocks; Enter splits a paragraph.
Backspace/Delete edit text or remove the selected equation. Tab inserts four
spaces. Formatting applies to the current **whole paragraph/equation block**;
mixed formatting within a paragraph is not implemented.

| Key | Action |
|---|---|
| F3 | Five built-in font sizes (8–24 px), left/centre/right alignment |
| F4 | Theme-following text or one of 16 fixed colours |
| F5 | Insert equation at caret; edit a selected equation |
| F6 | Undo the last edit or formatting change |
| F7 / F8 | Move up/down eight displayed lines |
| `eq()` then Space | Replace shorthand with a draft equation box |

In an equation, type `2^` then Space for a superscript, `2/` then Space for a
fraction, `sqrt()` then Space for a root, `log_` then Space for a base log or
`int()` then Space for an integral. Tab advances slots; Ctrl-Up goes back.
F7 opens the template catalogue, F3/F4 change equation font/colour. Enter
commits a complete expression; Escape cancels without changing the original
paragraph/equation. To edit a saved equation, navigate to it and press Enter.
These are typeset mathematical expressions, not automatic calculator results.

Native `.pword` documents store paragraph formatting and structured equations in
`picoware/documents/picoword/`. Export `.txt` writes text and linear `eq(...)`
expressions, losing formatting. DOCX, PDF, print layout and TXT import are not
implemented. Bounds are 8,192 text characters, 96 blocks, 384 items per equation,
1,536 equation items total and 48 KiB serialized documents.

Saves verify a temporary file before replacing the target. Existing documents
are temporarily backed up as `.bak`; preserve/recover a remaining `.bak` before
overwriting that filename. This does not guarantee every power-loss scenario.

## Development checks

Compile with `tools/compile-engineering-apps.py --mpy-cross PATH`; use a compiler
matching the installed MicroPython firmware. The full `engineering-preview.zip`
also includes the existing games and screensavers; `DesktopApps-preview.zip`
contains only desktop/engineering modules and installation documentation.

Run `simulator/test_desktop_apps.py`, `simulator/test_eggcel.py` and
`simulator/test_eggcel_plots.py` with the native desktop MicroPython build.
Desktop tests validate behaviour, not physical Pico memory/performance limits.
