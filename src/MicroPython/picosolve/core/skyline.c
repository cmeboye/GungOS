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

/* Offset such that val[offset(j) + i] is entry (i, j) for first(j) <= i <= j. */
static inline ptrdiff_t column_offset(const uint32_t *ptr, int32_t j)
{
    return (ptrdiff_t)ptr[j + 1] - 1 - j;
}

static inline int32_t column_first(const uint32_t *ptr, int32_t j)
{
    return j - (int32_t)(ptr[j + 1] - ptr[j]) + 1;
}

#define REAL double
#define NAME(x) x##_double
#include "skyline_real.h"
#undef REAL
#undef NAME

#define REAL float
#define NAME(x) x##_single
#include "skyline_real.h"
#undef REAL
#undef NAME

size_t ps_sky_value_bytes(uint32_t profile, ps_precision precision)
{
    return (size_t)profile * (precision == PS_SINGLE ? sizeof(float) : sizeof(double));
}

void ps_sky_zero(ps_sky *s)
{
    if (s->precision == PS_SINGLE)
        zero_single(s);
    else
        zero_double(s);
}

void ps_sky_add(ps_sky *s, const int32_t *dofs, int count, const double *block)
{
    if (s->precision == PS_SINGLE)
        add_single(s, dofs, count, block);
    else
        add_double(s, dofs, count, block);
}

void ps_sky_add_diagonal(ps_sky *s, int32_t dof, double value)
{
    if (s->precision == PS_SINGLE)
        ((float *)s->val)[s->ptr[dof + 1] - 1] += (float)value;
    else
        ((double *)s->val)[s->ptr[dof + 1] - 1] += value;
}

ps_status ps_sky_factor(ps_sky *s, ps_factor_info *info, ps_control *ctl)
{
    if (s->precision == PS_SINGLE)
        return factor_single(s, info, ctl, PS_PIVOT_SINGLE, PS_ERR_ACCURACY);
    return factor_double(s, info, ctl, PS_PIVOT_TOLERANCE, PS_ERR_MECHANISM);
}

void ps_sky_solve(const ps_sky *s, double *b)
{
    solve_double(s, b);
}

void ps_sky_solve_single(const ps_sky *s, float *b)
{
    solve_single(s, b);
}
