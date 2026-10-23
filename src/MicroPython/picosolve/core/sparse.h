/*
 * General sparse LU with partial pivoting, for matrices that are neither
 * symmetric nor positive definite (circuits). P A Q = L U.
 *
 * The column order Q comes once from a minimum-degree ordering of the
 * pattern of A + A^T. Each factorization then works left-looking, a column
 * at a time (Gilbert-Peierls): a sparse triangular solve finds the column's
 * entries, and the pivot is the largest of the rows not yet used, unless the
 * diagonal is within tol of it, which keeps the fill the ordering planned.
 * The factorization repeats its pivot search every time, so a Newton
 * iteration that changes the values cannot leave it with a tiny pivot.
 *
 * A is given column by column (CSC) with 16-bit row indices. The kernel
 * never allocates: the caller sizes the block with ps_lu_bytes() for a fill
 * capacity, and enlarges it when ps_lu_factor() returns PS_ERR_SPACE.
 */
#ifndef PICOSOLVE_SPARSE_H
#define PICOSOLVE_SPARSE_H

#include "ps_base.h"

typedef int16_t ps_row; /* row or column index: at most 32767 unknowns */

typedef struct
{
    int32_t n, cap;          /* size, and room for entries of L and of U each */
    const int32_t *ap;       /* A's column starts, n + 1 */
    const ps_row *ai, *q;    /* A's row indices; column order q[k] = column */
    int32_t *lp, *up, *xi;   /* column starts (n + 1 each); xi: 2n work */
    ps_row *li, *ui, *pinv;  /* row indices; pinv[row] = pivot step or -1 */
    double *lx, *ux, *x;     /* values; x: n work */
    uint8_t *mark;           /* n work */
    int32_t lnz, unz;        /* entries in the last factorization */
} ps_lu;

/* Minimum-degree column order of the n x n pattern (ap, ai), symmetrized.
 * scratch holds ps_order_scratch_bytes(n). */
size_t ps_order_scratch_bytes(int32_t n);
void ps_order_md(int32_t n, const int32_t *ap, const ps_row *ai, ps_row *q, uint32_t *scratch);

size_t ps_lu_bytes(int32_t n, int32_t cap);
void ps_lu_init(ps_lu *f, void *block, int32_t n, int32_t cap, const int32_t *ap, const ps_row *ai,
                const ps_row *q);

/* Factor A with values ax. PS_ERR_SINGULAR names the column (unknown) with
 * no usable pivot in *bad; PS_ERR_SPACE means cap is too small. */
ps_status ps_lu_factor(ps_lu *f, const double *ax, double tol, int32_t *bad);
/* Solve A x = b in place; work holds n values. */
void ps_lu_solve(const ps_lu *f, double *b, double *work);

#endif
