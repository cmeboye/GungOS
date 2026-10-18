#include "model.h"
#include "beam.h"
#include "../core/dense.h"
#include <math.h>

/* Element DOFs: 2 * dpn, at most PS_MAX_ELEMENT_DOF. */
#define EDOF_MAX PS_MAX_ELEMENT_DOF
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

static int is_frame(const ps_model *m)
{
    return m->dpn == PS_FRAME_DOF_PER_NODE;
}

/* Node DOF index of a flag: beam (v, theta), frame (u, v, theta). */
static int flag_dof(const ps_model *m, uint32_t flag)
{
    if (is_frame(m))
        return flag == PS_UX ? 0 : flag == PS_UY ? 1 : flag == PS_RZ ? 2 : -1;
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

static size_t model_bytes(int32_t dpn, int32_t nodes, int32_t elements, int32_t sections, int32_t loads)
{
    size_t n = (size_t)nodes, e = (size_t)elements, s = (size_t)sections, l = (size_t)loads;
    size_t bytes = align8(n * sizeof(float)) + align8(n * (size_t)dpn * sizeof(float)) +
                   2 * align8(s * sizeof(float)) + align8(l * sizeof(ps_load)) +
                   align8(2 * e * sizeof(int32_t)) + align8(e * sizeof(int32_t)) +
                   align8(n) + align8(e);
    if (dpn == PS_FRAME_DOF_PER_NODE)
        bytes += align8(n * sizeof(float)) + align8(s * sizeof(float));
    return bytes;
}

size_t ps_model_bytes(int32_t nodes, int32_t elements, int32_t sections, int32_t loads)
{
    return model_bytes(PS_BEAM_DOF_PER_NODE, nodes, elements, sections, loads);
}

size_t ps_frame_bytes(int32_t nodes, int32_t elements, int32_t sections, int32_t loads)
{
    return model_bytes(PS_FRAME_DOF_PER_NODE, nodes, elements, sections, loads);
}

static ps_status model_init(ps_model *m, int32_t dpn, void *block, int32_t nodes, int32_t elements,
                            int32_t sections, int32_t loads, int32_t cases)
{
    if (nodes < 2 || elements < 1 || sections < 1 || loads < 0 || cases < 1 || cases > 255)
        return PS_ERR_ARGUMENT;
    uint8_t *cursor = block;
    m->dpn = dpn;
    m->nodes = nodes;
    m->elements = elements;
    m->sections = sections;
    m->load_capacity = loads;
    m->cases = cases;
    m->load_count = 0;
    m->x = take(&cursor, (size_t)nodes * sizeof(float));
    m->spring = take(&cursor, (size_t)nodes * (size_t)dpn * sizeof(float));
    m->modulus = take(&cursor, (size_t)sections * sizeof(float));
    m->inertia = take(&cursor, (size_t)sections * sizeof(float));
    m->load = take(&cursor, (size_t)loads * sizeof(ps_load));
    m->connect = take(&cursor, 2 * (size_t)elements * sizeof(int32_t));
    m->section_of = take(&cursor, (size_t)elements * sizeof(int32_t));
    m->fixed = take(&cursor, (size_t)nodes);
    m->release = take(&cursor, (size_t)elements);
    m->y = m->area = NULL;
    if (dpn == PS_FRAME_DOF_PER_NODE)
    {
        m->y = take(&cursor, (size_t)nodes * sizeof(float));
        m->area = take(&cursor, (size_t)sections * sizeof(float));
    }
    for (int32_t i = 0; i < nodes; i++)
    {
        m->x[i] = 0.0f;
        if (m->y)
            m->y[i] = 0.0f;
        m->fixed[i] = 0;
        for (int d = 0; d < dpn; d++)
            m->spring[i * dpn + d] = 0.0f;
    }
    for (int32_t i = 0; i < sections; i++)
    {
        m->modulus[i] = m->inertia[i] = 0.0f;
        if (m->area)
            m->area[i] = 0.0f;
    }
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

ps_status ps_model_init(ps_model *m, void *block, int32_t nodes, int32_t elements,
                        int32_t sections, int32_t loads, int32_t cases)
{
    return model_init(m, PS_BEAM_DOF_PER_NODE, block, nodes, elements, sections, loads, cases);
}

ps_status ps_frame_init(ps_model *m, void *block, int32_t nodes, int32_t elements,
                        int32_t sections, int32_t loads, int32_t cases)
{
    return model_init(m, PS_FRAME_DOF_PER_NODE, block, nodes, elements, sections, loads, cases);
}

ps_status ps_model_node(ps_model *m, int32_t node, double x)
{
    if (node < 0 || node >= m->nodes || !isfinite(x))
        return PS_ERR_ARGUMENT;
    m->x[node] = (float)x;
    edited(m);
    return PS_OK;
}

ps_status ps_model_node_xy(ps_model *m, int32_t node, double x, double y)
{
    if (!is_frame(m) || node < 0 || node >= m->nodes || !isfinite(x) || !isfinite(y))
        return PS_ERR_ARGUMENT;
    m->x[node] = (float)x;
    m->y[node] = (float)y;
    edited(m);
    return PS_OK;
}

ps_status ps_model_support(ps_model *m, int32_t node, uint32_t flags)
{
    const uint32_t allowed = is_frame(m) ? (PS_UX | PS_UY | PS_RZ) : (PS_UY | PS_RZ);
    if (node < 0 || node >= m->nodes || (flags & ~allowed))
        return PS_ERR_ARGUMENT;
    uint8_t mask = 0;
    for (uint32_t flag = 1; flag <= PS_UX; flag <<= 1)
        if (flags & flag)
            mask |= (uint8_t)(1u << flag_dof(m, flag));
    m->fixed[node] = mask;
    edited(m);
    return PS_OK;
}

ps_status ps_model_spring(ps_model *m, int32_t node, uint32_t flag, double stiffness)
{
    int d = flag_dof(m, flag);
    if (node < 0 || node >= m->nodes || d < 0 || !(stiffness >= 0.0) || !isfinite(stiffness))
        return PS_ERR_ARGUMENT;
    m->spring[node * m->dpn + d] = (float)stiffness;
    edited(m);
    return PS_OK;
}

ps_status ps_model_section(ps_model *m, int32_t section, double modulus, double inertia)
{
    if (section < 0 || section >= m->sections || !isfinite(modulus) || !isfinite(inertia))
        return PS_ERR_ARGUMENT;
    m->modulus[section] = (float)modulus;
    m->inertia[section] = (float)inertia;
    edited(m);
    return PS_OK;
}

ps_status ps_model_section_area(ps_model *m, int32_t section, double area)
{
    if (!is_frame(m) || section < 0 || section >= m->sections || !isfinite(area))
        return PS_ERR_ARGUMENT;
    m->area[section] = (float)area;
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

static int is_axial(ps_load_kind kind)
{
    return kind == PS_LOAD_AXIAL_POINT || kind == PS_LOAD_AXIAL_LINE;
}

ps_status ps_model_load(ps_model *m, ps_load_kind kind, int32_t load_case, int32_t target,
                        uint32_t flag, double a, double b, double w1, double w2)
{
    if (m->load_count >= m->load_capacity || load_case < 0 || load_case >= m->cases ||
        kind > PS_LOAD_AXIAL_LINE || (is_axial(kind) && !is_frame(m)) ||
        !isfinite(a) || !isfinite(b) || !isfinite(w1) || !isfinite(w2))
        return PS_ERR_ARGUMENT;
    int d = 0;
    if (kind == PS_LOAD_NODE || kind == PS_LOAD_SETTLE)
    {
        d = flag_dof(m, flag);
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
    l->a = (float)a;
    l->b = (float)b;
    l->w1 = (float)w1;
    l->w2 = (float)w2;
    edited(m);
    return PS_OK;
}

void ps_model_clear_loads(ps_model *m)
{
    m->load_count = 0;
    edited(m);
}

/* ------------------------------------------------------------------------ */
/* Element geometry and matrices                                            */
/* ------------------------------------------------------------------------ */

static int element_nodes(const void *model, int32_t e, int32_t *nodes)
{
    const ps_model *m = model;
    nodes[0] = m->connect[2 * e];
    nodes[1] = m->connect[2 * e + 1];
    return 2;
}

/* Beam: signed length (must be positive, nodes left to right).
 * Frame: distance between the nodes. */
static double element_length(const ps_model *m, int32_t e)
{
    const int32_t a = m->connect[2 * e], b = m->connect[2 * e + 1];
    const double dx = (double)m->x[b] - (double)m->x[a];
    if (!is_frame(m))
        return dx;
    const double dy = (double)m->y[b] - (double)m->y[a];
    return sqrt(dx * dx + dy * dy);
}

/* Direction cosines of the element's local x axis. */
static void element_axis(const ps_model *m, int32_t e, double *c, double *s)
{
    *c = 1.0;
    *s = 0.0;
    if (!is_frame(m))
        return;
    const int32_t a = m->connect[2 * e], b = m->connect[2 * e + 1];
    const double length = element_length(m, e);
    *c = ((double)m->x[b] - (double)m->x[a]) / length;
    *s = ((double)m->y[b] - (double)m->y[a]) / length;
}

static double element_ei(const ps_model *m, int32_t e)
{
    int32_t s = m->section_of[e];
    return (double)m->modulus[s] * (double)m->inertia[s];
}

static double element_ea(const ps_model *m, int32_t e)
{
    int32_t s = m->section_of[e];
    return (double)m->modulus[s] * (double)m->area[s];
}

/* Local DOF indices of v1, theta1, v2, theta2 within the element. */
static void bending_dofs(const ps_model *m, int *index)
{
    const int f = is_frame(m);
    index[0] = f ? 1 : 0;
    index[1] = f ? 2 : 1;
    index[2] = f ? 4 : 2;
    index[3] = f ? 5 : 3;
}

/* Released element DOFs (end rotations) as a bit mask. */
static uint32_t released_dofs(const ps_model *m, int32_t e)
{
    int b[4];
    bending_dofs(m, b);
    uint32_t mask = 0;
    if (m->release[e] & PS_RELEASE_START)
        mask |= 1u << b[1];
    if (m->release[e] & PS_RELEASE_END)
        mask |= 1u << b[3];
    return mask;
}

/* Uncondensed stiffness in local axes. */
static void local_stiffness(const ps_model *m, int32_t e, double *k)
{
    const int n = 2 * m->dpn;
    const double length = element_length(m, e);
    double kb[PS_BEAM_DOF * PS_BEAM_DOF];
    int b[4];
    ps_beam_stiffness(element_ei(m, e), length, kb);
    if (!is_frame(m))
    {
        for (int i = 0; i < 16; i++)
            k[i] = kb[i];
        return;
    }
    for (int i = 0; i < n * n; i++)
        k[i] = 0.0;
    bending_dofs(m, b);
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 4; j++)
            k[b[i] * n + b[j]] = kb[i * 4 + j];
    const double axial = element_ea(m, e) / length;
    k[0] = k[3 * n + 3] = axial;
    k[3] = k[3 * n] = -axial;
}

/* v_local = T v_global node by node (frame); unchanged for a beam. */
static void to_local(const ps_model *m, double c, double s, double *v)
{
    if (!is_frame(m))
        return;
    for (int node = 0; node < 2; node++)
    {
        double *p = v + 3 * node;
        const double gx = p[0], gy = p[1];
        p[0] = c * gx + s * gy;
        p[1] = -s * gx + c * gy;
    }
}

static void to_global(const ps_model *m, double c, double s, double *v)
{
    if (!is_frame(m))
        return;
    for (int node = 0; node < 2; node++)
    {
        double *p = v + 3 * node;
        const double lx = p[0], ly = p[1];
        p[0] = c * lx - s * ly;
        p[1] = s * lx + c * ly;
    }
}

/* k_global = T^T k_local T, in place (frame only). */
static void rotate_matrix(const ps_model *m, double c, double s, double *k)
{
    if (!is_frame(m))
        return;
    const int n = 6;
    double column[6];
    /* Rows: apply T^T to each column; columns: apply T^T to each row. */
    for (int j = 0; j < n; j++)
    {
        for (int i = 0; i < n; i++)
            column[i] = k[i * n + j];
        to_global(m, c, s, column);
        for (int i = 0; i < n; i++)
            k[i * n + j] = column[i];
    }
    for (int i = 0; i < n; i++)
        to_global(m, c, s, k + i * n);
}

static int is_element_load(const ps_load *l)
{
    return l->kind == PS_LOAD_POINT || l->kind == PS_LOAD_MOMENT || l->kind == PS_LOAD_LINE ||
           is_axial((ps_load_kind)l->kind);
}

static void beam_load(const ps_load *l, ps_beam_load *out)
{
    out->kind = l->kind == PS_LOAD_POINT ? PS_BEAM_POINT
                : l->kind == PS_LOAD_MOMENT ? PS_BEAM_MOMENT
                                            : PS_BEAM_TRAP;
    out->a = (double)l->a;
    out->b = (double)l->b;
    out->w1 = (double)l->w1;
    out->w2 = (double)l->w2;
}

/* Add one element load's consistent nodal loads, local axes, to f. */
static void local_load(const ps_model *m, int32_t e, const ps_load *l, double *f)
{
    const double length = element_length(m, e);
    if (l->kind == PS_LOAD_AXIAL_POINT)
    {
        f[0] += (double)l->w1 * (1.0 - (double)l->a / length);
        f[3] += (double)l->w1 * (double)l->a / length;
        return;
    }
    if (l->kind == PS_LOAD_AXIAL_LINE)
    {
        /* Two-point Gauss is exact for a linear load times a linear shape. */
        static const double node[2] = {-0.5773502691896258, 0.5773502691896258};
        const double half = 0.5 * ((double)l->b - (double)l->a);
        const double mid = 0.5 * ((double)l->b + (double)l->a);
        for (int g = 0; g < 2; g++)
        {
            const double x = mid + half * node[g];
            const double w = (double)l->w1 + ((double)l->w2 - (double)l->w1) * (0.5 + 0.5 * node[g]);
            f[0] += half * w * (1.0 - x / length);
            f[3] += half * w * x / length;
        }
        return;
    }
    ps_beam_load bl;
    double fb[PS_BEAM_DOF] = {0.0, 0.0, 0.0, 0.0};
    int b[4];
    beam_load(l, &bl);
    ps_beam_load_vector(length, &bl, fb);
    bending_dofs(m, b);
    for (int i = 0; i < 4; i++)
        f[b[i]] += fb[i];
}

/* Element stiffness, hinges condensed out, in global axes. */
static void condensed_stiffness(const ps_model *m, int32_t e, double *k)
{
    double c, s;
    local_stiffness(m, e, k);
    ps_condense(k, NULL, 2 * m->dpn, released_dofs(m, e));
    element_axis(m, e, &c, &s);
    rotate_matrix(m, c, s, k);
}

/* ------------------------------------------------------------------------ */
/* Preparing: checks, numbering, lookups                                    */
/* ------------------------------------------------------------------------ */

size_t ps_model_index_bytes(const ps_model *m)
{
    size_t n = (size_t)m->nodes, e = (size_t)m->elements, l = (size_t)m->load_capacity;
    return ps_dofmap_bytes(m->nodes, m->dpn) +
           align8((n + 1) * sizeof(int32_t)) + align8(2 * e * sizeof(int32_t)) +
           align8((e + 1) * sizeof(int32_t)) + align8((n + 1) * sizeof(int32_t)) +
           2 * align8(l * sizeof(int32_t));
}

/* Compressed lists: ptr[k]..ptr[k+1] index into items. ptr has groups + 1 entries. */
static void list_finish(int32_t *ptr, int32_t groups)
{
    for (int32_t i = 0; i < groups; i++)
        ptr[i + 1] += ptr[i];
}

size_t ps_model_scratch_bytes(const ps_model *m)
{
    return ps_dofmap_scratch_bytes(m->nodes, 2 * m->elements);
}

static ps_status prepare(ps_model *m, void *block, void *scratch)
{
    uint8_t *cursor = block;
    const int32_t nn = m->nodes, ne = m->elements, nl = m->load_count, dpn = m->dpn;
    const size_t map_bytes = ps_dofmap_bytes(nn, dpn);
    ps_dofmap_init(&m->map, take(&cursor, map_bytes), scratch, nn, dpn, 2 * ne);
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
        if (!(m->modulus[s] > 0.0f) || !(m->inertia[s] > 0.0f) || (is_frame(m) && !(m->area[s] > 0.0f)))
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

    const int rotation = dpn - 1;
    for (int32_t i = 0; i < nn; i++)
    {
        if (m->incident_ptr[i + 1] == m->incident_ptr[i])
            return fail(m, PS_ERR_UNCONNECTED, i, -1);
        for (int d = 0; d < dpn; d++)
        {
            int fixed = (m->fixed[i] >> d) & 1;
            if (fixed && m->spring[i * dpn + d] > 0.0f)
                return fail(m, PS_ERR_SUPPORT, i, d);
            int32_t code = fixed ? PS_DOF_FIXED : 0;
            if (d == rotation && !fixed && rigid[i] == 0 && m->spring[i * dpn + d] == 0.0f)
                code = PS_DOF_FREE_HINGE;
            m->dof[i * dpn + d] = code;
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
            int32_t code = m->dof[l->target * dpn + l->dof];
            if (l->kind == PS_LOAD_SETTLE && code != PS_DOF_FIXED)
                return fail(m, PS_ERR_SUPPORT, l->target, l->dof);
            if (l->kind == PS_LOAD_NODE && code == PS_DOF_FREE_HINGE && l->w1 != 0.0f)
                return fail(m, PS_ERR_MECHANISM, l->target, l->dof);
            m->node_load_ptr[l->target + 1]++;
            continue;
        }
        const double length = element_length(m, l->target);
        /* Frame lengths come from float32 coordinates: allow their rounding. */
        const double slack = 1e-6 * length;
        int ok = (double)l->a >= -slack && (double)l->a <= length + slack;
        if (l->kind == PS_LOAD_LINE || l->kind == PS_LOAD_AXIAL_LINE)
            ok = ok && l->b > l->a && (double)l->b <= length + slack;
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

ps_status ps_model_prepare(ps_model *m, void *block, void *scratch)
{
    const ps_status status = prepare(m, block, scratch);
    /* The scratch is the caller's to release now: nothing may point into it. */
    m->map.xadj = m->map.adj = m->map.perm = m->map.level = NULL;
    m->map.mask = NULL;
    return status;
}

/* ------------------------------------------------------------------------ */
/* Solving                                                                  */
/* ------------------------------------------------------------------------ */

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
    const int32_t n = m->equations, dpn = m->dpn, edof = 2 * dpn;
    double k[EDOF_MAX * EDOF_MAX];
    int32_t eq[EDOF_MAX];
    for (int32_t i = 0; i < m->cases * n; i++)
        rhs[i] = 0.0;
    for (int32_t index = 0; index < m->load_count; index++)
    {
        const ps_load *l = &m->load[index];
        double *r = rhs + (size_t)l->load_case * (size_t)n;
        if (l->kind == PS_LOAD_NODE)
        {
            int32_t v = m->dof[l->target * dpn + l->dof];
            if (v >= 0)
                r[v] += (double)l->w1; /* loads on supports go straight into the reaction */
        }
        else if (l->kind == PS_LOAD_SETTLE)
        {
            /* Move K_free,fixed * u_fixed to the right-hand side. */
            for (int32_t p = m->incident_ptr[l->target]; p < m->incident_ptr[l->target + 1]; p++)
            {
                const int32_t e = m->incident[p] / 2, end = m->incident[p] % 2;
                condensed_stiffness(m, e, k);
                element_equations(m, e, eq);
                const int column = end * dpn + l->dof;
                for (int a = 0; a < edof; a++)
                    if (eq[a] >= 0)
                        r[eq[a]] -= k[a * edof + column] * (double)l->w1;
            }
        }
        else
        {
            const int32_t e = l->target;
            double f[EDOF_MAX] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
            double c, s;
            local_load(m, e, l, f);
            uint32_t released = released_dofs(m, e);
            if (released)
            {
                local_stiffness(m, e, k);
                ps_condense(k, f, edof, released);
            }
            element_axis(m, e, &c, &s);
            to_global(m, c, s, f);
            element_equations(m, e, eq);
            for (int a = 0; a < edof; a++)
                if (eq[a] >= 0)
                    r[eq[a]] += f[a];
        }
    }
}

/* residual = rhs - K u, element by element in double precision. */
static void residual(const ps_model *m, const double *rhs, const double *u, double *r)
{
    const int edof = 2 * m->dpn;
    double k[EDOF_MAX * EDOF_MAX];
    int32_t eq[EDOF_MAX];
    for (int32_t i = 0; i < m->equations; i++)
        r[i] = rhs[i];
    for (int32_t e = 0; e < m->elements; e++)
    {
        condensed_stiffness(m, e, k);
        element_equations(m, e, eq);
        for (int a = 0; a < edof; a++)
        {
            if (eq[a] < 0)
                continue;
            double sum = 0.0;
            for (int b = 0; b < edof; b++)
                if (eq[b] >= 0)
                    sum += k[a * edof + b] * u[eq[b]];
            r[eq[a]] -= sum;
        }
    }
    for (int32_t i = 0; i < m->nodes * m->dpn; i++)
        if (m->dof[i] >= 0 && m->spring[i] > 0.0f)
            r[m->dof[i]] -= (double)m->spring[i] * u[m->dof[i]];
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
    const int32_t n = m->equations, dpn = m->dpn;
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
    double k[EDOF_MAX * EDOF_MAX];
    int32_t eq[EDOF_MAX];
    for (int32_t e = 0; e < m->elements; e++)
    {
        condensed_stiffness(m, e, k);
        element_equations(m, e, eq);
        ps_sky_add(&m->sky, eq, 2 * dpn, k);
    }
    for (int32_t i = 0; i < m->nodes * dpn; i++)
        if (m->dof[i] >= 0 && m->spring[i] > 0.0f)
            ps_sky_add_diagonal(&m->sky, m->dof[i], (double)m->spring[i]);
    assemble_loads(m, rhs);

    ps_status status = ps_sky_factor(&m->sky, &m->info, ctl);
    if (status == PS_ERR_MECHANISM)
    {
        for (int32_t i = 0; i < m->nodes * dpn; i++)
            if (m->dof[i] == m->info.failed_dof)
                return fail(m, status, i / dpn, i % dpn);
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
            value += (double)l->w1;
    }
    return value;
}

static double node_value(const ps_model *m, int32_t load_case, int32_t node, int d)
{
    int32_t v = m->dof[node * m->dpn + d];
    if (v >= 0)
        return m->u[(size_t)load_case * (size_t)m->equations + (size_t)v];
    if (v == PS_DOF_FIXED)
        return settlement(m, load_case, node, d);
    return (double)NAN;
}

double ps_model_displacement(const ps_model *m, int32_t load_case, int32_t node, uint32_t flag)
{
    int d = flag_dof(m, flag);
    if (m->state != PS_STATE_SOLVED || load_case < 0 || load_case >= m->cases ||
        node < 0 || node >= m->nodes || d < 0)
        return (double)NAN;
    return node_value(m, load_case, node, d);
}

/* Element end displacements and end forces in local axes, hinge rotations
 * recovered from element equilibrium. */
static ps_status element_result(const ps_model *m, int32_t load_case, int32_t e,
                                double *ue, double *forces)
{
    const int dpn = m->dpn, edof = 2 * dpn;
    double k[EDOF_MAX * EDOF_MAX];
    double f[EDOF_MAX] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
    double c, s;
    local_stiffness(m, e, k);
    for (int32_t p = m->element_load_ptr[e]; p < m->element_load_ptr[e + 1]; p++)
    {
        const ps_load *l = &m->load[m->element_load[p]];
        if (l->load_case == load_case)
            local_load(m, e, l, f);
    }
    for (int end = 0; end < 2; end++)
        for (int d = 0; d < dpn; d++)
            ue[end * dpn + d] = node_value(m, load_case, m->connect[2 * e + end], d);
    element_axis(m, e, &c, &s);
    to_local(m, c, s, ue);
    ps_status status = ps_recover(k, f, edof, released_dofs(m, e), ue);
    if (status != PS_OK)
        return status;
    for (int a = 0; a < edof; a++)
    {
        double sum = -f[a];
        for (int b = 0; b < edof; b++)
            sum += k[a * edof + b] * ue[b];
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
    double ue[EDOF_MAX];
    return element_result(m, load_case, element, ue, forces);
}

ps_status ps_model_reaction(const ps_model *m, int32_t load_case, int32_t node, double *reaction)
{
    const int dpn = m->dpn;
    ps_status status = check_result(m, load_case);
    if (status != PS_OK)
        return status;
    if (node < 0 || node >= m->nodes)
        return PS_ERR_ARGUMENT;
    for (int d = 0; d < dpn; d++)
    {
        reaction[d] = 0.0;
        int32_t v = m->dof[node * dpn + d];
        if (v >= 0 && m->spring[node * dpn + d] > 0.0f)
            reaction[d] = -(double)m->spring[node * dpn + d] * node_value(m, load_case, node, d);
    }
    if (!m->fixed[node])
        return PS_OK;
    /* Node equilibrium: reaction = sum of element end forces - applied load. */
    double ue[EDOF_MAX], forces[EDOF_MAX];
    for (int32_t p = m->incident_ptr[node]; p < m->incident_ptr[node + 1]; p++)
    {
        const int32_t e = m->incident[p] / 2, end = m->incident[p] % 2;
        double c, s;
        status = element_result(m, load_case, e, ue, forces);
        if (status != PS_OK)
            return status;
        element_axis(m, e, &c, &s);
        to_global(m, c, s, forces);
        for (int d = 0; d < dpn; d++)
            if (m->dof[node * dpn + d] == PS_DOF_FIXED)
                reaction[d] += forces[end * dpn + d];
    }
    for (int32_t p = m->node_load_ptr[node]; p < m->node_load_ptr[node + 1]; p++)
    {
        const ps_load *l = &m->load[m->node_load[p]];
        if (l->kind == PS_LOAD_NODE && l->load_case == load_case &&
            m->dof[node * dpn + l->dof] == PS_DOF_FIXED)
            reaction[l->dof] -= (double)l->w1;
    }
    return PS_OK;
}

/* Running integrals of the axial loads up to x: load q and its integral. */
static void axial_add(const ps_load *l, double x, double *q1, double *q2)
{
    const double a = (double)l->a;
    if (!(x > a))
        return;
    if (l->kind == PS_LOAD_AXIAL_POINT)
    {
        *q1 += (double)l->w1;
        *q2 += (double)l->w1 * (x - a);
        return;
    }
    const double b = (double)l->b, w1 = (double)l->w1, w2 = (double)l->w2;
    const double rise = (w2 - w1) / (b - a);
    const double da = x - a, db = x > b ? x - b : 0.0;
    *q1 += w1 * da + rise * da * da / 2.0 - w2 * db - rise * db * db / 2.0;
    *q2 += w1 * da * da / 2.0 + rise * da * da * da / 6.0 - w2 * db * db / 2.0 - rise * db * db * db / 6.0;
}

/* Shear, moment, slope, deflection, normal force and axial displacement at
 * x, from end results already known (local axes). */
static void section(const ps_model *m, int32_t load_case, int32_t element, const double *ue,
                    const double *forces, double x, double *out)
{
    int b[4];
    bending_dofs(m, b);
    ps_beam_section s;
    double q1 = 0.0, q2 = 0.0;
    ps_beam_section_start(forces[b[0]], forces[b[1]], x, &s);
    for (int32_t p = m->element_load_ptr[element]; p < m->element_load_ptr[element + 1]; p++)
    {
        const ps_load *l = &m->load[m->element_load[p]];
        if (l->load_case != load_case)
            continue;
        if (is_axial((ps_load_kind)l->kind))
            axial_add(l, x, &q1, &q2);
        else
        {
            ps_beam_load bl;
            beam_load(l, &bl);
            ps_beam_section_add(&bl, x, &s);
        }
    }
    const double ei = element_ei(m, element);
    out[0] = s.shear;
    out[1] = s.moment;
    out[2] = ue[b[1]] + s.slope_ei / ei;
    out[3] = ue[b[0]] + ue[b[1]] * x + s.deflection_ei / ei;
    out[4] = out[5] = 0.0;
    if (is_frame(m))
    {
        /* N = -fx1 - (axial load up to x); u = u1 + integral of N / EA. */
        out[4] = -forces[0] - q1;
        out[5] = ue[0] + (-forces[0] * x - q2) / element_ea(m, element);
    }
}

ps_status ps_model_section_at(const ps_model *m, int32_t load_case, int32_t element,
                              double x, double *out)
{
    ps_status status = check_result(m, load_case);
    if (status != PS_OK)
        return status;
    if (element < 0 || element >= m->elements || !(x >= 0.0))
        return PS_ERR_ARGUMENT;
    /* A frame element's length comes from float32 coordinates: accept the
     * caller's own length for its end. */
    const double length = element_length(m, element);
    if (x > length * (1.0 + 1e-6))
        return PS_ERR_ARGUMENT;
    if (x > length)
        x = length;
    double ue[EDOF_MAX], forces[EDOF_MAX];
    status = element_result(m, load_case, element, ue, forces);
    if (status != PS_OK)
        return status;
    section(m, load_case, element, ue, forces, x, out);
    return PS_OK;
}

ps_status ps_model_diagram(const ps_model *m, int32_t load_case, int32_t element, int32_t samples,
                           float *shear, float *moment, float *slope, float *deflection,
                           float *normal, float *axial)
{
    ps_status status = check_result(m, load_case);
    if (status != PS_OK)
        return status;
    if (element < 0 || element >= m->elements || samples < 2)
        return PS_ERR_ARGUMENT;
    double ue[EDOF_MAX], forces[EDOF_MAX], out[6];
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
        if (normal)
            normal[i] = (float)out[4];
        if (axial)
            axial[i] = (float)out[5];
    }
    return PS_OK;
}
