/*
 * Host tests for the circuit simulator and the sparse LU under it:
 * closed-form circuits, every element kind, error paths, sweeps and
 * transients. Run tests/run-tests.sh from the picosolve folder.
 */
#include "../core/sparse.h"
#include "../fe/circuit.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures = 0, checks = 0;

#define CHECK(cond)                                                \
    do                                                             \
    {                                                              \
        checks++;                                                  \
        if (!(cond))                                               \
        {                                                          \
            failures++;                                            \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        }                                                          \
    } while (0)

#define NEAR(got, want, tol)                                                           \
    do                                                                                 \
    {                                                                                  \
        double g_ = (got), w_ = (want);                                                \
        checks++;                                                                      \
        if (!(fabs(g_ - w_) <= (tol) * (fabs(w_) > 1.0 ? fabs(w_) : 1.0)))             \
        {                                                                              \
            failures++;                                                                \
            printf("FAIL %s:%d: %s = %.10g, want %.10g\n", __FILE__, __LINE__, #got, g_, \
                   w_);                                                                \
        }                                                                              \
    } while (0)

#define VT 0.025865
#define PI 3.14159265358979323846

/* ------------------------------------------------------------------------ */
/* Sparse LU                                                                */
/* ------------------------------------------------------------------------ */

static uint32_t seed = 12345;
static double random_unit(void)
{
    seed = seed * 1103515245u + 12345u;
    return (double)((seed >> 8) & 0xFFFF) / 65535.0 - 0.5;
}

/* Random sparse matrices whose diagonal is mostly zero (as in circuits
 * with sources), solved against dense elimination with partial pivoting. */
static void test_lu_against_dense(void)
{
    enum { N = 40 };
    for (int trial = 0; trial < 20; trial++)
    {
        static double dense[N][N], copy[N][N];
        memset(dense, 0, sizeof(dense));
        for (int i = 0; i < N; i++)
        {
            dense[(i + 7) % N][i] = 2.0 + random_unit(); /* a permuted diagonal keeps it regular */
            for (int k = 0; k < 3; k++)
                dense[(int)((random_unit() + 0.5) * (N - 1))][i] += random_unit();
            if (i % 3 == 0)
                dense[i][i] = 0.0;
        }
        int32_t ap[N + 1], nnz = 0;
        ps_row ai[N * N], q[N];
        double ax[N * N], b[N], x[N], want[N];
        for (int j = 0; j < N; j++)
        {
            ap[j] = nnz;
            for (int i = 0; i < N; i++)
                if (dense[i][j] != 0.0)
                {
                    ai[nnz] = (ps_row)i;
                    ax[nnz++] = dense[i][j];
                }
        }
        ap[N] = nnz;
        uint32_t *scratch = malloc(ps_order_scratch_bytes(N));
        ps_order_md(N, ap, ai, q, scratch);
        free(scratch);
        int seen[N] = {0}, permutation = 1;
        for (int k = 0; k < N; k++)
            seen[q[k]]++;
        for (int k = 0; k < N; k++)
            permutation = permutation && seen[k] == 1;
        CHECK(permutation);
        const int32_t cap = N * (N + 1) / 2;
        void *block = malloc(ps_lu_bytes(N, cap));
        ps_lu f;
        ps_lu_init(&f, block, N, cap, ap, ai, q);
        int32_t bad = -1;
        CHECK(ps_lu_factor(&f, ax, 1e-3, &bad) == PS_OK);
        for (int i = 0; i < N; i++)
            b[i] = want[i] = random_unit();
        /* dense solve */
        memcpy(copy, dense, sizeof(copy));
        for (int k = 0; k < N; k++)
        {
            int p = k;
            for (int i = k + 1; i < N; i++)
                if (fabs(copy[i][k]) > fabs(copy[p][k]))
                    p = i;
            for (int j = 0; j < N; j++)
            {
                const double t = copy[k][j];
                copy[k][j] = copy[p][j];
                copy[p][j] = t;
            }
            const double t = want[k];
            want[k] = want[p];
            want[p] = t;
            for (int i = k + 1; i < N; i++)
            {
                const double l = copy[i][k] / copy[k][k];
                for (int j = k; j < N; j++)
                    copy[i][j] -= l * copy[k][j];
                want[i] -= l * want[k];
            }
        }
        for (int k = N - 1; k >= 0; k--)
        {
            for (int j = k + 1; j < N; j++)
                want[k] -= copy[k][j] * want[j];
            want[k] /= copy[k][k];
        }
        double work[N];
        memcpy(x, b, sizeof(x));
        ps_lu_solve(&f, x, work);
        for (int i = 0; i < N; i++)
            NEAR(x[i], want[i], 1e-9);
        /* Too little room is reported, not overrun. */
        ps_lu small;
        void *tiny = malloc(ps_lu_bytes(N, N));
        ps_lu_init(&small, tiny, N, N, ap, ai, q);
        CHECK(ps_lu_factor(&small, ax, 1e-3, &bad) == PS_ERR_SPACE || small.lnz + small.unz <= 2 * N);
        free(tiny);
        /* An empty column is singular and named. */
        for (int p = ap[5]; p < ap[6]; p++)
            ax[p] = 0.0;
        CHECK(ps_lu_factor(&f, ax, 1e-3, &bad) == PS_ERR_SINGULAR && bad == 5);
        free(block);
    }
}

/* ------------------------------------------------------------------------ */
/* Circuits                                                                 */
/* ------------------------------------------------------------------------ */

typedef struct
{
    ps_cir c;
    void *model, *index, *values, *lu;
    float *out;
    int32_t cap;
    int grows;
} circuit;

static void circuit_new(circuit *k, int nodes, int elements, int probes)
{
    memset(k, 0, sizeof(*k));
    k->model = malloc(ps_cir_bytes(nodes, elements, 32 * elements, probes));
    CHECK(ps_cir_init(&k->c, k->model, nodes, elements, 32 * elements, probes) == PS_OK);
}

static void circuit_free(circuit *k)
{
    free(k->model);
    free(k->index);
    free(k->values);
    free(k->lu);
    free(k->out);
    memset(k, 0, sizeof(*k));
}

static int32_t force_cap = 0; /* nonzero: start the LU this small */

static ps_status prepare(circuit *k)
{
    free(k->index);
    free(k->values);
    free(k->lu);
    k->index = malloc(ps_cir_index_bytes(&k->c));
    const size_t bytes = ps_cir_scratch_bytes(&k->c);
    void *scratch = malloc(bytes);
    const ps_status s = ps_cir_prepare(&k->c, k->index, scratch);
    memset(scratch, 0xA5, bytes); /* nothing may keep using it */
    free(scratch);
    k->values = k->lu = NULL;
    if (s != PS_OK)
        return s;
    k->values = malloc(ps_cir_value_bytes(&k->c));
    k->cap = force_cap ? force_cap : ps_cir_lu_capacity(&k->c);
    k->lu = malloc(ps_lu_bytes(k->c.n, k->cap));
    ps_cir_attach(&k->c, k->values, k->lu, k->cap);
    return PS_OK;
}

static void grow(circuit *k)
{
    const int32_t n = k->c.n, full = n * (n + 1) / 2;
    k->cap = 2 * k->cap < full ? 2 * k->cap : full;
    free(k->lu);
    k->lu = malloc(ps_lu_bytes(n, k->cap));
    ps_cir_attach_lu(&k->c, k->lu, k->cap);
    k->grows++;
}

/* Call an analysis, enlarging the LU block as often as it asks. */
#define WITH_ROOM(call)                     \
    do                                      \
    {                                       \
        while ((s = (call)) == PS_ERR_SPACE) \
            grow(k);                        \
    } while (0)

static ps_status op(circuit *k)
{
    ps_status s = prepare(k);
    if (s == PS_OK)
        WITH_ROOM(ps_cir_op(&k->c));
    return s;
}

static ps_status run(circuit *k)
{
    for (;;)
    {
        const ps_status s = ps_cir_run(&k->c, 64, NULL);
        if (s == PS_ERR_SPACE)
            grow(k);
        else if (s != PS_PENDING)
            return s;
    }
}

static ps_status dc(circuit *k, int source, double start, double stop, int points)
{
    ps_status s = prepare(k);
    free(k->out);
    k->out = malloc((size_t)points * (size_t)k->c.probes * sizeof(float));
    if (s == PS_OK)
        WITH_ROOM(ps_cir_dc(&k->c, source, start, stop, points, k->out));
    return s == PS_OK ? run(k) : s;
}

static ps_status tran(circuit *k, double stop, int points, double hmax, int uic)
{
    ps_status s = prepare(k);
    free(k->out);
    k->out = malloc((size_t)points * (size_t)k->c.probes * sizeof(float));
    if (s == PS_OK)
        WITH_ROOM(ps_cir_tran(&k->c, stop, points, hmax, uic, k->out));
    return s == PS_OK ? run(k) : s;
}

static double trace(const circuit *k, int probe, int i)
{
    return (double)k->out[probe * k->c.points + i];
}

static void add(circuit *k, int e, ps_el_kind kind, int32_t a, int32_t b, double value)
{
    const int32_t nodes[2] = {a, b};
    double values[2] = {value, 0.0};
    const int count = (kind == PS_EL_C || kind == PS_EL_L) ? 2 : 1;
    CHECK(ps_cir_element(&k->c, e, kind, nodes, 2, values, count, -1) == PS_OK);
}

static void add_n(circuit *k, int e, ps_el_kind kind, const int32_t *nodes, int count, const double *values,
                  int nvalues, int32_t ctrl)
{
    CHECK(ps_cir_element(&k->c, e, kind, nodes, count, values, nvalues, ctrl) == PS_OK);
}

static double v(const circuit *k, int node)
{
    return ps_cir_voltage(&k->c, node);
}

static void test_divider_and_sources(void)
{
    circuit k;
    circuit_new(&k, 3, 3, 0);
    add(&k, 0, PS_EL_V, 1, 0, 10.0);
    add(&k, 1, PS_EL_R, 1, 2, 1e3);
    add(&k, 2, PS_EL_R, 2, 0, 3e3);
    CHECK(op(&k) == PS_OK);
    NEAR(v(&k, 2), 7.5, 1e-12);
    NEAR(ps_cir_current(&k.c, 0, 0), -2.5e-3, 1e-12); /* into + of a source that supplies */
    NEAR(ps_cir_current(&k.c, 1, 0), 2.5e-3, 1e-12);
    NEAR(ps_cir_current(&k.c, 1, 1), -2.5e-3, 1e-12);
    CHECK(k.c.iterations == 1); /* linear: one solve */
    circuit_free(&k);

    /* A current source pushes its current out of its - terminal. */
    circuit_new(&k, 2, 2, 0);
    add(&k, 0, PS_EL_I, 0, 1, 1e-3);
    add(&k, 1, PS_EL_R, 1, 0, 1e3);
    CHECK(op(&k) == PS_OK);
    NEAR(v(&k, 1), 1.0, 1e-7); /* 1e-3 is stored as float32 */
    circuit_free(&k);
}

static void test_controlled_sources(void)
{
    /* V1 = 1 V across 1k; E x5, G 2 mS, F x3 and H 2k of I(V1) into 1k loads. */
    circuit k;
    circuit_new(&k, 6, 10, 0);
    add(&k, 0, PS_EL_V, 1, 0, 1.0);
    add(&k, 1, PS_EL_R, 1, 0, 1e3);
    const int32_t e_nodes[4] = {2, 0, 1, 0}, g_nodes[4] = {3, 0, 1, 0}, f_nodes[2] = {4, 0}, h_nodes[2] = {5, 0};
    const double five = 5.0, gm = 2e-3, three = 3.0, r = 2e3;
    add_n(&k, 2, PS_EL_E, e_nodes, 4, &five, 1, -1);
    add_n(&k, 3, PS_EL_G, g_nodes, 4, &gm, 1, -1);
    add_n(&k, 4, PS_EL_F, f_nodes, 2, &three, 1, 0);
    add_n(&k, 5, PS_EL_H, h_nodes, 2, &r, 1, 0);
    for (int i = 0; i < 4; i++)
        add(&k, 6 + i, PS_EL_R, 2 + i, 0, 1e3);
    CHECK(op(&k) == PS_OK);
    NEAR(v(&k, 2), 5.0, 1e-12);
    NEAR(v(&k, 3), -2.0, 1e-7);  /* gm = 2e-3 is stored as float32 */
    NEAR(v(&k, 4), 3.0, 1e-12);  /* I(V1) = -1 mA: F sinks -3 mA from node 4 */
    NEAR(v(&k, 5), -2.0, 1e-12);
    NEAR(ps_cir_current(&k.c, 3, 0), 2e-3, 1e-7); /* into G at +: gm V1 flows + to - */
    NEAR(ps_cir_current(&k.c, 4, 0), -3e-3, 1e-12);
    /* F controlled by an element without a branch is refused, by name. */
    add_n(&k, 4, PS_EL_F, f_nodes, 2, &three, 1, 1);
    CHECK(prepare(&k) == PS_ERR_ARGUMENT && k.c.error_element == 4);
    circuit_free(&k);
}

static void test_opamp(void)
{
    for (int finite = 0; finite < 2; finite++)
    {
        const double gain = finite ? 1e5 : 0.0;
        circuit k;
        circuit_new(&k, 4, 4, 0);
        add(&k, 0, PS_EL_V, 1, 0, 1.0);
        add(&k, 1, PS_EL_R, 1, 2, 1e3);
        add(&k, 2, PS_EL_R, 2, 3, 1e4);
        const int32_t nodes[3] = {0, 2, 3};
        add_n(&k, 3, PS_EL_OPAMP, nodes, 3, &gain, 1, -1);
        CHECK(op(&k) == PS_OK);
        /* Inverting: -R2/R1, reduced by the loop gain when finite. */
        NEAR(v(&k, 3), finite ? -10.0 / (1.0 + 11.0 / gain) : -10.0, 1e-9);
        NEAR(ps_cir_current(&k.c, 3, 2), -ps_cir_current(&k.c, 2, 1), 1e-12);
        circuit_free(&k);
    }
    /* Non-inverting x4. */
    circuit k;
    circuit_new(&k, 4, 4, 0);
    add(&k, 0, PS_EL_V, 1, 0, 0.5);
    add(&k, 1, PS_EL_R, 2, 0, 1e3);
    add(&k, 2, PS_EL_R, 3, 2, 3e3);
    const int32_t nodes[3] = {1, 2, 3};
    const double ideal = 0.0;
    add_n(&k, 3, PS_EL_OPAMP, nodes, 3, &ideal, 1, -1);
    CHECK(op(&k) == PS_OK);
    NEAR(v(&k, 3), 2.0, 1e-12);
    circuit_free(&k);
}

/* V across R in series with a diode: the diode voltage by bisection. */
static double diode_bisect(double supply, double r, double is, double n)
{
    double lo = -fabs(supply) - 1.0, hi = fabs(supply) + 1.0;
    for (int i = 0; i < 200; i++)
    {
        const double vd = 0.5 * (lo + hi);
        const double f = (supply - vd) / r - is * (exp(vd / (n * VT)) - 1.0) - 1e-12 * vd;
        if (f > 0)
            lo = vd;
        else
            hi = vd;
    }
    return 0.5 * (lo + hi);
}

static void test_diode(void)
{
    circuit k;
    circuit_new(&k, 3, 3, 1);
    add(&k, 0, PS_EL_V, 1, 0, 5.0);
    add(&k, 1, PS_EL_R, 1, 2, 1e3);
    const int32_t nodes[2] = {2, 0};
    const double d[2] = {1e-14, 1.0};
    add_n(&k, 2, PS_EL_D, nodes, 2, d, 2, -1);
    CHECK(op(&k) == PS_OK);
    /* The device models use float32 exponentials: about 7 digits. */
    NEAR(v(&k, 2), diode_bisect(5.0, 1e3, 1e-14, 1.0), 1e-7);
    NEAR(ps_cir_current(&k.c, 2, 0), ps_cir_current(&k.c, 1, 0), 1e-6);
    CHECK(k.c.iterations < 30);
    /* Reverse biased: only the saturation current flows. */
    add(&k, 0, PS_EL_V, 1, 0, -5.0);
    CHECK(op(&k) == PS_OK);
    NEAR(ps_cir_current(&k.c, 2, 0), -1e-14 - 5e-12, 1e-6);
    /* DC sweep of the supply: every point against bisection. */
    CHECK(ps_cir_probe(&k.c, 0, PS_PROBE_V, 2, 0) == PS_OK);
    CHECK(dc(&k, 0, -2.0, 10.0, 25) == PS_OK);
    for (int i = 0; i < 25; i++)
        NEAR(trace(&k, 0, i), diode_bisect(-2.0 + 0.5 * i, 1e3, 1e-14, 1.0), 1e-6);
    circuit_free(&k);
}

static void test_bjt(void)
{
    for (int pnp = 0; pnp < 2; pnp++)
    {
        const double sign = pnp ? -1.0 : 1.0;
        circuit k;
        circuit_new(&k, 4, 4, 0);
        add(&k, 0, PS_EL_V, 1, 0, 10.0 * sign);
        add(&k, 1, PS_EL_R, 1, 2, 100e3);
        add(&k, 2, PS_EL_R, 1, 3, 1e3);
        const int32_t nodes[3] = {3, 2, 0};
        const double q[4] = {1e-15, 100.0, 1.0, 0.0};
        add_n(&k, 3, pnp ? PS_EL_PNP : PS_EL_NPN, nodes, 3, q, 4, -1);
        CHECK(op(&k) == PS_OK);
        const double ib = ps_cir_current(&k.c, 3, 1), ic = ps_cir_current(&k.c, 3, 0);
        NEAR(ib, ps_cir_current(&k.c, 1, 1) * -1.0, 1e-9); /* KCL at the base */
        NEAR(ic, ps_cir_current(&k.c, 2, 0), 1e-9);        /* and at the collector */
        NEAR(ps_cir_current(&k.c, 3, 2), -(ic + ib), 1e-12);
        NEAR(ic / ib, 100.0, 1e-3); /* forward active */
        CHECK(sign * v(&k, 3) > 0.5 && sign * v(&k, 3) < 9.5);
        static double npn_vc;
        if (!pnp)
            npn_vc = v(&k, 3);
        else
            NEAR(v(&k, 3), -npn_vc, 1e-9); /* the PNP mirrors it */
        circuit_free(&k);
    }
}

static void test_mosfet(void)
{
    for (int p = 0; p < 2; p++)
        for (int linear = 0; linear < 2; linear++)
        {
            const double sign = p ? -1.0 : 1.0;
            circuit k;
            circuit_new(&k, 4, 4, 0);
            add(&k, 0, PS_EL_V, 1, 0, 10.0 * sign);
            add(&k, 1, PS_EL_R, 1, 2, 1e3);
            add(&k, 2, PS_EL_V, 3, 0, 3.0 * sign);
            const int32_t nodes[3] = {2, 3, 0};
            const double m[3] = {1.0 * sign, linear ? 1e-2 : 1e-3, 0.0};
            add_n(&k, 3, p ? PS_EL_PMOS : PS_EL_NMOS, nodes, 3, m, 3, -1);
            CHECK(op(&k) == PS_OK);
            /* Saturation: id = KP/2 (vgs - vto)^2 = 2 mA, so Vd = 8 V.
             * Linear: 5 vd^2 - 21 vd + 10 = 0. */
            const double want = linear ? (21.0 - sqrt(441.0 - 200.0)) / 10.0 : 8.0;
            NEAR(v(&k, 2), want * sign, 1e-6);
            NEAR(ps_cir_current(&k.c, 3, 0), ps_cir_current(&k.c, 1, 0), 1e-9);
            NEAR(ps_cir_current(&k.c, 3, 1), 0.0, 1e-15);
            circuit_free(&k);
        }
}

static void test_switch(void)
{
    for (int on = 0; on < 2; on++)
    {
        circuit k;
        circuit_new(&k, 4, 4, 0);
        add(&k, 0, PS_EL_V, 1, 0, 10.0);
        add(&k, 1, PS_EL_V, 3, 0, on ? 5.0 : 0.0);
        const int32_t nodes[4] = {1, 2, 3, 0};
        const double s[4] = {1.0, 1e6, 2.5, 0.1};
        add_n(&k, 2, PS_EL_SW, nodes, 4, s, 4, -1);
        add(&k, 3, PS_EL_R, 2, 0, 1e3);
        CHECK(op(&k) == PS_OK);
        NEAR(v(&k, 2), on ? 10.0 * 1e3 / 1001.0 : 10.0 * 1e3 / (1e6 + 1e3), 1e-9);
        circuit_free(&k);
    }
}

static void test_errors(void)
{
    circuit k;
    circuit_new(&k, 4, 3, 1);
    const int32_t nodes[2] = {1, 0}, far[2] = {1, 9};
    const double zero = 0.0, one = 1.0;
    CHECK(ps_cir_element(&k.c, 0, PS_EL_R, nodes, 2, &zero, 1, -1) == PS_ERR_ARGUMENT);
    CHECK(ps_cir_element(&k.c, 0, PS_EL_R, far, 2, &one, 1, -1) == PS_ERR_ARGUMENT);
    CHECK(ps_cir_element(&k.c, 0, PS_EL_R, nodes, 3, &one, 1, -1) == PS_ERR_ARGUMENT);
    CHECK(ps_cir_element(&k.c, 3, PS_EL_R, nodes, 2, &one, 1, -1) == PS_ERR_ARGUMENT);
    CHECK(ps_cir_probe(&k.c, 0, PS_PROBE_I, 0, 0) == PS_ERR_ARGUMENT); /* element not set yet */
    add(&k, 0, PS_EL_V, 1, 0, 1.0);
    add(&k, 1, PS_EL_C, 1, 2, 1e-6);
    CHECK(prepare(&k) == PS_ERR_ARGUMENT && k.c.error_element == 2); /* element 2 never set */
    add(&k, 2, PS_EL_R, 2, 2, 1.0);
    CHECK(prepare(&k) == PS_ERR_UNCONNECTED && k.c.error_node == 3);
    circuit_free(&k);

    /* Node 2 sits behind a capacitor: no DC path, named. */
    circuit_new(&k, 3, 2, 0);
    add(&k, 0, PS_EL_V, 1, 0, 1.0);
    add(&k, 1, PS_EL_C, 1, 2, 1e-6);
    CHECK(op(&k) == PS_ERR_SINGULAR && k.c.error_node == 2);
    circuit_free(&k);

    /* Two voltage sources in parallel: their branch is named. */
    circuit_new(&k, 2, 2, 0);
    add(&k, 0, PS_EL_V, 1, 0, 1.0);
    add(&k, 1, PS_EL_V, 1, 0, 2.0);
    CHECK(op(&k) == PS_ERR_SINGULAR && k.c.error_element >= 0);
    circuit_free(&k);

    /* Waveforms only on sources, with the right number of values. */
    circuit_new(&k, 2, 2, 0);
    add(&k, 0, PS_EL_V, 1, 0, 1.0);
    add(&k, 1, PS_EL_R, 1, 0, 1.0);
    const double pulse[7] = {0, 1, 0, 0, 0, 1, 2}, pwl[4] = {1, 0, 0, 1};
    CHECK(ps_cir_wave(&k.c, 1, PS_WAVE_PULSE, pulse, 7) == PS_ERR_ARGUMENT);
    CHECK(ps_cir_wave(&k.c, 0, PS_WAVE_PULSE, pulse, 6) == PS_ERR_ARGUMENT);
    CHECK(ps_cir_wave(&k.c, 0, PS_WAVE_PWL, pwl, 4) == PS_ERR_ARGUMENT); /* time goes back */
    CHECK(ps_cir_wave(&k.c, 0, PS_WAVE_PULSE, pulse, 7) == PS_OK);
    CHECK(ps_cir_run(&k.c, 1, NULL) == PS_ERR_STATE);
    circuit_free(&k);
}

/* ------------------------------------------------------------------------ */
/* Transients                                                               */
/* ------------------------------------------------------------------------ */

static void test_rc_step(void)
{
    /* 1 V step into 1k and 1 uF: v = 1 - exp(-t / 1 ms), i = exp(-t / 1 ms) / 1k. */
    circuit k;
    circuit_new(&k, 3, 3, 2);
    add(&k, 0, PS_EL_V, 1, 0, 0.0);
    add(&k, 1, PS_EL_R, 1, 2, 1e3);
    add(&k, 2, PS_EL_C, 2, 0, 1e-6);
    const double pulse[7] = {0.0, 1.0, 0.0, 1e-9, 1e-9, 1.0, 0.0};
    CHECK(ps_cir_wave(&k.c, 0, PS_WAVE_PULSE, pulse, 7) == PS_OK);
    CHECK(ps_cir_probe(&k.c, 0, PS_PROBE_V, 2, 0) == PS_OK);
    CHECK(ps_cir_probe(&k.c, 1, PS_PROBE_I, 2, 0) == PS_OK);
    CHECK(tran(&k, 5e-3, 101, 0.0, 0) == PS_OK);
    double worst = 0.0, worst_i = 0.0;
    for (int i = 0; i < 101; i++)
    {
        const double t = 5e-3 * i / 100.0;
        worst = fmax(worst, fabs(trace(&k, 0, i) - (1.0 - exp(-t / 1e-3))));
        if (i > 0)
            worst_i = fmax(worst_i, fabs(trace(&k, 1, i) * 1e3 - exp(-t / 1e-3)));
    }
    CHECK(worst < 2e-3);
    CHECK(worst_i < 5e-3);
    CHECK(k.c.done == 101 && k.c.steps < 400);
    printf("  rc step: max error %.2e V, %d steps, %d rejected, %d iterations\n", worst, (int)k.c.steps,
           (int)k.c.rejected, (int)k.c.iterations);
    circuit_free(&k);
}

static void test_rl_and_lc(void)
{
    /* 1 V step into 10 ohm and 10 mH: i = 0.1 (1 - exp(-t / 1 ms)). */
    circuit k;
    circuit_new(&k, 3, 3, 1);
    add(&k, 0, PS_EL_V, 1, 0, 0.0);
    add(&k, 1, PS_EL_R, 1, 2, 10.0);
    add(&k, 2, PS_EL_L, 2, 0, 10e-3);
    const double pwl[4] = {0.0, 0.0, 1e-9, 1.0};
    CHECK(ps_cir_wave(&k.c, 0, PS_WAVE_PWL, pwl, 4) == PS_OK);
    CHECK(ps_cir_probe(&k.c, 0, PS_PROBE_I, 2, 0) == PS_OK);
    CHECK(tran(&k, 5e-3, 51, 0.0, 0) == PS_OK);
    double worst = 0.0;
    for (int i = 0; i < 51; i++)
        worst = fmax(worst, fabs(trace(&k, 0, i) - 0.1 * (1.0 - exp(-1e-4 * i / 1e-3))));
    CHECK(worst < 2e-4);
    circuit_free(&k);

    /* LC tank from 1 V on the capacitor (uic): v = cos(t / sqrt(LC)). */
    circuit_new(&k, 2, 2, 1);
    const int32_t nodes[2] = {1, 0};
    const double cap[2] = {1e-6, 1.0}, ind[2] = {1e-3, 0.0};
    add_n(&k, 0, PS_EL_C, nodes, 2, cap, 2, -1);
    add_n(&k, 1, PS_EL_L, nodes, 2, ind, 2, -1);
    CHECK(ps_cir_probe(&k.c, 0, PS_PROBE_V, 1, 0) == PS_OK);
    CHECK(tran(&k, 1e-3, 1001, 0.0, 1) == PS_OK);
    worst = 0.0;
    const double w = 1.0 / sqrt(1e-9);
    for (int i = 1; i < 1001; i++)
        worst = fmax(worst, fabs(trace(&k, 0, i) - cos(w * 1e-6 * i)));
    CHECK(worst < 0.03);
    printf("  lc tank: max error %.3f over 5 periods, %d steps\n", worst, (int)k.c.steps);
    circuit_free(&k);
}

static void test_uic_with_sources(void)
{
    /* Starting from zero still drives the sources: 5 V into 1k and 1 uF
     * charges as 5 (1 - exp(-t / 1 ms)) from an empty capacitor. */
    circuit k;
    circuit_new(&k, 3, 3, 1);
    add(&k, 0, PS_EL_V, 1, 0, 5.0);
    add(&k, 1, PS_EL_R, 1, 2, 1e3);
    add(&k, 2, PS_EL_C, 2, 0, 1e-6);
    CHECK(ps_cir_probe(&k.c, 0, PS_PROBE_V, 2, 0) == PS_OK);
    CHECK(tran(&k, 5e-3, 51, 0.0, 1) == PS_OK);
    double worst = 0.0;
    for (int i = 1; i < 51; i++)
        worst = fmax(worst, fabs(trace(&k, 0, i) - 5.0 * (1.0 - exp(-1e-4 * i / 1e-3))));
    CHECK(worst < 0.01);
    circuit_free(&k);
}

static void test_sine_lowpass(void)
{
    /* 1 kHz through R = 1k, C = 1/(2 pi 1e6): gain 1/sqrt(2), lag 45 degrees. */
    circuit k;
    circuit_new(&k, 3, 3, 1);
    add(&k, 0, PS_EL_V, 1, 0, 0.0);
    add(&k, 1, PS_EL_R, 1, 2, 1e3);
    add(&k, 2, PS_EL_C, 2, 0, 1.0 / (2.0 * PI * 1e6));
    const double sine[6] = {0.0, 1.0, 1e3, 0.0, 0.0, 0.0};
    CHECK(ps_cir_wave(&k.c, 0, PS_WAVE_SIN, sine, 6) == PS_OK);
    CHECK(ps_cir_probe(&k.c, 0, PS_PROBE_V, 2, 0) == PS_OK);
    CHECK(tran(&k, 10e-3, 2001, 0.0, 0) == PS_OK);
    double worst = 0.0;
    for (int i = 1800; i < 2001; i++) /* the last cycle, transient gone */
    {
        const double t = 10e-3 * i / 2000.0;
        worst = fmax(worst, fabs(trace(&k, 0, i) - sin(2.0 * PI * 1e3 * t - PI / 4.0) / sqrt(2.0)));
    }
    CHECK(worst < 5e-3);
    circuit_free(&k);
}

static void test_rectifier(void)
{
    /* 10 V, 50 Hz half-wave rectifier into 1k || 100 uF. */
    circuit k;
    circuit_new(&k, 3, 4, 2);
    add(&k, 0, PS_EL_V, 1, 0, 0.0);
    const double sine[6] = {0.0, 10.0, 50.0, 0.0, 0.0, 0.0}, d[2] = {1e-14, 1.0};
    CHECK(ps_cir_wave(&k.c, 0, PS_WAVE_SIN, sine, 6) == PS_OK);
    const int32_t dn[2] = {1, 2};
    add_n(&k, 1, PS_EL_D, dn, 2, d, 2, -1);
    add(&k, 2, PS_EL_R, 2, 0, 1e3);
    add(&k, 3, PS_EL_C, 2, 0, 100e-6);
    CHECK(ps_cir_probe(&k.c, 0, PS_PROBE_V, 2, 0) == PS_OK);
    CHECK(ps_cir_probe(&k.c, 1, PS_PROBE_I, 1, 0) == PS_OK);
    CHECK(tran(&k, 100e-3, 501, 0.0, 0) == PS_OK);
    double top = -1e9, bottom = 1e9, reverse = 0.0;
    for (int i = 400; i < 501; i++)
    {
        top = fmax(top, trace(&k, 0, i));
        bottom = fmin(bottom, trace(&k, 0, i));
        reverse = fmin(reverse, trace(&k, 1, i));
    }
    CHECK(top > 9.1 && top < 9.5);                   /* the peak less one diode drop */
    CHECK(top - bottom > 1.2 && top - bottom < 1.9); /* ripple below I / (f C) = 1.86 V */
    CHECK(reverse > -1e-9);                          /* the diode never conducts backwards */
    printf("  rectifier: %.3f V peak, %.3f V ripple, %d steps, %d rejected\n", top, top - bottom,
           (int)k.c.steps, (int)k.c.rejected);
    circuit_free(&k);
}

static void test_mos_inverter(void)
{
    /* CMOS inverter driven by a pulse: output swings rail to rail. */
    circuit k;
    circuit_new(&k, 4, 5, 2);
    add(&k, 0, PS_EL_V, 1, 0, 5.0);
    add(&k, 1, PS_EL_V, 2, 0, 0.0);
    const double pulse[7] = {0.0, 5.0, 1e-6, 1e-7, 1e-7, 2e-6, 4e-6};
    CHECK(ps_cir_wave(&k.c, 1, PS_WAVE_PULSE, pulse, 7) == PS_OK);
    const int32_t pn[3] = {3, 2, 1}, nn[3] = {3, 2, 0};
    const double pm[3] = {-1.0, 1e-3, 0.01}, nm[3] = {1.0, 1e-3, 0.01};
    add_n(&k, 2, PS_EL_PMOS, pn, 3, pm, 3, -1);
    add_n(&k, 3, PS_EL_NMOS, nn, 3, nm, 3, -1);
    add(&k, 4, PS_EL_C, 3, 0, 10e-12);
    CHECK(ps_cir_probe(&k.c, 0, PS_PROBE_V, 3, 0) == PS_OK);
    CHECK(ps_cir_probe(&k.c, 1, PS_PROBE_V, 2, 0) == PS_OK);
    CHECK(tran(&k, 8e-6, 161, 0.0, 0) == PS_OK);
    NEAR(trace(&k, 0, 0), 5.0, 1e-6);  /* input low: output high */
    NEAR(trace(&k, 0, 50), 0.0, 1e-6); /* t = 2.5 us: input high */
    NEAR(trace(&k, 0, 110), 0.0, 1e-6); /* t = 5.5 us: second pulse */
    NEAR(trace(&k, 0, 150), 5.0, 1e-6); /* t = 7.5 us: low again */
    circuit_free(&k);
}

/* ------------------------------------------------------------------------ */
/* Size and memory                                                          */
/* ------------------------------------------------------------------------ */

static void test_ladder_and_growth(void)
{
    /* 50 nodes: V = 49 V into a chain of 49 resistors, V(k) = 50 - k. With
     * a deliberately tiny LU block the first factorization asks for more. */
    for (int tiny = 0; tiny < 2; tiny++)
    {
        circuit k;
        force_cap = tiny ? 8 : 0;
        circuit_new(&k, 50, 50, 0);
        add(&k, 0, PS_EL_V, 1, 0, 49.0);
        for (int i = 1; i < 49; i++)
            add(&k, i, PS_EL_R, i, i + 1, 1e3);
        add(&k, 49, PS_EL_R, 49, 0, 1e3);
        CHECK(op(&k) == PS_OK);
        for (int node = 1; node < 50; node++)
            NEAR(v(&k, node), 50.0 - node, 1e-12);
        CHECK(tiny ? k.grows > 0 : k.grows == 0);
        if (!tiny)
            printf("  50-node ladder: %d unknowns, %d entries, L+U %d of %d, blocks %zu + %zu + %zu + %zu bytes\n",
                   (int)k.c.n, (int)k.c.nnz, (int)(k.c.lu.lnz + k.c.lu.unz), (int)(2 * k.cap),
                   ps_cir_bytes(50, 50, 32 * 50, 0), ps_cir_index_bytes(&k.c), ps_cir_value_bytes(&k.c),
                   ps_lu_bytes(k.c.n, k.cap));
        circuit_free(&k);
    }
    force_cap = 0;
}

static void test_slices_and_cancel(void)
{
    /* Running a step at a time gives the same answer; cancel stops it. */
    float whole[41];
    for (int pass = 0; pass < 3; pass++)
    {
        circuit k;
        circuit_new(&k, 3, 3, 1);
        add(&k, 0, PS_EL_V, 1, 0, 0.0);
        add(&k, 1, PS_EL_R, 1, 2, 1e3);
        add(&k, 2, PS_EL_C, 2, 0, 1e-6);
        const double sine[6] = {0.0, 1.0, 500.0, 0.0, 0.0, 0.0};
        CHECK(ps_cir_wave(&k.c, 0, PS_WAVE_SIN, sine, 6) == PS_OK);
        CHECK(ps_cir_probe(&k.c, 0, PS_PROBE_V, 2, 0) == PS_OK);
        CHECK(prepare(&k) == PS_OK);
        k.out = malloc(41 * sizeof(float));
        CHECK(ps_cir_tran(&k.c, 4e-3, 41, 0.0, 0, k.out) == PS_OK);
        ps_control ctl = {0, 0, 0};
        ps_status s = PS_PENDING;
        int calls = 0;
        while (s == PS_PENDING)
        {
            s = ps_cir_run(&k.c, pass == 0 ? 100000 : 1, &ctl);
            calls++;
            if (pass == 2 && calls == 10)
                ctl.cancel = 1;
        }
        if (pass == 0)
            memcpy(whole, k.out, sizeof(whole));
        else if (pass == 1)
        {
            CHECK(s == PS_OK && calls > 40 && ctl.done == 41 && ctl.total == 41);
            CHECK(memcmp(whole, k.out, sizeof(whole)) == 0);
        }
        else
            CHECK(s == PS_CANCELLED && ctl.done < 41);
        circuit_free(&k);
    }
}

int main(void)
{
    test_lu_against_dense();
    test_divider_and_sources();
    test_controlled_sources();
    test_opamp();
    test_diode();
    test_bjt();
    test_mosfet();
    test_switch();
    test_errors();
    test_rc_step();
    test_rl_and_lc();
    test_uic_with_sources();
    test_sine_lowpass();
    test_rectifier();
    test_mos_inverter();
    test_ladder_and_growth();
    test_slices_and_cancel();
    printf("%s: %d checks, %d failures\n", failures ? "FAIL" : "PASS", checks, failures);
    return failures ? 1 : 0;
}
