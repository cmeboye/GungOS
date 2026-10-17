#include "skyline.h"

void ps_sky_heights_init(uint32_t *ptr, int32_t n)
{
    for (int32_t j = 0; j < n; j++)
        ptr[j] = 1;
}

void ps_sky_heights_add(uint32_t *ptr, const int32_t *dofs, int count)
{
    int32_t low = -1;
    for (int a = 0; a < count; a++)
        if (dofs[a] >= 0 && (low < 0 || dofs[a] < low))
            low = dofs[a];
    if (low < 0)
        return;
    for (int a = 0; a < count; a++)
    {
        int32_t j = dofs[a];
        if (j >= 0 && (uint32_t)(j - low + 1) > ptr[j])
            ptr[j] = (uint32_t)(j - low + 1);
    }
}

uint32_t ps_sky_heights_finish(uint32_t *ptr, int32_t n)
{
    uint32_t total = 0;
    for (int32_t j = 0; j < n; j++)
    {
        uint32_t height = ptr[j];
        ptr[j] = total;
        total += height;
    }
    ptr[n] = total;
    return total;
}

void ps_sky_zero(ps_sky *s)
{
    for (uint32_t k = 0; k < s->ptr[s->n]; k++)
        s->val[k] = 0.0;
}

/* Offset such that val[offset(j) + i] is entry (i, j) for first(j) <= i <= j. */
static inline ptrdiff_t column_offset(const uint32_t *ptr, int32_t j)
{
    return (ptrdiff_t)ptr[j + 1] - 1 - j;
}

static inline int32_t column_first(const uint32_t *ptr, int32_t j)
{
    return j - (int32_t)(ptr[j + 1] - ptr[j]) + 1;
}

void ps_sky_add(ps_sky *s, const int32_t *dofs, int count, const double *block)
{
    for (int a = 0; a < count; a++)
    {
        int32_t i = dofs[a];
        if (i < 0)
            continue;
        for (int b = 0; b < count; b++)
        {
            int32_t j = dofs[b];
            if (j < i)
                continue; /* also skips negative DOFs */
            s->val[column_offset(s->ptr, j) + i] += block[a * count + b];
        }
    }
}

void ps_sky_add_diagonal(ps_sky *s, int32_t dof, double value)
{
    s->val[s->ptr[dof + 1] - 1] += value;
}

/*
 * Column-by-column (Crout) LDL^T, as in Bathe's COLSOL. For column j:
 *   g_ij = a_ij - sum_k l_ki g_kj    (i < j, k over the shared profile)
 *   l_ij = g_ij / d_i,  d_j = a_jj - sum_i l_ij g_ij
 * The inner loop is a dot product over two contiguous column segments.
 */
ps_status PS_HOT(ps_sky_factor)(ps_sky *s, ps_factor_info *info, ps_control *ctl)
{
    const uint32_t *ptr = s->ptr;
    double *val = s->val;
    info->min_ratio = 1.0;
    info->min_ratio_dof = -1;
    info->failed_dof = -1;
    if (ctl)
    {
        ctl->total = s->n;
        ctl->done = 0;
    }
    for (int32_t j = 0; j < s->n; j++)
    {
        if (ctl && ctl->cancel)
            return PS_CANCELLED;
        const ptrdiff_t oj = column_offset(ptr, j);
        const int32_t fj = column_first(ptr, j);
        for (int32_t i = fj + 1; i < j; i++)
        {
            const ptrdiff_t oi = column_offset(ptr, i);
            const int32_t fi = column_first(ptr, i);
            const double *li = val + oi;
            const double *gj = val + oj;
            double sum = 0.0;
            for (int32_t k = fi > fj ? fi : fj; k < i; k++)
                sum += li[k] * gj[k];
            val[oj + i] -= sum;
        }
        const double original = val[oj + j];
        double pivot = original;
        for (int32_t i = fj; i < j; i++)
        {
            const double g = val[oj + i];
            const double l = g / val[ptr[i + 1] - 1];
            val[oj + i] = l;
            pivot -= g * l;
        }
        val[oj + j] = pivot;
        /* Written so that NaN, zero and negative diagonals also fail. */
        if (!(original > 0.0) || !(pivot > PS_PIVOT_TOLERANCE * original))
        {
            info->failed_dof = j;
            return PS_ERR_MECHANISM;
        }
        const double ratio = pivot / original;
        if (ratio < info->min_ratio)
        {
            info->min_ratio = ratio;
            info->min_ratio_dof = j;
        }
        if (ctl)
            ctl->done = j + 1;
    }
    return PS_OK;
}

void PS_HOT(ps_sky_solve)(const ps_sky *s, double *b)
{
    const uint32_t *ptr = s->ptr;
    const double *val = s->val;
    /* L y = b, with column j of L^T holding l_kj for k < j. */
    for (int32_t j = 0; j < s->n; j++)
    {
        const ptrdiff_t oj = column_offset(ptr, j);
        double sum = 0.0;
        for (int32_t k = column_first(ptr, j); k < j; k++)
            sum += val[oj + k] * b[k];
        b[j] -= sum;
    }
    for (int32_t j = 0; j < s->n; j++)
        b[j] /= val[ptr[j + 1] - 1];
    /* L^T x = z, column by column from the end. */
    for (int32_t j = s->n - 1; j > 0; j--)
    {
        const ptrdiff_t oj = column_offset(ptr, j);
        const double xj = b[j];
        for (int32_t k = column_first(ptr, j); k < j; k++)
            b[k] -= val[oj + k] * xj;
    }
}
