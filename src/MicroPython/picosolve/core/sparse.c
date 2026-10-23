#include "sparse.h"
#include <math.h>

/* A pivot this much smaller than its column's largest entry of A is zero. */
#define PS_LU_TINY 1e-13

static size_t align8(size_t n)
{
    return (n + 7u) & ~(size_t)7u;
}

static void *take(uint8_t **cursor, size_t bytes)
{
    void *p = *cursor;
    *cursor += align8(bytes);
    return p;
}

/* ------------------------------------------------------------------------ */
/* Minimum-degree ordering                                                  */
/* ------------------------------------------------------------------------ */

size_t ps_order_scratch_bytes(int32_t n)
{
    const size_t words = ((size_t)n + 31u) / 32u;
    return ((size_t)n + 1u) * words * sizeof(uint32_t);
}

/*
 * The elimination graph as one bit row per unknown, plus a row of unknowns
 * still to order. Eliminating v joins its neighbours into a clique; v is
 * the remaining unknown with the fewest neighbours. Circuits are small (a
 * few hundred unknowns at most), so plain bit rows beat a quotient graph in
 * both code and memory.
 */
void ps_order_md(int32_t n, const int32_t *ap, const ps_row *ai, ps_row *q, uint32_t *scratch)
{
    const int32_t w = (n + 31) / 32;
    uint32_t *alive = scratch + (size_t)n * (size_t)w;
    for (size_t i = 0; i < ((size_t)n + 1u) * (size_t)w; i++)
        scratch[i] = 0;
    for (int32_t j = 0; j < n; j++)
    {
        alive[j >> 5] |= 1u << (j & 31);
        for (int32_t p = ap[j]; p < ap[j + 1]; p++)
        {
            const int32_t i = ai[p];
            if (i == j)
                continue;
            scratch[(size_t)i * (size_t)w + (size_t)(j >> 5)] |= 1u << (j & 31);
            scratch[(size_t)j * (size_t)w + (size_t)(i >> 5)] |= 1u << (i & 31);
        }
    }
    for (int32_t k = 0; k < n; k++)
    {
        int32_t best = 0, degree = 0x7fffffff;
        for (int32_t v = 0; v < n; v++)
        {
            if (!((alive[v >> 5] >> (v & 31)) & 1u))
                continue;
            const uint32_t *row = scratch + (size_t)v * (size_t)w;
            int32_t d = 0;
            for (int32_t t = 0; t < w; t++)
                d += __builtin_popcount(row[t] & alive[t]);
            if (d < degree)
            {
                degree = d;
                best = v;
            }
        }
        q[k] = (ps_row)best;
        alive[best >> 5] &= ~(1u << (best & 31));
        const uint32_t *row = scratch + (size_t)best * (size_t)w;
        for (int32_t t = 0; t < w; t++)
        {
            uint32_t bits = row[t] & alive[t];
            while (bits)
            {
                const int32_t u = t * 32 + __builtin_ctz(bits);
                uint32_t *other = scratch + (size_t)u * (size_t)w;
                bits &= bits - 1u;
                for (int32_t s = 0; s < w; s++)
                    other[s] |= row[s];
                other[u >> 5] &= ~(1u << (u & 31));
            }
        }
    }
}

/* ------------------------------------------------------------------------ */
/* Factorization                                                            */
/* ------------------------------------------------------------------------ */

size_t ps_lu_bytes(int32_t n, int32_t cap)
{
    const size_t m = (size_t)n, c = (size_t)cap;
    return 2 * align8((m + 1) * sizeof(int32_t)) + align8(2 * m * sizeof(int32_t)) +
           2 * align8(c * sizeof(ps_row)) + align8(m * sizeof(ps_row)) +
           2 * align8(c * sizeof(double)) + align8(m * sizeof(double)) + align8(m);
}

void ps_lu_init(ps_lu *f, void *block, int32_t n, int32_t cap, const int32_t *ap, const ps_row *ai,
                const ps_row *q)
{
    uint8_t *cursor = block;
    const size_t m = (size_t)n, c = (size_t)cap;
    f->n = n;
    f->cap = cap;
    f->ap = ap;
    f->ai = ai;
    f->q = q;
    f->lp = take(&cursor, (m + 1) * sizeof(int32_t));
    f->up = take(&cursor, (m + 1) * sizeof(int32_t));
    f->xi = take(&cursor, 2 * m * sizeof(int32_t));
    f->li = take(&cursor, c * sizeof(ps_row));
    f->ui = take(&cursor, c * sizeof(ps_row));
    f->pinv = take(&cursor, m * sizeof(ps_row));
    f->lx = take(&cursor, c * sizeof(double));
    f->ux = take(&cursor, c * sizeof(double));
    f->x = take(&cursor, m * sizeof(double));
    f->mark = take(&cursor, m);
    f->lnz = f->unz = 0;
}

/* Depth-first search from row j through the finished columns of L, putting
 * the rows it reaches on xi[top-1], xi[top-2], ... in topological order.
 * xi[0..] doubles as the search stack and xi[n..] as each level's position. */
static int32_t reach(ps_lu *f, int32_t j, int32_t top)
{
    int32_t *stack = f->xi, *next = f->xi + f->n;
    int32_t head = 0;
    stack[0] = j;
    while (head >= 0)
    {
        j = stack[head];
        const int32_t col = f->pinv[j];
        if (!f->mark[j])
        {
            f->mark[j] = 1;
            next[head] = col < 0 ? 0 : f->lp[col];
        }
        int done = 1;
        const int32_t end = col < 0 ? 0 : f->lp[col + 1];
        for (int32_t p = next[head]; p < end; p++)
        {
            const int32_t i = f->li[p];
            if (f->mark[i])
                continue;
            next[head] = p;
            stack[++head] = i;
            done = 0;
            break;
        }
        if (done)
        {
            head--;
            stack[--top] = j;
        }
    }
    return top;
}

/* x = L \ A(:, col) on the rows the column reaches, xi[top..n-1]. */
static int32_t lower_solve(ps_lu *f, int32_t col, const double *ax)
{
    const int32_t n = f->n;
    int32_t top = n;
    for (int32_t p = f->ap[col]; p < f->ap[col + 1]; p++)
        if (!f->mark[f->ai[p]])
            top = reach(f, f->ai[p], top);
    for (int32_t p = top; p < n; p++)
        f->mark[f->xi[p]] = 0;
    for (int32_t p = f->ap[col]; p < f->ap[col + 1]; p++)
        f->x[f->ai[p]] = ax[p];
    for (int32_t px = top; px < n; px++)
    {
        const int32_t j = f->xi[px], k = f->pinv[j];
        if (k < 0)
            continue;
        const double xj = f->x[j];
        for (int32_t p = f->lp[k] + 1; p < f->lp[k + 1]; p++)
            f->x[f->li[p]] -= f->lx[p] * xj;
    }
    return top;
}

ps_status ps_lu_factor(ps_lu *f, const double *ax, double tol, int32_t *bad)
{
    const int32_t n = f->n;
    int32_t lnz = 0, unz = 0;
    for (int32_t i = 0; i < n; i++)
    {
        f->x[i] = 0.0;
        f->pinv[i] = -1;
        f->mark[i] = 0;
    }
    for (int32_t k = 0; k < n; k++)
    {
        const int32_t col = f->q[k];
        f->lp[k] = lnz;
        f->up[k] = unz;
        const int32_t top = lower_solve(f, col, ax);
        double big = 0.0, scale = 0.0;
        int32_t ipiv = -1, lower = 0;
        for (int32_t p = f->ap[col]; p < f->ap[col + 1]; p++)
            if (fabs(ax[p]) > scale)
                scale = fabs(ax[p]);
        for (int32_t p = top; p < n; p++)
        {
            const int32_t i = f->xi[p];
            if (f->pinv[i] >= 0)
                continue;
            lower++;
            if (fabs(f->x[i]) > big)
            {
                big = fabs(f->x[i]);
                ipiv = i;
            }
        }
        if (ipiv < 0 || !(big > PS_LU_TINY * scale))
        {
            *bad = col;
            return PS_ERR_SINGULAR;
        }
        if (lnz + lower > f->cap || unz + (n - top - lower) + 1 > f->cap)
            return PS_ERR_SPACE;
        if (f->pinv[col] < 0 && fabs(f->x[col]) >= tol * big)
            ipiv = col;
        const double pivot = f->x[ipiv];
        for (int32_t p = top; p < n; p++)
        {
            const int32_t i = f->xi[p];
            if (f->pinv[i] >= 0)
            {
                f->ui[unz] = f->pinv[i];
                f->ux[unz++] = f->x[i];
            }
        }
        f->ui[unz] = (ps_row)k;
        f->ux[unz++] = pivot;
        f->pinv[ipiv] = (ps_row)k;
        f->li[lnz] = (ps_row)ipiv;
        f->lx[lnz++] = 1.0;
        for (int32_t p = top; p < n; p++)
        {
            const int32_t i = f->xi[p];
            if (f->pinv[i] < 0)
            {
                f->li[lnz] = (ps_row)i;
                f->lx[lnz++] = f->x[i] / pivot;
            }
            f->x[i] = 0.0;
        }
    }
    f->lp[n] = lnz;
    f->up[n] = unz;
    for (int32_t p = 0; p < lnz; p++)
        f->li[p] = f->pinv[f->li[p]];
    f->lnz = lnz;
    f->unz = unz;
    return PS_OK;
}

void ps_lu_solve(const ps_lu *f, double *b, double *work)
{
    const int32_t n = f->n;
    for (int32_t i = 0; i < n; i++)
        work[f->pinv[i]] = b[i];
    for (int32_t j = 0; j < n; j++)
    {
        const double xj = work[j];
        for (int32_t p = f->lp[j] + 1; p < f->lp[j + 1]; p++)
            work[f->li[p]] -= f->lx[p] * xj;
    }
    for (int32_t j = n - 1; j >= 0; j--)
    {
        const int32_t last = f->up[j + 1] - 1;
        const double xj = work[j] /= f->ux[last];
        for (int32_t p = f->up[j]; p < last; p++)
            work[f->ui[p]] -= f->ux[p] * xj;
    }
    for (int32_t k = 0; k < n; k++)
        b[f->q[k]] = work[k];
}
