# Beam Lab

Open PicoLAB → Beam Lab. Choose a template (simply supported, cantilever,
propped cantilever, fixed–fixed, two or three spans, overhang, portal frame,
gable frame or blank) or open a saved model. The model is solved again after
every change, using the built-in `picosolve` solver, so the drawing and the
results are always up to date.

A model is made of **members** joined at **joints**. A straight beam is one
member (or a few in a row where its section changes); a frame has members at
any angle.

## Views

| Key | View |
|---|---|
| F3 | Model: the drawing and the selected item's values |
| F4 | Diagrams: shear, moment and deflection (slope or normal force) along a straight run, or the whole frame |
| F5 | Results: reactions, equilibrium, peaks, stress, span/deflection, pinned points |
| F6 | Options: new model, load cases, combinations, self-weight, save, open, CSV, help |

`?` or F9 shows the keys and sign conventions. ESC on the model leaves
Beam Lab; the model stays in memory until PicoLAB is closed.

## Model (F3)

- LEFT/RIGHT move the cursor between points along a straight run of
  members: ends, joints, supports, hinges and load positions. TAB moves to
  the next run (frames).
- UP/DOWN choose an item at that point, or one of its values.
- Type a number, or ENTER to edit. Arithmetic works (`6/4`, `2*pi`).
  ENTER on a choice opens a list.
- `S` support, `P` point load, `M` moment, `W` distributed load, `H` hinge.
- `B` adds a 3 m member from the cursor (splitting a member there if
  needed), pointing in a free direction; type its length and angle.
- `C` splits the member at the cursor and gives the far part its own
  section: a section change along a beam.
- DEL on an item's heading removes it; on a value it edits the value.
  Removing a member removes everything on it.
- `Z` undoes the last change (12 steps, including New and Open).
- `+` and `-` zoom the drawing around the cursor (x2, x4).

Problems the solver finds, such as a structure that can move freely, are
shown in red under the drawing and marked with an X where they occur.

### Items

| Item | Values |
|---|---|
| Joint (frames) | X, Y; moving it moves every member attached |
| Member (Beam on a single beam) | Length, angle (frames), section, Edit section |
| Support | Position, type (pin, roller, roller x, fixed, guide, spring), spring stiffness, settlement and its load case |
| Hinge | Position; at a joint it frees that member's end |
| Point load | Position, value, direction, load case |
| Moment | Position, value (counterclockwise +), load case |
| Distributed load | Start, end, w at each end, direction, load case; it stays on one member |

Positions are measured along the straight run from its start. Changing a
member's length or angle moves its end joint; items at that end move with
it. Supports are drawn upright: a roller resists vertical movement, a
roller x horizontal movement, a guide rotation and horizontal movement.

Load directions: **gravity** (down; per metre of member), **normal to the
member** (toward its right side, which is down on a member drawn left to
right) and **horizontal** (to the right, for example wind on a column).

## Section editor

ENTER on a member's **Edit section** opens it (choosing **+ New section**
in the Section list makes a copy and opens that). The top half shows the
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
- TAB steps through the peaks; ENTER pins the cursor position (see F5).
- `V` or SPACE shows the next load case or combination.
- `D` changes the third panel: deflection, slope, normal force (frames).
- `M` moves to the next straight run (frames).
- `F` shows the whole frame with one quantity along every member: moment on
  the tension side, shear, normal force, or the deflected shape; `D` steps
  through them.

Where shear or moment jumps, the readout shows both sides, for example
`V 16|-8 kN`.

## Load cases and combinations

F6 → Load cases adds, renames and removes cases (up to 6); a case in use
cannot be removed. F6 → Combinations holds factored sums such as 1.35 Dead +
1.5 Live (up to 6). F6 → Self-weight adds each member's weight (density x
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
- Export CSV writes the current view's diagram values for every run to
  `picoware/engineering/exports/<name>-001.csv` (line, s_m, V_kN, M_kNm,
  N_kN, slope_mrad, w_mm).

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
`simulator/test_picosolve.py` and the kernel host tests.
