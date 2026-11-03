# PicoSpice

Open **PicoLAB → Modules → Electrical → PicoSpice**. Draw a circuit as nodes
on a grid with elements between them, place probes, and simulate an
operating point, a DC sweep or a transient. The solver is the firmware's
`picosolve.Circuit` (see the [picosolve README](../src/MicroPython/picosolve/README.md#circuits)).
It works like [Beam view](BeamLab.md): only **F6** simulates, and editing
clears the results.

The first screen offers a blank circuit, eight examples and saved circuits.

## Layout and keys

The schematic fills the top; below it are the **Node**, **Element**,
**Probe** and **Sim** tabs. In a tab, Up/Down choose an item, Enter opens it
and lists its values, Esc closes it again.

| Key | Action |
|---|---|
| Left/Right | Change tab |
| Up/Down | Choose an item or a value |
| Enter | Open an item, edit a value, or choose (with a live preview) |
| [ / ] | Cycle the highlighted choice; otherwise the items |
| TAB | Grid cursor: arrows move it, Enter selects what is there, TAB or Esc returns |
| F1 | Add: a node at the cursor (Node tab, or with the cursor), an element, a probe |
| F2 | Remove the selected item |
| + / - | Zoom: grid pitch 8, 12, 16 and 24 pixels |
| F3 | Options: new, examples, save, open, CSV export |
| F4 | Waveforms |
| F5 | Results |
| F6 | Simulate the analysis set in the Sim tab |
| Z | Undo (12 steps) |
| F9 | All the keys |

Values take SPICE suffixes: `4.7k`, `10u`, `100n`, `2meg`; `m` is milli as in
SPICE. Arithmetic works too: `2*pi*50`.

## Building a circuit

1. **Nodes.** TAB to the grid cursor, move it with the arrows and press F1 to
   place a node. Nodes sit on whole-number grid points, at most one per
   point, up to 50.
2. **Ground.** In the Node tab open a node and set **Ground: Yes**. Every
   grounded node is the same ground, so a ground symbol can go wherever it
   is convenient.
3. **Elements.** Select a node (in the Node tab or with the cursor), change to
   the Element tab and press F1. A new element starts at that node and takes
   the nearest nodes for its other pins; open it and change **Pin** choices with
   [ ] or Enter while the schematic follows. A two-pin element is drawn at the
   middle of its nodes with leads to them; transistors, the op-amp and the
   four-pin elements are drawn at the centre of their nodes.
4. **Wires.** A Wire joins two nodes into one net. Use wires for rails, for
   corners, and to put elements in parallel without drawing them on top of
   each other.
5. **Probes.** In the Probe tab, F1 adds a **voltage** probe (a node against
   ground, or against a minus node) or a **current** probe: at a node, the
   current flowing from it into one chosen element. Up to 8 probes, each
   with its own colour on the schematic and in the waveforms.

## Elements

| Element | Pins | Values |
|---|---|---|
| Wire | A B | none |
| Resistor | A B | resistance |
| Capacitor | + − | capacitance; start voltage (used when starting from zero) |
| Inductor | A B | inductance; start current (likewise) |
| Voltage source | + − | DC value; waveform |
| Current source | + − | DC value, flowing from + to − through it; waveform |
| Diode | anode, cathode | Is, N |
| NPN, PNP transistor | C B E | Is, beta forward and reverse, Early voltage (0: none) |
| N-, P-channel MOSFET | D G S (body on S) | threshold (negative for PMOS), KP × W/L, lambda |
| Voltage- or current-controlled sources (E, G) | + − c+ c− | gain; gm |
| Current-controlled sources (F, H) | + − | gain, and the element whose current controls it: a V, L, E, H or op-amp |
| Op-amp | in+ in− out | open-loop gain; 0 is ideal. The output is not limited by supply rails. |
| Voltage switch | A B c+ c− | R on, R off, threshold, half transition (smooth in between) |

Sources take a waveform: **DC**, **PULSE** (initial, pulsed, delay, rise,
fall, width, period), **SIN** (offset, amplitude, frequency, delay, damping,
phase) or **PWL** points typed as `0 0, 1m 5, 2m 5`. The operating point and
the DC sweep use the value at t = 0.

## Simulating

The **Sim** tab chooses the analysis:

- **Operating point**: node voltages appear next to the nodes (from the
  third zoom, or for the selected node) and F5 lists every node, every
  element's current, voltage and power, and the probes.
- **DC sweep** of one V or I source from start to stop in a number of points.
- **Transient** to a stop time with a number of output points (up to 2001),
  an optional maximum step, and a start from the operating point or from
  zero (capacitor and inductor start values).

F6 runs it in slices, so the keys stay live; Esc stops a running simulation
and keeps what it has. A problem names the node or element at fault and
selects it, for example *N5 has no DC path to ground* or *V2: its voltage is
set twice*.

## Waveforms (F4)

Voltage and current probes get a pane each, scaled to their range. Left/Right
move the cursor, `,` and `.` move ten steps, Up/Down choose the probe whose
value the header shows, P jumps to its maximum and minimum.

## Results (F5)

For each probe of a sweep or transient: final value, maximum and minimum
(with the time or sweep value where they occur; Enter shows them in the
waveforms), average, RMS and peak to peak. Then the solver: equations,
entries, memory, Newton iterations and time steps.

## Signs and units

- Currents are positive into an element at the pin named; a source that
  supplies power reads negative, as in SPICE. Power is positive when absorbed.
- Units are SI with engineering prefixes: V, A, W, ohm, F, H, s.

## Files

- **Save** writes `picoware/engineering/cases/<name>.json`; **Open** lists the
  saved cases and loads a circuit without simulating.
- **Export CSV** writes the probe samples of the last sweep or transient to
  `picoware/engineering/exports/`. Runs of at most 511 cells are named
  `-eggcel-` and open in Eggcel; longer ones are `-full-`.

## Limits

50 nodes, 80 elements, 8 probes, 2001 points. The models are first-order:
no junction capacitances, no op-amp rails, no temperature. AC analysis is
planned.

## Code

- `engtools/spice/model.py`: elements, circuit, nets, checks, simulation, statistics, cases, examples.
- `engtools/spice/items.py`: tabs, fields and the rules for each value.
- `engtools/spice/symbols.py`: the 5 × 5 and 7 × 7 symbols and their pins.
- `engtools/spice/render.py`: schematic and waveforms.
- `engtools/spice/app.py`: pages and keys.

Tests: `simulator/test_picospice.py` (values, nets, every example against hand
results, statistics, saved cases, removal, named problems, and a circuit built
and simulated by keys through every page), `simulator/test_picosolve_circuit.py`
and `src/MicroPython/picosolve/tests/test_circuit.c` for the solver.
