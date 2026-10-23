# StressStrain

Open **PicoLAB → Modules → Structural → StressStrain**. This SD-card app
needs no picosolve or firmware changes. It covers section loads, section stress
maps and isotropic stress/strain conversion. Rosettes, Ramberg–Osgood curves,
Materialprop integration and mesh analysis remain later work.

## Controls

The layout follows Beam view: preview above, tabbed inputs below. Left/Right
changes tabs; Up/Down selects a field within the tab, and each tab remembers
its selected row. Section mode has **Analysis, Section, Loads**;
constitutive mode has **Analysis, Inputs, Material**.
In section mode, choose **Section + material** in the Section tab to open
the shared section preview with **Geometry, Material, Properties** tabs.
The evaluation-point coordinates remain in the main Section tab.
Enter edits the selected field or opens a choice. Typing a number
replaces the selected numeric field; expressions such as `20/3` work.
Enter applies an edit; Esc cancels. Displays use mm, kN, Nm, MPa, GPa and
microstrain (`ue`, one millionth); models and files use SI.

| Key | Action |
|---|---|
| F1 | Select Section loads or Stress ↔ strain |
| F2 | Open section material and choose a preset; in constitutive mode, choose its material preset |
| F3 | Examples, cases, exports and assumptions |
| F4 | Expanded stress map / stress-tensor view; calculates if needed |
| F5 | Results, properties and load contributions |
| F6 | Calculate the current inputs |
| F7 | In the expanded section view, cycle normal / resultant shear / von Mises maps |
| F8 | In the expanded section view, cycle max sx / min sx / max shear / max von Mises points |
| F9 | Equations in the scientific calculator's math layout, then help and conventions |
| Z | Undo up to eight input changes |
| Esc | Return to inputs, then exit |

The embedded section editor uses the same dimensioned, centroid-axis preview
as Section Properties and Beam view. Geometry edits highlight the corresponding
dimension; valid drafts update the outline and derived properties before Enter.
Esc cancels a draft, then returns from the section editor to StressStrain inputs.
Geometry, material and temperature edits apply to the current StressStrain case;
the Properties tab is read-only. Changes clear calculated point results and maps,
which F6 rebuilds. F9 in the editor opens formatted section-property equations.
The editor retains StressStrain's existing supported shapes, including custom
A/I records without an outline. It does not modify the standalone Section
Properties session or introduce saved-section exchange.

Input edits clear calculated results and maps. The expanded section view uses arrows to move
the point by 5% of the section dimension, and Tab cycles its four edge points
and centre (excluding the hole of a tube). Moving a calculated probe updates
its stress and strain immediately while retaining the section search and map.
Moves outside the material are refused. Entering coordinates numerically
allows any valid point; F6 checks it. Custom sections have no boundary to check.

Changing shape preserves the loads and moves the point to an outer point.
F6 reports unsupported loads rather than ignoring them. Changing the
stress/strain input direction converts the current inputs to the other form.

## Section loads

The cut face has normal +x: x is along the member, y is right and z is up.
Loads are resultants acting on that face; tension is positive, and moments
use the right-hand rule. Coordinates are measured from the centroid.

The supported shapes and loads are:

| Shape | Axial / biaxial bending | Torsion | Transverse shear |
|---|---|---|---|
| Solid circle / circular tube | Yes | Circular shaft theory | Pending |
| Solid rectangle | Yes | Pending | Breadth-averaged beam approximation |
| Custom A, Iy, Iz | Yes, about principal axes | Pending | Pending |

The normal stress is `sx = N/A + My*z/Iy - Mz*y/Iz`, where
`Iy = integral(z² dA)` and `Iz = integral(y² dA)`.
Circular torsion adds `txy = -T*z/J`, `txz = T*y/J`, with `J = Iy + Iz`.
For rectangles, the transverse contributions are
`txy = 1.5*Vy/A * (1 - (2*y/b)²)` and
`txz = 1.5*Vz/A * (1 - (2*z/h)²)`.
These shear components are beam-theory averages across the complementary
width, not a full three-dimensional elasticity solution at the point.
Stress concentrations, warping and plastic redistribution are not modelled.

Custom section axes must be centroidal principal axes (`Iyz = 0`). The preview
shows axes only; it does not invent an outline from A and I.
Uniform heating in Section loads produces free thermal strain, without
restraint stress. Use the constitutive mode to specify constrained total strain.

## Stress ↔ strain

The material is homogeneous, isotropic and linearly elastic. The shared
`engtools/materials.py` record holds E, nu, alpha and yield strength in SI.
Presets are explicitly illustrative steel-like/aluminium-like inputs, not
certified material grades. Every property is editable; yield = 0 disables
the yield factor. E must be positive and `-1 < nu < 0.5`.

Tensor order is xx, yy, zz, xy, yz, zx. Normal strains are total strains.
Shear inputs/outputs are engineering strains: `gamma_ij = 2*epsilon_ij`.
The shear modulus is `G = E / (2*(1+nu))`; thermal normal strain is
`alpha * delta T` in each direction. Thermal strain is added in compliance
and subtracted before applying stiffness.

- **3D:** six stress or six strain inputs.
- **Plane stress:** sx, sy, txy or ex, ey, gxy are inputs. sz, tyz, tzx are
  zero; ez is derived, including thermal expansion.
- **Plane strain:** the same three in-plane inputs. Total ez, gyz, gzx are
  zero; sz is derived, including restraint of thermal expansion.

For example, free heating at zero stress gives equal normal thermal strains.
Fully restrained 3D heating at zero total strain gives equal compressive
stresses `-E*alpha*delta T / (1-2*nu)`. The examples include both conditions.

Results include all stress/strain components, principal stresses, von Mises,
maximum shear, Tresca equivalent, and yield / von Mises. These are values
at the selected point. A separate section-critical-points group gives the
section-wide search described below.
Zero equivalent stress or disabled yield gives `--` for the yield factor.
When von Mises exceeds yield, the results identify the elastic extrapolation.

The implementation uses the existing Mohr calculation for invariants. The
device and native desktop MicroPython calculate in float32; very small
components relative to the dominant stress can be rounded away.

## Stress maps and critical points

After calculation, the input preview and F4 view show the section stress map.
F7 selects **normal sx**, **resultant shear** `sqrt(txy² + tzx²)`, or
**von Mises** `sqrt(sx² + 3*(txy² + tzx²))`. Resultant shear is the magnitude
of shear traction on the +x face; it is distinct from principal maximum shear.
The probe marker and readout always refer to the current point.

Normal stress uses a symmetric blue (compression), white (zero), red (tension)
scale. Nonnegative fields use blue through yellow to red. The displayed MPa
range belongs to the current section and loads; map colors do not indicate
yield status. A zero normal field is white. The raster is a visual approximation;
very thin walls can be represented mostly by their outline at screen resolution.

F8 moves the probe through four critical locations. Maximum/minimum sx are
**exact within the supported section model**: rectangle corners, or the outer
circle in the biaxial bending direction. Max sx and min sx are signed values;
they do not necessarily imply that both tension and compression are present.

Maximum resultant shear and von Mises are **sampled estimates**, not guaranteed
upper bounds. Rectangles use a 33 × 33 grid including edges and centre. Circles
and tubes use 9 radii × 96 angles including both radial boundaries; exact normal
extrema are also evaluated. Multiple tied extrema may select any equivalent
point. F5 lists each critical value, its coordinates and the search resolution.
The search uses the same supported shear/torsion approximations as point results.
Custom A/I sections retain point calculations and axes-only previews: without
an outline they have no map or section-wide extrema. Constitutive mode retains
its tensor view. Cases and point exports retain their existing format.

## Files

Version 1 cases live in `picoware/engineering/cases/` with tool
`stressstrain`. Inputs, including section dimensions, loads, total strains,
material and temperature difference, are stored in SI. Existing names are
refused. Saving and loading both validate the model.
The current inputs also survive unloading within the PicoLAB session.

CSV exports contain one row with six stress columns in Pa and six
dimensionless total-strain columns. Files are numbered in
`picoware/engineering/exports/`.

Stress-state JSON exports are numbered in `picoware/exchange/` and contain
kind `stress-state`, version 1, `from`, named stress components in Pa, point
coordinates in m and an axis description. This is a preliminary exchange
record: Mohr import and the shared Send to flow have not been implemented.

## References and validation

Equations follow the isotropic constitutive relations described by
[David Roylance, MIT, Constitutive Relations](https://eng.libretexts.org/Bookshelves/Mechanical_Engineering/Mechanics_of_Materials_(Roylance)/03%3A_General_Concepts_of_Stress_and_Strain/3.04%3A_Constitutive_Relations)
and elementary beam/shaft theory in
[MIT, Stresses: Beams in Bending](https://web.mit.edu/emech/admin/OldFiles/dontindex-build/full-text/emechbk_7.pdf).

The model test checks closed-form shaft and rectangle results, shear force
resultants by numerical integration, thermal restraint, plane conditions,
engineering shear and forward/inverse consistency. UI tests drive edits,
undo, point movement, errors, materials, files and exports by keys, then
render all examples and both dark/light backgrounds. Map tests independently
check biaxial extrema, combined-load von Mises, centre shear, thin tubes,
zero fields, probe updates, critical-point jumps and map controls. Section-editor
checks cover live drafts, cancel/commit/undo, invalid dimensions, material edits,
read-only properties, remembered tabs, theme rendering and standalone isolation.

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_stressstrain.py
sh tools/run-micropython-desktop.sh --viewer --network offline --audio silent --open 'Apps/PicoLAB/modules/structural/StressStrain'
```

Device heap and timing benchmarks remain a release requirement.
