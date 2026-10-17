/*
 * Small dense element systems: condensing released DOFs (hinges) out of an
 * element and recovering them after the solve.
 */
#ifndef PICOSOLVE_DENSE_H
#define PICOSOLVE_DENSE_H

#include "ps_base.h"

#define PS_MAX_ELEMENT_DOF 6

/*
 * Eliminate the DOFs set in released from the m x m row-major symmetric k
 * and the load vector f (may be NULL), in place. Released rows and columns
 * are zeroed, so the element contributes nothing there.
 */
ps_status ps_condense(double *k, double *f, int m, uint32_t released);

/*
 * Fill the released entries of u from element equilibrium,
 * k_bb u_b = f_b - k_ba u_a, using the original (uncondensed) k and f.
 */
ps_status ps_recover(const double *k, const double *f, int m, uint32_t released, double *u);

#endif
