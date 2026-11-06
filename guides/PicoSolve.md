# picosolve

picosolve is GungOS's built-in C module for structural solving, circuit analysis,
repeated formula evaluation and plot geometry. The applications provide Python
editors and displays; picosolve performs the selected numerical work underneath.
It is included in the custom firmware and host simulator as `import picosolve`.

## Where it is used

| Application | picosolve's role |
|---|---|
| BeamView | Euler–Bernoulli beams and 2D plane frames: displacements, support reactions, member forces and diagrams |
| PicoSpice | Circuit operating points, DC sweeps and transient traces using modified nodal analysis |
| Graph, Graph3D and Grapher | Supported expression evaluation, implicit contours and surface/isosurface geometry |
| Scientific calculator | Supported real expressions used in integration and equation solving; the Python numerical routines manage the overall calculation |

ulab provides separate array/numerical operations, while the native gfx module
handles drawing. Individual engineering apps may also use their own Python
models; picosolve is not the backend for every PicoLAB calculation.

## A small beam example

Run this in the GungOS device REPL or its custom desktop MicroPython interpreter.
It models a 2 m simply supported beam under a uniform downward load of 1,000 N/m.
The structural API uses SI units: m, N, N·m, Pa and m⁴. Indices start at zero.

```python
import picosolve as ps

b = ps.Beam(nodes=2, elements=1, sections=1, loads=1, cases=1)
try:
    b.section(0, 210e9, 8.333e-6)  # E [Pa], I [m^4]
    b.node(0, 0.0)
    b.node(1, 2.0)
    b.element(0, 0, 1)            # element 0 joins nodes 0 and 1
    b.line(0, 0, 0.0, 2.0, -1000.0)  # case, element, start/end, N/m
    b.support(0, ps.UY)           # restrain vertical movement
    b.support(1, ps.UY)           # rotations remain free
    b.solve()
    print(b.reaction(0))          # (1000.0, 0.0): force [N], moment [N*m]
    print(b.reaction(1))          # (1000.0, 0.0)
    print(b.at(0, 1.0))           # shear, moment, slope, deflection at midspan
    print(b.info())               # memory, precision and conditioning information
finally:
    b.free()
```

The midspan moment is approximately **500 N·m** and vertical deflection is
**−0.119 mm** for this example. Positive vertical force points upward;
the diagram moment convention is sagging positive. `ps.Frame` adds axial
movement/force for members in the x–y plane.

## Precision, memory and limits

- GungOS Python inputs and returned floats are float32. The beam/frame solver
  supports double factorization and single factorization with double-precision
  refinement; `AUTO` chooses a mode and can retry in double when required.
  `info()` reports the precision used. Formula evaluation uses float32 rules;
  circuit calculations combine double arithmetic with float32 device-model
  transcendental functions. Precision is not uniformly double throughout.
- Model storage is sized before solving. The core solve uses caller-owned
  memory blocks. Beam/frame solving exposes progress/cancellation and can run
  on the second core; circuits can advance in cooperative time slices. See the
  developer reference for the corresponding interfaces.
- Beam/frame models use linear, small-deformation Euler–Bernoulli theory.
  Shear-deformable beams, nonlinear structures and 3D frame analysis are outside
  this implementation. PicoSpice has a bounded set of device models; AC analysis
  is not implemented. Formula supports a restricted expression language, with
  rejection/fallback for unsupported cases.
- Host tests check analytical results, equilibrium, error handling and Python
  parity. Model size, latency and available heap still require device checks;
  a successfully solved model also depends on appropriate inputs and assumptions.

## Source and further reading

The [developer reference](../src/MicroPython/picosolve/README.md) covers the API,
solver algorithms, supported circuit devices, precision selection and memory.
Source lives under `src/MicroPython/picosolve/`, with MicroPython bindings in
`mp/`, structural/circuit models in `fe/`, and numerical routines in `core/`.

Run native checks with `sh src/MicroPython/picosolve/tests/run-tests.sh`, or
use `python3 tools/check-source.py --build` for the complete source checks.
See [BeamView](BeamLab.md), [PicoSpice](PicoSpice.md), [Grapher](Grapher.md) and
the [scientific calculator](ScientificCalculator.md) for their user interfaces.
