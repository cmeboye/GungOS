# PicoLAB engineering tools

`PicoLAB.py` provides a plotting preview gallery, a native Numerics checks page,
and a keyboard-driven scientific calculator with six numerical modes. Checks contains numerics validation and plot previews. Tools contains Graph,
Graph3D and the scientific calculator. Modules contains Structural → Beam view
Thermal → Heat transfer 2D (`thermal/`, see [HeatTransfer.md](../../../../guides/HeatTransfer.md)),
and empty planned folders for Dynamics, Electrical and Fluids. See
[ScientificCalculator.md](../../../../guides/ScientificCalculator.md) for
its input rules and current mode/precision limits.
Statistics now provides one-/two-variable data, frequencies, descriptive
statistics and linear fits through the shared `numerics/statistics.py` module.
See [Statistics.md](../../../../guides/Statistics.md).
`plots/plot2d.py` and `plot3d.py` now
contain the shared viewers used by both PicoLAB and the standalone
Graph/Graph3D entry apps. `ui/theme.py` owns their common styling.

The selected ulab configuration is integrated into the desktop and future
PicoCalc firmware builds. `numerics/backend.py` checks its capabilities and
guards QR workspace; `numerics/bench.py` tests known answers and reports check
timings/allocation deltas. See [the ulab guide](../../../../src/MicroPython/ulab/README.md).

Beam view, formerly Beam Lab (`beamlab/`) is the first complete engineering tool; see
[BeamLab.md](../../../../guides/BeamLab.md). It implements the shared
`units.py` (fixed engineering SI display units), `cases.py` (verified JSON
cases, streamed CSV) and `ui/forms.py` (single-line input). `jobs.py` remains
a placeholder.
Calculator equations and matrices have dedicated working numerical modules.
The gallery uses
synthetic examples; it does not present engineering calculations.

Numerics checks needs the new firmware containing ulab. On the existing device
UF2 that page reports the missing library. Updating the SD package alone cannot
install the native library; other plotting previews remain usable.

See [SharedPlots.md](../../../../guides/SharedPlots.md) for plot specifications,
viewer lifecycle, deployment and regression checks.

## Boundaries

- `numerics/`: mathematical routines; no display or SD dependencies.
- `tools/`: engineering models, assumptions, validation and plot descriptions.
- `plots/`: rendering and navigation for expressions or calculated data.
- `ui/`: shared theme, parameter forms and result pages.
- `calculator/`: bounded expression editing, textbook layout and calculator UI.
- `units.py`: consistent internal SI values and display-unit conversion.
- `jobs.py`: bounded work, progress, cancellation and memory limits.
- `cases.py`: versioned saved inputs/settings and streamed CSV export.

Package initializers import no submodules. Tool modules are loaded on selection.
No module launches an app or accesses storage when imported.

## Proposed contracts

These are design targets to implement and refine with the first complete tool:

1. Input fields have `id`, `label`, `default`, `unit` and applicable bounds.
2. Each model exports `TOOL`, `validate(parameters)`, `solve(parameters, job)`
   and `build_plots(result)`.
3. Calculation results include `status`, named values with units, assumptions,
   and convergence/error metadata where applicable. No-convergence, singular
   systems, invalid domains and budget limits must be distinguishable.
4. Plot descriptions contain kind, title, axes/units/scales, viewing bounds and
   expression or sampled-data series. Numerical data need not be converted to
   expression strings.
5. Jobs expose step, cancel, progress and terminal status. Tool models do not
   control the main UI loop.
6. Saved cases contain `version`, tool ID, reproducible inputs, display units
   and viewing/solver settings. Large derived datasets are exported separately.

Planned SD paths are `picoware/engineering/cases/` and
`picoware/engineering/exports/`.

## Simulator

From the project root:

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/run.py --viewer --board picocalc-pico2w --network offline --audio silent --app PicoLAB
```

Up/Down selects a row; Enter opens a folder or tool. Esc returns one level,
restoring the selection; Esc at the PicoLAB root exits. The logo and breadcrumb
remain visible throughout. See [PicoLAB navigation](../../../../guides/PicoLAB.md).

The simulator uses `apps_unfrozen` as its source automatically. For an SD
installation, deploy Graph, Graph3D, PicoLAB and the complete engtools
folder together. `tools/compile-engineering-apps.py` builds the compatible .mpy
tree and generates `builds/MicroPython/engineering-preview.zip`. Preserve package
directories; the original standalone plotters now require this shared package.

## Implementation order

1. Shared plotting extraction is complete, with regression checks and a preview gallery.
2. Add sampled-data plotting, units/labels, logarithmic axes and a tested solver
   core as required by the first model.
3. Complete one engineering tool end to end before adding further models.
