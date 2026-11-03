# PicoLAB keys

This is the keyboard convention for new PicoLAB apps and for aligning existing
apps. Read it together with [Screens and controls](UI.md). PicoDESK keeps its
own app menus.

The convention below is the target. The audit records current departures from
it; existing app guides still describe the controls implemented today. Creating
this guide does not change any app bindings.

## Main actions

| Key | Meaning | Application |
|---|---|---|
| F1 | Add | Add an item to the active collection: node, member, load, primitive, expression, row or probe. Open a type picker when needed. |
| F2 | Remove | Remove the selected item from the active collection. Identify the selected item clearly. |
| F3 | Options | Files, examples, settings, modes, import/export and other tool options. |
| F4 | Plots | Open the tool's plots, maps or graphical analysis views. |
| F5 | Results | Open numeric results, properties, summaries or equivalent values. |
| F6 | Build / Calculate / Evaluate | Run the tool's main computation. Use the appropriate verb, including Simulate for a simulator. |
| F9 | Help | Open or close help for the current screen, including its editing and preview controls. |

Keep these meanings across modes and subpages. An unavailable action stays
unused or reports why it is unavailable; its key must not acquire an unrelated
meaning. For example, a tool without removable items does not use F2 for its
material picker. Material, shape, analysis-mode and unit choices belong in
fields or F3 Options. F1 may choose a shape as part of **adding** a new item.

F4 and F5 select views. Explicit builds and solver runs belong to F6. When
results are missing or stale, show that F6 is required. Cheap live updates to
input values, geometry previews and derived properties are compatible with
this convention; their calculation policy must be described in the app guide.

F7, F8 and F10 have no shared assignment yet. An app may use them for additional
actions documented in F9, without replacing the main actions above.

On PicoCalc, F6–F10 are Shift+F1–F5: F6 = Shift+F1 and F9 = Shift+F4.

## Focus and navigation

An editor with an interactive preview has two focus targets: **Inputs** and
**Preview**. Start in Inputs. Tab moves to Preview; Tab again restores the
previous input tab and selected row. Changing focus preserves the model,
results, camera and probe position.

Show the focused panel with an accent border or equivalent focus treatment.
Show the active preview mode as state, such as Move, Orbit or Probe. Keep
shortcut instructions in F9, following the shared screen conventions.

| Context | Arrow keys | Tab | Space | + / - |
|---|---|---|---|---|
| Tabbed inputs | Left/Right changes tabs; Up/Down selects rows within the active tab | Focus preview | No preview action | No camera action |
| Menu or picker | Navigate entries; a grid uses both axes | No panel switch while a modal picker is open | Only an explicitly documented menu action | No camera action |
| Preview: Move | Pan the view | Return to inputs | Switch to another supported navigation mode | Zoom in / out |
| Preview: Orbit | Left/Right rotates; Up/Down tilts | Return to inputs | Switch to Move | Zoom in / out |
| Preview: Probe or grid cursor, when supported | Move the probe or cursor | Return to inputs | Switch between supported navigation modes | Zoom in / out where supported |
| Inline text/number edit | Left/Right moves the caret; Up/Down may accept and select the adjacent field | Accept the edit; a subsequent Tab can switch panels | Text input, not preview navigation | Text input, not zoom |

Space in a preview changes navigation mode. It must not start a calculation,
switch a load case, toggle a value's Given/Find state or change the plotted
quantity. A 2D preview can offer Move and Probe; a 3D preview can offer Move
and Orbit. Only expose modes that the view supports. With one navigation mode,
Space has no mode to change. Move means moving the view, not moving model
geometry; grid/probe navigation moves a cursor, not the selected model item.

An output-only panel, such as a conversion readout, need not accept focus.
Do not add a fake camera or an empty Tab stop. A plot occupying a whole page
already has preview focus; Esc returns to its caller. If it also has an input
panel, Tab follows the same two-panel rule. Tab must not double as next member,
next peak or an overlay toggle on a preview page.

Enter opens an item, edits a value, accepts a choice, or selects/pins a point
when a preview supports that action. The app must explain its preview Enter
action in F9. Preserve per-tab selection when navigating away and back.

## Editing, help and returning

- An active editor or modal dialog receives input before panel navigation.
  Enter accepts, Esc cancels, and invalid input keeps the editor open with its
  error. Tab must not discard a draft or leave an invalid edit behind.
- Shared single-line forms currently use Backspace and Delete to erase before
  the caret. End moves to the end. Home remains the system desktop shortcut,
  even during editing. Structured calculator editing is an audit item below.
- Esc closes the innermost help box, picker or edit first. With preview focus,
  it returns to inputs; on a separate plot/results page, it returns to the
  caller. At the app root it returns to PicoLAB.
- A running build/solver may consume Esc to cancel or pause before leaving.
  Document which operation stops and whether partial results are retained.
  Pause/resume needs an explicit control that does not consume preview Space.
- F9 works while editing and choosing values. Closing help restores the same
  draft, selection, focus and navigation mode. Help must describe the actual
  screen and its supported modes, not merely show a static list of global keys.
- Home returns to the desktop; Alt+S takes a screenshot. These remain system
  actions. Optional letter shortcuts must not fire while text is being entered.
- Z remains the existing undo convention in model editors. Other letter
  shortcuts are app-specific for now and must be listed in F9; their audit
  must account for the focused panel and active editor.

## Current alignment

Updated 30 October 2026.

The local source implements this migration. It is uncommitted; SD packaging
and physical PicoCalc Shift+F validation remain separate milestones.

| App / component | Current behavior |
|---|---|
| BeamView | Tab focuses the model preview and restores the input selection. Space selects Move/Probe; camera keys are scoped to preview. P steps plot peaks and V changes the load case. |
| Shrink fit | Tab replaces F6 preview focus. F6 refreshes live results. 3D supports Move/Orbit; section view supports Move. Camera arrows never select model bodies. |
| Mohr circle | Tab separates inputs from element rotation. Preview arrows rotate by one degree; bracket/P/S/R actions are rotation tools. F3 Options contains Examples; F6 refreshes live results. |
| StressStrain | Analysis/material choices use existing fields. F4 requires calculated results. A calculated section preview supports Tab probe focus; P cycles edge/centre points. |
| Buckling | End conditions and section materials use existing input fields. Its static illustration adds no focus stop; F4 opens the shared plot viewer. |
| Section Properties | Shape/material choices use existing fields. A toggles axes; the static section illustration adds no camera or empty Tab stop. |
| Heat transfer 2D | A calculated model preview supports Tab probe focus. P visits hot/cold/pinned points. F6 starts a fresh solve; F7 pauses/resumes. Space never starts or pauses solving. |
| PicoSpice | Tab focuses the schematic cursor. Zoom requires schematic focus; P replaces waveform Tab extrema. Full-page waveforms have their existing cursor/probe navigation. |
| PicoCAD | F6 builds; F4 focuses the preview; camera presets are in F3 Options. Camera zoom/fit/reset require preview focus. |
| UnitConverter | Category and unit fields open their pickers; F3 also offers Categories and Unit conventions. The conversion readout remains static. |
| Grapher / Graph / Graph3D | Mode changes are in Grapher Options. F1/F2 add/select-remove supported items; F4 returns to plots; F6 refreshes. F9 preserves expression/numeric drafts and carets. |
| Scientific calculator | All six modes share F3 Options and modal F9. F6 computes or accepts an active cell. F5 opens results/history. F7 templates, F8 variables and F10 clear keep editing tools accessible. Statistics data uses F1/F2 to insert/remove rows. |
| Numerics check | F6 reruns checks; Enter remains a menu-style alias. |
| Equation help | Up/Down scroll blocks; Left/Right page by the visible blocks. Drafts and picker selections remain owned by the app. |

### Deliberate context-specific actions

- Calculator Tab navigates mathematical slots or table cells, and Space expands
  shorthand while editing. Enter remains an evaluation/acceptance alias; both
  Back and Delete erase before the caret. There is no calculator preview focus.
- Shrink fit input-list Space toggles Given/Find; preview Space only changes
  navigation modes. Live calculations remain live; F6 provides an explicit refresh.
- Mohr's preview rotates the stress element rather than panning its fitted
  diagram. Probe-only previews/plots have one navigation mode, so Space does
  nothing there. No unsupported camera modes or zoom are advertised.
- Static section/column illustrations remain unfocusable. Section Properties
  uses A for its overlay; F4 still opens its enlarged static section.
- Graph3D Z changes the range. It is documented as a viewer shortcut, while Z
  remains undo in model editors. Its heat-map arrow behavior remains probe navigation.
- F2 on a 2D plot first opens its item list; F2 there removes the visibly
  selected item. A 3D plot's F2 opens the explicitly labelled second surface;
  accepting an empty expression removes it while retaining the main surface.

### Verification

Run the affected app tests with the built desktop MicroPython runtime.
`simulator/test_picolab_controls.py` additionally checks preview/input isolation,
focus restoration, editing/help round trips, explicit calculation, statistics
row actions, and help inside both plot editors. Numerical app tests retain their
independent known-answer checks. Simulator tests do not establish device memory,
latency or the physical Shift+F mapping.
