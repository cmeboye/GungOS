# PicoLAB

New apps follow [PicoLAB keys](Keys.md) for function keys and input/preview
focus. It records the local control alignment; the app guides linked below describe
the controls currently implemented.

Open Apps → PicoLAB. The launcher is organised as:

```text
PicoLAB
├── Checks
│   ├── Numerics check
│   └── Plot previews
├── Tools
│   ├── Grapher
│   ├── Scientific calculator
│   └── UnitConverter
└── Modules
    ├── Structural
    │   ├── BeamView
    │   ├── Shrink fit
    │   ├── Mohr circle
    │   ├── StressStrain
    │   ├── Buckling
    │   └── Section Properties
    ├── Machine design
    │   └── PicoCAD
    ├── Dynamics
    │   ├── ModalHarmonics (planned)
    │   ├── TransientSolve (planned)
    │   ├── Multibody (planned)
    │   └── TransferFunc (planned)
    ├── Fluids
    │   ├── FlowRegimes (planned)
    │   ├── PipeLoss (planned)
    │   ├── BoundaryDrag (planned)
    │   └── 1DNetSolve (planned)
    ├── Thermal
    │   └── Heat transfer 2D
    └── Electrical
        └── PicoSpice
```

Dynamics and Fluids show informational lists of their planned apps. The rows
are muted and have no selection or launch action; Esc returns to Modules.
PicoCAD is under Modules → Machine design, alongside the other disciplines.
BeamView is the former Beam Lab; its saved models, solver, controls and CSV
exports keep their existing formats and locations.

Up/Down chooses an entry, Enter opens it, and Esc returns one level. Returning
from a tool restores its parent folder and selected row. Esc at the root exits
PicoLAB. Home exits the full stack and clears the launcher session.

The PicoLAB logo remains in the header, followed by a slash-separated path,
for example `/ tools / Scientific calculator` or
`/ modules / structural / BeamView`. The logo follows the system accent.
The header remains visible in tool subpages, help and graph text editors.
The calculator and BeamView use the top 18-pixel strip. BeamView's model
preview sits directly below it, without a second app/model title bar.
BeamView, Mohr circle and Grapher share the same
title bar, panels, property forms, editor panel and F9 help box
(`engtools/ui/lab.py`); values are typed in place, with no on-screen keyboard.

UnitConverter, StressStrain and Buckling follow BeamView's preview-above,
tabs-below layout. Left/Right switches input sections and restores the selected
row in each tab; Up/Down moves within the active section. Their F9 pages
show equations first using the scientific calculator's actual mathematical
renderer, followed by definitions and controls. This is shared SD-app UI in
`engtools/ui/tool.py`; it requires no firmware change.
Buckling's Section tab opens a dedicated section/material editor using the
same preview renderer as BeamView (`engtools/ui/section.py`). Buckling's
column preview remains 184 pixels high; BeamView's model preview is now 204.

See [PicoCAD](PicoCAD.md), [BeamView](BeamLab.md), [Shrink fit](ShrinkFit.md), [Mohr circle](MohrCircle.md), [Heat transfer 2D](HeatTransfer.md), [PicoSpice](PicoSpice.md), [Scientific calculator](ScientificCalculator.md),
[Grapher](Grapher.md), the legacy [Graph](Graph.md) and [Graph3D](Graph3D.md) entry points, [UnitConverter](UnitConverter.md),
[StressStrain](StressStrain.md), [Buckling](Buckling.md),
[Section Properties](SectionProperties.md) and [plot previews](SharedPlots.md).

Grapher provides one workspace with independent 2D and 3D plots: F3 opens
its menu, including the mode choices. Existing solver apps retain their current plots while
the shared API is tested in isolation.

The hierarchy and breadcrumbs are SD applications. Update PicoLAB, Grapher,
Graph, Graph3D and the complete `engtools` package together; this UI update does not
require another UF2.

For simulator shortcuts, full paths work, for example:

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/run.py --viewer --board picocalc-pico2w --network offline --audio silent --open 'Apps/PicoLAB/modules/structural/BeamView'
```

Older simulator shortcuts such as `Apps/PicoLAB/Graph` and
`Apps/PicoLAB/Graph3D` open the corresponding Grapher mode. Direct legacy
entry points and their saved sessions remain available separately. The current
PicoCAD shortcut is `Apps/PicoLAB/modules/Machine design/PicoCAD`; the simulator
also accepts the former `Apps/PicoLAB/tools/PicoCAD` shortcut and the short
`PicoLAB/PicoCAD` form. They all open the new folder route.
