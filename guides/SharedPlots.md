# Shared engineering plotting

The unified **Grapher** workspace and new versioned `engtools.plots.show`
API are documented in [Grapher.md](Grapher.md). New capabilities are tested
there with isolated fixtures before migrating solver apps. The APIs below
remain the compatibility interfaces used by existing callers.

`Graph.py` and `Graph3D.py` now delegate to `engtools/plots/plot2d.py` and
`plot3d.py`. Both standalone apps and PicoLAB use the same rendering
code and `engtools/ui/theme.py` for their header, footer and menu styling.

Open **PicoLAB > Checks > Plot previews** in the simulator to compare:

- 2D equations: two curves and a colored legend.
- 2D shaded region: an implicit circle and inequality.
- 2D sampled data: line/scatter series with labels and display units.
- 3D function: a saddle with pan/orbit/zoom.
- 3D implicit surface: a sphere with equal XYZ units.

The data examples are synthetic visual fixtures, not engineering solver results.
Existing engineering tools retain their current plot integrations. Calculator
Solver and Matrix use their own numerical cores.

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/run.py --viewer --board picocalc-pico2w --network offline --audio silent --app PicoLAB
```

Arrow keys select gallery entries; Enter opens a plot. On a plot, arrows pan,
plus/minus zoom, W opens settings, and Back returns to the selected gallery
entry. In 3D, Space switches arrows between Pan and Orbit; F fits the surface.

## 2D API

From a managed tool view:

```python
from engtools.plots import plot2d

plot2d.show(view_manager, {
    'title': 'Response',
    'bounds': [0, 5, -1, 1],
    'axes': {
        'x': {'label': 'Time', 'unit': 's'},
        'y': {'label': 'Voltage', 'unit': 'V'},
    },
    'legend': True,
    'series': [
        {'type': 'samples', 'name': 'Calculated',
         'points': [(0, 0), (1, .5), (2, .25), (5, 0)], 'style': 'line'},
        {'expression': '0.5*exp(-x)', 'name': 'Reference'},
    ],
})
```

Expressions, general equalities, inequalities and parametric expressions use
the existing Graph syntax. Sample series support `line` and `scatter`, optional
RGB565 `color`, and `visible`. A `(None, None)` point breaks a line. There are
at most six series and 4096 sample points in total. Points are retained without
duplicating the caller's dataset; do not change that dataset while it is open.
Sample values are edited by the source tool; expression editing remains available.

`t_range`, `grid` and `equal_scale` are optional. Axes are currently linear;
requesting a logarithmic scale raises an error rather than silently drawing a
linear plot. Unit strings are display metadata; conversion belongs in the model.

## 3D API

```python
from engtools.plots import plot3d

plot3d.show(view_manager, {
    'title': 'Sphere',
    'range': 2,                    # or 'bounds': [x0, x1, y0, y1]
    'resolution': 12,
    'style': 'solid',
    'surfaces': [{'expression': 'x^2+y^2+z^2=1'}],
})
```

Use one or two expression surfaces, explicit or implicit. `range` is 0.01 to
100 (a symmetric ±range); `bounds` sets uneven x and y limits instead.
`style` is `solid`, `wire` or `heatmap` (functions only), and `resolution` is
an integer from 4 to 64. High resolution still requires
confirmation, sampling can be cancelled, and the memory budget remains enforced.
Sampled 3D grids and logarithmic axes are future extensions.

## Lifecycle and deployment

Both `show` functions validate specifications before switching views and return
the registered view name. They push a managed child view and release its plot
data on exit. Back on the plot returns to its caller. A tool must preserve the
navigation state it wants to restore when its `start` callback runs again.
PicoLAB preserves the gallery selection this way.

Embedded 2D plots do not load or overwrite the standalone Graph session.
Embedded 3D plots restore the standalone equation/range/resolution/style settings
on exit and leave the saved-equation list alone. Viewers are imported lazily.

Eggcel's sampled 2D plots set `system_theme=True` for a per-view system palette
and `data_only=True` for data controls: F fits every visible sample, and series
can be hidden without editing/removing source data. These options do not change
the standalone Graph palette/session. Sample series can specify `marker` as
`none`, `square`, `cross` or `diamond`; `(None, None)` breaks a line at a gap.
Eggcel preserves its workbook through the child's stop/start lifecycle and
releases it on an actual exit, including Home while a chart is active.

The standalone apps now require the `engtools` package alongside them. Build
and install them together:

```sh
python3 tools/compile-engineering-apps.py --mpy-cross /path/to/mpy-cross
```

This compiles the entry apps (including Eggcel), demos and complete package, updates
`builds/MicroPython/apps` and the workspace `SD contents` snapshot, and generates
`builds/MicroPython/engineering-preview.zip`. Merge the bundle's `picoware`
folder onto the SD root. Keep one `.py` or `.mpy` version of each deployed module.
There is no firmware change.

## Checks

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_graph.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_graph3d.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_graph3d_implicit.py
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_shared_plots.py
```

The shared-viewer test exercises all gallery cases, sampled-data controls, lazy
loading, return selection, view cleanup, standalone-session isolation, invalid
specifications, high-resolution cancellation and the original app entry points.
Rendering performance on the physical PicoCalc still needs measurement.
