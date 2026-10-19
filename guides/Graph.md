# Graph

The shared implementation is `builds/MicroPython/apps_unfrozen/engtools/plots/plot2d.py`.
`Graph.py` is now its standalone entry point. The compiled app is
`builds/MicroPython/apps/Graph.mpy`; the workspace SD snapshot also contains it.
The original app is backed up in `builds/MicroPython/app_backups/`.

## Simulator

From the project root:

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/run.py --viewer --board picocalc-pico2w --network offline --audio silent --app Graph
```

## Controls

Graph uses the same screen parts and keys as Beam view: the PicoLAB title bar,
panels, a one-line footer and the F9 help box. Values and expressions are typed
in place on the PicoCalc keyboard; there is no on-screen keyboard.

- Arrows: pan the plot; select rows in menus.
- Plus / minus: zoom around the center. Equals also zooms in.
- Enter: expressions. Enter on a row (or + Add expression) opens an editor
  panel; Enter applies, Esc cancels, and an invalid expression stays open with
  the reason.
- Back: plot menu; return from submenus. Choose Quit to exit.
- W: the Window form: X, Y and T limits, fit padding and grid. Type a number
  to replace the selected value (arithmetic such as `2*pi` works), Enter to
  edit it, Up/Down while typing to apply and move on. Enter on Grid toggles it.
- F: Fit Y, Fit visible curves, Equal axis scale or Default window.
- R: reset to the default -10 to 10 window.
- G: toggle grid. F9, H or ?: help.
- In Expressions: Space toggles visibility; D or Delete removes a row.

## Expressions

Up to six colored expressions can be visible together:

- `sin(x)` or `y=sin(x)`
- `x=3`
- `x^2+y^2=25`
- `x*y=1`
- `y>=sin(x)`
- `x^2+y^2<=25`
- `cos(t);sin(t)` (parametric x(t);y(t))

Use explicit multiplication (`2*x`), radians and `^` or `**` for powers.
Arithmetic, pi, e, standard trigonometry, logarithms, square roots, abs,
min/max and other listed math functions are supported. Arbitrary Python
code, attribute access and imports are rejected.

Strict inequalities have dashed boundaries; inclusive inequalities have solid
boundaries. Regions use colored stippling to keep overlaps visible. Separate
inequalities are drawn independently; this is not a Boolean region parser.

## Fit and persistence

Fit Y samples explicit y=f(x) functions in the current horizontal window and
trims 2 percent from each tail to reduce the influence of poles. Fit visible
curves uses boundaries sampled in the last completed plot: it cannot discover
components outside the current window or fit a region with no visible boundary.
Wait for ready before using that option. Equal axis scale preserves the X bounds
and adjusts Y so circles look circular. Fit padding is 0 to 50 percent.

Save session writes equations, visibility, bounds, t range, grid and padding to
`picoware/settings/graph/session.json`. Quit also saves. A fresh launch restores
that session; save errors are checked and reported.

General equations are sampled on a 5-pixel grid (10-pixel navigation preview),
with marching-square contours and midpoint checks for discontinuities. Rendering
runs in small batches and refines after navigation stops. Narrow features,
isolated roots and some singularities can be missed: this is a numerical plotter,
not a symbolic algebra system. Native PicoCalc performance still needs on-device
verification.

## Compile and install

```sh
python3 tools/compile-engineering-apps.py --mpy-cross /path/to/micropython/mpy-cross/build/mpy-cross
```

Use mpy-cross compatible with your firmware. Merge the bundle's `picoware` folder
from `builds/MicroPython/engineering-preview.zip` onto the SD root. Graph now needs
the complete `engtools` package alongside it. Exit the app before updating files,
then relaunch it. No UF2 rebuild is required. Keep one .py or .mpy copy of each
module in the deployed app tree.

## Verification

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_graph.py
```

Shared plotting and deployment now require the engtools package. See [SharedPlots.md](SharedPlots.md); use its bundle/build command when updating Graph.
