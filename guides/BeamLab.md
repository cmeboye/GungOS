# Beam view

Open PicoLAB → Modules → Structural → Beam view (formerly Beam Lab). Choose a template (simply supported, cantilever,
propped cantilever, fixed–fixed, two or three spans, overhang, portal frame,
gable frame or blank) or open a saved model. The model is solved again after
every change, using the built-in `picosolve` solver, so the drawing and the
results are always up to date.

A model is made of **members** joined at **joints**. A straight beam is one
member (or a few in a row where its section changes); a frame has members at
any angle.

## Layout

Beam view follows the calculator's compact layout: the top 18 pixels hold the
PicoLAB logo and breadcrumb, followed by a thin mode bar, a bordered preview and a separate scrolling editor.
The system theme supplies the colours. No additional framebuffer is allocated
for panel clipping; zoomed members, loads and labels stay inside the preview.

On the 320 x 320 display, the preview is at `(8, 43)` and measures **304 x 142**
pixels. The properties box starts at `(8, 191)`, with the same width. Its height
is 114 pixels, above a fixed 12-pixel footer. The beam, frame and
section views share those bounds. Property lists scroll to keep the active row
and inline editor visible. The lower box has **Beams**, **Supports** and
**Loads** tabs. Each lists all items of its type, with a count; selecting an
item highlights its location in the preview. Add and choice menus replace the
lower box while the preview stays visible. Joints and hinges remain available
under Beams when relevant.

**F9** opens a bordered, scrollable help box with all keys and sign conventions.
UP/DOWN scroll one line, LEFT/RIGHT one page, CTRL+UP/DOWN jump to the first/last
page (END also jumps to the last page). F9, Escape or Enter closes help. **?** also opens it outside text entry.
The pending edit, choice menu, insertion point and selection remain intact.
The bottom bar only shows F9 Help and a brief status message.

## Views

| Key | View |
|---|---|
| F1 | Add at the cursor, with options belonging to the selected tab |
| F2 | Rem: remove the selected item (Z undoes) |
| F3 | Opt: templates, load cases, combinations, self-weight and files |
| F4 | Plot: diagrams of shear, moment and deflection (slope or normal force) along a straight run, or the whole frame |
| F5 | Results: reactions, equilibrium, peaks, stress, span/deflection, pinned points |
| F9 | Open / close the scrollable keybindings box |

`?` is an alias for help outside text entry. Help consumes its own navigation
keys, so browsing it cannot change the model or a pending value.
ESC closes the current properties first; from the tab list, it leaves Beam view.
The model stays in memory until PicoLAB is closed.

## Model

- LEFT/RIGHT switch between Beams, Supports and Loads, remembering each tab's
  selection. Each tab lists the whole model, not only items at the cursor.
- UP/DOWN choose one whole item at a time. ENTER opens its properties; there,
  UP/DOWN select a value and ENTER edits it. ESC returns to the tab list. The
  preview follows an explicitly selected beam, joint, hinge, support or load.
  Switching category tabs alone preserves the insertion point.
- F1 opens a tab-specific Add menu: Beams offers Member, Section change and
  Hinge; Supports offers Pin, Roller, Roller x, Fixed, Guide and Spring; Loads
  offers Point load, Moment and Distributed load. Escape cancels without changes.
- TAB or `]` moves to the next individual beam; `[` moves to the previous
  beam, wrapping at either end. This works even for collinear beams in one run.
  Shift+Tab is reported as plain Tab by the current firmware, so use `[` for
  backwards navigation without a firmware update.
- Comma/period move the insertion cursor between points on that beam only:
  ends, joints, supports, hinges and load positions. The preview identifies
  the active beam and whether the cursor is at its Start, End or an interior
  distance. Category changes keep this target; UP/DOWN on items deliberately
  follows the item selected.
- While editing, LEFT/RIGHT move the caret; ENTER applies and ESC cancels.
- Type a number, or ENTER to edit. Arithmetic works (`6/4`, `2*pi`).
  ENTER on a choice opens a list.
- `S` support, `P` point load, `M` moment, `W` distributed load, `H` hinge.
- `B` adds a 3 m member from the cursor (splitting a member there if
  needed), pointing in a free direction; type its length and angle.
- `C` splits the member at the cursor and gives the far part its own
  section: a section change along a beam.
- F2 removes the selected item, including from its properties; Z undoes.
  During text entry, F2 leaves the item intact. DEL on an item's heading
  also removes it; on a numeric value it edits and erases before the caret.
  Removing a member removes everything on it.
- `Z` undoes the last change (12 steps, including New and Open).
- `+` and `-` zoom the drawing around the cursor (x2, x4).

Problems the solver finds, such as a structure that can move freely, are
shown in red under the drawing and marked with an X where they occur.

### Building an encastre / cantilever demo

F3 → New beam → Cantilever starts with one 3 m beam, a **Fixed** support
at its left end and a 10 kN downward load at the right tip. No extra member
is needed. Edit the existing beam's length/section under Beams, the Fixed
support under Supports, and the tip load under Loads. F4 shows its diagrams;
F5 shows reactions and calculated peaks. With the unchanged template, the
fixed reaction is 10 kN upward and its reaction moment is 30 kNm.
For a beam fixed at both ends, choose the Fixed-fixed template instead.

**F1 → Member adds another connected member.** It starts at the insertion
cursor, which is marked in the preview; selecting a beam's heading puts that
cursor at its start. Press period (`.`) to step toward its far end, or comma
(`,`) to step back, then F1 → Member to attach there. The Add menu's title
identifies the target beam and its Start, End or local distance. Switching to
Supports or Loads retains that point. Reselecting an item explicitly can move
the cursor to it.

A new member defaults to 3 m in an unused direction, usually vertical. Its
length and angle can then be edited. For example, on the cantilever template,
move the cursor to 3 m, add a member and set its angle to 0° to extend to the
right. The old tip load stays at the shared joint (3 m); move it in Loads if
you want it at the new tip. Angles use 0° right and 90° up.

To support the end of Beam 2: TAB to B2, period (`.`) to End, switch to the
Supports tab, then F1 and choose the support type. At a shared joint, the
support restrains the connected structure regardless of the chosen member.

### Items

| Item | Values |
|---|---|
| Joint (frames) | X, Y; moving it moves every member attached |
| Member (Beam on a single beam) | Length, angle (frames), section, Edit section |
| Support | Position, type (pin, roller, roller x, fixed, guide, spring), spring stiffness, settlement and its load case |
| Hinge | Position; at a joint it frees that member's end |
| Point load | Position, value, direction preset, global angle, load case |
| Moment | Position, value (counterclockwise +), load case |
| Distributed load | Start, end, w at each end, direction, load case; it stays on one member |

Positions are measured along the straight run from its start. Changing a
member's length or angle moves its end joint; items at that end move with
it. Supports are drawn upright: a roller resists vertical movement, a
roller x horizontal movement, a guide rotation and horizontal movement.

Load directions: **gravity** (down; per metre of member), **normal to the
member** (toward its right side, which is down on a member drawn left to
right) and **horizontal** (to the right, for example wind on a column).

Point forces also have an **Angle (0 right, 90 up)** field, measured globally
counterclockwise: 0° right, 90° up, 180° left and 270° down. Enter any finite
angle (negative angles and extra turns are accepted and displayed within
0–360°). Editing Angle automatically chooses Custom angle; the arrow, reactions,
axial/shear/bending results and exports all use the same force components.
A negative force magnitude reverses the specified direction. The angle and
magnitude persist in saved cases and participate in load combinations.

The Acts menu retains Gravity, Normal to member and Horizontal, plus Custom
angle for point forces. Choosing Custom angle initially preserves the current
force direction. In Normal mode the displayed angle follows the member when
its geometry changes; a custom angle stays relative to the global axes.
Distributed loads retain their existing direction presets.

## Section editor

ENTER on a member's **Edit section** opens it (choosing **+ New section**
in the Section list makes a copy and opens that). The upper preview shows the
cross-section to scale, with the size being edited highlighted, the depth
and width dimensioned, and the neutral axis dashed. Beside it: area A,
second moment I, elastic modulus W (the smaller one), mass per metre, E and
EI, and the members that use the section.

| Field | Values |
|---|---|
| Name | Up to 8 characters |
| Material | Steel, concrete, timber, aluminium (E and density set), or custom |
| Shape | I-section, rectangle, hollow rectangle, T-section, circle, tube, direct |
| Sizes | Depth, width, web, flange or wall in mm |
| Direct | I, A and W typed in |

Sections are shared: every member using one changes with it.

## Diagrams (F4)

- LEFT/RIGHT move the cursor one pixel; `,` and `.` move ten.
- UP/DOWN jump to the previous or next point.
- TAB steps through the selected beam's peaks; ENTER pins the cursor position
  with its beam context (see F5). At a shared joint, pinned values come from
  that beam's side and reopening the pin selects the same beam. Repinning a
  physical point from another beam updates that pin's beam context.
- `V` or SPACE shows the next load case or combination.
- `D` changes the third panel: deflection, slope, normal force (frames).
- `]` or `M` switches to the next individual beam; `[` switches to the
  previous beam, wrapping at either end. TAB retains its peak-stepping role.
- The top-left indicator identifies the selected beam, for example **B2/3**.
  `x` is the distance from that beam's start. Plots, vertical scales, peak
  stepping and cursor movement cover only that beam, including when several
  beams share one straight run. F4 from the model starts on the active beam.
- `F` shows the whole frame with one quantity along every member: moment on
  the tension side, shear, normal force, or the deflected shape; `D` steps
  through them. The same beam switching works here; the active member is
  highlighted in the theme colour and identified by the B2/3 indicator.

Where shear or moment jumps, the readout shows both sides, for example
`V 16|-8 kN`.

## Load cases and combinations

F3 → Load cases adds, renames and removes cases (up to 6); a case in use
cannot be removed. F3 → Combinations holds factored sums such as 1.35 Dead +
1.5 Live (up to 6). F3 → Self-weight adds each member's weight (density x
area x 9.81) to a load case, or turns it off.

## Results (F5)

Reactions (vertical, plus horizontal and moment where the support resists
them), the equilibrium check of all reactions against all loads, then for
each straight run: largest and smallest moment, shear, normal force
(frames), deflection and slope, and the largest stress |N/A| + |M/W|. A
single beam also shows the worst span/deflection ratio.

## Signs and units

- Loads act in their direction when positive; applied moments are
  counterclockwise positive; settlement moves a support down.
- Reactions are positive up and to the right.
- Along a member: sagging moment positive, V = dM/dx, tension positive,
  deflection positive toward the member's left (up on a member drawn left
  to right).
- Units are fixed: m, kN, kNm, kN/m, GPa, cm2, cm3, cm4, mm, mrad, degrees.
- Euler–Bernoulli members, small deflections, no shear deformation or
  buckling.

## Files

- Save writes `picoware/engineering/cases/<name>.json` and reads it back to
  verify. Saving over another model's name asks for ENTER again. Beams saved
  by the first Beam Lab open as members.
- F3 → Export CSV (Eggcel) writes a sampled table for the current view to
  `picoware/engineering/exports/<name>-eggcel-001.csv`. It includes every run,
  evenly selecting up to 72 data rows across the runs, including each run's
  endpoints. Seven columns plus the header use at most 511 populated cells,
  fitting Eggcel's 512-cell limit: line, s_m, V_kN, M_kNm, N_kN, slope_mrad, w_mm.
  This sampled table can miss local peaks or jumps; use Results for calculated
  peaks and the full export for detailed analysis.
- Export full CSV keeps every diagram sample and writes `<name>-full-001.csv`
  in the same folder. These files generally exceed Eggcel's import limit;
  use them with a desktop spreadsheet.
- In PicoDESK → Eggcel, F1 → Open CSV opens the SD file browser. Browse to
  `picoware/engineering/exports`, select the `-eggcel-` file and press Enter.
  It opens as a new unsaved workbook; saving creates an `.egg` document.
  Esc cancels the browser. Invalid or oversized files leave the current sheet
  intact.

## Limits

Up to 16 members, 48 items in total, 6 load cases and 6 combinations.

Frames need the firmware with `picosolve.Frame`; updating the SD card alone
is not enough.

## Code

- `engtools/beamlab/model.py`: model, sections, mesh, picosolve calls, results.
- `engtools/beamlab/items.py`: cursor, items, fields, editing rules.
- `engtools/beamlab/render.py`: drawing.
- `engtools/beamlab/app.py`: views and keys.
- `engtools/units.py`, `engtools/cases.py`, `engtools/ui/forms.py`: shared
  units, saved cases and input fields.

Tests: `simulator/test_beamlab.py` (closed-form results, sections, frames,
combinations, errors, files and the full key-driven app),
`simulator/test_beamlab_ui.py` (panel clipping and borders, themes, zoom, section
shapes, inline editing, lower-box menus and help toggling),
`simulator/test_picosolve.py` and the kernel host tests.
