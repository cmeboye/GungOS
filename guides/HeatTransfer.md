# Heat transfer 2D

Open PicoLAB → Modules → Thermal → Heat transfer 2D. It solves conduction in a
rectangular plate of one material and shows the temperature field as colours,
with the inputs and results in the list below. The screen is built from the
same parts as Mohr circle and Shrink fit ([Screens and controls](UI.md)).

## What it solves

- **Steady state** or **transient** (M switches). Steady state solves by
  itself after every change; a transient waits for SPACE, so you can set the
  start temperature and end time first.
- The plate is cut into 16 to 40 cells along its long side. Each cell balances
  the heat from its four neighbours, the sides and its sources. Steady state
  uses preconditioned conjugate gradients; a transient uses explicit steps
  with a stable step chosen for you. Both run in small slices, so the keys stay
  responsive and SPACE or ESC pauses.
- Each of the four sides is **Insulated**, **Temperature**, **Convection**
  (ambient temperature and h) or **Heat flux** (W/m² into the plate).
- Heat sources: one value for the whole plate, and one rectangular **heat
  patch** (a chip, a heater). The patch keeps its total power at any grid.
- Results: lowest, highest and mean temperature, the hottest point, the heat
  entering through each side in W, the heat generated and, for steady state,
  the **imbalance**. It is the net heat as a share of the heat flowing, and
  should be near 0 %. In a transient the net heat is the **stored rate**.

## Assumptions

Two-dimensional conduction with uniform properties and no heat through the
front and back faces. Heat flows are per the plate's **depth** and positive
into the plate. Cell values are at cell centres; temperature and convection
sides act through half a cell. There is no radiation, and k does not change
with temperature.

## Keys

F9 lists them all. SPACE runs or pauses, R starts again, M switches steady and
transient, C switches smooth and banded colours, F3 loads an example and F6
moves a probe over the field (arrows; ESC returns). The edge lines show each
side's condition: amber fixed temperature, accent convection, white heat flux,
grey insulated.

## Checks

`simulator/test_thermal.py` compares the model with known answers: a slab's
linear profile and heat flow, the parabola with internal heating, a wall's
U-value with convection on both sides, symmetry, lumped cooling, the transient
reaching the steady state, and the energy balance of each. It also drives the
screen's keys.
