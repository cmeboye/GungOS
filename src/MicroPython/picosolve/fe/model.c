#include "model.h"
#include "beam.h"
#include "../core/dense.h"
#include <math.h>

#define DPN PS_BEAM_DOF_PER_NODE
/* Single precision refinement: give up after this many steps, or when a step
 * shrinks the correction by less than half. */
#define PS_REFINE_MAX 30
#define PS_REFINE_TOLERANCE 1e-13

static size_t align8(size_t n)
{
    return (n + 7u) & ~(size_t)7u;
}

/* Carve consecutive arrays out of a block, keeping each 8-byte aligned. */
static void *take(uint8_t **cursor, size_t bytes)
{
    void *p = *cursor;
    *cursor += align8(bytes);
    return p;
}

static int flag_dof(uint32_t flag)
{
    return flag == PS_UY ? 0 : flag == PS_RZ ? 1 : -1;
}

static void edited(ps_model *m)
{
    m->state = PS_STATE_EDITED;
}

static ps_status fail(ps_model *m, ps_status status, int32_t item, int32_t dof)
{
    m->error_item = item;
    m->error_dof = dof;
    return status;
}

/* ------------------------------------------------------------------------ */
/* Building the model                                                       */
/* ------------------------------------------------------------------------ */

size_t ps_model_bytes(int32_t nodes, int32_t elements, int32_t sections, int32_t loads)
{
    size_t n = (size_t)nodes, e = (size_t)elements, s = (size_t)sections, l = (size_t)loads;
    return align8(n * sizeof(double)) + align8(n * DPN * sizeof(double)) +
           2 * align8(s * sizeof(double)) + align8(l * sizeof(ps_load)) +
           align8(2 * e * sizeof(int32_t)) + align8(e * sizeof(int32_t)) +
           align8(n) + align8(e);
}

ps_status ps_model_init(ps_model *m, void *block, int32_t nodes, int32_t elements,
                        int32_t sections, int32_t loads, int32_t cases)
{
    if (nodes < 2 || elements < 1 || sections < 1 || loads < 0 || cases < 1 || cases > 255)
        return PS_ERR_ARGUMENT;
    uint8_t *cursor = block;
    m->nodes = nodes;
    m->elements = elements;
    m->sections = sections;
    m->load_capacity = loads;
    m->cases = cases;
    m->load_count = 0;
    m->x = take(&cursor, (size_t)nodes * sizeof(double));
    m->spring = take(&cursor, (size_t)nodes * DPN * sizeof(double));
    m->modulus = take(&cursor, (size_t)sections * sizeof(double));
    m->inertia = take(&cursor, (size_t)sections * sizeof(double));
    m->load = take(&cursor, (size_t)loads * sizeof(ps_load));
    m->connect = take(&cursor, 2 * (size_t)elements * sizeof(int32_t));
    m->section_of = take(&cursor, (size_t)elements * sizeof(int32_t));
    m->fixed = take(&cursor, (size_t)nodes);
    m->release = take(&cursor, (size_t)elements);
    for (int32_t i = 0; i < nodes; i++)
    {
        m->x[i] = 0.0;
        m->fixed[i] = 0;
        for (int d = 0; d < DPN; d++)
            m->spring[i * DPN + d] = 0.0;
    }
    for (int32_t i = 0; i < sections; i++)
        m->modulus[i] = m->inertia[i] = 0.0;
    for (int32_t i = 0; i < elements; i++)
    {
        m->connect[2 * i] = m->connect[2 * i + 1] = -1;
        m->section_of[i] = -1;
        m->release[i] = 0;
    }
    m->equations = 0;
    m->profile = 0;
    m->precision = PS_DOUBLE;
    m->refinements = 0;
    m->error_item = m->error_dof = -1;
    edited(m);
    return PS_OK;
}

ps_status ps_model_node(ps_model *m, int32_t node, double x)
{
    if (node < 0 || node >= m->nodes || !isfinite(x))
        return PS_ERR_ARGUMENT;
    m->x[node] = x;
    edited(m);
    return PS_OK;
}

ps_status ps_model_support(ps_model *m, int32_t node, uint32_t flags)
{
    if (node < 0 || node >= m->nodes || (flags & ~(PS_UY | PS_RZ)))
        return PS_ERR_ARGUMENT;
    m->fixed[node] = (uint8_t)flags;
    edited(m);
    return PS_OK;
}

ps_status ps_model_spring(ps_model *m, int32_t node, uint32_t flag, double stiffness)
{
    int d = flag_dof(flag);
    if (node < 0 || node >= m->nodes || d < 0 || !(stiffness >= 0.0) || !isfinite(stiffness))
        return PS_ERR_ARGUMENT;
    m->spring[node * DPN + d] = stiffness;
    edited(m);
    return PS_OK;
}

ps_status ps_model_section(ps_model *m, int32_t section, double modulus, double inertia)
{
    if (section < 0 || section >= m->sections || !isfinite(modulus) || !isfinite(inertia))
        return PS_ERR_ARGUMENT;
    m->modulus[section] = modulus;
    m->inertia[section] = inertia;
    edited(m);
    return PS_OK;
}

ps_status ps_model_element(ps_model *m, int32_t element, int32_t start, int32_t end,
                           int32_t section, uint32_t releases)
{
    if (element < 0 || element >= m->elements || start < 0 || start >= m->nodes ||
        end < 0 || end >= m->nodes || section < 0 || section >= m->sections ||
        (releases & ~(PS_RELEASE_START | PS_RELEASE_END)))
        return PS_ERR_ARGUMENT;
    m->connect[2 * element] = start;
    m->connect[2 * element + 1] = end;
    m->section_of[element] = section;
    m->release[element] = (uint8_t)releases;
    edited(m);
    return PS_OK;
}

ps_status ps_model_load(ps_model *m, ps_load_kind kind, int32_t load_case, int32_t target,
                        uint32_t flag, double a, double b, double w1, double w2)
{
    if (m->load_count >= m->load_capacity || load_case < 0 || load_case >= m->cases ||
        kind > PS_LOAD_LINE || !isfinite(a) || !isfinite(b) || !isfinite(w1) || !isfinite(w2))
        return PS_ERR_ARGUMENT;
    int d = 0;
    if (kind == PS_LOAD_NODE || kind == PS_LOAD_SETTLE)
    {
        d = flag_dof(flag);
        if (d < 0 || target < 0 || target >= m->nodes)
            return PS_ERR_ARGUMENT;
    }
    else if (target < 0 || target >= m->elements)
        return PS_ERR_ARGUMENT;
    ps_load *l = &m->load[m->load_count++];
    l->kind = (uint8_t)kind;
    l->load_case = (uint8_t)load_case;
    l->target = target;
    l->dof = (uint8_t)d;
    l->a = a;
    l->b = b;
    l->w1 = w1;
    l->w2 = w2;
    edited(m);
    return PS_OK;
}

void ps_model_clear_loads(ps_model *m)
{
    m->load_count = 0;
    edited(m);
}

/* ------------------------------------------------------------------------ */
/* Preparing: checks, numbering, lookups                                    */
/* ------------------------------------------------------------------------ */

static int element_nodes(const void *model, int32_t e, int32_t *nodes)
{
    const ps_model *m = model;
    nodes[0] = m->connect[2 * e];
    nodes[1] = m->connect[2 * e + 1];
    return 2;
}

size_t ps_model_index_bytes(const ps_model *m)
{
    size_t n = (size_t)m->nodes, e = (size_t)m->elements, l = (size_t)m->load_capacity;
    return ps_dofmap_bytes(m->nodes, DPN, 2 * m->elements) +
           align8((n + 1) * sizeof(int32_t)) + align8(2 * e * sizeof(int32_t)) +
           align8((e + 1) * sizeof(int32_t)) + align8((n + 1) * sizeof(int32_t)) +
           2 * align8(l * sizeof(int32_t));
}

static double element_length(const ps_model *m, int32_t e)
{
    return m->x[m->connect[2 * e + 1]] - m->x[m->connect[2 * e]];
}

static double element_ei(const ps_model *m, int32_t e)
{
    int32_t s = m->section_of[e];
    return m->modulus[s] * m->inertia[s];
}

/* Released element DOFs (theta1 = 1, theta2 = 3) as a bit mask. */
static uint32_t released_dofs(const ps_model *m, int32_t e)
{
    uint32_t mask = 0;
    if (m->release[e] & PS_RELEASE_START)
        mask |= 1u << 1;
    if (m->release[e] & PS_RELEASE_END)
        mask |= 1u << 3;
    return mask;
}

static int is_element_load(const ps_load *l)
{
    return l->kind == PS_LOAD_POINT || l->kind == PS_LOAD_MOMENT || l->kind == PS_LOAD_LINE;
}

/* Compressed lists: ptr[k]..ptr[k+1] index into items. ptr has groups + 1 entries. */
static void list_finish(int32_t *ptr, int32_t groups)
{
    for (int32_t i = 0; i < groups; i++)
        ptr[i + 1] += ptr[i];
}

ps_status ps_model_prepare(ps_model *m, void *block)
{
    uint8_t *cursor = block;
    const int32_t nn = m->nodes, ne = m->elements, nl = m->load_count;
    const size_t map_bytes = ps_dofmap_bytes(nn, DPN, 2 * ne);
    ps_dofmap_init(&m->map, take(&cursor, map_bytes), nn, DPN, 2 * ne);
    m->dof = m->map.dof;
    m->incident_ptr = take(&cursor, ((size_t)nn + 1) * sizeof(int32_t));
    m->incident = take(&cursor, 2 * (size_t)ne * sizeof(int32_t));
    m->element_load_ptr = take(&cursor, ((size_t)ne + 1) * sizeof(int32_t));
    m->node_load_ptr = take(&cursor, ((size_t)nn + 1) * sizeof(int32_t));
    m->element_load = take(&cursor, (size_t)m->load_capacity * sizeof(int32_t));
    m->node_load = take(&cursor, (size_t)m->load_capacity * sizeof(int32_t));
    m->state = PS_STATE_EDITED;
    m->error_item = m->error_dof = -1;

    for (int32_t e = 0; e < ne; e++)
    {
        int32_t s = m->section_of[e];
        if (s < 0 || m->connect[2 * e] == m->connect[2 * e + 1])
            return fail(m, PS_ERR_GEOMETRY, e, -1);
        if (!(m->modulus[s] > 0.0) || !(m->inertia[s] > 0.0))
            return fail(m, PS_ERR_SECTION, s, -1);
        if (!(element_length(m, e) > 0.0))
            return fail(m, PS_ERR_GEOMETRY, e, -1);
    }

    /* Node -> element ends; also counts rigid (unreleased) rotation ends. */
    int32_t *rigid = m->map.level; /* free until numbering */
    for (int32_t i = 0; i <= nn; i++)
        m->incident_ptr[i] = 0;
    for (int32_t i = 0; i < nn; i++)
        rigid[i] = 0;
    for (int32_t e = 0; e < ne; e++)
        for (int end = 0; end < 2; end++)
        {
            int32_t node = m->connect[2 * e + end];
            m->incident_ptr[node + 1]++;
            if (!(m->release[e] & (end ? PS_RELEASE_END : PS_RELEASE_START)))
                rigid[node]++;
        }
    list_finish(m->incident_ptr, nn);
    for (int32_t i = 0; i < nn; i++)
        m->map.perm[i] = m->incident_ptr[i];
    for (int32_t e = 0; e < ne; e++)
        for (int end = 0; end < 2; end++)
        {
            int32_t node = m->connect[2 * e + end];
            m->incident[m->map.perm[node]++] = 2 * e + end;
        }

    for (int32_t i = 0; i < nn; i++)
    {
        if (m->incident_ptr[i + 1] == m->incident_ptr[i])
            return fail(m, PS_ERR_UNCONNECTED, i, -1);
        for (int d = 0; d < DPN; d++)
        {
            int fixed = (m->fixed[i] >> d) & 1;
            if (fixed && m->spring[i * DPN + d] > 0.0)
                return fail(m, PS_ERR_SUPPORT, i, d);
            int32_t code = fixed ? PS_DOF_FIXED : 0;
            if (d == 1 && !fixed && rigid[i] == 0 && m->spring[i * DPN + d] == 0.0)
                code = PS_DOF_FREE_HINGE;
            m->dof[i * DPN + d] = code;
        }
    }

    /* Check loads, then group them by element and by node. */
    for (int32_t i = 0; i <= ne; i++)
        m->element_load_ptr[i] = 0;
    for (int32_t i = 0; i <= nn; i++)
        m->node_load_ptr[i] = 0;
    for (int32_t k = 0; k < nl; k++)
    {
        const ps_load *l = &m->load[k];
        if (!is_element_load(l))
        {
            int32_t code = m->dof[l->target * DPN + l->dof];
            if (l->kind == PS_LOAD_SETTLE && code != PS_DOF_FIXED)
                return fail(m, PS_ERR_SUPPORT, l->target, l->dof);
            if (l->kind == PS_LOAD_NODE && code == PS_DOF_FREE_HINGE && l->w1 != 0.0)
                return fail(m, PS_ERR_MECHANISM, l->target, l->dof);
            m->node_load_ptr[l->target + 1]++;
            continue;
        }
        const double length = element_length(m, l->target);
        const double slack = 1e-9 * length;
        int ok = l->a >= -slack && l->a <= length + slack;
        if (l->kind == PS_LOAD_LINE)
            ok = ok && l->b > l->a && l->b <= length + slack;
        if (!ok)
            return fail(m, PS_ERR_LOAD, k, -1);
        m->element_load_ptr[l->target + 1]++;
    }
    list_finish(m->element_load_ptr, ne);
    list_finish(m->node_load_ptr, nn);
    {
        /* Fill cursors live in map.perm (nn) and map.adj (2 * ne >= ne). */
        int32_t *ecur = m->map.adj, *ncur = m->map.perm;
        for (int32_t i = 0; i < ne; i++)
            ecur[i] = m->element_load_ptr[i];
        for (int32_t i = 0; i < nn; i++)
            ncur[i] = m->node_load_ptr[i];
        for (int32_t k = 0; k < nl; k++)
        {
            const ps_load *l = &m->load[k];
            if (is_element_load(l))
                m->element_load[ecur[l->target]++] = k;
            else
                m->node_load[ncur[l->target]++] = k;
        }
    }

    ps_status status = ps_dofmap_number(&m->map, ne, element_nodes, m);
    if (status != PS_OK)
        return status;
    m->equations = m->map.equations;
    m->profile = m->map.profile;
    m->state = PS_STATE_PREPARED;
    return PS_OK;
}

/* ------------------------------------------------------------------------ */
/* Solving                                                                  */
/* ------------------------------------------------------------------------ */

static void beam_load(const ps_load *l, ps_beam_load *out)
{
    out->kind = l->kind == PS_LOAD_POINT ? PS_BEAM_POINT
                : l->kind == PS_LOAD_MOMENT ? PS_BEAM_MOMENT
                                            : PS_BEAM_TRAP;
    out->a = l->a;
    out->b = l->b;
    out->w1 = l->w1;
    out->w2 = l->w2;
}

/* Element stiffness with hinges condensed out. */
static void condensed_stiffness(const ps_model *m, int32_t e, double *k)
{
    ps_beam_stiffness(element_ei(m, e), element_length(m, e), k);
    ps_condense(k, NULL, PS_BEAM_DOF, released_dofs(m, e));
}

static void element_equations(const ps_model *m, int32_t e, int32_t *eq)
{
    int32_t nodes[2];
    element_nodes(m, e, nodes);
    ps_dofmap_equations(&m->map, nodes, 2, eq);
}

size_t ps_model_value_bytes(const ps_model *m, ps_precision precision)
{
    const size_t n = (size_t)m->equations, cases = (size_t)m->cases;
    size_t bytes = align8(ps_sky_value_bytes(m->profile, precision)) +
                   align8(cases * n * sizeof(double));
    if (precision == PS_SINGLE)
        /* right-hand sides, residual and the float correction */
        bytes += align8(cases * n * sizeof(double)) + align8(n * sizeof(double)) +
                 align8(n * sizeof(float));
    return bytes;
}

/* Assemble the right-hand side of every load case into rhs (cases x n). */
static void assemble_loads(const ps_model *m, double *rhs)
{
    const int32_t n = m->equations;
    double k[PS_BEAM_DOF * PS_BEAM_DOF];
    int32_t eq[PS_BEAM_DOF];
    for (int32_t i = 0; i < m->cases * n; i++)
        rhs[i] = 0.0;
    for (int32_t index = 0; index < m->load_count; index++)
    {
        const ps_load *l = &m->load[index];
        double *r = rhs + (size_t)l->load_case * (size_t)n;
        if (l->kind == PS_LOAD_NODE)
        {
            int32_t v = m->dof[l->target * DPN + l->dof];
            if (v >= 0)
                r[v] += l->w1; /* loads on supports go straight into the reaction */
        }
        else if (l->kind == PS_LOAD_SETTLE)
        {
            /* Move K_free,fixed * u_fixed to the right-hand side. */
            for (int32_t p = m->incident_ptr[l->target]; p < m->incident_ptr[l->target + 1]; p++)
            {
                const int32_t e = m->incident[p] / 2, end = m->incident[p] % 2;
                condensed_stiffness(m, e, k);
                element_equations(m, e, eq);
                const int column = end * DPN + l->dof;
                for (int a = 0; a < PS_BEAM_DOF; a++)
                    if (eq[a] >= 0)
                        r[eq[a]] -= k[a * PS_BEAM_DOF + column] * l->w1;
            }
        }
        else
        {
            const int32_t e = l->target;
            ps_beam_load bl;
            double f[PS_BEAM_DOF] = {0.0, 0.0, 0.0, 0.0};
            beam_load(l, &bl);
            ps_beam_load_vector(element_length(m, e), &bl, f);
            uint32_t released = released_dofs(m, e);
            if (released)
            {
                ps_beam_stiffness(element_ei(m, e), element_length(m, e), k);
                ps_condense(k, f, PS_BEAM_DOF, released);
            }
            element_equations(m, e, eq);
            for (int a = 0; a < PS_BEAM_DOF; a++)
                if (eq[a] >= 0)
                    r[eq[a]] += f[a];
        }
    }
}

/* residual = rhs - K u, element by element in double precision. */
static void residual(const ps_model *m, const double *rhs, const double *u, double *r)
{
    double k[PS_BEAM_DOF * PS_BEAM_DOF];
    int32_t eq[PS_BEAM_DOF];
    for (int32_t i = 0; i < m->equations; i++)
        r[i] = rhs[i];
    for (int32_t e = 0; e < m->elements; e++)
    {
        condensed_stiffness(m, e, k);
        element_equations(m, e, eq);
        for (int a = 0; a < PS_BEAM_DOF; a++)
        {
            if (eq[a] < 0)
                continue;
            double sum = 0.0;
            for (int b = 0; b < PS_BEAM_DOF; b++)
                if (eq[b] >= 0)
                    sum += k[a * PS_BEAM_DOF + b] * u[eq[b]];
            r[eq[a]] -= sum;
        }
    }
    for (int32_t i = 0; i < m->nodes * DPN; i++)
        if (m->dof[i] >= 0 && m->spring[i] > 0.0)
            r[m->dof[i]] -= m->spring[i] * u[m->dof[i]];
}

static double max_abs(const double *v, int32_t n)
{
    double best = 0.0;
    for (int32_t i = 0; i < n; i++)
        if (fabs(v[i]) > best)
            best = fabs(v[i]);
    return best;
}

/* Iterative refinement: u += solve_single(rhs - K u) until corrections vanish. */
static ps_status refine(ps_model *m, const double *rhs, double *u, double *r, float *d,
                        ps_control *ctl)
{
    const int32_t n = m->equations;
    double last = 0.0;
    for (int32_t i = 0; i < n; i++)
        u[i] = 0.0;
    for (int32_t i = 0; i < n; i++)
        r[i] = rhs[i];
    for (int32_t step = 1; step <= PS_REFINE_MAX; step++)
    {
        if (ctl && ctl->cancel)
            return PS_CANCELLED;
        for (int32_t i = 0; i < n; i++)
            d[i] = (float)r[i];
        ps_sky_solve_single(&m->sky, d);
        double change = 0.0;
        for (int32_t i = 0; i < n; i++)
        {
            u[i] += (double)d[i];
            if (fabs((double)d[i]) > change)
                change = fabs((double)d[i]);
        }
        if (step > m->refinements)
            m->refinements = step;
        const double size = max_abs(u, n);
        if (change <= PS_REFINE_TOLERANCE * size || size == 0.0)
            return PS_OK;
        if (step > 1 && change > 0.5 * last)
            return PS_ERR_ACCURACY; /* converging too slowly: badly conditioned */
        last = change;
        residual(m, rhs, u, r);
    }
    return PS_ERR_ACCURACY;
}

ps_status ps_model_solve(ps_model *m, void *block, ps_precision precision, ps_control *ctl)
{
    if (m->state == PS_STATE_EDITED)
        return PS_ERR_STATE;
    uint8_t *cursor = block;
    const int32_t n = m->equations;
    m->state = PS_STATE_PREPARED;
    m->precision = precision;
    m->refinements = 0;
    m->sky.n = n;
    m->sky.ptr = m->map.ptr;
    m->sky.precision = precision;
    m->sky.val = take(&cursor, ps_sky_value_bytes(m->profile, precision));
    m->u = take(&cursor, (size_t)m->cases * (size_t)n * sizeof(double));
    double *rhs = m->u, *r = NULL;
    float *d = NULL;
    if (precision == PS_SINGLE)
    {
        rhs = take(&cursor, (size_t)m->cases * (size_t)n * sizeof(double));
        r = take(&cursor, (size_t)n * sizeof(double));
        d = take(&cursor, (size_t)n * sizeof(float));
    }
    ps_sky_zero(&m->sky);
    double k[PS_BEAM_DOF * PS_BEAM_DOF];
    int32_t eq[PS_BEAM_DOF];
    for (int32_t e = 0; e < m->elements; e++)
    {
        condensed_stiffness(m, e, k);
        element_equations(m, e, eq);
        ps_sky_add(&m->sky, eq, PS_BEAM_DOF, k);
    }
    for (int32_t i = 0; i < m->nodes * DPN; i++)
        if (m->dof[i] >= 0 && m->spring[i] > 0.0)
            ps_sky_add_diagonal(&m->sky, m->dof[i], m->spring[i]);
    assemble_loads(m, rhs);

    ps_status status = ps_sky_factor(&m->sky, &m->info, ctl);
    if (status == PS_ERR_MECHANISM)
    {
        for (int32_t i = 0; i < m->nodes * DPN; i++)
            if (m->dof[i] == m->info.failed_dof)
                return fail(m, status, i / DPN, i % DPN);
        return fail(m, status, -1, -1);
    }
    if (status != PS_OK)
        return status;
    for (int32_t c = 0; c < m->cases; c++)
    {
        double *uc = m->u + (size_t)c * (size_t)n;
        if (precision == PS_DOUBLE)
            ps_sky_solve(&m->sky, uc);
        else if ((status = refine(m, rhs + (size_t)c * (size_t)n, uc, r, d, ctl)) != PS_OK)
            return status;
    }
    m->state = PS_STATE_SOLVED;
    return PS_OK;
}

/* ------------------------------------------------------------------------ */
/* Results                                                                  */
/* ------------------------------------------------------------------------ */

static double settlement(const ps_model *m, int32_t load_case, int32_t node, int d)
{
    double value = 0.0;
    for (int32_t p = m->node_load_ptr[node]; p < m->node_load_ptr[node + 1]; p++)
    {
        const ps_load *l = &m->load[m->node_load[p]];
        if (l->kind == PS_LOAD_SETTLE && l->load_case == load_case && l->dof == d)
            value += l->w1;
    }
    return value;
}

static double node_value(const ps_model *m, int32_t load_case, int32_t node, int d)
{
    int32_t v = m->dof[node * DPN + d];
    if (v >= 0)
        return m->u[(size_t)load_case * (size_t)m->equations + (size_t)v];
    if (v == PS_DOF_FIXED)
        return settlement(m, load_case, node, d);
    return (double)NAN;
}

double ps_model_displacement(const ps_model *m, int32_t load_case, int32_t node, uint32_t flag)
{
    int d = flag_dof(flag);
    if (m->state != PS_STATE_SOLVED || load_case < 0 || load_case >= m->cases ||
        node < 0 || node >= m->nodes || d < 0)
        return (double)NAN;
    return node_value(m, load_case, node, d);
}

/* Element end displacements (hinge rotations recovered) and end forces. */
static ps_status element_result(const ps_model *m, int32_t load_case, int32_t e,
                                double *ue, double *forces)
{
    double k[PS_BEAM_DOF * PS_BEAM_DOF];
    double f[PS_BEAM_DOF] = {0.0, 0.0, 0.0, 0.0};
    const double length = element_length(m, e);
    ps_beam_stiffness(element_ei(m, e), length, k);
    for (int32_t p = m->element_load_ptr[e]; p < m->element_load_ptr[e + 1]; p++)
    {
        const ps_load *l = &m->load[m->element_load[p]];
        if (l->load_case == load_case)
        {
            ps_beam_load bl;
            beam_load(l, &bl);
            ps_beam_load_vector(length, &bl, f);
        }
    }
    for (int end = 0; end < 2; end++)
        for (int d = 0; d < DPN; d++)
            ue[end * DPN + d] = node_value(m, load_case, m->connect[2 * e + end], d);
    ps_status status = ps_recover(k, f, PS_BEAM_DOF, released_dofs(m, e), ue);
    if (status != PS_OK)
        return status;
    for (int a = 0; a < PS_BEAM_DOF; a++)
    {
        double sum = -f[a];
        for (int b = 0; b < PS_BEAM_DOF; b++)
            sum += k[a * PS_BEAM_DOF + b] * ue[b];
        forces[a] = sum;
    }
    return PS_OK;
}

static ps_status check_result(const ps_model *m, int32_t load_case)
{
    if (m->state != PS_STATE_SOLVED)
        return PS_ERR_STATE;
    if (load_case < 0 || load_case >= m->cases)
        return PS_ERR_ARGUMENT;
    return PS_OK;
}

ps_status ps_model_end_forces(const ps_model *m, int32_t load_case, int32_t element, double *forces)
{
    ps_status status = check_result(m, load_case);
    if (status != PS_OK)
        return status;
    if (element < 0 || element >= m->elements)
        return PS_ERR_ARGUMENT;
    double ue[PS_BEAM_DOF];
    return element_result(m, load_case, element, ue, forces);
}

ps_status ps_model_reaction(const ps_model *m, int32_t load_case, int32_t node, double *reaction)
{
    ps_status status = check_result(m, load_case);
    if (status != PS_OK)
        return status;
    if (node < 0 || node >= m->nodes)
        return PS_ERR_ARGUMENT;
    for (int d = 0; d < DPN; d++)
    {
        reaction[d] = 0.0;
        int32_t v = m->dof[node * DPN + d];
        if (v >= 0 && m->spring[node * DPN + d] > 0.0)
            reaction[d] = -m->spring[node * DPN + d] * node_value(m, load_case, node, d);
    }
    if (!m->fixed[node])
        return PS_OK;
    /* Node equilibrium: reaction = sum of element end forces - applied load. */
    double ue[PS_BEAM_DOF], forces[PS_BEAM_DOF];
    for (int32_t p = m->incident_ptr[node]; p < m->incident_ptr[node + 1]; p++)
    {
        const int32_t e = m->incident[p] / 2, end = m->incident[p] % 2;
        status = element_result(m, load_case, e, ue, forces);
        if (status != PS_OK)
            return status;
        for (int d = 0; d < DPN; d++)
            if (m->dof[node * DPN + d] == PS_DOF_FIXED)
                reaction[d] += forces[end * DPN + d];
    }
    for (int32_t p = m->node_load_ptr[node]; p < m->node_load_ptr[node + 1]; p++)
    {
        const ps_load *l = &m->load[m->node_load[p]];
        if (l->kind == PS_LOAD_NODE && l->load_case == load_case &&
            m->dof[node * DPN + l->dof] == PS_DOF_FIXED)
            reaction[l->dof] -= l->w1;
    }
    return PS_OK;
}

/* Shear, moment, slope and deflection at x, from end results already known. */
static void section(const ps_model *m, int32_t load_case, int32_t element, const double *ue,
                    const double *forces, double x, double *out)
{
    ps_beam_section s;
    ps_beam_section_start(forces[0], forces[1], x, &s);
    for (int32_t p = m->element_load_ptr[element]; p < m->element_load_ptr[element + 1]; p++)
    {
        const ps_load *l = &m->load[m->element_load[p]];
        if (l->load_case == load_case)
        {
            ps_beam_load bl;
            beam_load(l, &bl);
            ps_beam_section_add(&bl, x, &s);
        }
    }
    const double ei = element_ei(m, element);
    out[0] = s.shear;
    out[1] = s.moment;
    out[2] = ue[1] + s.slope_ei / ei;
    out[3] = ue[0] + ue[1] * x + s.deflection_ei / ei;
}

ps_status ps_model_section_at(const ps_model *m, int32_t load_case, int32_t element,
                              double x, double *out)
{
    ps_status status = check_result(m, load_case);
    if (status != PS_OK)
        return status;
    if (element < 0 || element >= m->elements || !(x >= 0.0) || x > element_length(m, element))
        return PS_ERR_ARGUMENT;
    double ue[PS_BEAM_DOF], forces[PS_BEAM_DOF];
    status = element_result(m, load_case, element, ue, forces);
    if (status != PS_OK)
        return status;
    section(m, load_case, element, ue, forces, x, out);
    return PS_OK;
}

ps_status ps_model_diagram(const ps_model *m, int32_t load_case, int32_t element, int32_t samples,
                           float *shear, float *moment, float *slope, float *deflection)
{
    ps_status status = check_result(m, load_case);
    if (status != PS_OK)
        return status;
    if (element < 0 || element >= m->elements || samples < 2)
        return PS_ERR_ARGUMENT;
    double ue[PS_BEAM_DOF], forces[PS_BEAM_DOF], out[4];
    status = element_result(m, load_case, element, ue, forces);
    if (status != PS_OK)
        return status;
    const double length = element_length(m, element);
    for (int32_t i = 0; i < samples; i++)
    {
        section(m, load_case, element, ue, forces, length * i / (samples - 1), out);
        if (shear)
            shear[i] = (float)out[0];
        if (moment)
            moment[i] = (float)out[1];
        if (slope)
            slope[i] = (float)out[2];
        if (deflection)
            deflection[i] = (float)out[3];
    }
    return PS_OK;
}
