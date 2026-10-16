# Graph3D

The app uses the same dark panel colors, cyan title/footer hints and highlighted
menu rows as Graph. It opens directly on the default surface. Presets, the second surface, saved equation pairs and screenshots remain
available. 2D slices remain available for heightfield functions.

## Controls

- Arrows: move the surface in the screen plane (Pan, the default).
- Space: switch arrows between Pan and Orbit. The current mode appears in the header.
- Arrows in Orbit: rotate left/right and tilt up/down.
- Plus / minus: zoom in/out around the screen center; equals also zooms in.
- F: fit both sampled surfaces in the plot with padding, retaining orientation.
- R: reset pan, rotation and zoom; stop auto-spin.
- W: settings for XY range, mesh resolution, style, auto-spin and arrow mode.
- S: toggle solid/wireframe. G: enter mesh resolution. Z: cycle sampled range.
- Enter: edit the main surface. Back: plot menu.
- C: 2D slice. P: screenshot to SD. A: auto-spin. H or ?: help.

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
in the cube [-range,+range] on all three axes. The UI accepts any integer N from
4 to 64, via G or Settings > Resolution > Enter. Values above 24 for functions,
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
torus and cone presets are included. Pan moves the existing mesh; change Range
to search a different mathematical volume. Very small features, isolated roots
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
