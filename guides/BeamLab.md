# BeamView

Open **PicoLAB → Modules → Structural → BeamView**. Choose a beam/frame
template, **Triangular bridge**, **Blank structure**, or a saved model.
Only **F6 Evaluate** runs the built-in `picosolve` solver. Editing redraws
geometry and clears the old solution; opening a file and undoing also leave
results unevaluated. F4 Plots, F5 Results and CSV export need a successful F6.
Navigation preserves an existing solution.

## Layout and keys

The model preview starts at `(8,23)`, **304 × 204** pixels, directly below
the PicoLAB breadcrumb. The redundant app/model title strip is omitted on
this page. The scrolling properties box starts at `(8,230)`. Its centered tab labels use the 5×8
font in a 14-pixel strip; 12-pixel property rows use the same font, fitting
a node/member heading and all three fields without scrolling. Node IDs J1… and member IDs L1… are
shown on the sketch; with several sections, each member ID is followed by
its section name. Rigid nodes are squares; pinned nodes are open circles.
Colours follow system appearance. The displacement overlay appears only
after evaluation. **I** toggles a calculated summary; solve problems always
appear in red. Preview drawing is clipped without another framebuffer.

| Key | Action |
|---|---|
| Left/Right | Node / Member / Support / Load tabs |
| Up/Down | Select an item or property |
| Enter | Expand properties, edit a number, or preview a choice |
| [ / ] | Cycle the highlighted choice; otherwise cycle members |
| F1 | Add at the selected node, according to the active tab |
| F2 | Remove selected item |
| F3 | Options, topology operations, templates and files |
| F4 | Plots; empty until evaluated |
| F5 | Results; empty until evaluated |
| F6 (Shift+F1 on PicoCalc) | Evaluate and validate |
| Shift+E | Open the selected member's section editor |
| Z | Undo (12 steps) |
| Tab | Next member |
| , / . | Previous/next position on the active member |
| + / - | Preview zoom |
| F9 / ? | Scrollable help |
| Esc | Cancel edit, collapse properties, or return |

Back and Del erase before the caret. F2 cannot delete an item while its
number editor is active. F9 help preserves pending edits and choice menus;
Up/Down scroll lines, Left/Right pages, Ctrl+Up first page, End last page.
The model survives returning to PicoLAB, without undo history or a solution;
the tool's code unloads from RAM. Closing PicoLAB clears its session.

## Nodes and members

**Node** properties are X, Y (metres), and Type (**Rigid/Pinned**). Moving a
node updates every attached member. Arithmetic uses degrees regardless of
the calculator's angle mode: for a 6 m member at 30°, enter `6*cos(30)` and
`6*sin(30)` in the endpoint's X and Y fields, plus any origin offsets.
Pinned releases each incident member's end rotation; rigid shares rotation.
A pinned node is a connection, not a ground support.

Nodes can be created before any member. F1 creates a node at the cursor;
edit its coordinates before evaluating. In **Member**, F1 connects two
existing nodes and selects Start. Members have **Start, End, Section**.
Use [ / ] on Start/End to see their geometry change immediately. Enter opens
a choice list with the same live preview; Enter accepts one undoable change,
Esc restores the original. Section brackets cycle defined sections; Enter
also offers **+ New section**, making a copy and opening its editor. Unused
sections remain available. Shift+E opens the current section directly.

### First bridge test

Choose **Triangular bridge**: six pinned nodes, nine members, a pin and roller
at the ends, and two 10 kN downward loads. The initial sketch has no computed
response. F6 evaluates it; F5 shows 10 kN vertical reaction at each end.
F4 opens per-member plots; [ / ] chooses another member. Edit a node to
clear the solution and press F6 when ready to evaluate again.

For a cantilever, choose **Cantilever**: its first node has a Fixed support,
its second node a tip force. Edit the second node's coordinates to change
the length/direction, or add another node and connect a new member to it.
Select the new endpoint in Node, switch to Support or Load, then F1.

## Supports and loads

Each item has **From node**. At a branch, **Along member** selects which
incident member supplies the positive-distance direction, marked by an arrow
in the preview. The default prefers a member starting at the reference node;
other incident members can be selected explicitly. Point and moment loads
have an editable **Offset**, including at terminal nodes: zero is at the node,
positive values move inward toward the other end of the member, up to its
length. A new terminal support remains at its node. Position/offset measures
metres from the reference node toward the chosen member's other end, even
when that direction opposes the member's stored start/end order.

| Item | Properties |
|---|---|
| Support | From node, along member when needed, position, type, Settlement X/Y; case when settlement is nonzero; spring stiffnesses for Spring |
| Point load | From node, along member, offset, force, direction, global angle, case |
| Moment | From node, along member, offset, counterclockwise-positive moment, case |
| Distributed | From node, along member, start/end distances, endpoint intensities, direction, case |

Support types are Pin, Roller, Roller x, Fixed, Guide and Spring. Supports
remain oriented to global axes: Roller restrains Y, Roller x restrains X,
Guide restrains X/rotation. Settlement X/Y is signed global displacement in
mm (+right/+up); only restrained directions are editable. Old downward
settlements migrate without a sign change in their physical meaning.
Distributed start/end and intensities are read from the chosen node's side.

Point forces accept a global angle: 0° right, 90° up, 180° left, 270° down.
Angles wrap to 0–360°. Editing Angle chooses Custom; preset Gravity, Normal
to member and Horizontal remain available. A custom angle stays global
when geometry changes; Normal follows the member. Negative magnitude
reverses the force. Distributed presets retain the same meaning.

Removing a member retains its nodes and node-attached point items, reattaching
them to another incident member where possible. Orphan point items remain
editable and are refused on F6 until reconnected. Interior items and distributed
loads on the removed member are removed; Z restores the complete change.
A connected node must have its members and attachments removed first.

A new node needs a member before adding a support or load. If the node lies
inside an existing member, **F3 → Split at node** joins it explicitly; placing
it on the line alone does not connect it. Existing items whose member was
removed or disconnected remain editable. Evaluation identifies their load/
support number and node, and selects **From node** for repair. Choosing a
connected node or adding a member restores the attachment without a solve.

## Solve-side topology checks

Validation runs inside `model.Solution`, so callers bypassing the editor get
the same checks. An invalid draft remains editable until F6. On refusal the
red message gives the reason; overlapping members are highlighted.

- Positive-length collinear overlaps are refused: L1 J1→J2 plus L2 J1→J3
  with J2 inside J1→J3 would otherwise double stiffness on the shared part.
- Distinct nodes with the same coordinates need an explicit **Merge nodes**.
- A used node inside an unsplit member needs **Split at node** to connect it.
- Crossing members remain unconnected without shared endpoint IDs, including
  when load/sample stations happen to coincide.
- Zero-length members, bad references, out-of-range positions, non-finite
  inputs and unstable mechanisms report errors without closing the app.

F3 provides explicit, undoable topology operations:

| Operation | Behavior |
|---|---|
| Merge nodes | Choose source and destination; reconnect members and node attachments. Refuse different connection types, zero-length results and duplicate supports. |
| Split at node | Choose a member and an existing interior node. Preserve the section and split distributed loading with interpolated intensities. |
| Resolve overlaps | Preview splitting at used nodes and keeping one member per shared interval. Enter applies; Esc cancels. Refuse conflicting sections, loads on both duplicated pieces, or conflicting supports. |

There is no automatic normalization or duplicated stiffness on evaluation.
Unsupported conflicts remain for the user to resolve explicitly.

## Section editor

**Shift+E** from a selected member opens its section (choosing **+ New section**
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
- `D` changes the third panel: deflection, slope, normal force (frames) and
  axial displacement u, the movement along the member, positive toward its end.
  With that panel showing, the readout gives u in place of the last value.
- `]` or `M` switches to the next individual beam; `[` switches to the
  previous beam, wrapping at either end. TAB retains its peak-stepping role.
- The top-left indicator identifies the selected beam, for example **L2/3**.
  `x` is the distance from that beam's start. Plots, vertical scales, peak
  stepping and cursor movement cover only that beam, including when several
  beams share one straight run. F4 from the model starts on the active beam.
- `F` shows the whole frame with one quantity along every member: moment on
  the tension side, shear, normal force, or the deflected shape; `D` steps
  through them. The same beam switching works here; the active member is
  highlighted in the theme colour and identified by the L2/3 indicator.

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
(frames), deflection and slope (straight beams), axial displacement (frames,
and straight beams with axial load), and the largest stress |N/A| + |M/W|. A
single beam also shows the worst span/deflection ratio.

## Signs and units

- Loads act in their direction when positive; applied moments are
  counterclockwise positive. Settlement X/Y moves the support right/up when positive (mm).
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

Up to 40 nodes, 16 members, 48 member/support/hinge/load items in total,
6 load cases and 6 combinations. Unconnected draft nodes do not enter the
finite-element equations.

This node-editor revision is an SD update on GungOS v1.32: the installed
`picosolve.Frame` already supports end releases and XY settlement. It requires
that native solver; older firmware without it must be updated first.

## Code

- `engtools/beamlab/model.py`: model, sections, mesh, picosolve calls, results.
- `engtools/beamlab/structure.py`: node attachments, topology validation and explicit normalization.
- `engtools/beamlab/items.py`: cursor, items, fields, editing rules.
- `engtools/beamlab/render.py`: drawing.
- `engtools/beamlab/app.py`: views and keys.
- `engtools/units.py`, `engtools/cases.py`, `engtools/ui/forms.py`: shared
  units, saved cases and input fields.

Tests: `simulator/test_beamlab.py` (closed-form results, sections, frames,
combinations, errors and files),
`simulator/test_beamlab_ui.py` (panel clipping and borders, themes, zoom, section
shapes, inline editing, lower-box menus, help toggling, member labels and
whole-frame colours),
`simulator/test_beam_nodes.py` (node/member editing, degree expressions,
no implicit solves, pinned bridge, settlements, overlap refusal, explicit
merge/split/normalization, load preservation, independent crossings,
orphaned items and hinges, undo limits and cached results),
`simulator/test_picosolve.py` and the kernel host tests.
