#include "dense.h"

ps_status ps_condense(double *k, double *f, int m, uint32_t released)
{
    for (int b = 0; b < m; b++)
    {
        if (!(released & (1u << b)))
            continue;
        const double pivot = k[b * m + b];
        if (!(pivot > 0.0))
            return PS_ERR_MECHANISM;
        for (int i = 0; i < m; i++)
        {
            if (i == b)
                continue;
            const double factor = k[i * m + b] / pivot;
            if (factor == 0.0)
                continue;
            for (int j = 0; j < m; j++)
                if (j != b)
                    k[i * m + j] -= factor * k[b * m + j];
            if (f)
                f[i] -= factor * f[b];
        }
        for (int j = 0; j < m; j++)
        {
            k[b * m + j] = 0.0;
            k[j * m + b] = 0.0;
        }
        if (f)
            f[b] = 0.0;
    }
    return PS_OK;
}

ps_status ps_recover(const double *k, const double *f, int m, uint32_t released, double *u)
{
    int index[PS_MAX_ELEMENT_DOF];
    double a[PS_MAX_ELEMENT_DOF * PS_MAX_ELEMENT_DOF];
    double r[PS_MAX_ELEMENT_DOF];
    int count = 0;
    for (int b = 0; b < m; b++)
        if (released & (1u << b))
            index[count++] = b;
    if (count == 0)
        return PS_OK;
    for (int p = 0; p < count; p++)
    {
        const int b = index[p];
        r[p] = f ? f[b] : 0.0;
        for (int j = 0; j < m; j++)
            if (!(released & (1u << j)))
                r[p] -= k[b * m + j] * u[j];
        for (int q = 0; q < count; q++)
            a[p * count + q] = k[b * m + index[q]];
    }
    /* Gaussian elimination; the released block is symmetric positive definite. */
    for (int p = 0; p < count; p++)
    {
        const double pivot = a[p * count + p];
        if (!(pivot > 0.0))
            return PS_ERR_MECHANISM;
        for (int q = p + 1; q < count; q++)
        {
            const double factor = a[q * count + p] / pivot;
            for (int c = p; c < count; c++)
                a[q * count + c] -= factor * a[p * count + c];
            r[q] -= factor * r[p];
        }
    }
    for (int p = count - 1; p >= 0; p--)
    {
        double sum = r[p];
        for (int c = p + 1; c < count; c++)
            sum -= a[p * count + c] * r[c];
        r[p] = sum / a[p * count + p];
    }
    for (int p = 0; p < count; p++)
        u[index[p]] = r[p];
    return PS_OK;
}
