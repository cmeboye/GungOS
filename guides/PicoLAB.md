# PicoLAB

Open Apps → PicoLAB. The launcher is organised as:

```text
PicoLAB
├── Checks
│   ├── Numerics check
│   └── Plot previews
├── Tools
│   ├── Graph
│   ├── Graph3D
│   └── Scientific calculator
└── Modules
    ├── Structural
    │   ├── Beam view
    │   └── Mohr circle
    ├── Dynamics
    ├── Thermal
    ├── Electrical
    └── Fluids
```

Dynamics, Thermal, Electrical and Fluids are empty folders labelled as planned.
Beam view is the former Beam Lab; its saved models, solver, controls and CSV
exports keep their existing formats and locations.

Up/Down chooses an entry, Enter opens it, and Esc returns one level. Returning
from a tool restores its parent folder and selected row. Esc at the root exits
PicoLAB. Home exits the full stack and clears the launcher session.

The PicoLAB logo remains in the header, followed by a slash-separated path,
for example `/ tools / Scientific calculator` or
`/ modules / structural / Beam view`. The logo follows the system accent.
The header remains visible in tool subpages, help and graph text editors.
The calculator and Beam view use the top 18-pixel strip; their mode bars and
content panels remain below it. Beam view, Mohr circle, Graph and Graph3D share the same
title bar, panels, property forms, editor panel and F9 help box
(`engtools/ui/lab.py`); values are typed in place, with no on-screen keyboard.

See [Beam view](BeamLab.md), [Mohr circle](MohrCircle.md), [Scientific calculator](ScientificCalculator.md),
[Graph](Graph.md), [Graph3D](Graph3D.md) and [plot previews](SharedPlots.md).

The hierarchy and breadcrumbs are SD applications. Update PicoLAB, Graph,
Graph3D and the complete `engtools` package together; this UI update does not
require another UF2.

For simulator shortcuts, full paths work, for example:

```sh
builds/MicroPython/desktop/micropython -X heapsize=16M simulator/run.py --viewer --board picocalc-pico2w --network offline --audio silent --open 'Apps/PicoLAB/modules/structural/Beam view'
```

Older simulator shortcuts such as `Apps/PicoLAB/Graph` remain aliases.
