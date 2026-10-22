# UnitConverter — first pass

Open **PicoLAB → Tools → UnitConverter**. This is an offline SD-card app;
it needs no changes to picosolve or the device firmware.

The first pass has **49 categories and 322 unit entries**, covering everyday
quantities, engineering, fluids, thermal properties, electricity, magnetism,
light, radiation and computing. Type a category, unit name or symbol to filter
the browser. Search is case insensitive; displayed symbols retain their case.
Left/Right pages through search results. Enter opens a category.

## Converting

The result appears above four fields: quantity, value, source unit and target
unit. Up/Down selects a field; Enter edits it. Unit selectors also support
typing to filter. Left/Right cycles units when a unit field is selected.

Type a number from the conversion screen to replace the value immediately.
Arithmetic such as `3/8`, `2*pi` and `1e-6` works. Enter applies the input;
Esc cancels. Results update when a value or unit is accepted.

| Key | Action |
|---|---|
| F1 | Category browser |
| F2 | Search source unit when From is selected; otherwise target unit |
| F3 | Options, favorites, recent conversions, saved cases and CSV |
| F4 | Conventions for the selected quantity |
| F5 | All equivalents; Enter picks a target unit |
| F6 | Calculate and remember the current conversion |
| S | Swap units, preserving the physical quantity |
| Z | Undo the last change (up to eight changes) |
| F9 | Help |
| Esc | Clear search, cancel an edit, or return one level |

Selecting a source unit reinterprets the entered number in that unit.
Swapping instead carries the calculated result into the input. Favorites
restore the saved pair and its value. The latest twelve favorites and twelve
calculations are retained. CSV export contains the current value in its SI
base unit, with a `value [unit]` heading, ready for future table exchange.

## Definitions and precision

The catalogue uses the international inch/foot, avoirdupois pound, standard
gravity, and explicitly named US liquid, US dry and Imperial measures.
Mechanical horsepower and metric horsepower are separate, as are section
second moment of area and mass moment of inertia. A year means a Julian year
of 365.25 days. Decimal data units use powers of 1000; binary units use 1024.

Absolute temperatures convert through kelvin and reject values below absolute
zero, with a small tolerance for float rounding at the boundary. Temperature
intervals have a separate category and no offset. Fuel consumption and economy
use reciprocal conversion and require positive inputs. No pressure
gauge/absolute offset or medium-dependent Mach conversion is assumed.

Unit factors follow [NIST SP 811 Appendix B.8](https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b8)
and its [explanatory footnotes](https://www.nist.gov/pml/special-publication-811/nist-guide-si-footnotes).
Electronvolt uses the exact elementary charge 1.602176634e-19 C.
The device and desktop MicroPython use float32 arithmetic: the display gives
up to seven significant digits, rather than arbitrary precision.

## Files and first-pass boundaries

- Cases: `picoware/engineering/cases/*.json`; version 1, tool `unitconvert`,
  kind `unit-conversion`, category, source/target symbols and an SI value.
  Existing filenames are refused rather than overwritten.
- CSV: numbered files in `picoware/engineering/exports/`.
- Favorites/history: `picoware/engineering/unitconvert.json`, version 1.
- Current conversion: retained for the PicoLAB session when the app unloads.

This pass does not yet implement arbitrary compound-unit expressions, unit
suffixes in other apps' number fields, the shared clipboard or Send to.
Currency, number bases, typography, logarithmic units and many specialist
categories from the reference site remain outside this first catalogue.
The first pass is accepted as done. Device heap measurements and release
packaging remain release tasks; shared infrastructure is a separate follow-up.
The four app modules compile to 24,314 bytes of `.mpy` code in the host check.

## Validation and simulator

The native desktop MicroPython test checks independent known answers,
temperature/reciprocal errors, every unit through SI cases and swaps, and
keyboard-driven search, editing, favorites, files, CSV and screen rendering.

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_unitconvert.py
sh tools/run-micropython-desktop.sh --viewer --network offline --audio silent --open 'Apps/PicoLAB/tools/UnitConverter'
```
