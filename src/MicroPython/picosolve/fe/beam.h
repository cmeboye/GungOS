/*
 * Euler-Bernoulli beam element along x.
 *
 * Element DOFs: v1, theta1, v2, theta2 (y up, rotation counterclockwise).
 * Element loads use positions measured from the element's first node.
 * Internal forces follow the usual textbook convention: shear V is the sum
 * of upward forces left of the cut (so dM/dx = V) and sagging moment is
 * positive (EI y'' = M).
 */
#ifndef PICOSOLVE_BEAM_H
#define PICOSOLVE_BEAM_H

#include "../core/ps_base.h"

#define PS_BEAM_DOF 4

typedef enum
{
    PS_BEAM_POINT,  /* force w1 at a */
    PS_BEAM_MOMENT, /* counterclockwise moment w1 at a */
    PS_BEAM_TRAP,   /* line load from w1 at a to w2 at b (N/m) */
} ps_beam_load_kind;

typedef struct
{
    uint8_t kind;
    double a, b, w1, w2;
} ps_beam_load;

/* Values at a section, before dividing the integrals by EI. */
typedef struct
{
    double shear, moment;
    double slope_ei, deflection_ei;
} ps_beam_section;

void ps_beam_stiffness(double ei, double length, double *k);
/* Add the consistent (fixed-end) nodal loads of one element load to f. */
void ps_beam_load_vector(double length, const ps_beam_load *load, double *f);

/* Start a section at x from the forces the first node applies (fy1, m1). */
void ps_beam_section_start(double fy1, double m1, double x, ps_beam_section *s);
/* Add one element load's effect on the section at x. */
void ps_beam_section_add(const ps_beam_load *load, double x, ps_beam_section *s);

#endif
