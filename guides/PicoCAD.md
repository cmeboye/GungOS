# PicoCAD

Open **Apps → PicoLAB → Modules → Machine design → PicoCAD**. PicoCAD uses direct geometry only.
Box, Cylinder, Cone and Sphere build at arbitrary positions and rotations.
Supported analytic Boolean cases are listed below; a general trimmed-face
Boolean kernel is still in progress. Units are mm and degrees.

The editable Add/Cut/Intersect construction history and `.pcad` format are
unchanged. A valid operation the kernel cannot calculate is **Unsupported**,
not Invalid. Failed builds retain inputs and the last complete boundary cache.

The default demonstration is a **40 × 30 × 10 mm box with a cylindrical
through-hole of radius 5 mm**. The cylinder is 16 mm high and centred on the
box, so it extends beyond both faces. The app starts a direct boundary build of this
example; Esc cancels that build while retaining the editable inputs.

## Editing and controls

The upper box previews the part; the lower box has Features and Properties
tabs. Left/Right switches tabs, Up/Down browses the active list, and Enter on
a feature opens its properties. A selected feature is overlaid in white in
Properties. Cut and Intersect primitives use dashed outlines. Editing changes
the primitive preview immediately; combined boundaries require **F6 Build**.

| Key | Action |
|---|---|
| F1 | Add Box, Cylinder, Cone or Sphere; Operation is set in Properties |
| F2 | Remove the selected step; Z can undo |
| F3 | Save, Save as, Open, New (blank), Curve Quality, Projection, Camera views |
| F4 | Focus the part preview |
| F6 | Build the combined part |
| F3 → Camera views | Isometric/Front/Top/Right, Fit and Reset camera |
| F9 | Scrollable help; F9/Esc closes it |
| Tab | Switch keyboard focus between preview and editor |
| Arrows with preview focused | Orbit, or pan after pressing Space |
| + / − | Zoom; on a numeric property − starts a negative value |
| F / R | Fit / reset to isometric |
| [ / ] | Previous / next feature |
| Q in editor | Select curve quality |
| Z | Undo one model edit; six entries are retained |
| Esc | Cancel entry/menu/build, return from preview/properties, or leave the tool |

On a numeric property, Enter opens inline editing; typing starts a replacement.
Enter/Tab commits and Esc cancels. Both Back and Del erase before the cursor.
Decimal and scientific notation are supported; arithmetic expressions are not
part of the initial editor. Enter on Operation cycles Add/Cut/Intersect. The
first step cannot become Cut or Intersect. Names are generated automatically.

Help uses Up/Down for lines and Left/Right for pages. Ctrl-Up/Ctrl-Down jump to
the first/last page; End also reaches the end. **Home remains the firmware's
exit-to-home shortcut** and bypasses the app's unsaved-changes prompt. Save
important projects before Home/reset/power-off.

## Primitive conventions

All shapes are centred at their X/Y/Z position. Box dimensions are full width X,
depth Y and height Z. Sphere uses its radius. Cylinder and Cone use a radius and
full height along local Z. A cone's base is at −height/2 and its tip at +height/2.
Rotations apply local X, then Y, then Z. Sphere rotation has no geometric effect.

To make the demonstration manually:

1. F3 → New opens a blank model. F1 → Box adds the initial solid.
2. F1 → Cylinder, then set Operation to Cut in Properties (Enter on Operation).
   Set Radius to 5 and Height Z to 16, with X/Y/Z all zero.
3. Press F6. Tab focuses the preview; arrows orbit it and +/− zoom.
4. F3 → Save as stores the editable construction history.
5. F3 → Open lists the saved projects; selecting one reloads and rebuilds it.

F1 always inserts a primitive with Operation = Add and opens its Properties.
For subsequent steps, Enter on Operation cycles Add, Cut and Intersect. The
first step must remain Add. All four primitives are visible in the F1 menu.

F3 contains Save, Save as, Open, New, Curve Quality, Projection and Camera views. New always opens a blank model, using the normal Save/Discard/Cancel
guard if the current model is modified. The startup demo remains a box and bore.
Undo remains available with Z; Help with F9. Undo restores model inputs and can
recover the previously cached result when the construction history matches it.

A small theme-coloured **XYZ orientation guide** occupies the preview's top left.
It follows camera rotation and stays fixed in position/size during pan and zoom.
F3 → Projection selects **Perspective** or **Isometric** without rebuilding the
geometry or modifying the project. Isometric uses parallel (orthographic)
projection and starts at an equal-axis isometric orientation. Arrows can orbit
to other parallel views afterward. Perspective applies depth foreshortening.
Options' named camera views and R reset the viewing direction while retaining the selected
projection mode. Fitting after a projection change keeps the part in view.

## Geometry and rendering

The wireframe stores analytic straight edges, planar circle/ellipse curves
and primitive surface records. At draw time the curves adapt to screen size,
zoom and projection. Sphere outlines and cylinder/cone side silhouettes are
calculated from the camera, including perspective tangent geometry. Primitives
can be freely rotated and translated. Rear edges and enclosed cavity boundaries
remain visible; hidden-line removal and solid shading are not implemented.

Supported operations currently include:

| Case | Result |
|---|---|
| Standalone Box/Cylinder/Cone/Sphere | Direct edges, rims and silhouettes |
| Add separated primitives | Multiple bodies |
| Add a primitive already inside a plain body | No change |
| Add a primitive enclosing the existing plain body | Replacement by enclosing body |
| Cut a tool missing the body | No change |
| Cut a tool covering the whole body | Empty |
| Intersect separated bodies | Empty |
| Intersect contained primitives | Inner primitive / unchanged containing tool |
| Cut a strictly enclosed, disjoint tool | Closed cavity |
| Box + cylindrical cutter | Through/blind bores with complete circle/ellipse rims |
| Through-cylinder crossing one side face | Trimmed circular notch arcs and box edges |
| Boxes sharing local axes | Intersection, rectangular union, full-cross-section slab cuts |

Boxes may share any rigid rotation. Slab cuts can split a body. Cylindrical
bores may drill along X/Y/Z or at an angle, as long as each whole rim lies on
an opposed box face or an entirely internal cylinder cap. Tilted face rims are
analytic ellipses. A cylinder cap partly crossing a box face requires trimmed
arcs and remains unsupported. Through-cylinders parallel to any local box axis may cross one lateral face,
producing an open-sided notch. Circle/face intersections determine the arc
intervals and where box edges are removed. Curved-wall silhouettes are clipped
to the retained arcs. The opposite face and the other lateral sides must retain
clearance; blind side-notches and cuts crossing multiple lateral faces remain
unsupported. Multiple voids/bores/notches must be provably disjoint.

For a semicircular notch in the Y+ edge, use a Box of 40 x 30 x 10 at the
origin, and Cut Cylinder radius 5, height 16 at X=0, Y=15, Z=0. Its two rim
arcs span X=-5..5 and Y=10..15, joined by vertical edges at X=+/-5, Y=15.
The old straight rim portions through the notch are removed. Camera focus
shows the combined part; Properties retains the editing-tool overlay.

Partial curved-solid intersections, overlapping voids, general rotated box
intersections and non-rectangular box unions still require boundary trimming.
They receive **Unsupported**, never a sampled approximation or invented solid.
The planner proves its supported cases using analytic support functions,
containment tests and known construction topology. It is not a general BRep
validator. Curve samples are used only to draw/fit the model, not to decide
Boolean topology. Input model coordinates are recentered during construction.

The default demonstration stores 12 straight lines, two rims and one cylindrical
surface record: **460 bytes of packed geometry**. Curve display uses an adaptive
projected-midpoint error target of 0.5 pixel at default quality, capped at 256
segments per curve. This is a display target, not a formal global error bound
or a tolerance on stored dimensions. At the cap the target may be exceeded.

No volume sampler, marching tetrahedra, triangle edge cleanup, triangle renderer,
extra framebuffer or mesh fallback is included in PicoCAD. Direct-boundary-to-mesh
conversion, filled rendering and mesh export remain deferred. Graph3D is separate.

## Results and diagnostics

| Status | Meaning |
|---|---|
| Built | Supported construction completed |
| No change | Valid operation leaves the existing material unchanged |
| Empty result | Valid operation leaves no volume; an empty New model also builds empty |
| Multiple bodies | Valid result contains separate components |
| Invalid | Malformed inputs, nonpositive active dimensions, non-finite values |
| Limit | Project range/count or available heap capacity exceeded |
| Unsupported | Valid inputs require unimplemented boundary trimming |
| Precision | A feature/contact is too close to numerical tolerance to classify safely |
| Non-manifold | A known edge/point connection or tangent bore breaks the solid-boundary rules |
| Calculation | An internal arithmetic/boundary calculation failed |

Failures include the offending step where available, appear in the red recovery
box and preserve edits. Correct a property, undo with Z, or change the operation
and rebuild with F6. Empty/No change/Multiple bodies are successful outcomes.
Tolerance is **1e-5 mm + 2e-6 times the largest active primitive extent**; tiny
features in much larger constructions may require rescaling. Positively sized
features below the app's 0.01 mm input limit are classified as Limit, not invalid
mathematics. This is not a general manufacturing-quality exact CAD kernel.

## Bounds and performance

- Up to **eight construction steps** and **16 resulting bodies**.
- Quality choices remain **N = 6, 8, 10, 12, 16, 20, 24** in existing files.
- Direct geometry uses N for its curve error target: **4/N pixels**. Changing
  quality changes display subdivision, not the circle radius or hole topology.
- Build work is cancellable in batches. The app aims to return to input
  handling after about 8 ms of geometry work.
- Physical Pico timing and peak heap still require hardware measurements.

The expanded analytic kernel is measured with the direct-only benchmark below.
Earlier direct-only N8 measurements and the old sampled baseline are historical.
These figures exclude drawing and warmed imports; CPU speed, heap layout and
allocator behaviour differ from the Pico. The current packed box/bore geometry is 460 bytes.
See [the historical comparison report](PicoCAD-benchmark.md) for the earlier
sampled baseline and direct-only benchmark instructions.

Fillets/chamfers, general exact Boolean topology, sketch constraints,
STL/STEP import/export and assemblies remain outside this version.

## Files and recovery

Projects are JSON **`.pcad` files** in `picoware/engineering/cad`, containing the
version, mm units, quality N and primitive construction steps. The format is
unchanged; direct boundaries are rebuilt on load when supported. Projects are limited to 32 KiB and validated before replacing
the current model; malformed inputs leave the current model intact.

Save writes and read-verifies a temporary file, backs up an existing target to
`.bak`, then replaces it. Failure attempts to restore the previous target;
if a `.bak` remains, recover it before saving over that name. Save as refuses
a different existing project name. This does not guarantee survival of every
possible SD failure or power interruption.

Leaving a modified project, opening another, or choosing New
asks Save / Discard / Cancel, with Cancel selected initially. Settings and
models are never written automatically. A clean model is retained in PicoLAB's
small session store while tool code is unloaded; all rendered geometry is released.

## Installation and checks

This implementation is SD application code. Update **PicoLAB.mpy and the whole
engtools package together**. PicoCAD no longer uses `picosolve` or ulab; it
uses the existing GungOS drawing and UI modules. No UF2 change is needed for
PicoCAD itself. The source launcher and simulator contain the new Tools entry.

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_picocad.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_picocad_kernel.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/benchmark_picocad.py
sh tools/run-micropython-desktop.sh --viewer --board picocalc-pico2w --open 'Apps/PicoLAB/modules/Machine design/PicoCAD'
```

Checks cover direct radii and face positions, rotated and multiple bores, tiny
holes, analytic tangent silhouettes, support functions, containment, box operations,
all outcome classes, one-side notches, arc/straight-edge trimming, seam handling,
clipped silhouettes, adaptive curves, unsupported-operation rejection and recovery, model
validation, cancellation, XYZ guide, perspective/parallel projection, blank New,
primitive-only Add and property operations, numeric editing, camera cache reuse, verified files,
replacement recovery, unsaved prompts and the actual PicoLAB route. Screenshots
are saved to `/private/tmp/gungos-picocad-previews`.
