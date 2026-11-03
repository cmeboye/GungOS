# Mohr circle

Open PicoLAB → Modules → Structural → Mohr circle. It takes the stress at a
point, draws Mohr's circle(s), and shows the element turned by an angle. The
principal stresses, maximum shear and yield checks update as you type.

## Layout

The layout matches Beam view's section editor. The **preview** at `(8, 43)` is
304 × 142 pixels:

- Left: Mohr's circle(s) to scale. σ runs to the right and τ is drawn
  **positive down**, so the X′ and Y′ points move 2θ around the circle in the
  same direction the element turns by θ. X′ is (σx′, τx′y′) in the accent
  colour. Y′ is (σy′, −τx′y′) in amber. The ticks on the σ axis mark the
  principal stresses.
- Right: the element seen along the rotation axis, turned by θ. Normal-stress
  arrows point outward for tension, in the X′ and Y′ colours. Shear arrows are
  white. The fixed axes are dim.
- Below the drawing: one summary line with s1, s2 (s3), the maximum shear and
  the principal angle.

The **properties** box from `(8, 191)` lists the inputs and the results:

| Group | Rows |
|---|---|
| Stress state | Mode (2D plane stress or 3D general), sx, sy, txy; in 3D also sz, tyz, tzx |
| Rotation | Angle theta; in 3D, About axis; the rotated stresses on the turned faces |
| Principal | s1, s2 (and s3 in 3D), maximum in-plane shear or maximum shear, principal angle |
| Yield check | von Mises, Tresca (s1 − s3), Yield strength, and safety factors when the yield strength is set |

In **3D** the preview draws all three principal circles. The (σ, τ) of every
plane lies in the shaded band. The accent circle holds the planes you reach by
turning about the chosen axis.

## Keys

| Key | Action |
|---|---|
| Up / Down | choose a row (headings are skipped) |
| Enter | edit the value, or choose the mode or axis |
| digits, `-`, `.` | type a new value straight away; arithmetic works (`120*0.8`) |
| Enter / Tab, Esc | apply or cancel; Up/Down applies and moves on |
| Tab | Focus the rotation preview / return to inputs |
| Left / Right in preview | turn the element by 1° |
| `[` / `]` in preview | turn by 15° |
| P in preview | principal axes; press again to put s2 on the first axis |
| S in preview | maximum-shear axes; press again for the other pair |
| R in preview | θ back to 0 |
| M | switch between 2D and 3D (3D values are kept) |
| A | next rotation axis, x → y → z (3D only) |
| F3 → Examples | examples: pure shear, uniaxial tension, shaft under bending and torsion, thin pressure vessel, a 3D state, hydrostatic, clear |
| F9 | help, preserving the current edit or picker |
| F6 | Refresh the live results |
| Esc | Leave preview focus, cancel the innermost edit/picker, then exit |

Rows that are worked out (rotated stresses, principal values, checks) can't be
edited. Pressing Enter on one shows a note in the footer.

## Conventions

- Units are MPa and degrees. Tension is positive. A positive shear on a
  positive face acts in the positive direction.
- θ turns counterclockwise looking down the rotation axis, from the first axis
  of the plane toward the second: about z, x toward y; about x, y toward z;
  about y, z toward x. In 2D the rotation is always about z.
- 2D is plane stress, so sz = tyz = tzx = 0. Principal s1 and s2 are the
  in-plane values. The maximum shear, von Mises and Tresca also count the
  zero out-of-plane stress, so a biaxial tension state shows a maximum shear
  of s1/2.
- The principal angle is the θ that puts the larger in-plane principal stress
  on the first axis.
- Safety factor = yield strength / equivalent stress. Set Yield strength to 0
  to hide the safety factors.

The stress state stays in memory while PicoLAB is open and comes back on your
next visit. It is not saved to the SD card. The tool's code (about 29 KB of
heap) unloads when you return to the PicoLAB menu.

Simulator:

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/run.py --viewer --board picocalc-pico2w --network offline --audio silent --open 'Apps/PicoLAB/modules/structural/Mohr circle'
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_mohr.py
```
