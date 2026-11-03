# Heat transfer 2D

Open PicoLAB → Modules → Thermal → Heat transfer 2D. It solves conduction in a
rectangular plate of one material and shows the temperature field as colours,
with the inputs and results in the list below. The screen is built from the
same parts as Mohr circle and Shrink fit ([Screens and controls](UI.md)).

## What it solves

- **Steady state** or **transient** (M switches, or Solve → Mode). Only
  **F6 Evaluate** solves; editing a value clears the field, and Z undoes
  (12 steps). A transient shows its field live while it runs; F7 pauses
  and resumes, ESC pauses.
- The plate is cut into 16 to 40 cells along its long side. Each cell balances
  the heat from its four neighbours, the sides and its sources. Steady state
  uses preconditioned conjugate gradients; a transient uses explicit steps
  with a stable step chosen for you. Both run in small slices, so the keys stay
  responsive.
- Each of the four sides is **Insulated**, **Temperature**, **Convection**
  (ambient temperature and h) or **Heat flux** (W/m² into the plate).
- Heat sources: one value for the whole plate (W/m³), and up to four
  rectangular **heat patches** (chips, heaters), each with its power in W.
  A patch keeps its power at any grid; one smaller than a cell heats the cell
  it sits in.

## Model page

The plate is drawn to scale with each side's condition written beside it and
the patches outlined. Below it, LEFT/RIGHT choose a tab:

| Tab | Values |
|---|---|
| Plate | Width, height, depth, material, k, density, specific heat |
| Sides | Condition of each side and its temperature, h or flux |
| Sources | Whole-plate heating; F1 adds a patch, F2 removes the selected one |
| Solve | Mode, end time and start temperature (transient), grid, cell size, diffusion time |

The side or patch being edited is highlighted on the plate. ENTER edits a
value or opens a choice; [ and ] cycle a choice in place. After F6 the plate
shows the temperature field with its colour range and the hottest point.

## Plots (F4)

- **Field**: the temperature map with a cursor; arrows move it a cell, the
  readout gives T and the heat flux |q| and its direction.
- **Profiles**: temperature along the cursor's row and column.
- **History** (transient): lowest, mean and highest temperature over time.

D changes the view, P visits the hottest and coldest points and the pinned
points, ENTER pins the cursor (up to 8).

## Results (F5)

Status, highest and lowest temperature with their positions (ENTER shows the
point in the plots), the mean, the heat entering through each side in W with
its mean flux, the heat generated, and the **balance** for a steady state:
the net heat as a share of the heat flowing, near 0 %. A transient gives the
**stored rate** and the Fourier number. A convection side adds the Biot
number. Pinned points list T and the flux components; F2 unpins one.

## Options and files (F3)

Examples, a new plate, Save and Open (`picoware/engineering/cases/`), and CSV
exports to `picoware/engineering/exports/`: the whole field (x, y, T, qx, qy),
the cursor's row and column profiles and a transient's history. The profile
and history files fit Eggcel's 512-cell limit.

## Assumptions

Two-dimensional conduction with uniform properties and no heat through the
front and back faces. Heat flows are per the plate's **depth** and positive
into the plate. Cell values are at cell centres; temperature and convection
sides act through half a cell. There is no radiation, and k does not change
with temperature.

## Keys

F9 lists them all. The edge lines show each side's condition: amber fixed
temperature, accent convection, white heat flux, grey dashes insulated.

## Checks

`simulator/test_thermal.py` compares the model with known answers: a slab's
linear profile, heat flow and flux, the parabola with internal heating, a
wall's U-value with convection on both sides, symmetry, lumped cooling, the
transient reaching the steady state, and the energy balance of each. It checks
patches, the transient history and saved cases, and drives every page's keys,
the examples, saving, opening and the exports.

## Code

- `engtools/thermal/model.py`: plate, solvers, results, saved cases.
- `engtools/thermal/items.py`: tabs, rows and the rules for each value.
- `engtools/thermal/render.py`: plate, field, colour bar and line plots.
- `engtools/thermal/app.py`: pages and keys.

After calculating, Tab focuses the input page’s temperature probe; arrows move
the probe, Enter pins it, and P visits extrema. Tab or Esc returns to the same
input tab and row. Space does not run or pause the solver. F6 starts a fresh
solve; F7 pauses or resumes it. The full-page plots already have probe focus.
