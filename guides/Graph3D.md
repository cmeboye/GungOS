# Graph3D

The app uses the shared PicoLAB screen parts (title bar, panels, one-line
footer, F9 help) of Beam view and Graph; values and equations are typed in
place, without an on-screen keyboard. It opens directly on the default surface. Presets, the second surface, saved equation pairs and screenshots remain
available. 2D slices remain available for heightfield functions.

## Controls

- Arrows: move the surface in the screen plane (Pan, the default).
- Space: switch arrows between Pan and Orbit. The current mode appears in the header.
- Arrows in Orbit: rotate left/right and tilt up/down.
- Plus / minus: zoom in/out around the screen center; equals also zooms in.
- F: fit both sampled surfaces in the plot with padding, retaining orientation.
- R: reset pan, rotation and zoom; stop auto-spin.
- W: settings: X, Y and Z ranges, aspect, resolution, style, contours,
  auto-spin and arrow mode (see Ranges).
- S: style: solid, wireframe, heat map. G: type the mesh resolution.
- Z: next symmetric range preset (±2 … ±10), replacing typed ranges.
- Enter: edit the main surface in an editor panel. Back: plot menu.
- C: 2D slice. P: screenshot to SD. A: auto-spin. F9, H or ?: help.

## Ranges

Settings hold X minimum/maximum and Y minimum/maximum, typed in place like
Beam view's values (type a number, Enter to edit, Up/Down while typing to
apply and move on). Z range is Auto or Fixed:

- For z = f(x, y), Auto fits the height scale to the values; Fixed sets the
  height scale and colours to Z minimum..maximum and clips the surface there.
- For F(x, y, z) = 0, Z minimum..maximum bounds the sampled volume; Auto uses
  the larger of the X and Y spans, centred on zero.

Typing a Z value switches Z range to Fixed. Aspect Equal keeps true
proportions (a sphere stays round, a 10 x 2 range looks long); Box stretches
every axis to fill the same cube.

## Heat map

Style Heat map (S, or Settings > Style) shows z = f(x, y) from above as
colour on 3-pixel cells, with the colour bar and its range on the right and
nine contour lines (L toggles them). Arrows move a probe; the title bar reads
its x, y and z. Plus/minus zoom the x/y range about the probe. Aspect and a
fixed Z range apply here too. Only the main surface f is mapped.

A heat map needs one height per point, so an implicit surface such as
`x^2+y^2+z^2=1` refuses it: an error box explains why and the plot stays 3D.

Camera navigation reuses a compact triangle mesh. Only changes to expressions,
range or resolution trigger resampling. During movement the surface uses a wireframe preview,
then restores the chosen style after 250 ms of inactivity. Auto-spin is paced at
50 ms intervals and uses the preview. Zoom is bounded from 0.2x to 8x. Projected
lines and filled triangles are clipped to the plot area at high zoom.

## General equations and resolution

Enter `z=f(x,y)` or a bare expression for a heightfield function. General
equations such as `x^2+y^2+z^2=1`, `z^2=x^2+y^2` and `x=0` are implicit
surfaces. A bare expression containing z is interpreted as F(x,y,z)=0.
A torus example is `(sqrt(x^2+y^2)-1.2)^2+z^2=0.25`. Both surfaces can use
either form, including a mixed pair. Use explicit multiplication; `^` and `**`
are accepted. Expressions are restricted to arithmetic and known math functions.
3D inequalities are not supported; enter an equality for the boundary surface.

Heightfield functions use N x N samples. Implicit surfaces use N x N x N samples
in the volume set by the X, Y and Z ranges. The UI accepts any integer N from
4 to 64, typed with G or in Settings > Resolution N. Values above 24 for functions,
or 16 for implicit surfaces, show the sample count and a performance/RAM warning.
Enter applies the value; Back keeps the previous one. These thresholds are
conservative heuristics, not measured frame-rate guarantees.

Implicit meshes use marching tetrahedra, streaming only two volume planes in
memory. Sampling proceeds in small batches with a progress screen; Back cancels.
Triangle storage is budgeted from available memory and capped at 6000 triangles.
If a dense mesh exceeds that budget, the app reports an error instead of showing
a truncated shape. Press G on the error screen to lower resolution and retry.
A high N is therefore accepted for sampling, but a completed plot is not
necessarily possible within the Pico's memory budget.

Implicit surfaces keep equal XYZ units (a sphere stays spherical) and fit to the
view after sampling. Functions retain the existing automatic height scaling;
a mixed pair uses the implicit surface's equal XYZ scale. Sphere, ellipsoid,
torus and cone presets are included. Pan moves the existing mesh; change the
ranges to search a different mathematical volume. Very small features, isolated roots
and sign changes at some discontinuities can be missed by numerical sampling.


## Try it in the simulator

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/run.py --viewer --board picocalc-pico2w --network offline --audio silent --app Graph3D
```

## Files

- Shared implementation: `builds/MicroPython/apps_unfrozen/engtools/plots/plot3d.py`
- Standalone entry point: `builds/MicroPython/apps_unfrozen/Graph3D.py`
- Compiled app: `builds/MicroPython/apps/Graph3D.mpy`
- Workspace SD snapshot: `SD contents/picoware/apps/Graph3D.mpy`
- Original backups: `builds/MicroPython/app_backups/Graph3D-original.py` and `.mpy`

Deploy the complete `builds/MicroPython/engineering-preview.zip` bundle: Graph3D
now needs the engtools package alongside its entry file. Merge the picoware folder
onto your SD root, exit the app before replacing files, and relaunch it. No
firmware rebuild is required.

## Verification

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_graph3d.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_graph3d_implicit.py
```

The regression checks pan/orbit, zoom limits, projected fit bounds, safe edge
clipping, cached mesh reuse, preview refinement, menus/settings, existing presets,
second surface, slices, saved equations and paced auto-spin. The implicit tests also check sphere octants and scale, tori, planes, mixed
surfaces, custom resolution input, confirmation/cancellation, missing surfaces
and memory limits. Hardware performance has not yet been measured on PicoCalc.

Graph3D now requires the shared engtools package. See [SharedPlots.md](SharedPlots.md) for the complete deployment bundle and plot API.
