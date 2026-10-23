# Buckling — first pass

Open **PicoLAB → Modules → Structural → Buckling**. F9 opens directly with
Euler's equation, using the scientific calculator's fraction bars, superscripts,
subscripts and radicals. Its underlying expressions are:

```text
Pcr = pi^2 * E * I / (K*L)^2
sigma_cr = Pcr/A = pi^2*E/lambda^2
r = sqrt(I/A); lambda = K*L/r
```

This is an Euler column calculator with independent restraints about both
principal section axes. It needs no picosolve or firmware changes.

## Inputs and controls

Choose a rectangle, hollow rectangle, solid circle, circular tube, I-section,
or custom area and principal inertias. The section y axis runs across the
width and z up the height: Iy is the integral of z² over area, and Iz the
integral of y². The physical member length is L. Applied load P is positive
in compression; zero allows calculation without an applied-load factor.

Set the end condition independently about y and z. The ideal K values are:

| End conditions | K |
|---|---:|
| Pinned–pinned | 1 |
| Fixed–fixed | 0.5 |
| Fixed–pinned | 0.7, rounded |
| Fixed–free | 2 |
| Custom | Editable positive Ky or Kz |

The app compares both Euler loads. Different K values can make the axis
with the larger inertia govern. Equal Euler loads are displayed as y = z.

Material presets reuse `engtools/materials.py`. They are illustrative inputs,
not certified grades. Young's modulus and yield strength are editable.
Yield = 0 disables the yield comparison.

The screen follows Beam view: a column preview above a tabbed properties panel.
The preview is 184 pixels high, matching Beam view's larger model preview.
Left/Right changes between **Section, Member and Ends**; each tab remembers
its selected field. Up/Down chooses a field, Enter edits it, and typing replaces a selected
numeric value. Arithmetic such as `2*1.5` works. Enter applies; Esc cancels.
The model and files use SI; the screen uses m, mm, kN, GPa, MPa and mm4.

| Key | Action |
|---|---|
| Left/Right | Change input tab; restore its selected row |
| F1 | Set the same end condition for both axes |
| F2 | Open the section editor at its material picker |
| F3 | Examples, saved cases and CSV export |
| F4 | Euler stress versus effective slenderness plot |
| F5 | Per-axis results and yield screen |
| F6 | Calculate |
| F9 | Calculator-rendered equations, then definitions, assumptions and controls |
| Z | Undo up to eight changes |
| Esc | Back to inputs, then exit |

Edits clear earlier results. Returning from the F4 plot preserves the case,
calculated results and input focus. The plot shows the governing axis point,
the ideal elastic Euler curve and, when enabled, a horizontal yield line.
The column sketch uses the governing axis restraints after calculation.
Its amplitude is illustrative, not a displacement prediction; custom K has
no calculated mode shape.

### Section and material editor

Select **Section → Section + material**, then Enter. The editor uses Beam
view's shared cross-section preview, scale dimensions, neutral axis and
dimension highlighting. Its side panel gives area, both principal inertias,
Young's modulus and yield strength. Shape, dimensions, material preset,
Young's modulus and yield strength are all edited here; there is no separate
Material tab.

Valid dimensions and material edits update the preview as you type. Drafts
also update area and inertias without changing the saved inputs or calculated
buckling results. Enter applies a valid change and clears the old results;
Esc cancels it. Shape and material chooser highlights preview their pending
selection before acceptance. Esc from the editor returns to the column view.
Custom A/Iy/Iz shows Beam view's direct-values placeholder instead of an
invented outline.

## Reading the results

F5 gives K, effective length, radius of gyration, effective slenderness,
Euler load and stress, and `Pcr/P` for each axis. The summary uses the smaller
Euler load. It also reports average applied stress, axial yield load
`Py = strength*A`, yield factor `Py/P`, and the yield-screen transition
slenderness `pi*sqrt(E/strength)`. Load factors are undefined at P = 0 and
display `--`.

When the Euler critical load exceeds Py, the app explicitly reports that
yielding precedes Euler. It preserves the Euler answer rather than silently
capping it at yield. This comparison is a screening calculation; it is not
an inelastic column resistance model. Separate notes identify applied loads
at or above Euler critical load or axial yield.

Euler assumes a straight, prismatic member under concentric compression,
linear elastic response and ideal restraints. Comparing with yield does
not establish that the proportional limit is respected. Imperfections,
eccentricity, residual stresses, local/torsional buckling, code reduction
factors and whole-frame stability are outside this first pass.

## Cases and exports

Cases use version 1, tool `buckling`, and SI inputs in
`picoware/engineering/cases/`. Saving and loading validate the model;
existing filenames are refused. Current inputs also survive unloading
within the PicoLAB session.

Numbered CSV exports go to `picoware/engineering/exports/`. Each file has
two rows, one for each axis (axis = 0 for y, 1 for z), with SI headers:
length, K, effective length, area, inertia, radius, slenderness, E, applied
load, Euler critical load/stress and yield strength.

Direct Beam view member/axial-force handoff, the shared exchange layer,
Materialprop catalogue integration and device heap/timing measurements
remain follow-ups. Enter or copy a member's properties manually for now;
frame end restraints are not inferred from beam supports.

## Validation and simulator

Model tests check closed-form loads, end-condition ratios, length scaling,
independent section properties, governing-axis changes, zero load, yield
screening, saved cases and invalid inputs. Keyboard tests cover equation-first
help, editing, undo, custom K, presets, plots and returning, files and CSV,
all examples, light/dark screens and lifecycle.

The equations and ideal end factors follow
[Jönköping University, Applied Mechanics: Buckling](https://mechanics.ju.se/SolidMechanics/Buckling.html).

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_buckling.py
sh tools/run-micropython-desktop.sh --viewer --network offline --audio silent --open 'Apps/PicoLAB/modules/structural/Buckling'
```
