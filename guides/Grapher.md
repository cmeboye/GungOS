# Grapher

Open **PicoLAB → Tools → Grapher**. One workspace contains independent 2D
and 3D working plots. It uses a versioned shared API, with the existing
Graph and Graph3D renderers behind adapters. Existing solver plots have
not been migrated. This first stage is tested with synthetic fixtures.

## Controls

- **F3 → 2D plot / 3D plot** changes mode, retaining each plot’s expressions,
  bounds and settings, including the 3D camera.
- **F1** adds an expression or a second surface. **F2** opens the layer list
  for selection/removal in 2D, or the second-surface editor in 3D (clear it
  to remove). At least one layer remains in a shared plot.
- **F4** returns to the plot; **F6** refreshes it. Neither key changes mode.
- **F3** or **Esc**, at the plot: Grapher menu. Continue resumes the plot;
  Plot options opens the selected mode's editors, settings and presets.
- **Enter**: expressions in 2D; the main surface editor in 3D.
- **Arrows** pan; **+ / −** zoom; **F** fit; **W** settings.
- **Space**, in 3D: switch pan/orbit. **S** cycles surface style;
  **C** opens a heightfield slice. Existing per-mode keys remain available.
- **F9**, at the plot or Grapher menu: workspace help. Plot options →
  Mode help contains the expression syntax and detailed controls.
- **Esc** in the Grapher menu: save and close. Home releases the viewer
  and attempts to save the session while leaving the full app stack.

The Examples menu contains expression/sample overlays, an implicit region,
a parametric curve, a height surface, an implicit sphere and a heat map.
Selecting an example replaces that mode's working plot.

Both working plots are saved in
`picoware/settings/grapher/session.json` (maximum 32 KB). Writes are verified
before replacement. Replacement uses `.tmp` and `.bak` files because the
device's FAT32 rename does not overwrite an existing destination. A failed
explicit save keeps the menu open and reports the error; reopening recovers
a `.bak` when the main session is missing. This is not a guarantee against
power loss during an SD filesystem operation.

The old Graph/Graph3D entry points and their session files remain independent.
Grapher starts a new workspace rather than importing those sessions.

## Shared API, version 1

```python
from engtools import plots

document = {
    'kind': 'plot',
    'version': 1,
    'title': 'Synthetic response',
    'sources': {
        'reference': {'kind': 'expression', 'expression': '0.5*exp(-x)'},
        'observations': {'kind': 'samples',
                         'points': [(0, .5), (1, .2), (2, .08)]},
    },
    'layers': [
        {'source': 'reference', 'name': 'Reference'},
        {'source': 'observations', 'name': 'Samples',
         'style': 'scatter', 'marker': 'cross'},
    ],
    'axes': {
        'x': {'bounds': [0, 5], 'label': 'Time', 'unit': 's'},
        'y': {'bounds': [0, .6], 'label': 'Voltage', 'unit': 'V'},
    },
    'view': {'mode': '2d', 'grid': True, 'legend': True},
}

plots.validate(document)       # validates before opening a view
plots.show(view_manager, document)
```

`show` also validates, so callers need not invoke both. It returns the managed
view name `eng_plot`. Esc at the plot returns to the caller. Invalid documents
are rejected before navigation; an unexpected startup failure returns to the
caller and raises an error. Callers follow the existing managed-view stop/start
lifecycle described in [SharedPlots.md](SharedPlots.md).

The layers reference named sources. The public description contains no
compiled formulas, render buffers or app objects. Metadata is copied during
validation; sampled point sequences are borrowed without copying their data.
The caller must keep them unchanged until the viewer closes. Plot edits affect
the viewer's working state, not the caller's document. There is no edit-result
callback in v1.

Importing `engtools.plots` loads no renderer. `plots.validate` temporarily loads
only the requested renderer for expression validation and releases it if it
was not already loaded. `document.normalize` checks structure without loading
UI or renderers. One shared viewer can be active at a time; attempts to open
another are rejected. The runtime restores pre-existing 3D settings and only
unloads a renderer it imported itself.

### Supported fields

Unknown keys and unsupported capabilities raise an error. Version 1 exposes
the existing capabilities; it does not silently approximate future ones.

| Field | 2D | 3D |
|---|---|---|
| Sources | Expressions; sampled `(x, y)` pairs | Expression surfaces |
| Layers | 1–6; optional `name`, `visible`, RGB565 `color` | 1–2; source reference only |
| Sample styles | `line`, `scatter`; markers `none`, `square`, `cross`, `diamond` | Not supported |
| Axes | `x`, `y`: `bounds`, `label`, `unit`, `scale` | `x`, `y`, `z`: `bounds`, `scale` |
| Scale | `linear` | `linear` |
| View | `mode`, `grid`, `legend`, `t_range`, `padding` | `mode`, `resolution`, `style`, `aspect`, `contours`, `camera` |

2D expressions keep Graph's equations, inequalities and parametric syntax.
There are at most 4096 sample points across the rendered layers. A
`(None, None)` pair breaks a line; other coordinates must be finite numbers.
`padding` is a percentage from 0 to 50. Default X/Y bounds are −10 to 10.
At least one layer remains in a shared plot; it can be hidden or edited.

3D expressions keep Graph3D's heightfield and implicit-surface syntax.
Resolution is an integer from 4 to 64; the existing confirmation, cancellation
and triangle budgets apply. Styles are `solid`, `wire` and `heatmap`.
Heat maps require the first surface to be a heightfield and display only that
surface. Aspect is `equal` or `box`. Default X/Y bounds are −4 to 4; omitted
Z bounds retain automatic scaling/sampling. `camera` may contain `yaw`,
`pitch` (radians), `zoom` (0.2–8), `pan_x`, `pan_y` (screen pixels), and
`navigation` (`pan` or `orbit`). Geometry is sampled before restoring a camera.

```python
plots.show(view_manager, {
    'kind': 'plot', 'version': 1, 'title': 'Sphere',
    'sources': {'sphere': {'kind': 'expression',
                           'expression': 'x^2+y^2+z^2=4'}},
    'layers': [{'source': 'sphere'}],
    'axes': {'x': {'bounds': [-3, 3]}, 'y': {'bounds': [-3, 3]},
             'z': {'bounds': [-3, 3]}},
    'view': {'mode': '3d', 'resolution': 12, 'aspect': 'equal'},
})
```

Axis units are metadata in v1: values must already be in the declared units.
Engineering exchange remains SI; a later display-transform layer will convert
SI values for display without modifying sources. There is no CSV importer,
file-backed data provider, Send to integration or generic plot-file UI yet.

## Implementation boundaries and next stages

- `document.py`: schema, validation of structure and translation at the legacy
  API boundary. No UI or renderer imports.
- `runtime.py`: renderer ownership, semantic validation, lifecycle and compact
  snapshots. Only one active engine is needed for mode switching.
- `grapher.py`: workspace menus, examples and session persistence.
- `arithmetic.py`: restricted arithmetic validation shared by both renderers.
- `plot2d.py`, `plot3d.py`: existing sampling and native/Python rendering paths.
  Their older `show` APIs remain available to current callers.

The 3D implementation still uses module state internally; the adapter enforces
single ownership rather than claiming it is a reentrant renderer. This stage
does not yet expose rendering into an arbitrary app-owned viewport.

Next capabilities should extend this contract through isolated fixtures first:
log axes and probes; linked panes; streamed signals; display-unit transforms;
sampled grids and scalar fields independent of geometry; later meshes, vectors
and animation. Existing apps migrate only after the shared behavior and device
budgets have been verified.

## Run and verify

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/run.py --viewer --board picocalc-pico2w --network offline --audio silent --open 'Apps/PicoLAB/tools/Grapher'
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_grapher.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_shared_plots.py
```

The isolated suite exercises all six fixtures, invalid specifications, startup
failure, lazy loading, borrowed buffers, reentry rejection, cancellation, mode
switching, camera restoration, legacy-session isolation, repeated heap recovery,
FAT32 replacement/rollback, backup recovery and Home cleanup. Native parity and
legacy Graph/Graph3D tests cover the shared arithmetic extraction.

Simulator memory stability is not a PicoCalc memory or frame-rate benchmark.
Device measurements remain required before release. Deploy PicoLAB and the
complete `engtools` package together using the existing engineering bundle
command in [SharedPlots.md](SharedPlots.md). This change needs no native kernel
or firmware modification.
