/*
 * Symmetric skyline (variable band) storage with an LDL^T factorization, in
 * double or single precision.
 *
 * Column j holds rows first(j)..j, ending with the diagonal:
 *   val[ptr[j] .. ptr[j+1]-1]
 * Only the profile of the upper triangle is stored, so memory follows the
 * band of the model rather than the square of its size.
 *
 * Single precision halves the memory and uses the M33's hardware floating
 * point unit; the model recovers full accuracy by iterative refinement with
 * double-precision residuals. A single-precision factorization that meets a
 * tiny pivot returns PS_ERR_ACCURACY rather than deciding the structure is
 * a mechanism: only the double-precision factorization decides that.
 */
#ifndef PICOSOLVE_SKYLINE_H
#define PICOSOLVE_SKYLINE_H

#include "ps_base.h"

/* A pivot below this fraction of its original diagonal means a mechanism. */
#define PS_PIVOT_TOLERANCE 1e-12
/* Below this fraction the model solves but its results lose many digits. */
#define PS_PIVOT_WARNING 1e-8
/* Single precision gives up (asks for double) below this fraction. */
#define PS_PIVOT_SINGLE 1e-5

typedef enum
{
    PS_DOUBLE = 0,
    PS_SINGLE = 1,
} ps_precision;

typedef struct
{
    int32_t n;
    uint32_t *ptr; /* n + 1 offsets */
    void *val;     /* ptr[n] values, double or float */
    ps_precision precision;
} ps_sky;

typedef struct
{
    double min_ratio;      /* smallest pivot / original diagonal */
    int32_t min_ratio_dof; /* where that happened */
    int32_t failed_dof;    /* DOF where factorization stopped, or -1 */
} ps_factor_info;

/* Profile building: ptr[0..n-1] hold column heights until finished. */
void ps_sky_heights_init(uint32_t *ptr, int32_t n);
void ps_sky_heights_add(uint32_t *ptr, const int32_t *dofs, int count);
uint32_t ps_sky_heights_finish(uint32_t *ptr, int32_t n);

size_t ps_sky_value_bytes(uint32_t profile, ps_precision precision);
void ps_sky_zero(ps_sky *s);
/* Add a count x count row-major symmetric block; negative DOFs are skipped. */
void ps_sky_add(ps_sky *s, const int32_t *dofs, int count, const double *block);
void ps_sky_add_diagonal(ps_sky *s, int32_t dof, double value);

/* Factor in place. ctl may be NULL. */
ps_status ps_sky_factor(ps_sky *s, ps_factor_info *info, ps_control *ctl);
/* Solve with a factored double-precision matrix, overwriting b with x. */
void ps_sky_solve(const ps_sky *s, double *b);
/* Solve with a factored single-precision matrix, overwriting b with x. */
void ps_sky_solve_single(const ps_sky *s, float *b);

#endif
