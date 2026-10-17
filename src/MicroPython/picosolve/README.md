# picosolve

picosolve is the small built-in solver kernel behind the picoLAB engineering
suites. Python describes a model and reads back results. All the arithmetic
in between runs here, in C and in double precision.

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
| Precision | Python inputs are float32 (MicroPython's float), which is ample for material and geometry data. Everything derived from them is double: element matrices, assembly, factorization, displacements, reactions, end forces and diagrams. |
| Size limits | Not fixed. Before allocating, `prepare` reports the memory this model needs, so the hardware decides. |

## Layout

```
core/   pure C, no MicroPython headers
  ps_base.h     status codes, the shared progress/cancel block, PS_HOT
  skyline.*     symmetric skyline storage, LDLᵀ factorization, solve
  order.*       reverse Cuthill–McKee node ordering
  dense.*       hinge condensation and recovery on element systems
fe/     element library and models
  beam.*        Euler–Bernoulli element: stiffness, consistent loads, exact sections
  model.*       beam model: build, prepare, solve, results
tests/  host tests (tests/run-tests.sh)
```

The MicroPython binding (`mp/`) and its build files come next. It is the
only part that will include MicroPython headers.

## Memory

The kernel never allocates. A model uses three blocks owned by the caller,
each sized before it is needed:

| Block | Sized by | Holds |
|---|---|---|
| model | `ps_model_bytes(nodes, elements, sections, loads)` | the model description |
| index | `ps_model_index_bytes()` | equation numbering, profile, ordering scratch |
| values | `ps_model_value_bytes()`, after `prepare` | skyline values and one solution per load case |

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
5. Results are computed on demand from the stored displacements:
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
- every error path.

The solver is also checked against dense arithmetic, and condensation and
reordering are tested on their own.

Every solved model must also satisfy two invariants:

- equilibrium of the whole beam;
- each element's exact deflection curve and slope meet the solved node
  values at its far end.

The tests are also run under AddressSanitizer and UBSan.

## Next

0. Refactor before the binding, while only beams exist (the host tests
   guard it):
   - extract a generic DOF map (numbering, profile, ordering) and an element
     function table from `fe/model.c`, so frames, trusses, thermal links and
     circuit stamps can plug in;
   - put the solvers behind one interface, with the stored precision as a
     parameter;
   - add float32 skyline storage with double-precision iterative refinement
     (residual computed element by element). The M33 FPU is single precision
     only, so this should be faster and halve memory. Fall back to double
     storage when refinement stalls;
   - add a results cache built once after the solve: end forces per element
     and case, loads indexed by element, elements indexed by node, and
     whole-buffer diagram sampling. Today's on-demand queries are O(n²) over
     a full model;
   - later solvers: banded/dense LU with pivoting, real and complex (circuits);
     matrix-free preconditioned CG (2-D thermal grids); time-stepping, Newton
     and eigen drivers.
1. `mp/` binding: a `picosolve.Beam` object, the three blocks on the heap, a
   blocking `solve()` plus `start()` on core 1 with progress and cancel,
   status codes mapped to messages that name the node or element. Build it
   into the firmware with `-O2` for these files, as the rp2 port already does
   for its float libraries, and into the desktop simulator from the same
   source.
2. A benchmark on the device.
3. The beam suite in picoLAB: model editor, diagrams, max/min values,
   load cases.
