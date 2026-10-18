/*
 * Host tests for the picosolve kernel: closed-form beam cases, solver
 * checks against dense arithmetic, and invariants every model must satisfy.
 * Run tests/run-tests.sh from the picosolve folder.
 */
#include "../core/dense.h"
#include "../core/order.h"
#include "../core/skyline.h"
#include "../fe/beam.h"
#include "../fe/model.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int failures = 0, checks = 0;

#define CHECK(cond)                                                    \
    do                                                                 \
    {                                                                  \
        checks++;                                                      \
        if (!(cond))                                                   \
        {                                                              \
            failures++;                                                \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);     \
        }                                                              \
    } while (0)

static int near(double got, double want, double tolerance)
{
    double scale = fabs(want) > 1.0 ? fabs(want) : 1.0;
    return fabs(got - want) <= tolerance * scale;
}

#define NEAR(got, want)                                                          \
    do                                                                           \
    {                                                                            \
        double g_ = (got), w_ = (want);                                          \
        checks++;                                                                \
        if (!near(g_, w_, 1e-9))                                                 \
        {                                                                        \
            failures++;                                                          \
            printf("FAIL %s:%d: %s = %.12g, want %.12g\n", __FILE__, __LINE__, \
                   #got, g_, w_);                                                \
        }                                                                        \
    } while (0)

/* Test model owning its three blocks. */
typedef struct
{
    ps_model m;
    void *model_block, *index_block, *value_block;
} beam;

static void beam_new(beam *b, int nodes, int elements, int sections, int loads, int cases)
{
    memset(b, 0, sizeof(*b));
    b->model_block = malloc(ps_model_bytes(nodes, elements, sections, loads));
    CHECK(ps_model_init(&b->m, b->model_block, nodes, elements, sections, loads, cases) == PS_OK);
}

/* Precision tried first; single falls back to double, as the binding does. */
static ps_precision first_precision = PS_DOUBLE;
static int escalations = 0;

static ps_status beam_solve(beam *b)
{
    free(b->index_block);
    free(b->value_block);
    b->index_block = malloc(ps_model_index_bytes(&b->m));
    b->value_block = NULL;
    ps_status status = ps_model_prepare(&b->m, b->index_block);
    if (status != PS_OK)
        return status;
    b->value_block = malloc(ps_model_value_bytes(&b->m, first_precision) + 8);
    status = ps_model_solve(&b->m, b->value_block, first_precision, NULL);
    if (status == PS_ERR_ACCURACY)
    {
        escalations++;
        free(b->value_block);
        b->value_block = malloc(ps_model_value_bytes(&b->m, PS_DOUBLE) + 8);
        status = ps_model_solve(&b->m, b->value_block, PS_DOUBLE, NULL);
    }
    return status;
}

static void beam_free(beam *b)
{
    free(b->model_block);
    free(b->index_block);
    free(b->value_block);
}

/* Uniform spans: nodes at i * length / elements, one section, given supports. */
static void uniform(beam *b, int elements, double length, double ei, int loads, int cases)
{
    beam_new(b, elements + 1, elements, 1, loads, cases);
    for (int i = 0; i <= elements; i++)
        ps_model_node(&b->m, i, length * i / elements);
    for (int e = 0; e < elements; e++)
        ps_model_element(&b->m, e, e, e + 1, 0, 0);
    ps_model_section(&b->m, 0, ei, 1.0);
}

static double deflection(beam *b, int c, int node)
{
    return ps_model_displacement(&b->m, c, node, PS_UY);
}

static double reaction(beam *b, int c, int node, int d)
{
    double r[2];
    CHECK(ps_model_reaction(&b->m, c, node, r) == PS_OK);
    return r[d];
}

static double section(beam *b, int c, int e, double x, int what)
{
    double out[4];
    CHECK(ps_model_section_at(&b->m, c, e, x, out) == PS_OK);
    return out[what];
}
enum
{
    SHEAR,
    MOMENT,
    SLOPE,
    DEFLECTION
};

/*
 * Invariants for any solved model: vertical and moment equilibrium of the
 * whole beam, and the exact section curve of every element meeting the
 * solved displacements at both of its nodes.
 */
static void invariants(beam *b)
{
    ps_model *m = &b->m;
    for (int c = 0; c < m->cases; c++)
    {
        double fy = 0.0, mz = 0.0, scale = 0.0;
        for (int i = 0; i < m->nodes; i++)
        {
            double r[2];
            ps_model_reaction(m, c, i, r);
            fy += r[0];
            mz += r[1] + r[0] * m->x[i];
            scale += fabs(r[0]) + fabs(r[1]);
        }
        for (int k = 0; k < m->load_count; k++)
        {
            const ps_load *l = &m->load[k];
            if (l->load_case != c || l->kind == PS_LOAD_SETTLE)
                continue;
            double x0 = l->kind == PS_LOAD_NODE ? m->x[l->target] : m->x[m->connect[2 * l->target]];
            double force = 0.0, moment = 0.0;
            if (l->kind == PS_LOAD_NODE)
            {
                if (l->dof == 0)
                    force = l->w1;
                else
                    moment = l->w1;
            }
            else if (l->kind == PS_LOAD_POINT)
            {
                force = l->w1;
                x0 += l->a;
            }
            else if (l->kind == PS_LOAD_MOMENT)
                moment = l->w1;
            else
            {
                double span = l->b - l->a;
                force = 0.5 * (l->w1 + l->w2) * span;
                double centroid = (l->w1 + l->w2) != 0.0
                                      ? span * (l->w1 + 2.0 * l->w2) / (3.0 * (l->w1 + l->w2))
                                      : 0.5 * span;
                x0 += l->a + centroid;
            }
            fy += force;
            mz += moment + force * x0;
            scale += fabs(force) + fabs(moment);
        }
        if (scale == 0.0)
            scale = 1.0;
        checks += 2;
        if (fabs(fy) > 1e-9 * scale || fabs(mz) > 1e-9 * scale * 100.0)
        {
            failures++;
            printf("FAIL equilibrium case %d: sum fy %.3g, sum mz %.3g\n", c, fy, mz);
        }
        /* Compare against the largest displacement along the beam, not zero. */
        double v_scale = 1e-300, t_scale = 1e-300;
        for (int e = 0; e < m->elements; e++)
        {
            double mid[4];
            double half = 0.5 * (m->x[m->connect[2 * e + 1]] - m->x[m->connect[2 * e]]);
            ps_model_section_at(m, c, e, half, mid);
            v_scale = fabs(mid[3]) > v_scale ? fabs(mid[3]) : v_scale;
            t_scale = fabs(mid[2]) > t_scale ? fabs(mid[2]) : t_scale;
        }
        for (int i = 0; i < m->nodes; i++)
        {
            double v = fabs(ps_model_displacement(m, c, i, PS_UY));
            double t = fabs(ps_model_displacement(m, c, i, PS_RZ));
            v_scale = v > v_scale ? v : v_scale;
            t_scale = t > t_scale ? t : t_scale; /* NaN (free hinge) is skipped */
        }
        for (int e = 0; e < m->elements; e++)
        {
            int n2 = m->connect[2 * e + 1];
            double length = m->x[n2] - m->x[m->connect[2 * e]];
            double v2 = ps_model_displacement(m, c, n2, PS_UY);
            double end[4];
            ps_model_section_at(m, c, e, length, end);
                        checks++;
            if (fabs(end[3] - v2) > 1e-9 * v_scale)
            {
                failures++;
                printf("FAIL element %d case %d: curve ends at %.12g, node at %.12g\n", e, c, end[3], v2);
            }
            if (!(m->release[e] & PS_RELEASE_END))
            {
                double t2 = ps_model_displacement(m, c, n2, PS_RZ);
                checks++;
                if (fabs(end[2] - t2) > 1e-9 * t_scale)
                {
                    failures++;
                    printf("FAIL element %d case %d: slope ends at %.12g, node at %.12g\n", e, c, end[2], t2);
                }
            }
        }
    }
}

static void test_skyline_against_dense(void)
{
    enum
    {
        N = 40
    };
    static double a[N][N];
    static int32_t first[N];
    srand(7);
    for (int j = 0; j < N; j++)
        first[j] = j - rand() % 8 < 0 ? 0 : j - rand() % 8;
    memset(a, 0, sizeof(a));
    for (int j = 0; j < N; j++)
        for (int i = first[j]; i < j; i++)
            a[i][j] = a[j][i] = (rand() % 2000 - 1000) / 1000.0;
    for (int j = 0; j < N; j++)
    {
        double row = 0.0;
        for (int i = 0; i < N; i++)
            row += fabs(a[i][j]);
        a[j][j] = row + 1.0 + j; /* diagonally dominant, so positive definite */
    }
    uint32_t ptr[N + 1];
    for (int j = 0; j < N; j++)
        ptr[j] = (uint32_t)(j - first[j] + 1);
    uint32_t nnz = ps_sky_heights_finish(ptr, N);
    double *val = malloc(nnz * sizeof(double));
    ps_sky s = {N, ptr, val, PS_DOUBLE};
    ps_sky_zero(&s);
    for (int j = 0; j < N; j++)
        for (int i = first[j]; i <= j; i++)
        {
            int32_t d[2] = {i, j};
            double block[4] = {0.0, i == j ? 0.0 : a[i][j], 0.0, 0.0};
            if (i == j)
                ps_sky_add_diagonal(&s, j, a[j][j]);
            else
                ps_sky_add(&s, d, 2, block);
        }
    ps_factor_info info;
    CHECK(ps_sky_factor(&s, &info, NULL) == PS_OK);
    double b[N], x[N];
    for (int i = 0; i < N; i++)
        x[i] = b[i] = sin(i + 1.0);
    ps_sky_solve(&s, x);
    double worst = 0.0;
    for (int i = 0; i < N; i++)
    {
        double r = -b[i];
        for (int j = 0; j < N; j++)
            r += a[i][j] * x[j];
        if (fabs(r) > worst)
            worst = fabs(r);
    }
    CHECK(worst < 1e-12);
    free(val);

    /* A singular matrix fails at the DOF where it loses positive definiteness. */
    uint32_t p2[4] = {1, 2, 2};
    ps_sky_heights_finish(p2, 3);
    double v2[5];
    ps_sky s2 = {3, p2, v2, PS_DOUBLE};
    ps_sky_zero(&s2);
    int32_t d01[2] = {0, 1}, d12[2] = {1, 2};
    double spring[4] = {1.0, -1.0, -1.0, 1.0};
    ps_sky_add(&s2, d01, 2, spring);
    ps_sky_add(&s2, d12, 2, spring);
    CHECK(ps_sky_factor(&s2, &info, NULL) == PS_ERR_MECHANISM && info.failed_dof == 2);

    ps_control ctl = {1, 0, 0};
    ps_sky_zero(&s2);
    ps_sky_add_diagonal(&s2, 0, 1.0);
    CHECK(ps_sky_factor(&s2, &info, &ctl) == PS_CANCELLED);

    /* Single precision: same matrix, float accuracy; a singular one asks for double. */
    float *fval = malloc(nnz * sizeof(float));
    ps_sky f = {N, ptr, fval, PS_SINGLE};
    ps_sky_zero(&f);
    for (int j = 0; j < N; j++)
        for (int i = first[j]; i <= j; i++)
        {
            int32_t d[2] = {i, j};
            double block[4] = {0.0, i == j ? 0.0 : a[i][j], 0.0, 0.0};
            if (i == j)
                ps_sky_add_diagonal(&f, j, a[j][j]);
            else
                ps_sky_add(&f, d, 2, block);
        }
    CHECK(ps_sky_factor(&f, &info, NULL) == PS_OK);
    float fx[N];
    for (int i = 0; i < N; i++)
        fx[i] = (float)b[i];
    ps_sky_solve_single(&f, fx);
    double ferr = 0.0;
    for (int i = 0; i < N; i++)
        ferr = fabs((double)fx[i] - x[i]) > ferr ? fabs((double)fx[i] - x[i]) : ferr;
    CHECK(ferr < 1e-5);
    free(fval);
    float fv2[5];
    ps_sky f2 = {3, p2, fv2, PS_SINGLE};
    ps_sky_zero(&f2);
    ps_sky_add(&f2, d01, 2, spring);
    ps_sky_add(&f2, d12, 2, spring);
    CHECK(ps_sky_factor(&f2, &info, NULL) == PS_ERR_ACCURACY);
}

static void test_condense(void)
{
    /* Releasing theta2 of a beam gives the propped-cantilever stiffness 3EI/L^3. */
    double k[16], f[4] = {0.0, 0.0, 0.0, 0.0};
    ps_beam_stiffness(1.0, 2.0, k);
    CHECK(ps_condense(k, f, 4, 1u << 3) == PS_OK);
    NEAR(k[0], 3.0 / 8.0);
    NEAR(k[3 * 4 + 3], 0.0);
    double full[16], u[4] = {1.0, 0.0, 0.0, 0.0};
    ps_beam_stiffness(1.0, 2.0, full);
    CHECK(ps_recover(full, NULL, 4, 1u << 3, u) == PS_OK);
    NEAR(u[3], -1.5 / 2.0); /* pinned-end rotation -3 v / (2 L) */
}

static void test_rcm(void)
{
    /* A path numbered at random must come out as a chain. */
    enum
    {
        N = 30
    };
    int32_t label[N], xadj[N + 1], adj[2 * (N - 1)], perm[N], level[N];
    uint8_t mask[N];
    for (int i = 0; i < N; i++)
        label[i] = i;
    srand(3);
    for (int i = N - 1; i > 0; i--)
    {
        int j = rand() % (i + 1), t = label[i];
        label[i] = label[j];
        label[j] = t;
    }
    int degree[N] = {0};
    for (int i = 0; i + 1 < N; i++)
    {
        degree[label[i]]++;
        degree[label[i + 1]]++;
    }
    xadj[0] = 0;
    for (int i = 0; i < N; i++)
        xadj[i + 1] = xadj[i] + degree[i];
    int fill[N];
    for (int i = 0; i < N; i++)
        fill[i] = xadj[i];
    for (int i = 0; i + 1 < N; i++)
    {
        adj[fill[label[i]]++] = label[i + 1];
        adj[fill[label[i + 1]]++] = label[i];
    }
    ps_rcm(N, xadj, adj, perm, level, mask);
    int seen[N] = {0}, ok = 1;
    for (int i = 0; i < N; i++)
        seen[perm[i]]++;
    for (int i = 0; i < N; i++)
        ok = ok && seen[i] == 1;
    CHECK(ok);
    int position[N];
    for (int i = 0; i < N; i++)
        position[perm[i]] = i;
    int band = 0;
    for (int i = 0; i + 1 < N; i++)
    {
        int d = abs(position[label[i]] - position[label[i + 1]]);
        if (d > band)
            band = d;
    }
    CHECK(band == 1);
}

static const double L = 6.0, EI = 2.1e11 * 8.36e-5, W = -5e3, P = -12e3;

static void test_simply_supported_udl(void)
{
    for (int elements = 1; elements <= 4; elements += 3)
    {
        beam b;
        uniform(&b, elements, L, EI, elements, 1);
        ps_model_support(&b.m, 0, PS_UY);
        ps_model_support(&b.m, elements, PS_UY);
        for (int e = 0; e < elements; e++)
            ps_model_load(&b.m, PS_LOAD_LINE, 0, e, 0, 0.0, L / elements, W, W);
        CHECK(beam_solve(&b) == PS_OK);
        NEAR(reaction(&b, 0, 0, 0), -W * L / 2.0);
        double mid_e = elements == 1 ? 0 : 1, mid_x = elements == 1 ? L / 2.0 : L / 4.0;
        NEAR(section(&b, 0, (int)mid_e, mid_x, MOMENT), -W * L * L / 8.0);
        NEAR(section(&b, 0, (int)mid_e, mid_x, DEFLECTION), 5.0 * W * L * L * L * L / (384.0 * EI));
        NEAR(section(&b, 0, 0, 0.0, SHEAR), -W * L / 2.0);
        invariants(&b);
        beam_free(&b);
    }
}

static void test_cantilever_point(void)
{
    beam b;
    uniform(&b, 3, L, EI, 1, 1);
    ps_model_support(&b.m, 0, PS_UY | PS_RZ);
    ps_model_load(&b.m, PS_LOAD_NODE, 0, 3, PS_UY, 0, 0, P, 0);
    CHECK(beam_solve(&b) == PS_OK);
    NEAR(deflection(&b, 0, 3), P * L * L * L / (3.0 * EI));
    NEAR(ps_model_displacement(&b.m, 0, 3, PS_RZ), P * L * L / (2.0 * EI));
    NEAR(reaction(&b, 0, 0, 0), -P);
    NEAR(reaction(&b, 0, 0, 1), -P * L); /* counterclockwise for a downward load */
    NEAR(section(&b, 0, 0, 0.0, MOMENT), P * L); /* hogging */
    invariants(&b);
    beam_free(&b);
}

static void test_fixed_fixed_udl(void)
{
    beam b;
    uniform(&b, 2, L, EI, 2, 1);
    ps_model_support(&b.m, 0, PS_UY | PS_RZ);
    ps_model_support(&b.m, 2, PS_UY | PS_RZ);
    ps_model_load(&b.m, PS_LOAD_LINE, 0, 0, 0, 0.0, L / 2, W, W);
    ps_model_load(&b.m, PS_LOAD_LINE, 0, 1, 0, 0.0, L / 2, W, W);
    CHECK(beam_solve(&b) == PS_OK);
    NEAR(section(&b, 0, 0, 0.0, MOMENT), W * L * L / 12.0);
    NEAR(section(&b, 0, 1, 0.0, MOMENT), -W * L * L / 24.0);
    NEAR(deflection(&b, 0, 1), W * L * L * L * L / (384.0 * EI));
    invariants(&b);
    beam_free(&b);
}

static void test_propped_cantilever(void)
{
    beam b;
    uniform(&b, 1, L, EI, 1, 1);
    ps_model_support(&b.m, 0, PS_UY | PS_RZ);
    ps_model_support(&b.m, 1, PS_UY);
    ps_model_load(&b.m, PS_LOAD_LINE, 0, 0, 0, 0.0, L, W, W);
    CHECK(beam_solve(&b) == PS_OK);
    NEAR(reaction(&b, 0, 1, 0), -3.0 * W * L / 8.0);
    NEAR(reaction(&b, 0, 0, 1), -W * L * L / 8.0);
    /* Largest sagging moment 9wL^2/128 at 5L/8 from the fixed end. */
    NEAR(section(&b, 0, 0, 5.0 * L / 8.0, MOMENT), -9.0 * W * L * L / 128.0);
    NEAR(section(&b, 0, 0, 5.0 * L / 8.0, SHEAR), 0.0);
    invariants(&b);
    beam_free(&b);
}

static void test_two_span_continuous(void)
{
    beam b;
    uniform(&b, 2, 2.0 * L, EI, 2, 1);
    for (int i = 0; i < 3; i++)
        ps_model_support(&b.m, i, PS_UY);
    ps_model_load(&b.m, PS_LOAD_LINE, 0, 0, 0, 0.0, L, W, W);
    ps_model_load(&b.m, PS_LOAD_LINE, 0, 1, 0, 0.0, L, W, W);
    CHECK(beam_solve(&b) == PS_OK);
    NEAR(reaction(&b, 0, 1, 0), -1.25 * W * L);
    NEAR(reaction(&b, 0, 0, 0), -0.375 * W * L);
    NEAR(section(&b, 0, 1, 0.0, MOMENT), W * L * L / 8.0);
    invariants(&b);
    beam_free(&b);
}

/* Fixed at A, hinge at L, roller at 2L, line load on the right span only. */
static void test_hinge(void)
{
    for (int both = 0; both < 2; both++)
    {
        beam b;
        uniform(&b, 2, 2.0 * L, EI, 1, 1);
        ps_model_support(&b.m, 0, PS_UY | PS_RZ);
        ps_model_support(&b.m, 2, PS_UY);
        ps_model_element(&b.m, 1, 1, 2, 0, PS_RELEASE_START);
        if (both)
            ps_model_element(&b.m, 0, 0, 1, 0, PS_RELEASE_END);
        ps_model_load(&b.m, PS_LOAD_LINE, 0, 1, 0, 0.0, L, W, W);
        /* Releasing both sides of the hinge drops the node rotation; the
         * answers must not change. */
        ps_status status = beam_solve(&b);
        CHECK(!both || b.m.dof[1 * 2 + 1] == PS_DOF_FREE_HINGE);
        CHECK(status == PS_OK);
        NEAR(reaction(&b, 0, 2, 0), -W * L / 2.0);
        NEAR(reaction(&b, 0, 0, 0), -W * L / 2.0);
        NEAR(reaction(&b, 0, 0, 1), -W * L * L / 2.0);
        NEAR(section(&b, 0, 1, 0.0, MOMENT), 0.0);
        invariants(&b);
        beam_free(&b);
    }
}

/* A hinge between two simply supported spans with a middle support. */
static void test_free_hinge_rotation(void)
{
    beam b;
    uniform(&b, 3, 3.0 * L, EI, 3, 1);
    for (int i = 0; i < 4; i++)
        ps_model_support(&b.m, i, PS_UY);
    ps_model_element(&b.m, 0, 0, 1, 0, PS_RELEASE_END);
    ps_model_element(&b.m, 1, 1, 2, 0, PS_RELEASE_START);
    for (int e = 0; e < 3; e++)
        ps_model_load(&b.m, PS_LOAD_LINE, 0, e, 0, 0.0, L, W, W);
    CHECK(beam_solve(&b) == PS_OK);
    CHECK(isnan(ps_model_displacement(&b.m, 0, 1, PS_RZ)));
    NEAR(reaction(&b, 0, 0, 0), -W * L / 2.0); /* first span is simply supported */
    invariants(&b);
    beam_free(&b);
}

static void test_settlement(void)
{
    const double delta = -0.01;
    beam b;
    uniform(&b, 2, 2.0 * L, EI, 1, 1);
    for (int i = 0; i < 3; i++)
        ps_model_support(&b.m, i, PS_UY);
    ps_model_load(&b.m, PS_LOAD_SETTLE, 0, 1, PS_UY, 0, 0, delta, 0);
    CHECK(beam_solve(&b) == PS_OK);
    NEAR(deflection(&b, 0, 1), delta);
    NEAR(reaction(&b, 0, 1, 0), 6.0 * EI * delta / (L * L * L));
    NEAR(reaction(&b, 0, 0, 0), -3.0 * EI * delta / (L * L * L));
    invariants(&b);
    beam_free(&b);
}

static void test_spring(void)
{
    const double k = 2e6;
    beam b;
    uniform(&b, 2, L, EI, 1, 1);
    ps_model_support(&b.m, 0, PS_UY);
    ps_model_support(&b.m, 2, PS_UY);
    ps_model_spring(&b.m, 1, PS_UY, k);
    ps_model_load(&b.m, PS_LOAD_NODE, 0, 1, PS_UY, 0, 0, P, 0);
    CHECK(beam_solve(&b) == PS_OK);
    double delta = P / (k + 48.0 * EI / (L * L * L));
    NEAR(deflection(&b, 0, 1), delta);
    NEAR(reaction(&b, 0, 1, 0), -k * delta);
    invariants(&b);
    beam_free(&b);
}

static void test_element_loads(void)
{
    /* Triangular load 0 -> w on a simple span: reactions wL/6 and wL/3. */
    beam b;
    uniform(&b, 1, L, EI, 4, 3);
    ps_model_support(&b.m, 0, PS_UY);
    ps_model_support(&b.m, 1, PS_UY);
    ps_model_load(&b.m, PS_LOAD_LINE, 0, 0, 0, 0.0, L, 0.0, W);
    /* Case 1: point moment at mid-span; reactions +-M/L. */
    ps_model_load(&b.m, PS_LOAD_MOMENT, 1, 0, 0, L / 2.0, 0, 9e3, 0);
    /* Case 2: off-centre point load and a partial trapezoid. */
    ps_model_load(&b.m, PS_LOAD_POINT, 2, 0, 0, 1.5, 0, P, 0);
    ps_model_load(&b.m, PS_LOAD_LINE, 2, 0, 0, 2.0, 5.0, -2e3, -7e3);
    CHECK(beam_solve(&b) == PS_OK);
    NEAR(reaction(&b, 0, 0, 0), -W * L / 6.0);
    NEAR(reaction(&b, 0, 1, 0), -W * L / 3.0);
    NEAR(reaction(&b, 1, 0, 0), 9e3 / L);
    NEAR(section(&b, 1, 0, L / 2.0 + 1e-12, MOMENT) - section(&b, 1, 0, L / 2.0, MOMENT), -9e3);
    /* Left reaction from moments about the right support. */
    const double total = 0.5 * (-2e3 - 7e3) * 3.0;
    const double centroid = 2.0 + 3.0 * (-2e3 + 2.0 * -7e3) / (3.0 * (-2e3 - 7e3));
    NEAR(reaction(&b, 2, 0, 0), -(P * (L - 1.5) + total * (L - centroid)) / L);
    invariants(&b);
    beam_free(&b);
}

static void test_load_cases_superpose(void)
{
    beam b;
    uniform(&b, 3, 3.0 * L, EI, 6, 3);
    for (int i = 0; i < 4; i++)
        ps_model_support(&b.m, i, PS_UY);
    ps_model_load(&b.m, PS_LOAD_LINE, 0, 0, 0, 0.0, L, W, W);
    ps_model_load(&b.m, PS_LOAD_POINT, 1, 2, 0, 2.0, 0, P, 0);
    ps_model_load(&b.m, PS_LOAD_LINE, 2, 0, 0, 0.0, L, W, W);
    ps_model_load(&b.m, PS_LOAD_POINT, 2, 2, 0, 2.0, 0, P, 0);
    CHECK(beam_solve(&b) == PS_OK);
    for (int i = 0; i < 4; i++)
        NEAR(reaction(&b, 0, i, 0) + reaction(&b, 1, i, 0), reaction(&b, 2, i, 0));
    invariants(&b);
    beam_free(&b);
}

static void test_scrambled_numbering(void)
{
    /* Same continuous beam, nodes numbered out of order along the span. */
    enum
    {
        SPANS = 12
    };
    int order[SPANS + 1];
    for (int i = 0; i <= SPANS; i++)
        order[i] = (i * 5) % (SPANS + 1); /* 5 is coprime with 13 */
    beam b;
    beam_new(&b, SPANS + 1, SPANS, 1, SPANS, 1);
    for (int i = 0; i <= SPANS; i++)
    {
        ps_model_node(&b.m, order[i], L * i);
        ps_model_support(&b.m, order[i], PS_UY);
    }
    for (int e = 0; e < SPANS; e++)
    {
        ps_model_element(&b.m, e, order[e], order[e + 1], 0, 0);
        ps_model_load(&b.m, PS_LOAD_LINE, 0, e, 0, 0.0, L, W, W);
    }
    ps_model_section(&b.m, 0, EI, 1.0);
    CHECK(beam_solve(&b) == PS_OK);
    /* Rotations only, chained: the reordered profile is the tridiagonal one. */
    CHECK(b.m.profile == 2 * (SPANS + 1) - 1);
    invariants(&b);
    beam_free(&b);
}

static void test_errors(void)
{
    beam b;
    uniform(&b, 2, L, EI, 2, 1);
    ps_model_support(&b.m, 0, PS_UY);
    CHECK(beam_solve(&b) == PS_ERR_MECHANISM); /* decided in double, also after single */
    CHECK(b.m.error_item >= 0);
    CHECK(ps_model_reaction(&b.m, 0, 0, (double[2]){0}) == PS_ERR_STATE);

    ps_model_support(&b.m, 2, PS_UY);
    ps_model_load(&b.m, PS_LOAD_LINE, 0, 0, 0, 1.0, L, W, W);
    CHECK(beam_solve(&b) == PS_ERR_LOAD && b.m.error_item == 0);
    ps_model_clear_loads(&b.m);
    ps_model_load(&b.m, PS_LOAD_SETTLE, 0, 1, PS_UY, 0, 0, 0.01, 0);
    CHECK(beam_solve(&b) == PS_ERR_SUPPORT && b.m.error_item == 1);
    ps_model_clear_loads(&b.m);
    ps_model_spring(&b.m, 0, PS_UY, 1e5);
    CHECK(beam_solve(&b) == PS_ERR_SUPPORT && b.m.error_item == 0);
    ps_model_spring(&b.m, 0, PS_UY, 0.0);
    ps_model_node(&b.m, 2, -1.0);
    CHECK(beam_solve(&b) == PS_ERR_GEOMETRY && b.m.error_item == 1);
    beam_free(&b);

    beam lonely;
    beam_new(&lonely, 3, 1, 1, 0, 1);
    ps_model_node(&lonely.m, 1, 1.0);
    ps_model_element(&lonely.m, 0, 0, 1, 0, 0);
    ps_model_section(&lonely.m, 0, EI, 1.0);
    CHECK(beam_solve(&lonely) == PS_ERR_UNCONNECTED && lonely.m.error_item == 2);
    ps_model_section(&lonely.m, 0, 0.0, 1.0);
    CHECK(beam_solve(&lonely) == PS_ERR_SECTION);
    beam_free(&lonely);
}

static void test_diagram(void)
{
    beam b;
    uniform(&b, 2, L, EI, 3, 1);
    ps_model_support(&b.m, 0, PS_UY | PS_RZ);
    ps_model_support(&b.m, 2, PS_UY);
    ps_model_load(&b.m, PS_LOAD_LINE, 0, 0, 0, 0.5, 2.5, W, 2 * W);
    ps_model_load(&b.m, PS_LOAD_POINT, 0, 1, 0, 1.0, 0, P, 0);
    CHECK(beam_solve(&b) == PS_OK);
    enum
    {
        S = 7
    };
    float v[S], mo[S], sl[S], de[S];
    CHECK(ps_model_diagram(&b.m, 0, 1, S, v, mo, sl, de) == PS_OK);
    for (int i = 0; i < S; i++)
    {
        double out[4];
        ps_model_section_at(&b.m, 0, 1, (L / 2) * i / (S - 1), out);
        NEAR((double)v[i], (double)(float)out[0]);
        NEAR((double)mo[i], (double)(float)out[1]);
        NEAR((double)de[i], (double)(float)out[3]);
    }
    CHECK(ps_model_diagram(&b.m, 0, 1, S, NULL, mo, NULL, NULL) == PS_OK);
    CHECK(ps_model_diagram(&b.m, 0, 1, 1, v, mo, sl, de) == PS_ERR_ARGUMENT);
    beam_free(&b);
}

/* Stiffness ratios too large for float32: single asks for double. */
static void test_ill_conditioned(void)
{
    const int before = escalations;
    beam b;
    beam_new(&b, 4, 3, 2, 1, 1);
    for (int i = 0; i < 4; i++)
        ps_model_node(&b.m, i, L * i);
    ps_model_section(&b.m, 0, EI, 1.0);
    ps_model_section(&b.m, 1, EI * 1e7, 1.0);
    ps_model_element(&b.m, 0, 0, 1, 0, 0);
    ps_model_element(&b.m, 1, 1, 2, 1, 0);
    ps_model_element(&b.m, 2, 2, 3, 0, 0);
    ps_model_support(&b.m, 0, PS_UY);
    ps_model_support(&b.m, 3, PS_UY);
    ps_model_load(&b.m, PS_LOAD_NODE, 0, 1, PS_UY, 0, 0, P, 0);
    CHECK(beam_solve(&b) == PS_OK);
    if (first_precision == PS_SINGLE)
        CHECK(escalations > before && b.m.precision == PS_DOUBLE);
    /* Supported only at the ends, so statically determinate: the load at a
     * third of the span splits 2/3 : 1/3 whatever the stiffnesses. */
    double r0[2], r3[2];
    ps_model_reaction(&b.m, 0, 0, r0);
    ps_model_reaction(&b.m, 0, 3, r3);
    CHECK(fabs(r0[0] + 2.0 * P / 3.0) < 1e-6 * fabs(P) && fabs(r3[0] + P / 3.0) < 1e-6 * fabs(P));
    beam_free(&b);
}

static void test_single_memory(void)
{
    beam b;
    uniform(&b, 400, 400.0, EI, 0, 1);
    for (int i = 0; i <= 400; i += 5)
        ps_model_support(&b.m, i, PS_UY);
    void *index = malloc(ps_model_index_bytes(&b.m));
    CHECK(ps_model_prepare(&b.m, index) == PS_OK);
    size_t single = ps_model_value_bytes(&b.m, PS_SINGLE), dbl = ps_model_value_bytes(&b.m, PS_DOUBLE);
    printf("values block, 400 elements: double %zu bytes, single %zu bytes\n", dbl, single);
    CHECK(single > 0 && dbl > 0);
    free(index);
    beam_free(&b);
}

static void benchmark(void)
{
    enum
    {
        SPANS = 2000
    };
    beam b;
    uniform(&b, SPANS, SPANS * 1.0, EI, SPANS, 1);
    for (int i = 0; i <= SPANS; i += 4)
        ps_model_support(&b.m, i, PS_UY);
    for (int e = 0; e < SPANS; e++)
        ps_model_load(&b.m, PS_LOAD_LINE, 0, e, 0, 0.0, 1.0, W, W);
    clock_t start = clock();
    CHECK(beam_solve(&b) == PS_OK);
    double ms = 1000.0 * (double)(clock() - start) / CLOCKS_PER_SEC;
    printf("host benchmark (%s): %d elements, %d equations, %u stored values, %d refinement steps, %.2f ms\n",
           first_precision == PS_SINGLE ? "single" : "double", SPANS, b.m.equations, b.m.profile,
           b.m.refinements, ms);
    beam_free(&b);
}

static void beam_suite(void)
{
    test_simply_supported_udl();
    test_cantilever_point();
    test_fixed_fixed_udl();
    test_propped_cantilever();
    test_two_span_continuous();
    test_hinge();
    test_free_hinge_rotation();
    test_settlement();
    test_spring();
    test_element_loads();
    test_load_cases_superpose();
    test_scrambled_numbering();
    test_errors();
    test_diagram();
    test_ill_conditioned();
    benchmark();
}

int main(void)
{
    test_skyline_against_dense();
    test_condense();
    test_rcm();
    test_single_memory();
    beam_suite();
    first_precision = PS_SINGLE;
    beam_suite();
    printf("%s: %d checks, %d failures\n", failures ? "FAIL" : "PASS", checks, failures);
    return failures ? 1 : 0;
}
