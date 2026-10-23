#include "circuit.h"
#include <math.h>

#define PS_PI 3.14159265358979323846
#define PS_SQRT2 1.41421356237309504880
#define VT 0.025865      /* thermal voltage kT/q at 27 C */
#define PIVOT_TOL 1e-3   /* keep the diagonal pivot unless 1000x smaller than the best */
#define ITL_OP 100       /* Newton iterations for an operating point */
#define ITL_STEP 50      /* ... for each homotopy step and DC sweep point */
#define ITL_TRAN 20      /* ... for each time step */
#define TRTOL 7.0        /* allowance for the overestimated truncation error, as SPICE */
#define MODE_DC 0
#define MODE_BE 1        /* backward Euler: the first step after a breakpoint */
#define MODE_TRAP 2      /* trapezoidal: every other step */
#define UNSET 0xFF

/* Stamp terms: terminals 0-3, the element's own branch and the branch of
 * the element controlling it. P(row, column) packs one matrix entry. */
#define BR 4
#define CT 5
#define P(r, c) (uint8_t)((r) << 4 | (c))

/* Kinds: R C L V I D NPN PNP NMOS PMOS E G F H OPAMP SW */
static const uint8_t TERMINALS[PS_EL_KINDS] = {2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 2, 2, 3, 4};
static const uint8_t VALUES[PS_EL_KINDS] = {1, 2, 2, 1, 1, 2, 4, 4, 3, 3, 1, 1, 1, 1, 1, 4};
/* State values: C (v, i, v before), L (i, v, i before), and for each device
 * its last linearization (voltages, currents, derivatives). */
static const uint8_t STATES[PS_EL_KINDS] = {0, 3, 3, 0, 0, 3, 8, 8, 5, 5, 0, 0, 0, 0, 0, 0};
#define BRANCHES ((1u << PS_EL_L) | (1u << PS_EL_V) | (1u << PS_EL_E) | (1u << PS_EL_H) | (1u << PS_EL_OPAMP))
#define NONLINEAR ((1u << PS_EL_D) | (1u << PS_EL_NPN) | (1u << PS_EL_PNP) | (1u << PS_EL_NMOS) | \
                   (1u << PS_EL_PMOS) | (1u << PS_EL_SW))

/* Matrix entries each kind stamps, in the order load() fills them. The
 * nonlinear devices list rows by columns. */
static const uint8_t STAMPS[] = {
    P(0, 0), P(0, 1), P(1, 0), P(1, 1), P(0, 2), P(0, 3), P(1, 2), P(1, 3),      /* 0: R C D; 4: G */
    P(0, BR), P(1, BR), P(BR, 0), P(BR, 1), P(BR, BR),                           /* 8: V; L */
    P(0, BR), P(1, BR), P(BR, 0), P(BR, 1), P(BR, 2), P(BR, 3),                  /* 13: E */
    P(0, BR), P(1, BR), P(BR, 0), P(BR, 1), P(BR, CT),                           /* 19: H */
    P(0, CT), P(1, CT),                                                          /* 24: F */
    P(2, BR), P(BR, 0), P(BR, 1), P(BR, 2),                                      /* 26: OPAMP */
    P(0, 0), P(0, 1), P(0, 2), P(1, 0), P(1, 1), P(1, 2), P(2, 0), P(2, 1), P(2, 2), /* 30: BJT */
    P(0, 0), P(0, 1), P(0, 2), P(2, 0), P(2, 1), P(2, 2),                        /* 39: MOS */
    P(0, 0), P(0, 1), P(0, 2), P(0, 3), P(1, 0), P(1, 1), P(1, 2), P(1, 3),      /* 45: SW */
};
static const uint8_t STAMP_AT[PS_EL_KINDS] = {0, 0, 8, 8, 0, 0, 30, 30, 39, 39, 13, 4, 24, 19, 26, 45};
static const uint8_t STAMP_COUNT[PS_EL_KINDS] = {4, 4, 5, 4, 0, 4, 9, 9, 6, 6, 6, 4, 2, 5, 4, 8};

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

/* e^x, ln x and sin x to float32 accuracy, which the device models and
 * waveforms need: the firmware already carries expf, logf and sinf, while
 * double versions would add several KB of flash. */
static double fexp(double v)
{
    return (double)expf((float)v);
}

static double fln(double v)
{
    return (double)logf((float)v);
}

static double big(double a, double b)
{
    return a > b ? a : b;
}

static double small(double a, double b)
{
    return a < b ? a : b;
}

/* The fractional part of x >= 0 (whole numbers beyond 2^31 give 0). */
static double frac(double x)
{
    return x < 2e9 ? x - (double)(int32_t)x : 0.0;
}

static int in_set(uint32_t set, int kind)
{
    return (int)((set >> kind) & 1u);
}

int ps_cir_terminals(ps_el_kind kind)
{
    return kind < PS_EL_KINDS ? TERMINALS[kind] : 0;
}

static ps_status fail(ps_cir *c, ps_status status, int32_t node, int32_t element)
{
    c->error_node = node;
    c->error_element = element;
    return status;
}

/* ------------------------------------------------------------------------ */
/* Building                                                                 */
/* ------------------------------------------------------------------------ */

size_t ps_cir_bytes(int32_t nodes, int32_t elements, int32_t values, int32_t probes)
{
    (void)nodes;
    return align8((size_t)elements * sizeof(ps_el)) + align8((size_t)values * sizeof(float)) +
           align8((size_t)probes * sizeof(ps_probe));
}

ps_status ps_cir_init(ps_cir *c, void *block, int32_t nodes, int32_t elements, int32_t values, int32_t probes)
{
    if (nodes < 2 || nodes > 4000 || elements < 1 || elements > 4000 || values < 0 || probes < 0)
        return PS_ERR_ARGUMENT;
    uint8_t *cursor = block;
    c->nodes = nodes;
    c->elements = elements;
    c->pool_size = values;
    c->pool_used = 0;
    c->probes = probes;
    c->el = take(&cursor, (size_t)elements * sizeof(ps_el));
    c->pool = take(&cursor, (size_t)values * sizeof(float));
    c->probe = take(&cursor, (size_t)probes * sizeof(ps_probe));
    for (int32_t e = 0; e < elements; e++)
        c->el[e].kind = UNSET;
    for (int32_t k = 0; k < probes; k++)
        c->probe[k] = (ps_probe){PS_PROBE_V, 0, 0};
    c->reltol = 1e-3;
    c->vntol = 1e-6;
    c->abstol = 1e-12;
    c->gmin = 1e-12;
    c->gshunt = 0.0;
    c->tstop = 0.0;
    c->prepared = 0;
    c->analysis = PS_AN_NONE;
    c->out = NULL;
    c->points = c->done = 0;
    c->error_node = c->error_element = -1;
    return PS_OK;
}

static int valid_values(int kind, const double *v)
{
    switch (kind)
    {
    case PS_EL_R:
        return v[0] != 0.0;
    case PS_EL_C:
    case PS_EL_L:
        return v[0] >= 0.0;
    case PS_EL_D:
        return v[0] > 0.0 && v[1] > 0.0;
    case PS_EL_NPN:
    case PS_EL_PNP:
        return v[0] > 0.0 && v[1] > 0.0 && v[2] > 0.0 && v[3] >= 0.0;
    case PS_EL_NMOS:
    case PS_EL_PMOS:
        return v[1] > 0.0 && v[2] >= 0.0;
    case PS_EL_OPAMP:
        return v[0] >= 0.0;
    case PS_EL_SW:
        return v[0] > 0.0 && v[1] > 0.0 && v[3] >= 0.0;
    default:
        return 1;
    }
}

/* Store count values in the pool as float32; 0 when they do not fit or
 * are not finite there. */
static int32_t store(ps_cir *c, const double *values, int count)
{
    if (count > c->pool_size - c->pool_used)
        return -1;
    const int32_t at = c->pool_used;
    for (int i = 0; i < count; i++)
    {
        c->pool[at + i] = (float)values[i];
        if (!isfinite(c->pool[at + i]))
            return -1;
    }
    c->pool_used += count;
    return at;
}

ps_status ps_cir_element(ps_cir *c, int32_t e, ps_el_kind kind, const int32_t *nodes, int count,
                         const double *values, int nvalues, int32_t ctrl)
{
    if (e < 0 || e >= c->elements)
        return fail(c, PS_ERR_ARGUMENT, -1, -1);
    if (kind >= PS_EL_KINDS || count != TERMINALS[kind] || nvalues != VALUES[kind] ||
        !valid_values(kind, values))
        return fail(c, PS_ERR_ARGUMENT, -1, e);
    for (int t = 0; t < count; t++)
        if (nodes[t] < 0 || nodes[t] >= c->nodes)
            return fail(c, PS_ERR_ARGUMENT, -1, e);
    const int controlled = kind == PS_EL_F || kind == PS_EL_H;
    if (controlled && (ctrl < 0 || ctrl >= c->elements || ctrl == e))
        return fail(c, PS_ERR_ARGUMENT, -1, e);
    const int32_t at = store(c, values, nvalues);
    if (at < 0)
        return fail(c, PS_ERR_ARGUMENT, -1, e);
    ps_el *el = &c->el[e];
    el->kind = (uint8_t)kind;
    el->wave = PS_WAVE_DC;
    el->values = (uint8_t)nvalues;
    el->wave_values = 0;
    el->value = el->wave_value = at;
    for (int t = 0; t < PS_EL_TERMINALS; t++)
        el->node[t] = (int16_t)(t < count ? nodes[t] : 0);
    el->ctrl = (int16_t)(controlled ? ctrl : -1);
    c->prepared = 0;
    c->analysis = PS_AN_NONE;
    return PS_OK;
}

ps_status ps_cir_wave(ps_cir *c, int32_t e, ps_wave wave, const double *v, int count)
{
    if (e < 0 || e >= c->elements)
        return fail(c, PS_ERR_ARGUMENT, -1, -1);
    ps_el *el = &c->el[e];
    int ok = el->kind == PS_EL_V || el->kind == PS_EL_I;
    if (wave == PS_WAVE_DC)
        ok = ok && count == 0;
    else if (wave == PS_WAVE_PULSE)
        ok = ok && count == 7 && v[2] >= 0.0 && v[3] >= 0.0 && v[4] >= 0.0 && v[5] >= 0.0 && v[6] >= 0.0;
    else if (wave == PS_WAVE_SIN)
        ok = ok && count == 6 && v[2] >= 0.0 && v[3] >= 0.0;
    else if (wave == PS_WAVE_PWL)
    {
        ok = ok && count >= 2 && count <= 254 && count % 2 == 0;
        for (int i = 2; ok && i < count; i += 2)
            ok = v[i] >= v[i - 2];
    }
    else
        ok = 0;
    const int32_t at = ok ? store(c, v, count) : -1;
    if (at < 0)
        return fail(c, PS_ERR_ARGUMENT, -1, e);
    el->wave = (uint8_t)wave;
    el->wave_value = at;
    el->wave_values = (uint8_t)count;
    c->prepared = 0;
    c->analysis = PS_AN_NONE;
    return PS_OK;
}

ps_status ps_cir_probe(ps_cir *c, int32_t k, ps_probe_kind kind, int32_t a, int32_t b)
{
    if (k < 0 || k >= c->probes)
        return fail(c, PS_ERR_ARGUMENT, -1, -1);
    if (kind == PS_PROBE_V ? (a < 0 || a >= c->nodes || b < 0 || b >= c->nodes)
                           : (kind != PS_PROBE_I || a < 0 || a >= c->elements || c->el[a].kind == UNSET ||
                              b < 0 || b >= TERMINALS[c->el[a].kind]))
        return fail(c, PS_ERR_ARGUMENT, -1, -1);
    c->probe[k] = (ps_probe){(uint8_t)kind, (int16_t)a, (int16_t)b};
    c->analysis = PS_AN_NONE;
    return PS_OK;
}

/* ------------------------------------------------------------------------ */
/* Matrix pattern                                                           */
/* ------------------------------------------------------------------------ */

/* Unknowns, matrix entries to stamp (with one diagonal per node) and state
 * values, from the kinds as they stand. */
static void sizes(const ps_cir *c, int32_t *n, int32_t *pairs, int32_t *states)
{
    int32_t branches = 0, p = c->nodes - 1, s = 0;
    for (int32_t e = 0; e < c->elements; e++)
    {
        const int kind = c->el[e].kind;
        if (kind == UNSET)
            continue;
        branches += in_set(BRANCHES, kind);
        p += STAMP_COUNT[kind];
        s += STATES[kind];
    }
    *n = c->nodes - 1 + branches;
    *pairs = p;
    *states = s;
}

size_t ps_cir_index_bytes(const ps_cir *c)
{
    int32_t n, pairs, states;
    sizes(c, &n, &pairs, &states);
    return align8(((size_t)n + 1) * sizeof(int32_t)) + 2 * align8((size_t)pairs * sizeof(ps_row)) +
           align8((size_t)n * sizeof(ps_row));
}

size_t ps_cir_scratch_bytes(const ps_cir *c)
{
    int32_t n, pairs, states;
    sizes(c, &n, &pairs, &states);
    return 2 * align8((size_t)pairs * sizeof(ps_row)) + align8(((size_t)n + 1) * sizeof(int32_t)) +
           ps_order_scratch_bytes(n);
}

/* The unknown a stamp term stands for; -1 is ground. */
static int32_t unknown(const ps_cir *c, const ps_el *el, int term)
{
    if (term == BR)
        return el->branch;
    if (term == CT)
        return c->el[el->ctrl].branch;
    return el->node[term] - 1;
}

ps_status ps_cir_prepare(ps_cir *c, void *index, void *scratch)
{
    int32_t n, pairs, states;
    c->prepared = 0;
    c->analysis = PS_AN_NONE;
    c->error_node = c->error_element = -1;
    sizes(c, &n, &pairs, &states);
    if (n > 32000 || pairs > 32000)
        return PS_ERR_ARGUMENT;
    uint8_t *cursor = index;
    c->ap = take(&cursor, ((size_t)n + 1) * sizeof(int32_t));
    c->ai = take(&cursor, (size_t)pairs * sizeof(ps_row));
    c->slot = take(&cursor, (size_t)pairs * sizeof(ps_row));
    c->q = take(&cursor, (size_t)n * sizeof(ps_row));
    cursor = scratch;
    ps_row *rows = take(&cursor, (size_t)pairs * sizeof(ps_row));
    ps_row *cols = take(&cursor, (size_t)pairs * sizeof(ps_row));
    int32_t *count = take(&cursor, ((size_t)n + 1) * sizeof(int32_t));
    uint32_t *order = (uint32_t *)cursor;

    /* Every element set and every node used; branches and states numbered. */
    for (int32_t i = 0; i <= n; i++)
        count[i] = 0;
    int32_t branch = c->nodes - 1, state = 0;
    for (int32_t e = 0; e < c->elements; e++)
    {
        ps_el *el = &c->el[e];
        if (el->kind == UNSET)
            return fail(c, PS_ERR_ARGUMENT, -1, e);
        for (int t = 0; t < TERMINALS[el->kind]; t++)
            count[el->node[t]] = 1;
        el->branch = (int16_t)(in_set(BRANCHES, el->kind) ? branch++ : -1);
        el->state = (int16_t)state;
        state += STATES[el->kind];
    }
    for (int32_t node = 1; node < c->nodes; node++)
        if (!count[node])
            return fail(c, PS_ERR_UNCONNECTED, node, -1);
    for (int32_t k = 0; k < c->probes; k++)
        if (c->probe[k].kind == PS_PROBE_I && c->probe[k].b >= TERMINALS[c->el[c->probe[k].a].kind])
            return fail(c, PS_ERR_ARGUMENT, -1, c->probe[k].a);

    /* Each stamp's (row, column), then one diagonal entry per node. */
    int32_t m = 0;
    int8_t linear = 1;
    for (int32_t e = 0; e < c->elements; e++)
    {
        ps_el *el = &c->el[e];
        if (el->ctrl >= 0 && el->ctrl < c->elements && c->el[el->ctrl].branch < 0)
            return fail(c, PS_ERR_ARGUMENT, -1, e); /* controlled by an element without a branch */
        linear = (int8_t)(linear && !in_set(NONLINEAR, el->kind));
        el->slot = (int16_t)m;
        const uint8_t *pattern = STAMPS + STAMP_AT[el->kind];
        for (int s = 0; s < STAMP_COUNT[el->kind]; s++, m++)
        {
            rows[m] = (ps_row)unknown(c, el, pattern[s] >> 4);
            cols[m] = (ps_row)unknown(c, el, pattern[s] & 15);
        }
    }
    for (int32_t i = 0; i < c->nodes - 1; i++, m++)
        rows[m] = cols[m] = (ps_row)i;

    /* Compressed columns, sorted, without repeats. */
    for (int32_t i = 0; i <= n; i++)
        count[i] = 0;
    for (int32_t p = 0; p < m; p++)
        if (rows[p] >= 0 && cols[p] >= 0)
            count[cols[p]]++;
    c->ap[0] = 0;
    for (int32_t j = 0; j < n; j++)
    {
        c->ap[j + 1] = c->ap[j] + count[j];
        count[j] = c->ap[j];
    }
    for (int32_t p = 0; p < m; p++)
        if (rows[p] >= 0 && cols[p] >= 0)
            c->ai[count[cols[p]]++] = rows[p];
    int32_t nnz = 0, start = 0;
    for (int32_t j = 0; j < n; j++)
    {
        const int32_t end = c->ap[j + 1];
        c->ap[j] = nnz;
        for (int32_t p = start + 1; p < end; p++)
        {
            const ps_row r = c->ai[p];
            int32_t i = p;
            for (; i > start && c->ai[i - 1] > r; i--)
                c->ai[i] = c->ai[i - 1];
            c->ai[i] = r;
        }
        for (int32_t p = start; p < end; p++)
            if (nnz == c->ap[j] || c->ai[nnz - 1] != c->ai[p])
                c->ai[nnz++] = c->ai[p];
        start = end;
    }
    c->ap[n] = nnz;

    /* Where each stamp lands; ground entries share one spare slot (nnz). */
    for (int32_t p = 0; p < m; p++)
    {
        c->slot[p] = (ps_row)nnz;
        if (rows[p] < 0 || cols[p] < 0)
            continue;
        int32_t lo = c->ap[cols[p]], hi = c->ap[cols[p] + 1] - 1;
        while (lo < hi)
        {
            const int32_t mid = (lo + hi) / 2;
            if (c->ai[mid] < rows[p])
                lo = mid + 1;
            else
                hi = mid;
        }
        c->slot[p] = (ps_row)lo;
    }
    ps_order_md(n, c->ap, c->ai, c->q, order);
    c->n = n;
    c->nnz = nnz;
    c->slots = m;
    c->states = state;
    c->linear = linear;
    c->prepared = 1;
    return PS_OK;
}

size_t ps_cir_value_bytes(const ps_cir *c)
{
    const size_t n = (size_t)c->n;
    return align8(((size_t)c->nnz + 1) * sizeof(double)) + 4 * align8((n + 1) * sizeof(double)) +
           align8(n * sizeof(double)) + align8((size_t)c->states * sizeof(double));
}

/* Half the entries of A plus a diagonal for each of L and U: circuits fill
 * in little, and the binding grows the block on the rare PS_ERR_SPACE. */
int32_t ps_cir_lu_capacity(const ps_cir *c)
{
    const int32_t n = c->n, full = (int32_t)(((int64_t)n * (n + 1)) / 2);
    const int32_t guess = c->nnz / 2 + n;
    return guess < full ? guess : full;
}

void ps_cir_attach_lu(ps_cir *c, void *lu, int32_t cap)
{
    ps_lu_init(&c->lu, lu, c->n, cap, c->ap, c->ai, c->q);
}

void ps_cir_attach(ps_cir *c, void *values, void *lu, int32_t cap)
{
    uint8_t *cursor = values;
    const size_t n = (size_t)c->n;
    c->ax = take(&cursor, ((size_t)c->nnz + 1) * sizeof(double));
    c->rhs = take(&cursor, (n + 1) * sizeof(double));
    c->x = take(&cursor, (n + 1) * sizeof(double));
    c->xp = take(&cursor, (n + 1) * sizeof(double));
    c->w = take(&cursor, (n + 1) * sizeof(double));
    c->work = take(&cursor, n * sizeof(double));
    c->state = take(&cursor, (size_t)c->states * sizeof(double));
    for (size_t i = 0; i <= n; i++)
        c->x[i] = c->xp[i] = c->w[i] = 0.0;
    for (int32_t i = 0; i < c->states; i++)
        c->state[i] = 0.0;
    ps_cir_attach_lu(c, lu, cap);
    c->analysis = PS_AN_NONE;
}

/* ------------------------------------------------------------------------ */
/* Sources                                                                  */
/* ------------------------------------------------------------------------ */

/* A pulse edge given as 0 takes a millionth of the run. */
static double edge(const ps_cir *c, float v)
{
    return v > 0.0f ? (double)v : c->tstop * 1e-6;
}

static double wave_at(const ps_cir *c, const ps_el *el, double t)
{
    const float *w = c->pool + el->wave_value;
    switch (el->wave)
    {
    case PS_WAVE_PULSE:
    {
        const double v1 = (double)w[0], v2 = (double)w[1], td = (double)w[2], pw = (double)w[5],
                     per = (double)w[6], tr = edge(c, w[3]), tf = edge(c, w[4]);
        double s = t - td;
        if (s > 0.0 && per > 0.0)
            s = per * frac(s / per);
        if (s <= 0.0)
            return v1;
        if (s < tr)
            return v1 + (v2 - v1) * s / tr;
        if ((s -= tr) < pw)
            return v2;
        if ((s -= pw) < tf)
            return v2 + (v1 - v2) * s / tf;
        return v1;
    }
    case PS_WAVE_SIN:
    {
        /* Whole cycles are dropped in double before the float32 sine. */
        const double turn = (double)w[5] / 360.0, s = t - (double)w[3];
        if (s < 0.0)
            return (double)w[0] + (double)w[1] * (double)sinf((float)(2.0 * PS_PI * turn));
        const double cycle = frac((double)w[2] * s) + turn;
        return (double)w[0] + (double)w[1] * fexp(-(double)w[4] * s) * (double)sinf((float)(2.0 * PS_PI * cycle));
    }
    case PS_WAVE_PWL:
    {
        const int count = el->wave_values / 2;
        if (t <= (double)w[0])
            return (double)w[1];
        for (int i = 1; i < count; i++)
            if (t <= (double)w[2 * i])
            {
                const double t0 = (double)w[2 * i - 2], t1 = (double)w[2 * i];
                const double v0 = (double)w[2 * i - 1], v1 = (double)w[2 * i + 1];
                return t1 > t0 ? v0 + (v1 - v0) * (t - t0) / (t1 - t0) : v1;
            }
        return (double)w[2 * count - 1];
    }
    default:
        return (double)c->pool[el->value];
    }
}

static double source(const ps_cir *c, const ps_el *el, double t)
{
    if (c->analysis == PS_AN_DC && el == c->el + c->sweep)
        return c->srcfact * c->sweep_value;
    return c->srcfact * wave_at(c, el, t);
}

/* The first source corner after t, where a time step must end. */
static double next_break(const ps_cir *c, double t)
{
    const double after = t + c->tstop * 1e-9;
    double best = HUGE_VAL;
    for (int32_t e = 0; e < c->elements; e++)
    {
        const ps_el *el = &c->el[e];
        const float *w = c->pool + el->wave_value;
        if (el->kind != PS_EL_V && el->kind != PS_EL_I)
            continue;
        if (el->wave == PS_WAVE_PULSE)
        {
            const double td = (double)w[2], per = (double)w[6], tr = edge(c, w[3]), tf = edge(c, w[4]);
            double base = td;
            if (per > 0.0 && after > td)
                base += ((after - td) / per - frac((after - td) / per)) * per;
            const double corner[5] = {0.0, tr, tr + (double)w[5], tr + (double)w[5] + tf, per > 0.0 ? per : HUGE_VAL};
            for (int i = 0; i < 5; i++)
                if (base + corner[i] > after && base + corner[i] < best)
                    best = base + corner[i];
        }
        else if (el->wave == PS_WAVE_PWL)
        {
            for (int i = 0; i < el->wave_values; i += 2)
                if ((double)w[i] > after)
                {
                    if ((double)w[i] < best)
                        best = (double)w[i];
                    break;
                }
        }
        else if (el->wave == PS_WAVE_SIN && (double)w[3] > after && (double)w[3] < best)
            best = (double)w[3];
    }
    return best;
}

/* ------------------------------------------------------------------------ */
/* Devices                                                                  */
/* ------------------------------------------------------------------------ */

static double volt(const double *x, int16_t node)
{
    return node ? x[node - 1] : 0.0;
}

/* exp() and its slope, continuing as a straight line beyond e^80 so a wild
 * Newton iterate cannot overflow. */
static double safe_exp(double v, double *slope)
{
    if (v > 80.0)
    {
        *slope = fexp(80.0);
        return *slope * (1.0 + v - 80.0);
    }
    return *slope = fexp(v);
}

/* SPICE's junction voltage limiting: big forward steps become logarithmic. */
static double pnjlim(double vnew, double vold, double vt, double vcrit, int *limited)
{
    if (vnew > vcrit && fabs(vnew - vold) > 2.0 * vt)
    {
        if (vold > 0.0)
        {
            const double arg = 1.0 + (vnew - vold) / vt;
            vnew = arg > 0.0 ? vold + vt * fln(arg) : vcrit;
        }
        else
            vnew = vt * fln(vnew / vt);
        *limited = 1;
    }
    return vnew;
}

/* SPICE's gate voltage limiting for MOSFETs. */
static double fetlim(double vnew, double vold, double vto)
{
    const double hi = fabs(2.0 * (vold - vto)) + 2.0, lo = fabs(vold - vto) + 1.0, vtox = vto + 3.5;
    const double delta = vnew - vold;
    if (vold >= vto)
    {
        if (vold >= vtox)
        {
            if (delta <= 0.0)
                return vnew >= vtox ? (-delta > lo ? vold - lo : vnew) : big(vnew, vto + 2.0);
            return delta >= hi ? vold + hi : vnew;
        }
        return delta <= 0.0 ? big(vnew, vto - 0.5) : small(vnew, vto + 4.0);
    }
    if (delta <= 0.0)
        return -delta > hi ? vold - hi : vnew;
    return vnew <= vto + 0.5 ? (delta > lo ? vold + lo : vnew) : vto + 0.5;
}

static double limvds(double vnew, double vold)
{
    if (vold >= 3.5)
        return vnew > vold ? small(vnew, 3.0 * vold + 2.0) : vnew < 3.5 ? big(vnew, 2.0) : vnew;
    return vnew > vold ? small(vnew, 4.0) : big(vnew, -0.5);
}

static double diode(const float *p, double gmin, double vd, double *g)
{
    const double is = (double)p[0], nvt = (double)p[1] * VT;
    double slope;
    const double e = safe_exp(vd / nvt, &slope);
    *g = is * slope / nvt + gmin;
    return is * (e - 1.0) + gmin * vd;
}

/* Ebers-Moll transport model with the Early effect, in NPN polarity:
 * collector and base currents and d = {dic/dvbe, dic/dvbc, dib/dvbe, dib/dvbc}. */
static void bjt(const float *p, double gmin, double vbe, double vbc, double *ic, double *ib, double *d)
{
    const double is = (double)p[0], bf = (double)p[1], br = (double)p[2], vaf = (double)p[3];
    double sf, sr;
    const double ef = safe_exp(vbe / VT, &sf), er = safe_exp(vbc / VT, &sr);
    const double fwd = is * (ef - 1.0), rev = is * (er - 1.0), gf = is * sf / VT, gr = is * sr / VT;
    const double early = vaf > 0.0 ? 1.0 - vbc / vaf : 1.0;
    *ic = (fwd - rev) * early - rev / br - gmin * vbc;
    *ib = fwd / bf + rev / br + gmin * (vbe + vbc);
    d[0] = gf * early;
    d[1] = -gr * early - (vaf > 0.0 ? (fwd - rev) / vaf : 0.0) - gr / br - gmin;
    d[2] = gf / bf + gmin;
    d[3] = gr / br + gmin;
}

/* Shichman-Hodges (level 1) drain current in NMOS polarity, with its
 * derivatives by vgs and vds; drain and source swap when vds < 0. */
static double mos(const float *p, double vto, double gmin, double vgs, double vds, double *dgs, double *dds)
{
    const double kp = (double)p[1], lambda = (double)p[2];
    const int reverse = vds < 0.0;
    const double vd = reverse ? -vds : vds, vov = (reverse ? vgs - vds : vgs) - vto, cl = 1.0 + lambda * vd;
    double id = 0.0, gm = 0.0, gds = 0.0;
    if (vov > 0.0 && vd < vov)
    {
        const double core = vov * vd - 0.5 * vd * vd;
        id = kp * core * cl;
        gm = kp * vd * cl;
        gds = kp * (vov - vd) * cl + kp * core * lambda;
    }
    else if (vov > 0.0)
    {
        id = 0.5 * kp * vov * vov * cl;
        gm = kp * vov * cl;
        gds = 0.5 * kp * vov * vov * lambda;
    }
    *dgs = reverse ? -gm : gm;
    *dds = (reverse ? gm + gds : gds) + gmin;
    return (reverse ? -id : id) + gmin * vds;
}

/* Switch conductance and its derivative by the control voltage. */
static double sw(const float *p, double vc, double *dg)
{
    const double ron = (double)p[0], roff = (double)p[1], vt = (double)p[2], vh = (double)p[3];
    const double span = fln(roff / ron);
    double s, ds = 0.0;
    if (vh <= 0.0)
        s = vc > vt ? 1.0 : 0.0;
    else
    {
        const double u = (vc - vt + vh) / (2.0 * vh);
        s = u <= 0.0 ? 0.0 : u >= 1.0 ? 1.0 : u * u * (3.0 - 2.0 * u);
        if (u > 0.0 && u < 1.0)
            ds = 6.0 * u * (1.0 - u) / (2.0 * vh);
    }
    const double g = fexp(span * s) / roff;
    *dg = g * span * ds;
    return g;
}

/* ------------------------------------------------------------------------ */
/* Assembly                                                                 */
/* ------------------------------------------------------------------------ */

static double *rhs_at(ps_cir *c, int16_t node)
{
    return c->rhs + (node ? node - 1 : c->n);
}

static void conduct(double *a, const ps_row *s, double g)
{
    a[s[0]] += g;
    a[s[1]] -= g;
    a[s[2]] -= g;
    a[s[3]] += g;
}

static void branch_rows(double *a, const ps_row *s)
{
    a[s[0]] += 1.0;
    a[s[1]] -= 1.0;
    a[s[2]] += 1.0;
    a[s[3]] -= 1.0;
}

/* A linearized device: rows x columns Jacobian (columns are terminals
 * 0..cols-1) and the current left over at the linearization point. */
static void stamp(ps_cir *c, const ps_el *el, const ps_row *s, const double *jac, const double *ceq,
                  const uint8_t *rows, int nr, int nc)
{
    for (int r = 0; r < nr; r++)
    {
        for (int k = 0; k < nc; k++)
            c->ax[s[r * nc + k]] += jac[r * nc + k];
        *rhs_at(c, el->node[rows[r]]) -= ceq[r];
    }
}

/* SPICE's device test: a Newton iterate has not settled while a device's
 * current differs from what its last linearization predicted. */
static void settle(const ps_cir *c, double now, double predicted, int *noncon)
{
    if (fabs(now - predicted) > c->reltol * big(fabs(now), fabs(predicted)) + c->abstol)
        *noncon = 1;
}

static const uint8_t ROWS_ABC[3] = {0, 1, 2};
static const uint8_t ROWS_DS[2] = {0, 2};

static void load_device(ps_cir *c, const ps_el *el, int *noncon)
{
    const ps_row *s = c->slot + el->slot;
    const float *p = c->pool + el->value;
    double *st = c->state + el->state;
    const int16_t *nd = el->node;
    const double *x = c->w;
    double jac[9], ceq[3];
    switch (el->kind)
    {
    case PS_EL_D:
    {
        const double nvt = (double)p[1] * VT, vcrit = nvt * fln(nvt / (PS_SQRT2 * (double)p[0]));
        double vd = volt(x, nd[0]) - volt(x, nd[1]), g;
        vd = c->first ? vcrit : pnjlim(vd, st[0], nvt, vcrit, noncon);
        const double id = diode(p, c->gmin, vd, &g);
        settle(c, id, st[1] + st[2] * (vd - st[0]), noncon);
        st[0] = vd;
        st[1] = id;
        st[2] = g;
        conduct(c->ax, s, g);
        *rhs_at(c, nd[0]) -= id - g * vd;
        *rhs_at(c, nd[1]) += id - g * vd;
        break;
    }
    case PS_EL_NPN:
    case PS_EL_PNP:
    {
        const double pol = el->kind == PS_EL_NPN ? 1.0 : -1.0, vcrit = VT * fln(VT / (PS_SQRT2 * (double)p[0]));
        double vbe = pol * (volt(x, nd[1]) - volt(x, nd[2])), vbc = pol * (volt(x, nd[1]) - volt(x, nd[0]));
        if (c->first)
        {
            vbe = vcrit;
            vbc = 0.0;
        }
        else
        {
            vbe = pnjlim(vbe, st[0], VT, vcrit, noncon);
            vbc = pnjlim(vbc, st[1], VT, vcrit, noncon);
        }
        double ic, ib, d[4];
        bjt(p, c->gmin, vbe, vbc, &ic, &ib, d);
        settle(c, ic, st[2] + st[4] * (vbe - st[0]) + st[5] * (vbc - st[1]), noncon);
        settle(c, ib, st[3] + st[6] * (vbe - st[0]) + st[7] * (vbc - st[1]), noncon);
        st[0] = vbe;
        st[1] = vbc;
        st[2] = ic;
        st[3] = ib;
        for (int k = 0; k < 4; k++)
            st[4 + k] = d[k];
        /* Rows c, b, e by columns c, b, e: vbe = Vb - Ve, vbc = Vb - Vc. */
        jac[0] = -d[1];
        jac[1] = d[0] + d[1];
        jac[2] = -d[0];
        jac[3] = -d[3];
        jac[4] = d[2] + d[3];
        jac[5] = -d[2];
        for (int k = 0; k < 3; k++)
            jac[6 + k] = -(jac[k] + jac[3 + k]);
        ceq[0] = pol * (ic - d[0] * vbe - d[1] * vbc);
        ceq[1] = pol * (ib - d[2] * vbe - d[3] * vbc);
        ceq[2] = -(ceq[0] + ceq[1]);
        stamp(c, el, s, jac, ceq, ROWS_ABC, 3, 3);
        break;
    }
    case PS_EL_NMOS:
    case PS_EL_PMOS:
    {
        const double pol = el->kind == PS_EL_NMOS ? 1.0 : -1.0, vto = pol * (double)p[0];
        const double vgs0 = pol * (volt(x, nd[1]) - volt(x, nd[2])), vds0 = pol * (volt(x, nd[0]) - volt(x, nd[2]));
        double vgs = vgs0, vds = vds0;
        if (st[1] >= 0.0)
        {
            vgs = fetlim(vgs, st[0], vto);
            vds = limvds(vds, st[1]);
        }
        else
        {
            const double vgd = fetlim(vgs - vds, st[0] - st[1], vto);
            vds = -limvds(-vds, -st[1]);
            vgs = vgd + vds;
        }
        if (fabs(vgs - vgs0) + fabs(vds - vds0) > 1e-9)
            *noncon = 1;
        double dgs, dds;
        const double id = mos(p, vto, c->gmin, vgs, vds, &dgs, &dds);
        settle(c, id, st[2] + st[3] * (vgs - st[0]) + st[4] * (vds - st[1]), noncon);
        st[0] = vgs;
        st[1] = vds;
        st[2] = id;
        st[3] = dgs;
        st[4] = dds;
        /* Rows d, s by columns d, g, s. */
        jac[0] = dds;
        jac[1] = dgs;
        jac[2] = -(dgs + dds);
        for (int k = 0; k < 3; k++)
            jac[3 + k] = -jac[k];
        ceq[0] = pol * (id - dgs * vgs - dds * vds);
        ceq[1] = -ceq[0];
        stamp(c, el, s, jac, ceq, ROWS_DS, 2, 3);
        break;
    }
    default: /* PS_EL_SW */
    {
        const double vc = volt(x, nd[2]) - volt(x, nd[3]), vs = volt(x, nd[0]) - volt(x, nd[1]);
        double dg;
        const double g = sw(p, vc, &dg);
        jac[0] = g;
        jac[1] = -g;
        jac[2] = dg * vs;
        jac[3] = -dg * vs;
        for (int k = 0; k < 4; k++)
            jac[4 + k] = -jac[k];
        ceq[0] = -dg * vs * vc;
        ceq[1] = -ceq[0];
        stamp(c, el, s, jac, ceq, ROWS_ABC, 2, 4);
        break;
    }
    }
}

/* The Newton system at the iterate c->w: matrix in c->ax, right side in
 * c->rhs. t and h are the time and step (transient). */
static void load(ps_cir *c, double t, double h, int *noncon)
{
    double *a = c->ax;
    for (int32_t i = 0; i <= c->nnz; i++)
        a[i] = 0.0;
    for (int32_t i = 0; i <= c->n; i++)
        c->rhs[i] = 0.0;
    const double order = c->mode == MODE_TRAP ? 2.0 : 1.0;
    for (int32_t e = 0; e < c->elements; e++)
    {
        const ps_el *el = &c->el[e];
        const ps_row *s = c->slot + el->slot;
        const float *p = c->pool + el->value;
        const double *st = c->state + el->state;
        switch (el->kind)
        {
        case PS_EL_R:
            conduct(a, s, 1.0 / (double)p[0]);
            break;
        case PS_EL_C:
            if (c->mode != MODE_DC)
            {
                /* Companion model: i = g v + ieq from the last step. */
                const double g = order * (double)p[0] / h;
                const double ieq = c->mode == MODE_TRAP ? -g * st[0] - st[1] : -g * st[0];
                conduct(a, s, g);
                *rhs_at(c, el->node[0]) -= ieq;
                *rhs_at(c, el->node[1]) += ieq;
            }
            break;
        case PS_EL_L:
            branch_rows(a, s);
            if (c->mode != MODE_DC)
            {
                const double r = order * (double)p[0] / h;
                a[s[4]] -= r;
                c->rhs[el->branch] += c->mode == MODE_TRAP ? -r * st[0] - st[1] : -r * st[0];
            }
            break;
        case PS_EL_V:
            branch_rows(a, s);
            c->rhs[el->branch] += source(c, el, t);
            break;
        case PS_EL_I:
        {
            const double i = source(c, el, t);
            *rhs_at(c, el->node[0]) -= i;
            *rhs_at(c, el->node[1]) += i;
            break;
        }
        case PS_EL_E:
            branch_rows(a, s);
            a[s[4]] -= (double)p[0];
            a[s[5]] += (double)p[0];
            break;
        case PS_EL_G:
            conduct(a, s, (double)p[0]);
            break;
        case PS_EL_F:
            a[s[0]] += (double)p[0];
            a[s[1]] -= (double)p[0];
            break;
        case PS_EL_H:
            branch_rows(a, s);
            a[s[4]] -= (double)p[0];
            break;
        case PS_EL_OPAMP:
            a[s[0]] += 1.0;
            a[s[1]] += 1.0;
            a[s[2]] -= 1.0;
            if (p[0] > 0.0f)
                a[s[3]] -= 1.0 / (double)p[0];
            break;
        default:
            load_device(c, el, noncon);
        }
    }
    const double shunt = c->gstep + c->gshunt;
    if (shunt > 0.0)
        for (int32_t i = 0; i < c->nodes - 1; i++)
            a[c->slot[c->slots - (c->nodes - 1) + i]] += shunt;
    if (c->first)
        *noncon = 1;
    c->first = 0;
}

/* ------------------------------------------------------------------------ */
/* Newton and the operating point                                           */
/* ------------------------------------------------------------------------ */

static ps_status singular(ps_cir *c, int32_t unknown_index)
{
    if (unknown_index < c->nodes - 1)
        return fail(c, PS_ERR_SINGULAR, unknown_index + 1, -1);
    for (int32_t e = 0; e < c->elements; e++)
        if (c->el[e].branch == unknown_index)
            return fail(c, PS_ERR_SINGULAR, -1, e);
    return fail(c, PS_ERR_SINGULAR, -1, -1);
}

static void copy(double *to, const double *from, int32_t n)
{
    for (int32_t i = 0; i < n; i++)
        to[i] = from[i];
}

/* Newton iterations from the guess in c->w; the solution is left there. */
static ps_status newton(ps_cir *c, double t, double h, int limit)
{
    const int32_t n = c->n, nodes = c->nodes - 1;
    for (int it = 0; it < limit; it++)
    {
        int noncon = 0;
        int32_t bad = -1;
        load(c, t, h, &noncon);
        const ps_status s = ps_lu_factor(&c->lu, c->ax, PIVOT_TOL, &bad);
        if (s == PS_ERR_SINGULAR)
            return singular(c, bad);
        if (s != PS_OK)
            return s;
        ps_lu_solve(&c->lu, c->rhs, c->work);
        c->iterations++;
        int settled = !noncon;
        for (int32_t i = 0; i < n; i++)
        {
            const double now = c->rhs[i], was = c->w[i];
            if (!isfinite(now))
                return fail(c, PS_ERR_CONVERGENCE, -1, -1);
            const double tol = c->reltol * big(fabs(now), fabs(was)) + (i < nodes ? c->vntol : c->abstol);
            if (fabs(now - was) > tol)
                settled = 0;
            c->w[i] = now;
        }
        if (settled || c->linear)
            return PS_OK;
    }
    return fail(c, PS_ERR_CONVERGENCE, -1, -1);
}

static void clear(double *v, int32_t n)
{
    for (int32_t i = 0; i < n; i++)
        v[i] = 0.0;
}

/* Plain Newton from zero; then gmin stepping (a shunt on every node,
 * lowered a decade at a time); then source stepping (sources ramped up
 * from zero). */
static ps_status operating_point(ps_cir *c)
{
    c->mode = MODE_DC;
    c->srcfact = 1.0;
    c->gstep = 0.0;
    clear(c->w, c->n);
    c->first = 1;
    ps_status s = newton(c, 0.0, 0.0, ITL_OP);
    if (s != PS_ERR_CONVERGENCE)
        return s;
    clear(c->w, c->n);
    c->first = 1;
    for (double g = 1e-2;; g *= 0.1)
    {
        c->gstep = g < 1e-12 ? 0.0 : g;
        s = newton(c, 0.0, 0.0, ITL_STEP);
        if (s != PS_OK || c->gstep == 0.0)
            break;
    }
    c->gstep = 0.0;
    if (s != PS_ERR_CONVERGENCE)
        return s;
    clear(c->w, c->n);
    c->first = 1;
    double done = 0.0, step = 0.1;
    c->srcfact = 0.0;
    s = newton(c, 0.0, 0.0, ITL_STEP);
    while (s == PS_OK && done < 1.0)
    {
        copy(c->xp, c->w, c->n);
        c->srcfact = small(1.0, done + step);
        s = newton(c, 0.0, 0.0, ITL_STEP);
        if (s == PS_OK)
        {
            done = c->srcfact;
            step *= 1.5;
        }
        else if (s == PS_ERR_CONVERGENCE && step > 1e-4)
        {
            copy(c->w, c->xp, c->n);
            step *= 0.25;
            s = PS_OK;
        }
    }
    c->srcfact = 1.0;
    return s;
}

/* ------------------------------------------------------------------------ */
/* Results                                                                  */
/* ------------------------------------------------------------------------ */

double ps_cir_voltage(const ps_cir *c, int32_t node)
{
    if (node < 0 || node >= c->nodes || c->analysis == PS_AN_NONE)
        return (double)NAN;
    return volt(c->x, (int16_t)node);
}

double ps_cir_current(const ps_cir *c, int32_t e, int t)
{
    if (e < 0 || e >= c->elements || c->analysis == PS_AN_NONE || t < 0 || t >= TERMINALS[c->el[e].kind])
        return (double)NAN;
    const ps_el *el = &c->el[e];
    const float *p = c->pool + el->value;
    const int16_t *nd = el->node;
    const double *x = c->x;
    const double pol = (el->kind == PS_EL_PNP || el->kind == PS_EL_PMOS) ? -1.0 : 1.0;
    double i = 0.0, g;
    switch (el->kind)
    {
    case PS_EL_R:
        i = (volt(x, nd[0]) - volt(x, nd[1])) / (double)p[0];
        break;
    case PS_EL_C:
        i = c->analysis == PS_AN_TRAN ? c->state[el->state + 1] : 0.0;
        break;
    case PS_EL_L:
    case PS_EL_V:
    case PS_EL_E:
    case PS_EL_H:
        i = x[el->branch];
        break;
    case PS_EL_I:
        i = source(c, el, c->time);
        break;
    case PS_EL_G:
        i = (double)p[0] * (volt(x, nd[2]) - volt(x, nd[3]));
        break;
    case PS_EL_F:
        i = (double)p[0] * x[c->el[el->ctrl].branch];
        break;
    case PS_EL_OPAMP:
        return t == 2 ? x[el->branch] : 0.0;
    case PS_EL_D:
        i = diode(p, c->gmin, volt(x, nd[0]) - volt(x, nd[1]), &g);
        break;
    case PS_EL_NPN:
    case PS_EL_PNP:
    {
        double ic, ib, d[4];
        bjt(p, c->gmin, pol * (volt(x, nd[1]) - volt(x, nd[2])), pol * (volt(x, nd[1]) - volt(x, nd[0])), &ic, &ib, d);
        return pol * (t == 0 ? ic : t == 1 ? ib : -(ic + ib));
    }
    case PS_EL_NMOS:
    case PS_EL_PMOS:
    {
        double dgs, dds;
        const double id = mos(p, pol * (double)p[0], c->gmin, pol * (volt(x, nd[1]) - volt(x, nd[2])),
                              pol * (volt(x, nd[0]) - volt(x, nd[2])), &dgs, &dds);
        return pol * (t == 0 ? id : t == 2 ? -id : 0.0);
    }
    default: /* PS_EL_SW */
        i = sw(p, volt(x, nd[2]) - volt(x, nd[3]), &g) * (volt(x, nd[0]) - volt(x, nd[1]));
    }
    return t == 0 ? i : t == 1 ? -i : 0.0;
}

double ps_cir_probe_value(const ps_cir *c, int32_t k)
{
    if (k < 0 || k >= c->probes)
        return (double)NAN;
    const ps_probe *pr = &c->probe[k];
    if (pr->kind == PS_PROBE_I)
        return ps_cir_current(c, pr->a, pr->b);
    return ps_cir_voltage(c, pr->a) - ps_cir_voltage(c, pr->b);
}

static void record(ps_cir *c)
{
    for (int32_t k = 0; k < c->probes; k++)
        c->out[k * c->points + c->done] = (float)ps_cir_probe_value(c, k);
    c->done++;
}

/* ------------------------------------------------------------------------ */
/* Analyses                                                                 */
/* ------------------------------------------------------------------------ */

static void begin(ps_cir *c, ps_analysis analysis)
{
    c->analysis = analysis;
    c->srcfact = 1.0; /* sources at full value, no homotopy shunt */
    c->gstep = 0.0;
    c->time = 0.0;
    c->done = 0;
    c->iterations = c->steps = c->rejected = 0;
    c->error_node = c->error_element = -1;
}

ps_status ps_cir_op(ps_cir *c)
{
    if (!c->prepared)
        return PS_ERR_STATE;
    begin(c, PS_AN_OP);
    c->points = 0;
    const ps_status s = operating_point(c);
    copy(c->x, c->w, c->n);
    if (s != PS_OK)
        c->analysis = PS_AN_NONE;
    return s;
}

ps_status ps_cir_dc(ps_cir *c, int32_t source_index, double start, double stop, int32_t points, float *out)
{
    if (!c->prepared)
        return PS_ERR_STATE;
    if (source_index < 0 || source_index >= c->elements || points < 1 || !isfinite(start) || !isfinite(stop) ||
        (c->el[source_index].kind != PS_EL_V && c->el[source_index].kind != PS_EL_I))
        return PS_ERR_ARGUMENT;
    begin(c, PS_AN_DC);
    c->sweep = source_index;
    c->start = start;
    c->stop = stop;
    c->points = points;
    c->out = out;
    return PS_OK;
}

static double sweep_value(const ps_cir *c, int32_t k)
{
    return c->points > 1 ? c->start + (c->stop - c->start) * (double)k / (double)(c->points - 1) : c->start;
}

/* One sweep point, from the last one's solution; a point that will not
 * converge is approached in ten smaller steps, then solved from scratch. */
static ps_status dc_point(ps_cir *c)
{
    ps_status s;
    const double value = sweep_value(c, c->done);
    if (c->done == 0)
    {
        c->sweep_value = value;
        s = operating_point(c);
    }
    else
    {
        copy(c->w, c->x, c->n);
        c->sweep_value = value;
        s = newton(c, 0.0, 0.0, ITL_STEP);
        if (s == PS_ERR_CONVERGENCE)
        {
            const double from = sweep_value(c, c->done - 1);
            copy(c->w, c->x, c->n);
            s = PS_OK;
            for (int i = 1; i <= 10 && s == PS_OK; i++)
            {
                c->sweep_value = from + (value - from) * i / 10.0;
                s = newton(c, 0.0, 0.0, ITL_STEP);
            }
            if (s == PS_ERR_CONVERGENCE)
            {
                c->sweep_value = value;
                s = operating_point(c);
            }
        }
    }
    if (s != PS_OK)
        return s;
    copy(c->x, c->w, c->n);
    record(c);
    return c->done >= c->points ? PS_OK : PS_PENDING;
}

ps_status ps_cir_tran(ps_cir *c, double stop, int32_t points, double hmax, int uic, float *out)
{
    if (!c->prepared)
        return PS_ERR_STATE;
    if (!(stop > 0.0) || points < 2 || !(hmax >= 0.0))
        return PS_ERR_ARGUMENT;
    begin(c, PS_AN_TRAN);
    c->tstop = stop;
    c->points = points;
    c->out = out;
    const double dt = stop / (points - 1);
    c->hmax = hmax > 0.0 && hmax < dt ? hmax : dt;
    if (uic)
    {
        clear(c->w, c->n);
        c->first = 1;
    }
    else
    {
        const ps_status s = operating_point(c);
        if (s != PS_OK)
        {
            c->analysis = PS_AN_NONE;
            return s;
        }
    }
    copy(c->x, c->w, c->n);
    copy(c->xp, c->w, c->n);
    /* Capacitor (v, i, v before) and inductor (i, v, i before) histories. */
    for (int32_t e = 0; e < c->elements; e++)
    {
        const ps_el *el = &c->el[e];
        double *st = c->state + el->state;
        if (el->kind == PS_EL_C)
        {
            st[0] = st[2] = uic ? (double)c->pool[el->value + 1] : volt(c->x, el->node[0]) - volt(c->x, el->node[1]);
            st[1] = 0.0;
        }
        else if (el->kind == PS_EL_L)
        {
            st[0] = st[2] = uic ? (double)c->pool[el->value + 1] : c->x[el->branch];
            st[1] = 0.0;
        }
    }
    c->h = c->hprev = 0.1 * c->hmax;
    c->fresh = 1;
    c->have_prev = 0;
    record(c);
    return PS_OK;
}

/* Truncation error of the step just solved, as a multiple of the allowed
 * one: each capacitor voltage and inductor current against its value
 * extrapolated from the two before. */
static double step_error(const ps_cir *c, double h)
{
    const double r = h / c->hprev;
    double worst = 0.0;
    for (int32_t e = 0; e < c->elements; e++)
    {
        const ps_el *el = &c->el[e];
        if (el->kind != PS_EL_C && el->kind != PS_EL_L)
            continue;
        const double *st = c->state + el->state;
        const double now = el->kind == PS_EL_C ? volt(c->w, el->node[0]) - volt(c->w, el->node[1]) : c->w[el->branch];
        const double guess = st[0] + r * (st[0] - st[2]);
        const double tol = c->reltol * big(fabs(now), fabs(st[0])) + (el->kind == PS_EL_C ? c->vntol : c->abstol);
        const double err = fabs(now - guess) / (TRTOL * tol);
        if (err > worst)
            worst = err;
    }
    return worst;
}

static void accept(ps_cir *c, double h)
{
    const double order = c->mode == MODE_TRAP ? 2.0 : 1.0;
    for (int32_t e = 0; e < c->elements; e++)
    {
        const ps_el *el = &c->el[e];
        double *st = c->state + el->state;
        if (el->kind == PS_EL_C)
        {
            const double v = volt(c->w, el->node[0]) - volt(c->w, el->node[1]);
            const double g = order * (double)c->pool[el->value] / h;
            st[1] = g * v + (c->mode == MODE_TRAP ? -g * st[0] - st[1] : -g * st[0]);
            st[2] = st[0];
            st[0] = v;
        }
        else if (el->kind == PS_EL_L)
        {
            st[2] = st[0];
            st[0] = c->w[el->branch];
            st[1] = volt(c->w, el->node[0]) - volt(c->w, el->node[1]);
        }
    }
    copy(c->xp, c->x, c->n);
    copy(c->x, c->w, c->n);
}

/* One time step: to the next output time or source corner at most, solved
 * with the trapezoidal rule (backward Euler just after a corner), checked
 * for truncation error and repeated smaller when it fails. */
static ps_status tran_step(ps_cir *c)
{
    const double eps = c->tstop * 1e-9, hmin = c->hmax * 1e-9;
    const double out = c->done == c->points - 1 ? c->tstop : c->tstop * c->done / (c->points - 1);
    const double corner = next_break(c, c->time);
    const double target = corner < out ? corner : out, left = target - c->time;
    double h = c->h;
    if (left <= 1.25 * h)
        h = left;
    else if (left < 2.0 * h)
        h = 0.5 * left;
    const int trap = !c->fresh;
    c->mode = trap ? MODE_TRAP : MODE_BE;
    for (int32_t i = 0; i < c->n; i++)
        c->w[i] = trap && c->have_prev ? c->x[i] + (c->x[i] - c->xp[i]) * h / c->hprev : c->x[i];
    const ps_status s = newton(c, c->time + h, h, ITL_TRAN);
    if (s == PS_ERR_CONVERGENCE)
    {
        c->rejected++;
        c->h = h / 8.0;
        c->fresh = 1;
        return c->h < hmin ? fail(c, PS_ERR_TIMESTEP, -1, -1) : PS_PENDING;
    }
    if (s != PS_OK)
        return s;
    const double err = trap && c->have_prev ? step_error(c, h) : 0.0;
    if (err > 1.0 && h > 100.0 * hmin)
    {
        /* At most half, so stretching to the next target cannot repeat it. */
        c->rejected++;
        c->h = h * big(0.25, small(0.5, 0.9 / sqrt(err)));
        return PS_PENDING;
    }
    accept(c, h);
    c->steps++;
    c->hprev = h;
    c->have_prev = 1;
    c->time = fabs(c->time + h - target) <= eps ? target : c->time + h;
    c->fresh = fabs(c->time - corner) <= eps;
    const double grow = err > 0.0 ? small(2.0, 0.9 / sqrt(err)) : 2.0;
    if (h >= c->h || grow < 1.0)
        c->h = small(c->hmax, h * grow);
    if (fabs(c->time - out) <= eps)
        record(c);
    return c->done >= c->points ? PS_OK : PS_PENDING;
}

ps_status ps_cir_run(ps_cir *c, int32_t steps, ps_control *ctl)
{
    if (!c->prepared || (c->analysis != PS_AN_DC && c->analysis != PS_AN_TRAN))
        return c->analysis == PS_AN_OP ? PS_OK : PS_ERR_STATE;
    ps_status s = c->done >= c->points ? PS_OK : PS_PENDING;
    for (int32_t i = 0; i < steps && s == PS_PENDING; i++)
    {
        if (ctl && ctl->cancel)
            return PS_CANCELLED;
        s = c->analysis == PS_AN_DC ? dc_point(c) : tran_step(c);
    }
    if (ctl)
    {
        ctl->done = c->done;
        ctl->total = c->points;
    }
    return s;
}
