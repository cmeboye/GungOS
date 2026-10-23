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

## Current outlier audit

Audited **2026-10-23** against the source working tree, including uncommitted
apps. This is a static input-handler audit, not a device or simulator acceptance
test. The [launcher](../builds/MicroPython/apps_unfrozen/PicoLAB.py) contains
12 apps plus Numerics check and Plot previews. Dynamics and Fluids are empty.
Graph and Graph3D remain separate legacy entry points to the shared viewers.

Every migration below is **pending**. A matching function-key row does not
mean the app's focus, editing and help behavior is already compliant.

### Function keys

| App / source | Current departure | Migration to review |
|---|---|---|
| [BeamView](../builds/MicroPython/apps_unfrozen/engtools/beamlab/app.py) | Main F1–F6 and F9 meanings match. | Preserve these meanings while aligning preview focus. |
| [Shrink fit](../builds/MicroPython/apps_unfrozen/engtools/discs/app.py) | F6 toggles preview focus. | Move focus switching to Tab; decide whether F6 explicitly recalculates or is unused alongside live calculation. |
| [Mohr circle](../builds/MicroPython/apps_unfrozen/engtools/mohr/app.py) | F3 opens only Examples. Values calculate live; most main action keys are unused. | Put Examples within Options. Unused actions and live calculation need no artificial replacement. |
| [StressStrain](../builds/MicroPython/apps_unfrozen/engtools/stressstrain/app.py) | F1 selects analysis mode; F2 selects material. F4 can calculate before opening the stress view. | Move mode/material selection to fields or Options. Keep explicit calculation on F6 and show the missing-results state from F4. F7 map kind and F8 critical points can remain additional actions. |
| [Buckling](../builds/MicroPython/apps_unfrozen/engtools/buckling/app.py) | F1 selects both end conditions; F2 selects material. | Use input fields or Options for both. F3–F6 and F9 already have the target meanings. |
| [Section Properties](../builds/MicroPython/apps_unfrozen/engtools/sectionprops/app.py) | F1 replaces the shape; F2 selects material. F4 enlarges the section. | Move shape/material selection to fields or Options. Keep F4 as the graphical section view, F5 properties and F6 refresh. |
| [Heat transfer 2D](../builds/MicroPython/apps_unfrozen/engtools/thermal/app.py) | Main F1–F6 and F9 meanings match. Space also starts/restarts or pauses/resumes calculation. | Preserve the main actions; provide run/pause access without taking preview Space. |
| [PicoSpice](../builds/MicroPython/apps_unfrozen/engtools/spice/app.py) | Main F1–F6 and F9 meanings match. | Preserve these meanings while aligning waveform navigation. |
| [PicoCAD](../builds/MicroPython/apps_unfrozen/engtools/picocad/app.py) | F4 builds; F5 opens camera views; F6 is unused. | Move Build to F6 and camera presets to Options. Decide whether F4 opens the enlarged part view and what results, if any, warrant F5. |
| [UnitConverter](../builds/MicroPython/apps_unfrozen/engtools/unitconvert/app.py) | F1 opens categories; F2 selects units; F4 shows conventions. | Use its existing quantity/unit fields or Options. Put conventions in Help/Options. F5 equivalents and F6 calculate/remember fit the target. |
| [Grapher](../builds/MicroPython/apps_unfrozen/engtools/plots/grapher.py) | F2 switches 2D/3D; F3 opens the workspace menu. Add/remove expressions is inside the 2D viewer. | Put mode selection in Options. Define F1/F2 for adding/removing supported plot items and F4 for returning to the plot; decide F5/F6 applicability for each source type. |
| [Scientific calculator](../builds/MicroPython/apps_unfrozen/engtools/calculator/app.py) | F2 changes mode; F4–F6 and F9 differ by workflow. | Review all six modes together using the table below; do not treat the calculator as implicitly exempt. |

The calculator needs a separate mode audit:

| Mode / source | Current bindings needing review |
|---|---|
| Calculate / Complex ([app](../builds/MicroPython/apps_unfrozen/engtools/calculator/app.py)) | F2 modes; F4 variables; F5 clear input; F6 history; Enter evaluates. F3 settings is compatible with Options. |
| Statistics ([statistics](../builds/MicroPython/apps_unfrozen/engtools/calculator/statistics.py)) | F3 Data; F4 Summary; F5 Fit or clear input during editing; F6 Options. F2 modes, F7 templates and F8 variables also need to remain reachable. |
| Solver ([workspaces](../builds/MicroPython/apps_unfrozen/engtools/calculator/workspaces.py)) | F3 directly changes degree/size; F5 solves or clears input while editing; F4 inserts variables during editing. |
| Base-N ([workspaces](../builds/MicroPython/apps_unfrozen/engtools/calculator/workspaces.py)) | F5 clears; Enter evaluates. F3 base/width/signedness settings fits Options; F7 is the operator catalogue. |
| Matrix ([workspaces](../builds/MicroPython/apps_unfrozen/engtools/calculator/workspaces.py)) | F3 opens matrix selection/dimensions; F4 variables while editing; F5 clears; Enter evaluates. |
| All six modes | F9 toggles shortcut bars/explanations instead of opening help. Tab navigates structured input or table cells; Delete erases after the caret in expression editing. |

The calculator migration must preserve structured entry, history, variables,
templates, cell navigation and solving. Move conflicting actions to Options
or additional documented keys. Decide explicitly whether Enter-to-evaluate
and structured-editor Tab remain context-specific aliases; F6 must retain
the calculation meaning wherever it is assigned.

### Preview focus, navigation and help

| App / component | Current departure or gap | Migration to review |
|---|---|---|
| BeamView | Tab selects the next member in the model and the next peak in plots. Space cycles load cases in plots. Zoom works from model input focus. | Add Tab preview focus; relocate member/peak stepping and load-case selection. Scope camera keys to preview. |
| Shrink fit | F6 focuses preview. Arrows orbit in 3D or select bodies in section view; there is no Space navigation-mode switch. Space toggles Given/Find in the list. | Use Tab focus and supported preview modes. Given/Find may stay an explicitly documented input-list action, never a preview action. |
| Mohr circle | Left/Right rotates the element while Up/Down selects input rows; no separate preview focus. The guide advertises ? help, but the handler only implements F9. | Separate input and element/circle interaction with Tab. Reconcile the ? documentation with the handler. |
| StressStrain | The model preview has no Tab focus. In the expanded section view, arrows move the probe and Tab cycles edge/centre points; no camera/mode controls. | Add focus for the interactive preview and move point cycling off Tab. Keep supported probe navigation explicit. |
| Buckling | No Tab focus on the column preview; F4 opens a separate shared 2D viewer. | A static column illustration may remain unfocusable. Audit the separate plot through the shared viewer; add Tab only if the column becomes interactive. |
| Section Properties | Tab toggles centroid/axes on the model and enlarged view; no preview focus or camera controls. | Move the overlay toggle into Options or another documented key. Define meaningful section-view interaction before adding focus. |
| Heat transfer 2D | No Tab focus on the model preview. Plot arrows move the probe; Tab cycles hot/cold/pinned points. Space is intercepted for run/pause before page handling. | Separate focus and navigation modes; move point cycling off Tab and run/pause off preview Space. |
| PicoSpice | Model Tab already switches to the schematic cursor; arrows navigate it. Zoom also works with input focus. In waveforms, Tab cycles extrema and there is no navigation-mode switch. | Preserve schematic focus behavior; scope zoom to preview and move waveform extrema off Tab. Define only supported cursor/pan modes. |
| PicoCAD | Browsing Tab focus and preview Space orbit/pan already match. Zoom/Fit/Reset also act with editor focus; Tab while editing only commits. | Scope camera shortcuts to preview. Preserve edit-first Tab behavior and verify returning to the prior property selection. |
| UnitConverter | Conversion preview is a static readout; Tab has no browsing focus action. | No focus or camera is needed for static output. Retain input navigation and search editing. |
| Grapher and legacy Graph/Graph3D | Plot pages already have preview focus; 3D Space switches pan/orbit. 3D Z changes range, unlike model-editor undo. Plot editors do not currently open F9 help while typing. | Preserve viewer navigation; implement help during edits and document or relocate the Z shortcut. Any future split editor/preview must use Tab focus. |
| Scientific calculator | Tab is mathematical-slot/table navigation, Space expands shorthand and arrows navigate expressions/cells. It has no interactive plot preview today. | Keep text actions inside the active editor. Resolve the calculator's specialised focus behavior explicitly before adding a preview. |
| Shared forms and help | [LineEdit](../builds/MicroPython/apps_unfrozen/engtools/ui/forms.py) consumes Tab to commit; apps own focus afterward. [EquationHelp](../builds/MicroPython/apps_unfrozen/engtools/ui/tool.py) scrolls four blocks with Left/Right; other help boxes page by screen height. | Document editor-first Tab and provide one shared focus contract. Align help navigation and preserve drafts when help closes. |
| Numerics check / Plot previews | Numerics uses Enter to rerun. Gallery Enter opens a shared viewer; there is no split preview panel. | Review F6 as the check action; audit gallery viewers with Graph/Graph3D. Standard menu navigation remains applicable. |

## Migration and verification

1. Define shared focus handling around `engtools/ui/lab.py`, `ui/tool.py` and
   `ui/forms.py`; keep camera/probe operations in the owning app or viewer.
   Reuse existing parts before introducing another input dispatcher.
2. Align the model editors with matching main actions first: BeamView,
   PicoSpice and Heat transfer 2D. Use PicoCAD's existing preview focus and
   orbit/pan behavior as a reference, while correcting its function keys.
3. Migrate Shrink fit, Mohr circle, StressStrain, Buckling, Section Properties
   and UnitConverter, leaving static output unfocusable where appropriate.
4. Review Grapher and both legacy viewer entry points together. Review the
   calculator as all six modes, including structured editing and statistics.
5. Update each app's F9 content, guide and existing simulator key sequences
   with its implementation. Record any deliberate exception here with its
   context and reason. Do not mark a row migrated from a documentation edit.

For each migrated app, verify the relevant behaviors:

- F1/F2 act on the selected collection; F3–F6 retain their meanings in each
  supported page/mode. Unsupported actions do not become unrelated shortcuts.
- Tab enters and leaves an interactive preview while retaining the input tab,
  row, camera and probe. Static output introduces no empty focus stop.
- Input arrows never navigate the preview. Preview arrows, Space and zoom
  operate only on the active navigation mode; they do not change model geometry
  or start a solver unexpectedly.
- Numeric signs, spaces and letter shortcuts remain text during editing.
  Accept, cancel and invalid-entry behavior preserve the intended model state.
- F9 opens during editing and pickers; closing it restores their exact state.
  Esc unwinds focus/pages correctly and cancels or pauses a running job first
  where that behavior is supported.
- Standalone and embedded plots return to their callers correctly. Home and
  Alt+S keep their system behavior. Verify the physical Shift+F mapping on
  PicoCalc as well as simulator input.

These checks are for the later behavior changes. This documentation pass has
not migrated or runtime-tested any app.
