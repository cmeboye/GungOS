/*
 * Skyline kernels for one precision. Included twice by skyline.c with REAL
 * set to double and to float, and NAME(x) giving each copy its own names.
 */

static void NAME(zero)(ps_sky *s)
{
    REAL *val = s->val;
    for (uint32_t k = 0; k < s->ptr[s->n]; k++)
        val[k] = (REAL)0;
}

static void NAME(add)(ps_sky *s, const int32_t *dofs, int count, const double *block)
{
    REAL *val = s->val;
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
            val[column_offset(s->ptr, j) + i] += (REAL)block[a * count + b];
        }
    }
}

/*
 * Column-by-column (Crout) LDL^T, as in Bathe's COLSOL. For column j:
 *   g_ij = a_ij - sum_k l_ki g_kj    (i < j, k over the shared profile)
 *   l_ij = g_ij / d_i,  d_j = a_jj - sum_i l_ij g_ij
 * The inner loop is a dot product over two contiguous column segments.
 * A pivot below tolerance * original diagonal returns tiny.
 */
static ps_status PS_HOT(NAME(factor))(ps_sky *s, ps_factor_info *info, ps_control *ctl,
                                      double tolerance, ps_status tiny)
{
    const uint32_t *ptr = s->ptr;
    REAL *val = s->val;
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
            const REAL *li = val + oi;
            const REAL *gj = val + oj;
            REAL sum = (REAL)0;
            for (int32_t k = fi > fj ? fi : fj; k < i; k++)
                sum += li[k] * gj[k];
            val[oj + i] -= sum;
        }
        const REAL original = val[oj + j];
        REAL pivot = original;
        for (int32_t i = fj; i < j; i++)
        {
            const REAL g = val[oj + i];
            const REAL l = g / val[ptr[i + 1] - 1];
            val[oj + i] = l;
            pivot -= g * l;
        }
        val[oj + j] = pivot;
        /* Written so that NaN, zero and negative diagonals also fail. */
        if (!(original > (REAL)0) || !((double)pivot > tolerance * (double)original))
        {
            info->failed_dof = j;
            return tiny;
        }
        const double ratio = (double)pivot / (double)original;
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

static void PS_HOT(NAME(solve))(const ps_sky *s, REAL *b)
{
    const uint32_t *ptr = s->ptr;
    const REAL *val = s->val;
    /* L y = b, with column j of L^T holding l_kj for k < j. */
    for (int32_t j = 0; j < s->n; j++)
    {
        const ptrdiff_t oj = column_offset(ptr, j);
        REAL sum = (REAL)0;
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
        const REAL xj = b[j];
        for (int32_t k = column_first(ptr, j); k < j; k++)
            b[k] -= val[oj + k] * xj;
    }
}
