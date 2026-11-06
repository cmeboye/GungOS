# picosolve

picosolve is the built-in C solver module used by selected PicoLAB tools.
Python describes a model or expression and reads back the results. It provides
beam/frame solving, circuit analysis, formula evaluation and plot geometry.
Precision depends on the component; see [Precision](#precision) and [Circuits](#circuits).

Start with the [brief picosolve guide](../../../guides/PicoSolve.md) for an
overview and a runnable beam example. This page is the detailed developer reference.

It is a solver, not a matrix library. Models go in and results come out:
displacements, reactions, end forces and the internal-force and deflection
curves. Stiffness matrices are never exposed.

## Decisions

| Topic | Decision |
|---|---|
| Where it lives | Built into the firmware. It is generic infrastructure, not app logic. |
| First suite | Structural, starting with beams. |
| Beam theory | Euler–Bernoulli. Timoshenko may follow. |
| Units | SI everywhere: m, N, N·m, Pa, m⁴, N/m. The kernel does no unit conversion. |
| Precision | Structural inputs are float32. Derived element calculations, residuals and stored displacements use double; factorization can use double or single with refinement, as described below. Results returned as MicroPython floats are float32. Formula and circuit precision are described in their own sections. |
| Size limits | Not fixed. Before allocating, `prepare` reports the memory this model needs, so the hardware decides. |

## Layout

```
core/   pure C, no MicroPython headers
  ps_base.h     status codes, the shared progress/cancel block, PS_HOT
  skyline.*     symmetric skyline storage, LDLᵀ factorization and solve, in
                double or single precision from one template (skyline_real.h)
  dofmap.*      equation numbering for any element type: DOF marks, node
                reordering, skyline profile
  order.*       reverse Cuthill–McKee node ordering
  dense.*       hinge condensation and recovery on element systems
  sparse.*      general sparse LU with partial pivoting (left-looking,
                Gilbert–Peierls) and a minimum-degree column order
fe/     element library and models
  beam.*        Euler–Bernoulli element: stiffness, consistent loads, exact sections
  model.*       beam model: build, prepare, solve, results
  circuit.*     circuit model: modified nodal analysis, devices, operating
                point, DC sweep and transient
geom/   geometry for plots and contour views
  mesh.*        triangles from sampled surfaces and implicit isosurfaces
                (marching tetrahedra)
  contour.*     contour segments of a sampled 2-D field (marching squares)
expr/   formulas
  formula.*     compiles a Python arithmetic expression once, evaluates it at
                many points; results bit-identical to MicroPython's eval
mp/     the MicroPython binding (the only part with MicroPython headers)
tests/  host tests (tests/run-tests.sh)
```

The firmware builds it through `micropython.cmake` (kernel at `-O2`); the
simulator compiles the same sources (`Desktop/modules/picosolve`).

## From Python

```python
import picosolve as ps
b = ps.Beam(nodes=5, elements=4, sections=1, loads=8, cases=1)
b.section(0, 210e9, 8.36e-5)                 # E (Pa), I (m^4)
for i in range(5):
    b.node(i, 1.5 * i)                       # x (m)
for e in range(4):
    b.element(e, e, e + 1)                   # section=0, releases=0
    b.line(0, e, 0.0, 1.5, -5e3)             # case, element, a, b, w1 (N/m)
b.support(0, ps.UY)
b.support(4, ps.UY)
b.solve()                                    # ps.AUTO, ps.DOUBLE or ps.SINGLE
b.reaction(0)                                # (fy, mz) in N, N·m
b.at(1, 0.75)                                # (shear, moment, slope, deflection)
b.diagram(1, 64, None, moments, None, None)  # fill array('f') buffers
```

Plane frames use the same methods on `ps.Frame`, with three DOFs per node
(`ps.UX`, `ps.UY`, `ps.RZ`), nodes anywhere in the plane and an area for
axial stiffness:

```python
f = ps.Frame(nodes=4, elements=3, loads=4)
f.section(0, 210e9, 8.36e-5, 5.38e-3)        # E, I, A
f.node(0, 0, 0); f.node(1, 0, 4); f.node(2, 6, 4); f.node(3, 6, 0)
f.element(0, 0, 1); f.element(1, 1, 2); f.element(2, 3, 2)
f.support(0, ps.UX | ps.UY | ps.RZ); f.support(3, ps.UX | ps.UY | ps.RZ)
f.line(0, 1, 0.0, 6.0, -10e3)                # element loads in local axes
f.axial_line(0, 0, 0.0, 4.0, -1e3)           # along the element: axial_point too
f.solve()
f.reaction(0)                                # (fx, fy, mz)
f.at(1, 3.0)                                 # (+ normal force, axial displacement)
f.axial_diagram(1, 64, normal, axial)
```

A frame element's local x runs from its first node to its second, local y
90 degrees counterclockwise from it. Normal force is tension positive.

Other loads: `point(case, e, a, P)`, `moment(case, e, a, M)`,
`node_load(case, node, ps.UY or ps.RZ, value)`, `settle(case, node, flag,
delta)`. Hinges: `element(e, a, b, section, ps.RELEASE_START | ps.RELEASE_END)`.
Springs: `spring(node, flag, k)`. Problems raise `picosolve.SolveError`
naming the node, element, load or section at fault.

To keep the interface responsive, solve on the second core:

```python
b.begin()                                    # checks and allocates here
_thread.start_new_thread(b.compute, ())      # touches no Python objects
while b.busy(): show(b.progress())           # (done, total); b.cancel()
while not b.finish():                        # False: retrying in double
    _thread.start_new_thread(b.compute, ())
```

Geometry for plots (the caller samples the formula; C builds the shapes):
`grid_strip(row0, row1, xs, y0, y1, out)` triangulates a strip of a z(x, y)
surface; `iso_slab(prev, cur, coords, z0, z1, triangles, centres, limits,
cube)` runs marching tetrahedra between two sampled planes and returns each
triangle's centre for an optional pole check; `contour_queries` and
`contour_segments` trace f = 0 across a row of cells, with or without that
check. Graph3D and Graph use them and match their earlier Python output
exactly; they are also the basis for isotherm and contour plots.

Formulas: `Formula(text, variables, constants=None, derived=None, limit=None)`
compiles a Python arithmetic expression (numbers, `+ - * / // % **`, the math
functions the plot tools offer, `min`, `max`, `abs`, `round`, `int`, `float`,
`pow`) once. `f(x, y)` evaluates one point and returns a float, or None where
Python would raise or the result is not finite or exceeds `limit`.
`f.map(out, xs, 0.5)` fills `out` from `array('f')` inputs or numbers and
returns how many results were kept (NaN marks the rest); `f.points(out, xyz,
n)` takes n interleaved points. `derived={'r': 'sqrt(x*x+y*y+z*z)'}` defines a
name by another expression. Results match MicroPython's own evaluation bit for
bit; a formula that cannot be matched exactly (for example `abs()` of a power
that may be complex) raises ValueError, and the caller keeps using `eval`.
Python's whole numbers are exact at any size, float32 only up to 2^24: points
whose whole-number arithmetic leaves that range are evaluated by
`fallback=fn` (the caller's `eval`), or are undefined without one, never
wrong. The one remaining difference, in rare min/max mixes of whole and
fractional numbers, is the sign of a zero result (see `expr/formula.h`).

`b.free()` releases the model's memory at once; any later use of the model
raises ValueError. A MemoryError while solving leaves the model consistent:
edit it or solve again.

`b.info()` reports equations, stored values, the precision used, refinement
steps, the smallest pivot ratio and memory; `b.free()` releases the memory.

## Precision

`ps.AUTO` factors in single precision when the average skyline column is at
least 16 values high, and in double otherwise. Single precision halves the
matrix and uses the M33's hardware floating point; iterative refinement with
double-precision residuals (computed element by element) recovers full
accuracy, typically in 4 steps. For narrow bands such as beams the extra
refinement vectors outweigh the halved matrix, so double is used. If
refinement converges too slowly (a badly conditioned model) the solve is
repeated in double automatically. Only the double-precision factorization
decides that a structure is a mechanism. The threshold is to be calibrated
with the device benchmark.

## Memory

The kernel never allocates. A model uses blocks owned by the caller, each
sized before it is needed:

| Block | Sized by | Holds |
|---|---|---|
| model | `ps_model_bytes(nodes, elements, sections, loads)` | the model description (float32 inputs) |
| index | `ps_model_index_bytes()` | equation numbering, skyline column pointers, lookups for results |
| scratch | `ps_model_scratch_bytes()` | node graph and ordering work space, needed only during `prepare` |
| values | `ps_model_value_bytes()`, after `prepare` | skyline values and one solution per load case |

The binding frees the scratch block as soon as `prepare` returns, before the
values block is allocated. A 600-element continuous beam (1,051 equations)
needs 91 KB: about 29 KB model, 27 KB index and 35 KB values.

The binding will allocate these blocks on the MicroPython heap and attach them
to the model object, so the garbage collector frees them with the model.
Because the values block is sized after `prepare`, the app can compare it with
free memory and refuse cleanly before anything large is allocated.

## Solving on the second core

`ps_model_solve` touches only its three blocks: it reads no Python objects and
allocates nothing. That makes it safe to run on core 1 while core 0 keeps the
UI responsive. The two cores share a `ps_control` struct: core 0 sets `cancel`
and reads `done`/`total` for a progress bar. Errors are returned as status
codes, and the binding raises them as Python exceptions on core 0.

## Algorithm

1. `prepare` checks the model and turns mistakes into a status code that names
   the node, element, load or section at fault. It then:
   - marks restrained DOFs;
   - drops the rotation of any node where every attached element end is a
     hinge, since that rotation has no stiffness and no meaning (its result
     reads NaN);
   - renumbers nodes with reverse Cuthill–McKee and keeps whichever numbering,
     the user's or the renumbered one, gives the smaller profile.
2. `solve` assembles element stiffness matrices into skyline storage. Hinges
   are condensed out at element level first. Springs go on the diagonal, and
   element loads become consistent nodal loads. Support settlement moves to
   the right-hand side.
3. The LDLᵀ factorization runs column by column (Crout, as in Bathe's
   COLSOL). Its inner loop is a dot product over contiguous memory. Each
   pivot is compared with its original diagonal:
   - a ratio below 1e-12 is reported as a mechanism, at the node and DOF
     where it occurred;
   - the smallest ratio is kept in `info.min_ratio`, for a warning that the
     model is badly conditioned.
4. Every load case is solved against the same factorization, so extra cases
   cost only two triangular solves each. Later, influence lines will use the
   same mechanism.
5. Results are computed on demand from the stored displacements, using lookups
   built once at prepare (loads by element and by node, element ends by node):
   - hinge rotations are recovered from element equilibrium;
   - end forces = k·u − f (in double precision);
   - reactions come from node equilibrium.

## Conventions

- Axes: x to the right, y up, rotations counterclockwise positive. Loads in −y
  point down.
- Element loads are positioned from the element's start node. Elements must
  run left to right.
- End forces are the forces the nodes apply to the element: `fy1, m1, fy2, m2`.
- Diagram values follow the usual textbook convention:
  - shear V is the sum of upward forces to the left of the cut, so dM/dx = V;
  - sagging moment is positive, so EI·y″ = M.
- A reaction is the force the support applies to the node. On a spring it is
  the spring force, −k·u.
- Sections are exact: shear, moment, slope and deflection at any point come
  from Macaulay terms of the element's loads, not from interpolation.

## Loads

| Kind | Target | Values |
|---|---|---|
| `PS_LOAD_NODE` | node DOF | force or moment `w1` |
| `PS_LOAD_SETTLE` | restrained node DOF | prescribed displacement `w1` |
| `PS_LOAD_POINT` | element | force `w1` at `a` |
| `PS_LOAD_MOMENT` | element | counterclockwise moment `w1` at `a` |
| `PS_LOAD_LINE` | element | `w1` at `a` varying linearly to `w2` at `b`; covers uniform, triangular and partial loads |

Each load belongs to a load case (up to 255 per model).

## Circuits

`ps.Circuit` simulates a circuit by modified nodal analysis, for PicoSpice.
Node 0 is ground; elements connect nodes and are numbered from 0.

```python
C = ps.Circuit
c = C(nodes=4, elements=4, probes=2)          # values=: room for element values
c.element(0, C.V, (1, 0), (0,))               # + - , dc value
c.wave(0, C.PULSE, (0, 5, 0, 1e-9, 1e-9, 1e-3, 2e-3))   # or SIN, PWL
c.element(1, C.R, (1, 2), (1e3,))
c.element(2, C.C, (2, 0), (1e-6, 0))          # C, initial voltage (uic)
c.element(3, C.D, (2, 3), (1e-14, 1))         # Is, N
c.probe(0, C.VOLTAGE, 2)                      # V(2) - V(0)
c.probe(1, C.CURRENT, 3, 0)                   # into element 3 at terminal 0
c.op(); c.voltage(2); c.current(1, 0)         # operating point
c.tran(5e-3, 501)                             # or c.dc(source, start, stop, points)
while not c.run(30): show(c.progress())       # 30 ms slices; True when done
c.trace(0, out)                               # array('f') of the samples so far
```

| Kind | Terminals | Values |
|---|---|---|
| R, C, L | a b | R; C, v0; L, i0 |
| V, I | + − | dc value; waveform by `wave()` |
| D | anode cathode | Is, N |
| NPN, PNP | c b e | Is, BF, BR, VAF (0: none) |
| NMOS, PMOS | d g s (body on s) | VTO, KP, LAMBDA |
| E, G | + − c+ c− | gain; gm |
| F, H | + − (`ctrl=` element with a branch) | gain; r |
| OPAMP | in+ in− out | A (0: ideal) |
| SW | + − c+ c− | Ron, Roff, Vt, Vh (smooth over Vt ± Vh) |

Waveforms: `PULSE` (v1 v2 td tr tf pw per), `SIN` (vo va freq td theta
phase), `PWL` (t0 v0 t1 v1 ...). Currents are positive into the element at
the terminal asked for, so a source that supplies reads negative, as in
SPICE. Problems raise `SolveError` naming the node or element (also
`c.error()`).

How it solves:

- Each element stamps into a pattern fixed when the circuit is prepared;
  ground entries go to one spare slot, so stamping has no branches.
- The LU orders columns once by minimum degree and pivots on every
  factorization, keeping the diagonal when it is within 1000× of the best.
- Newton iterations follow SPICE: junction and MOSFET voltage limiting, and
  convergence when node voltages (reltol 1e-3, 1 µV) and every device current
  against its linearization have settled. An operating point that fails
  tries gmin stepping, then source stepping.
- Transients use the trapezoidal rule, with backward Euler for the step after
  each source corner (breakpoint). The step size follows the truncation error
  of capacitor voltages and inductor currents; a failed step is repeated
  smaller. Outputs land exactly on the requested times.
- Device models (diode, Ebers–Moll with Early effect, Shichman–Hodges level 1)
  use the firmware's float32 `expf`, `logf` and `sinf`: about seven digits,
  and no double transcendental functions in flash. Everything else is double.

Memory: the model block (28 bytes per element plus 4 per value), then on the
first analysis the pattern and order, the vectors and device states, the LU
(grown by half whenever it asks) and the output (points × probes floats). A
50-node, 83-element transient with 4 probes of 401 points uses 19.9 KB, 6.4 KB
of it the output. Nothing is allocated while stepping.

## Tests

`tests/run-tests.sh` builds the kernel with strict warnings and runs it on the
host. The tests compare against closed-form results:

- simply supported, cantilever, fixed–fixed, propped cantilever and two-span
  continuous beams;
- an internal hinge, released on one side or on both;
- support settlement, spring supports;
- triangular, partial trapezoidal, point and moment loads;
- superposition of load cases;
- scrambled node numbering (checks reordering);
- every error path;
- frames: a horizontal frame member against the beam, an inclined
  cantilever (bending and axial), axial point and line loads, portal frame
  equilibrium, invariance when the whole frame is rotated, hinged knees,
  and the frame-only errors.

The solver is also checked against dense arithmetic, and condensation and
reordering are tested on their own.

Every solved model must also satisfy two invariants:

- equilibrium of the whole beam;
- each element's exact deflection curve and slope meet the solved node
  values at its far end.

The circuit tests (`tests/test_circuit.c`) check the LU against dense
elimination with partial pivoting on matrices with zero diagonals, and
circuits against closed forms: dividers, every controlled source, ideal and
finite-gain op-amps, a diode by bisection (also swept), BJT and MOSFET bias in
both polarities and both MOSFET regions, a switch, RC, RL and LC transients,
a filtered sine, a half-wave rectifier, a CMOS inverter, a 50-node ladder that
must grow its LU block, running in slices and cancelling, and every error
path. `simulator/test_picosolve_circuit.py` drives the same through Python.

The tests are also run under AddressSanitizer and UBSan.

## Next

1. Calibrate the AUTO precision threshold with the device benchmark.
2. ~~The beam suite in picoLAB~~: done as Beam Lab
   ([guide](../../../guides/BeamLab.md)). Envelopes over combinations next.
3. ~~2-D frames on the same DOF map~~: done (`ps.Frame`). Trusses (pinned
   members, axial only) and inclined supports next.
4. Formulas as solver inputs: load functions w(x) and other user-written
   data for the suites, through `Formula`.
5. ~~Sparse LU with pivoting for circuits~~: done (`ps.Circuit`: operating
   point, DC sweep, transient). AC analysis (complex LU) next.
6. Later solvers: matrix-free preconditioned CG (2-D thermal grids) and
   eigen drivers.
