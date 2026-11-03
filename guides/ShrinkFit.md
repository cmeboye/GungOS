# Shrink fit

Open PicoLAB → Modules → Structural → Shrink fit. It models up to six
concentric bodies: a solid or bored shaft, rings, hubs or a flywheel. Each
body can spin, carry pressure inside and outside, and be pressed or shrunk
onto its neighbour. Every change solves the model again.

The keys follow Beam view: **F1** Add, **F2** Remove, **F3** Options, **F4**
Plot, **F5** Results, **F6** Refresh, **F9** Help.

## Given and Find

The speed ω, the inner pressure Pi, the outer pressure Po, and each fit's
interference δ and contact pressure p are each either **Given** or **Find**.
**SPACE** switches the selected value. With N bodies, exactly N − 1 values are
Find. Here is what each choice gives for a shaft in a hub (two bodies, so one
value is Find):

| Given | Find | Answers |
|---|---|---|
| δ, ω, Pi, Po | p | the contact pressure of a given fit |
| p, ω, … | δ | the interference needed for a contact pressure |
| p = 0, δ, … | ω | the speed at which the fit comes loose |
| p, δ, … | Po | the outer pressure that gives that contact |

A Find value shows its solved value with "(find)". Typing a number into it
makes it Given. Switching it back to Given keeps the solved value.

Some combinations have no answer. In each case the tool says why, as a red
box over the preview:
- the wrong number of Find values;
- Pi on a solid centre;
- a speed that would need ω² < 0;
- values that do not set each other, such as finding the speed of massless
  bodies.

A fit whose contact pressure comes out negative has opened. It shows as an
amber warning, because the stresses assume the parts still touch.

## Screen

- **Preview** (top, 304 × 184 pixels):
  - **Section** view: the stack cut through its axis. Material is shaded and
    hatched, the hatching alternates between neighbouring bodies, and the
    bore is left empty. The axis is dash-dotted. Amber arrows mark Pi and Po,
    and an accent arrow marks rotation. Diameters are labelled along the
    bottom.
  - **3D** view: a wireframe of the same stack.
  - The selected body or fit is drawn in the accent colour.
  - **I** shows or hides a summary box: the largest von Mises stress with its
    body, radius and safety factor, and the contact pressures.
- **Lower box**: three tabs, three rows at a time.
  - **Bodies**: for each body, the radii, thickness, material, E, ν, density,
    expansion coefficient and yield strength.
  - **Loads**: the speed, Pi, Po, the analysis model and the speed unit
    (rpm or rad/s).
  - **Fits**: the interference on the diameter (µm), contact pressure,
    friction coefficient, holding torque, axial holding force and assembly
    heating.

Bodies are listed from the centre outward. An inner radius of 0 makes body 1
solid. Each body's outer radius is also the next body's inner radius.
Choosing a material fills in its properties, and editing a property changes
the material to Custom.

## Keys

| Key | List | Preview (Tab) |
|---|---|---|
| Left / Right | Bodies / Loads / Fits tabs | Orbit: turn; Move/section: pan |
| Up / Down | choose a row | Orbit: tilt; Move/section: pan |
| Enter | edit or choose | switch section / 3D |
| digits, `-`, `.` | type a value (arithmetic works) | |
| SPACE | Given / Find | Switch Move / Orbit in 3D |
| Tab | Focus preview | Return to the same input row |
| `+` / `-` | | zoom |
| R | | reset the view |
| V | switch section / 3D | switch section / 3D |
| I | summary box | |
| Z | undo (12 steps) | |
| F1 / F2 | add a body / remove the selected body | |
| Esc | leave Shrink fit | back to the list |

While the preview has focus the preview's outline turns the accent colour, the same way
the desktop shows a focused widget. F1 offers a ring outside and, when body 1
has a bore, a solid shaft or ring inside. Each new interface is a new fit
whose contact pressure is Find.

**F4 Plot** shows the radial stress, the hoop stress, and a third panel that
**D** switches between von Mises, the radial displacement u and (in plane
strain) the axial stress, all through the radius. Interfaces are dashed.
Left/Right moves the cursor, and `,` / `.` jump to body boundaries.

**F5 Results** lists:
- every value, given or found;
- for each body, the peak stresses with their radii, the largest radial
  displacement, and the safety factor against yield;
- for each fit, the holding torque and axial force, the heating needed to
  assemble it, and the speed at which it comes loose;
- the rotor's inertia and kinetic energy.

Enter on a stress row opens the plot at that radius.

**F3 Options** has examples (shrink fit, rotating disc, flywheel ring, thick
cylinder, compound cylinder, required fit), Save and Open (to
`picoware/engineering/cases`), and the conventions.

## Theory and conventions

- Lamé's thick-cylinder solution with the rotation's body force, for each
  body:

  σr = A + B/r² − (3+ν)/8 ρω²r²
  σθ = A − B/r² − (1+3ν)/8 ρω²r²

- **Thin discs (plane stress)**: σz = 0.
- **Long cylinders (plane strain, ends held)**: E/(1−ν²) and ν/(1−ν) replace
  E and ν, and σz = ν(σr + σθ).
- **Fits**: at each fit, the radial stress on both sides equals −p, and the
  difference in radial displacement is half the diametral interference.
  Because the radius changes are small, both sides use the nominal radius.
- **Signs**: tension is positive. Pressures act inward on their surface.
  u is positive outward. Every body turns at the same speed.
- **Holding torque** = μ p 2πr² L and **axial force** = μ p 2πr L, where L is
  the thickness of the thinner of the two bodies.
- **Assembly heating** = δ / (α d) for the outer part, with no extra
  clearance.
- **Loosening speed**: the speed at which the fit's contact pressure reaches
  zero, with the other values held.
- **Single precision**: the device works in single precision. The solver uses
  mm, MPa and ω in krad/s to keep the equations well scaled.

Simulator:

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/run.py --viewer --board picocalc-pico2w --network offline --audio silent --open 'Apps/PicoLAB/modules/structural/Shrink fit'
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_discs.py
```
