# Section Properties — first pass

Open **PicoLAB → Modules → Structural → Section Properties**. The standalone
app uses the existing Beam view cross-section preview and the shared tabbed
UI. It is an SD-card app; no firmware changes are needed.

This pass is for reviewing the editor and geometric calculations. Saved
sections and reports belong to this app. Import/picking from Beam view,
Buckling, StressStrain and PicoCAD will be discussed after this review.

## Editing and navigation

The upper panel shows the section to scale, the selected dimension, its
centroid and axes, area, both inertias, centroid coordinates and mass per
unit length. The lower tabs are **Geometry, Material, Properties**.
Left/Right changes tab; Up/Down selects a row. Each tab remembers its row.

Enter edits a field. Typing a number replaces a selected numeric field;
arithmetic such as `2*40` is supported. Valid drafts update the shape and
derived values immediately, without changing the accepted section. Enter
applies; Esc cancels. Invalid inputs remain in the editor for correction.
Shape and material pickers also preview the selected option before acceptance.
Names are edited with Enter and may contain up to 24 printable characters.

| Key | Action |
|---|---|
| Left/Right | Tabs; move the cursor during an inline edit |
| Up/Down | Select a field or result |
| Enter | Edit or accept |
| F3 | Examples, saved sections, CSV/JSON reports, New |
| F4 | Enlarged section view; press again to return |
| A | Toggle centroid/axis overlay |
| F5 | Full results list |
| F6 | Refresh properties (accepted edits already update them) |
| F9 | Calculator-style equations, definitions and controls |
| Z | Undo up to eight accepted changes |
| Esc | Cancel edit, return from a page, or exit |

## Shapes and coordinates

The six templates are rectangle, hollow rectangle, solid circle, circular
tube, symmetric I-section and T-section. Each has an editable example in F3.
The T-section flange is at the top. Shapes must have positive dimensions;
webs, flanges and holes must fit within the outer envelope. A tube may have
zero inner diameter, giving the solid-circle properties.

The coordinate origin is the **bottom-left corner of the outer bounding
box**, with y right and z up. Centroid coordinates cy/cz use that origin.
Second moments are about the centroidal y/z axes. The horizontal axis in the
preview passes through the centroid, including the offset T-section centroid.

Every first-pass template is symmetric about its vertical axis. Thus the
centroidal product Iyz is zero, and y/z are principal axes. The reported I1
is the larger moment and I2 the smaller. The I1-axis angle is measured from
+y toward +z (0 or 90 degrees for these templates); equal moments display
**Any**, since a principal direction is not unique.

## Properties and material

Results include area, centroid, Iy/Iz/Iyz, polar area moment Ip, elastic
section moduli for the top/bottom and left/right extreme fibres, radii of
gyration, principal moments/direction, mass per length, bending rigidities
EIy/EIz and isotropic shear modulus G. T-section top and bottom moduli differ
because their distances from the centroid differ.

**Ip is a polar area moment, not a mass inertia or a general torsion
constant.** J is reported only for the circular templates, where J = Ip.
Noncircular J is shown as `--`; it is not approximated by Ip.

Materials are editable illustrative steel-like, aluminium-like and custom
records, not certified material grades. Density determines mass per length;
E determines bending rigidity and E/nu determine G. Yield and thermal
expansion are retained as material data, without a load or failure analysis.
Changing material does not change the geometric area moments. Density may
be zero; E must be positive and -1 < nu < 0.5.

Dimensions and results display in mm, mm2, mm3, mm4, kg/m, GPa and Nm2.
Internal values and files use SI. The device and desktop interpreter use
float32 arithmetic, so displayed precision is limited to about six digits.

## Files

Saved sections use the existing versioned case mechanism in
`picoware/engineering/cases/`, with tool `sectionprops`, version 1 and kind
`section-properties-case`. They store the name, template, SI dimensions and
material record. Existing filenames are refused, and writes are verified.
The current section also survives app unloading within the PicoLAB session.

Numbered reports go to `picoware/engineering/exports/`:

- **CSV:** one row of numeric properties with `name [unit]` SI headings.
  Noncircular sections omit the J column.
- **JSON:** kind `section-properties`, version 1, `from`, SI inputs/results,
  coordinate convention and a note identifying it as a standalone report.
  Noncircular J is null. For equal principal moments, theta = 0 is a
  representative direction and `equal_axes` is true.

These are standalone reports, not a finalized exchange contract. No existing
app is rewired to consume these files in this pass.

## Validation and remaining work

The model checks closed-form rectangle, box, circle, tube and I-section
references, T-section centroid/inertia against numerical integration, and
dimensional scaling. UI checks drive live drafts, cancellation, invalid
edits, materials, picker previews, focus restoration, files, reports,
equation help, all templates and dark/light themes.

The area parallel-axis calculation follows
[University of Alberta, Moments of Inertia of Area](https://engcourses-uofa.ca/books/statics/moments-of-inertia-of-area/parallel-axis-theorem/).

Composite sections, arbitrary profiles, general asymmetric principal axes,
noncircular torsion, shared section consumers and device memory/timing
benchmarks remain later work.

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_sectionprops.py
sh tools/run-micropython-desktop.sh --viewer --network offline --audio silent --open 'Apps/PicoLAB/modules/structural/Section Properties'
```
