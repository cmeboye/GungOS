/*
 * picosolve MicroPython binding: the Beam model.
 *
 *   import picosolve as ps
 *   b = ps.Beam(nodes, elements, sections=1, loads=16, cases=1)
 *   b.node(i, x); b.support(i, ps.UY | ps.RZ); b.spring(i, ps.UY, k)
 *   b.section(s, E, I); b.element(e, start, end, section=0, releases=0)
 *   b.point(case, e, a, P); b.moment(case, e, a, M); b.line(case, e, a, b, w1, w2)
 *   b.node_load(case, i, ps.UY, F); b.settle(case, i, ps.UY, delta)
 *   b.solve()                       # or begin / compute (other core) / finish
 *   b.displacement(i, ps.UY, case=0); b.reaction(i, case=0) -> (fy, mz)
 *   b.end_forces(e, case=0); b.at(e, x, case=0) -> (shear, moment, slope, deflection)
 *   b.diagram(e, samples, shear, moment, slope, deflection, case=0)
 *
 * Units are SI. Problems in the model raise picosolve.SolveError with a
 * message naming the node, element, load or section at fault.
 *
 * Background solving: begin() checks the model and allocates all memory on
 * the calling core; compute() then works only on that memory, never raising
 * and never allocating, so it can run on core 1 (_thread) while the UI polls
 * progress(); finish() raises any error and returns True when results are
 * ready, or False after preparing a double-precision retry, in which case
 * compute() runs again.
 */
#include "py/runtime.h"
#include "py/objexcept.h"
#include "py/mpthread.h"
#include "../fe/model.h"

MP_DEFINE_EXCEPTION(SolveError, ValueError)

#define PRECISION_AUTO (-1)
/* Average skyline column height from which float32 pays off: below it the
 * refinement vectors outweigh the halved matrix. Calibrated on the device. */
#define AUTO_SINGLE_HEIGHT 16

typedef struct
{
    mp_obj_base_t base;
    ps_model m;
    void *model_block, *index_block, *value_block;
    size_t model_bytes, index_bytes, value_bytes;
    ps_control ctl;
    volatile ps_status status; /* of the last compute */
    int precision;             /* requested: PS_DOUBLE, PS_SINGLE or PRECISION_AUTO */
    volatile bool busy;
    bool ready; /* begin() succeeded for the current model */
} beam_obj_t;

const mp_obj_type_t picosolve_beam_type;

static beam_obj_t *beam(mp_obj_t self)
{
    return MP_OBJ_TO_PTR(self);
}

static void editable(beam_obj_t *b)
{
    if (b->busy)
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("model is being solved"));
    b->ready = false;
}

static const char *dof_name(int32_t dof)
{
    return dof == 1 ? "rotation" : "vertical movement";
}

/* Raise the model's problem as a message that names what is at fault. */
static void raise_status(beam_obj_t *b, ps_status status)
{
    const int32_t item = b->m.error_item, dof = b->m.error_dof;
    switch (status)
    {
    case PS_OK:
        return;
    case PS_CANCELLED:
        mp_raise_msg(&mp_type_SolveError, MP_ERROR_TEXT("solve cancelled"));
    case PS_ERR_MECHANISM:
        if (item >= 0)
            mp_raise_msg_varg(&mp_type_SolveError,
                              MP_ERROR_TEXT("structure can move: %s of node %d is free (add a support or remove a hinge)"),
                              dof_name(dof), (int)item);
        mp_raise_msg(&mp_type_SolveError, MP_ERROR_TEXT("structure can move (add a support)"));
    case PS_ERR_UNCONNECTED:
        mp_raise_msg_varg(&mp_type_SolveError, MP_ERROR_TEXT("node %d is not attached to any element"), (int)item);
    case PS_ERR_GEOMETRY:
        mp_raise_msg_varg(&mp_type_SolveError,
                          MP_ERROR_TEXT("element %d needs two different nodes, left to right"), (int)item);
    case PS_ERR_SECTION:
        mp_raise_msg_varg(&mp_type_SolveError, MP_ERROR_TEXT("section %d needs E and I above zero"), (int)item);
    case PS_ERR_LOAD:
        mp_raise_msg_varg(&mp_type_SolveError, MP_ERROR_TEXT("load %d lies outside its element"), (int)item);
    case PS_ERR_SUPPORT:
        mp_raise_msg_varg(&mp_type_SolveError,
                          MP_ERROR_TEXT("node %d %s: springs need a free direction, settlements a support"),
                          (int)item, dof_name(dof));
    case PS_ERR_STATE:
        mp_raise_msg(&mp_type_SolveError, MP_ERROR_TEXT("solve the model first"));
    case PS_ERR_ACCURACY:
        mp_raise_msg(&mp_type_SolveError, MP_ERROR_TEXT("model too badly conditioned to solve accurately"));
    default:
        mp_raise_ValueError(MP_ERROR_TEXT("invalid value"));
    }
}

static void check(ps_status status)
{
    if (status != PS_OK)
        mp_raise_ValueError(MP_ERROR_TEXT("invalid index or value"));
}

static void *renew(void *old, size_t old_bytes, size_t bytes)
{
    if (old)
        m_free(old);
    (void)old_bytes;
    return bytes ? m_malloc(bytes) : NULL;
}

/* ------------------------------------------------------------------------ */
/* Building                                                                 */
/* ------------------------------------------------------------------------ */

static mp_obj_t beam_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *all)
{
    enum
    {
        ARG_nodes,
        ARG_elements,
        ARG_sections,
        ARG_loads,
        ARG_cases
    };
    static const mp_arg_t allowed[] = {
        {MP_QSTR_nodes, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0}},
        {MP_QSTR_elements, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0}},
        {MP_QSTR_sections, MP_ARG_INT, {.u_int = 1}},
        {MP_QSTR_loads, MP_ARG_INT, {.u_int = 16}},
        {MP_QSTR_cases, MP_ARG_INT, {.u_int = 1}},
    };
    mp_arg_val_t a[MP_ARRAY_SIZE(allowed)];
    mp_arg_parse_all_kw_array(n_args, n_kw, all, MP_ARRAY_SIZE(allowed), allowed, a);
    const mp_int_t nodes = a[ARG_nodes].u_int, elements = a[ARG_elements].u_int;
    const mp_int_t sections = a[ARG_sections].u_int, loads = a[ARG_loads].u_int, cases = a[ARG_cases].u_int;
    if (nodes < 2 || elements < 1 || sections < 1 || loads < 0 || cases < 1 || cases > 255 ||
        nodes > 100000 || elements > 100000 || sections > 10000 || loads > 100000)
        mp_raise_ValueError(MP_ERROR_TEXT("need 2+ nodes, 1+ elements and sections, 1-255 load cases"));
    beam_obj_t *b = mp_obj_malloc(beam_obj_t, type);
    b->index_block = b->value_block = NULL;
    b->index_bytes = b->value_bytes = 0;
    b->model_bytes = ps_model_bytes(nodes, elements, sections, loads);
    b->model_block = m_malloc(b->model_bytes);
    check(ps_model_init(&b->m, b->model_block, nodes, elements, sections, loads, cases));
    b->ctl.cancel = b->ctl.done = b->ctl.total = 0;
    b->status = PS_OK;
    b->precision = PRECISION_AUTO;
    b->busy = false;
    b->ready = false;
    return MP_OBJ_FROM_PTR(b);
}

static mp_obj_t beam_node(mp_obj_t self, mp_obj_t i, mp_obj_t x)
{
    editable(beam(self));
    check(ps_model_node(&beam(self)->m, mp_obj_get_int(i), (double)mp_obj_get_float(x)));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_3(beam_node_obj, beam_node);

static mp_obj_t beam_support(mp_obj_t self, mp_obj_t i, mp_obj_t flags)
{
    editable(beam(self));
    check(ps_model_support(&beam(self)->m, mp_obj_get_int(i), (uint32_t)mp_obj_get_int(flags)));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_3(beam_support_obj, beam_support);

static mp_obj_t beam_spring(size_t n, const mp_obj_t *args)
{
    (void)n;
    editable(beam(args[0]));
    check(ps_model_spring(&beam(args[0])->m, mp_obj_get_int(args[1]), (uint32_t)mp_obj_get_int(args[2]),
                          (double)mp_obj_get_float(args[3])));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_spring_obj, 4, 4, beam_spring);

static mp_obj_t beam_section(size_t n, const mp_obj_t *args)
{
    (void)n;
    editable(beam(args[0]));
    check(ps_model_section(&beam(args[0])->m, mp_obj_get_int(args[1]), (double)mp_obj_get_float(args[2]),
                           (double)mp_obj_get_float(args[3])));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_section_obj, 4, 4, beam_section);

static mp_obj_t beam_element(size_t n, const mp_obj_t *args)
{
    editable(beam(args[0]));
    check(ps_model_element(&beam(args[0])->m, mp_obj_get_int(args[1]), mp_obj_get_int(args[2]),
                           mp_obj_get_int(args[3]), n > 4 ? mp_obj_get_int(args[4]) : 0,
                           n > 5 ? (uint32_t)mp_obj_get_int(args[5]) : 0));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_element_obj, 4, 6, beam_element);

static void add_load(mp_obj_t self, ps_load_kind kind, mp_obj_t load_case, mp_obj_t target, uint32_t flag,
                     double a, double b2, double w1, double w2)
{
    beam_obj_t *b = beam(self);
    editable(b);
    if (b->m.load_count >= b->m.load_capacity)
        mp_raise_ValueError(MP_ERROR_TEXT("no room for more loads; create the Beam with a larger loads="));
    check(ps_model_load(&b->m, kind, mp_obj_get_int(load_case), mp_obj_get_int(target), flag, a, b2, w1, w2));
}

/* point(case, element, a, P): force at a from the element's start. */
static mp_obj_t beam_point(size_t n, const mp_obj_t *args)
{
    (void)n;
    add_load(args[0], PS_LOAD_POINT, args[1], args[2], 0, (double)mp_obj_get_float(args[3]), 0.0,
             (double)mp_obj_get_float(args[4]), 0.0);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_point_obj, 5, 5, beam_point);

/* moment(case, element, a, M): counterclockwise moment at a. */
static mp_obj_t beam_moment(size_t n, const mp_obj_t *args)
{
    (void)n;
    add_load(args[0], PS_LOAD_MOMENT, args[1], args[2], 0, (double)mp_obj_get_float(args[3]), 0.0,
             (double)mp_obj_get_float(args[4]), 0.0);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_moment_obj, 5, 5, beam_moment);

/* line(case, element, a, b, w1, w2=w1): load per metre from a to b. */
static mp_obj_t beam_line(size_t n, const mp_obj_t *args)
{
    const double w1 = (double)mp_obj_get_float(args[5]);
    add_load(args[0], PS_LOAD_LINE, args[1], args[2], 0, (double)mp_obj_get_float(args[3]), (double)mp_obj_get_float(args[4]),
             w1, n > 6 ? (double)mp_obj_get_float(args[6]) : w1);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_line_obj, 6, 7, beam_line);

/* node_load(case, node, flag, value): force (UY) or moment (RZ) on a node. */
static mp_obj_t beam_node_load(size_t n, const mp_obj_t *args)
{
    (void)n;
    add_load(args[0], PS_LOAD_NODE, args[1], args[2], (uint32_t)mp_obj_get_int(args[3]), 0.0, 0.0,
             (double)mp_obj_get_float(args[4]), 0.0);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_node_load_obj, 5, 5, beam_node_load);

/* settle(case, node, flag, value): prescribed movement of a support. */
static mp_obj_t beam_settle(size_t n, const mp_obj_t *args)
{
    (void)n;
    add_load(args[0], PS_LOAD_SETTLE, args[1], args[2], (uint32_t)mp_obj_get_int(args[3]), 0.0, 0.0,
             (double)mp_obj_get_float(args[4]), 0.0);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_settle_obj, 5, 5, beam_settle);

static mp_obj_t beam_clear_loads(mp_obj_t self)
{
    editable(beam(self));
    ps_model_clear_loads(&beam(self)->m);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(beam_clear_loads_obj, beam_clear_loads);

/* ------------------------------------------------------------------------ */
/* Solving                                                                  */
/* ------------------------------------------------------------------------ */

static ps_precision choose(beam_obj_t *b)
{
    if (b->precision != PRECISION_AUTO)
        return (ps_precision)b->precision;
    const int32_t n = b->m.equations > 0 ? b->m.equations : 1;
    return b->m.profile / (uint32_t)n >= AUTO_SINGLE_HEIGHT ? PS_SINGLE : PS_DOUBLE;
}

static void allocate_values(beam_obj_t *b, ps_precision precision)
{
    const size_t bytes = ps_model_value_bytes(&b->m, precision) + 8;
    b->value_block = renew(b->value_block, b->value_bytes, bytes);
    b->value_bytes = bytes;
    b->m.sky.precision = precision; /* the precision compute() uses */
}

/* begin(precision=AUTO): check and number the model, allocate everything.
 * Returns the bytes of the values block. */
static mp_obj_t beam_begin(size_t n, const mp_obj_t *args)
{
    beam_obj_t *b = beam(args[0]);
    if (b->busy)
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("model is being solved"));
    b->precision = n > 1 ? mp_obj_get_int(args[1]) : PRECISION_AUTO;
    if (b->precision != PRECISION_AUTO && b->precision != PS_DOUBLE && b->precision != PS_SINGLE)
        mp_raise_ValueError(MP_ERROR_TEXT("precision must be AUTO, DOUBLE or SINGLE"));
    const size_t index_bytes = ps_model_index_bytes(&b->m);
    b->index_block = renew(b->index_block, b->index_bytes, index_bytes);
    b->index_bytes = index_bytes;
    raise_status(b, ps_model_prepare(&b->m, b->index_block));
    allocate_values(b, choose(b));
    b->ctl.cancel = 0;
    b->ctl.done = 0;
    b->ctl.total = b->m.equations;
    b->status = PS_OK;
    b->ready = true;
    return mp_obj_new_int_from_uint(b->value_bytes);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_begin_obj, 1, 2, beam_begin);

/* compute(): the solve itself. Touches only memory allocated by begin(), so it
 * may run on another core; it records its status instead of raising. */
static mp_obj_t beam_compute(mp_obj_t self)
{
    beam_obj_t *b = beam(self);
    if (!b->ready || b->busy)
    {
        b->status = PS_ERR_STATE;
        return mp_const_none;
    }
    b->busy = true;
    MP_THREAD_GIL_EXIT();
    b->status = ps_model_solve(&b->m, b->value_block, b->m.sky.precision, &b->ctl);
    MP_THREAD_GIL_ENTER();
    b->busy = false;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(beam_compute_obj, beam_compute);

/* finish(): True when results are ready; False after setting up a retry in
 * double precision (run compute() again); raises the model's problem. */
static mp_obj_t beam_finish(mp_obj_t self)
{
    beam_obj_t *b = beam(self);
    if (b->busy)
        return mp_const_false;
    if (b->status == PS_ERR_ACCURACY && b->m.sky.precision == PS_SINGLE)
    {
        allocate_values(b, PS_DOUBLE);
        b->status = PS_OK;
        return mp_const_false;
    }
    raise_status(b, b->status);
    return mp_obj_new_bool(b->m.state == PS_STATE_SOLVED);
}
static MP_DEFINE_CONST_FUN_OBJ_1(beam_finish_obj, beam_finish);

/* solve(precision=AUTO): begin, compute and finish on this core. */
static mp_obj_t beam_solve(size_t n, const mp_obj_t *args)
{
    beam_begin(n, args);
    for (int attempt = 0; attempt < 2; attempt++)
    {
        beam_compute(args[0]);
        if (mp_obj_is_true(beam_finish(args[0])))
            return mp_const_none;
    }
    raise_status(beam(args[0]), PS_ERR_ACCURACY);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_solve_obj, 1, 2, beam_solve);

/* progress() -> (done, total) work units of the current factorization. */
static mp_obj_t beam_progress(mp_obj_t self)
{
    beam_obj_t *b = beam(self);
    mp_obj_t items[2] = {mp_obj_new_int(b->ctl.done), mp_obj_new_int(b->ctl.total)};
    return mp_obj_new_tuple(2, items);
}
static MP_DEFINE_CONST_FUN_OBJ_1(beam_progress_obj, beam_progress);

static mp_obj_t beam_cancel(mp_obj_t self)
{
    beam(self)->ctl.cancel = 1;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(beam_cancel_obj, beam_cancel);

static mp_obj_t beam_busy(mp_obj_t self)
{
    return mp_obj_new_bool(beam(self)->busy);
}
static MP_DEFINE_CONST_FUN_OBJ_1(beam_busy_obj, beam_busy);

/* ------------------------------------------------------------------------ */
/* Results                                                                  */
/* ------------------------------------------------------------------------ */

static beam_obj_t *solved(mp_obj_t self)
{
    beam_obj_t *b = beam(self);
    if (b->busy || b->m.state != PS_STATE_SOLVED)
        raise_status(b, PS_ERR_STATE);
    return b;
}

static int32_t case_arg(size_t n, const mp_obj_t *args, size_t index, const beam_obj_t *b)
{
    const mp_int_t c = n > index ? mp_obj_get_int(args[index]) : 0;
    if (c < 0 || c >= b->m.cases)
        mp_raise_ValueError(MP_ERROR_TEXT("no such load case"));
    return (int32_t)c;
}

static mp_obj_t tuple_of(const double *v, size_t count)
{
    mp_obj_t items[4];
    for (size_t i = 0; i < count; i++)
        items[i] = mp_obj_new_float((mp_float_t)v[i]);
    return mp_obj_new_tuple(count, items);
}

/* displacement(node, flag, case=0): metres (UY) or radians (RZ); NaN for the
 * rotation of a node that is a hinge on every side. */
static mp_obj_t beam_displacement(size_t n, const mp_obj_t *args)
{
    beam_obj_t *b = solved(args[0]);
    const int32_t c = case_arg(n, args, 3, b);
    const mp_int_t node = mp_obj_get_int(args[1]);
    if (node < 0 || node >= b->m.nodes)
        mp_raise_ValueError(MP_ERROR_TEXT("no such node"));
    return mp_obj_new_float((mp_float_t)ps_model_displacement(&b->m, c, node, (uint32_t)mp_obj_get_int(args[2])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_displacement_obj, 3, 4, beam_displacement);

/* reaction(node, case=0) -> (fy, mz) the support (or spring) applies. */
static mp_obj_t beam_reaction(size_t n, const mp_obj_t *args)
{
    beam_obj_t *b = solved(args[0]);
    double r[2];
    check(ps_model_reaction(&b->m, case_arg(n, args, 2, b), mp_obj_get_int(args[1]), r));
    return tuple_of(r, 2);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_reaction_obj, 2, 3, beam_reaction);

/* end_forces(element, case=0) -> (fy1, m1, fy2, m2) the nodes apply. */
static mp_obj_t beam_end_forces(size_t n, const mp_obj_t *args)
{
    beam_obj_t *b = solved(args[0]);
    double f[4];
    check(ps_model_end_forces(&b->m, case_arg(n, args, 2, b), mp_obj_get_int(args[1]), f));
    return tuple_of(f, 4);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_end_forces_obj, 2, 3, beam_end_forces);

/* at(element, x, case=0) -> (shear, moment, slope, deflection). */
static mp_obj_t beam_at(size_t n, const mp_obj_t *args)
{
    beam_obj_t *b = solved(args[0]);
    double out[4];
    check(ps_model_section_at(&b->m, case_arg(n, args, 3, b), mp_obj_get_int(args[1]),
                              (double)mp_obj_get_float(args[2]), out));
    return tuple_of(out, 4);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_at_obj, 3, 4, beam_at);

static float *float_buffer(mp_obj_t obj, mp_int_t samples)
{
    if (obj == mp_const_none)
        return NULL;
    mp_buffer_info_t info;
    mp_get_buffer_raise(obj, &info, MP_BUFFER_WRITE);
    if (info.typecode != 'f' || info.len < (size_t)samples * sizeof(float))
        mp_raise_ValueError(MP_ERROR_TEXT("diagram outputs must be array('f') of samples floats"));
    return info.buf;
}

/* diagram(element, samples, shear, moment, slope, deflection, case=0): fill
 * array('f') outputs (or None) with evenly spaced values along the element. */
static mp_obj_t beam_diagram(size_t n, const mp_obj_t *args)
{
    beam_obj_t *b = solved(args[0]);
    const mp_int_t samples = mp_obj_get_int(args[2]);
    if (samples < 2)
        mp_raise_ValueError(MP_ERROR_TEXT("need at least 2 samples"));
    check(ps_model_diagram(&b->m, case_arg(n, args, 7, b), mp_obj_get_int(args[1]), samples,
                           float_buffer(args[3], samples), float_buffer(args[4], samples),
                           float_buffer(args[5], samples), float_buffer(args[6], samples)));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(beam_diagram_obj, 7, 8, beam_diagram);

/* info() -> dict: equations, stored values, precision, refinement steps,
 * smallest pivot ratio (how well conditioned), memory per block. */
static mp_obj_t beam_info(mp_obj_t self)
{
    beam_obj_t *b = beam(self);
    mp_obj_t d = mp_obj_new_dict(8);
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_equations), mp_obj_new_int(b->m.equations));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_profile), mp_obj_new_int_from_uint(b->m.profile));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_precision),
                      MP_OBJ_NEW_QSTR(b->m.sky.precision == PS_SINGLE ? MP_QSTR_single : MP_QSTR_double));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_refinements), mp_obj_new_int(b->m.refinements));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_min_pivot_ratio),
                      mp_obj_new_float((mp_float_t)(b->m.state == PS_STATE_SOLVED ? b->m.info.min_ratio : 1.0)));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_ill_conditioned),
                      mp_obj_new_bool(b->m.state == PS_STATE_SOLVED && b->m.info.min_ratio < PS_PIVOT_WARNING));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_bytes),
                      mp_obj_new_int_from_uint(b->model_bytes + b->index_bytes + b->value_bytes));
    return d;
}
static MP_DEFINE_CONST_FUN_OBJ_1(beam_info_obj, beam_info);

static mp_obj_t beam_del(mp_obj_t self)
{
    beam_obj_t *b = beam(self);
    if (b->busy)
        return mp_const_none; /* never free memory a solve is using */
    b->model_block = renew(b->model_block, b->model_bytes, 0);
    b->index_block = renew(b->index_block, b->index_bytes, 0);
    b->value_block = renew(b->value_block, b->value_bytes, 0);
    b->ready = false;
    b->m.state = PS_STATE_EDITED;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(beam_del_obj, beam_del);

static const mp_rom_map_elem_t beam_locals_table[] = {
    {MP_ROM_QSTR(MP_QSTR_node), MP_ROM_PTR(&beam_node_obj)},
    {MP_ROM_QSTR(MP_QSTR_support), MP_ROM_PTR(&beam_support_obj)},
    {MP_ROM_QSTR(MP_QSTR_spring), MP_ROM_PTR(&beam_spring_obj)},
    {MP_ROM_QSTR(MP_QSTR_section), MP_ROM_PTR(&beam_section_obj)},
    {MP_ROM_QSTR(MP_QSTR_element), MP_ROM_PTR(&beam_element_obj)},
    {MP_ROM_QSTR(MP_QSTR_point), MP_ROM_PTR(&beam_point_obj)},
    {MP_ROM_QSTR(MP_QSTR_moment), MP_ROM_PTR(&beam_moment_obj)},
    {MP_ROM_QSTR(MP_QSTR_line), MP_ROM_PTR(&beam_line_obj)},
    {MP_ROM_QSTR(MP_QSTR_node_load), MP_ROM_PTR(&beam_node_load_obj)},
    {MP_ROM_QSTR(MP_QSTR_settle), MP_ROM_PTR(&beam_settle_obj)},
    {MP_ROM_QSTR(MP_QSTR_clear_loads), MP_ROM_PTR(&beam_clear_loads_obj)},
    {MP_ROM_QSTR(MP_QSTR_begin), MP_ROM_PTR(&beam_begin_obj)},
    {MP_ROM_QSTR(MP_QSTR_compute), MP_ROM_PTR(&beam_compute_obj)},
    {MP_ROM_QSTR(MP_QSTR_finish), MP_ROM_PTR(&beam_finish_obj)},
    {MP_ROM_QSTR(MP_QSTR_solve), MP_ROM_PTR(&beam_solve_obj)},
    {MP_ROM_QSTR(MP_QSTR_progress), MP_ROM_PTR(&beam_progress_obj)},
    {MP_ROM_QSTR(MP_QSTR_cancel), MP_ROM_PTR(&beam_cancel_obj)},
    {MP_ROM_QSTR(MP_QSTR_busy), MP_ROM_PTR(&beam_busy_obj)},
    {MP_ROM_QSTR(MP_QSTR_displacement), MP_ROM_PTR(&beam_displacement_obj)},
    {MP_ROM_QSTR(MP_QSTR_reaction), MP_ROM_PTR(&beam_reaction_obj)},
    {MP_ROM_QSTR(MP_QSTR_end_forces), MP_ROM_PTR(&beam_end_forces_obj)},
    {MP_ROM_QSTR(MP_QSTR_at), MP_ROM_PTR(&beam_at_obj)},
    {MP_ROM_QSTR(MP_QSTR_diagram), MP_ROM_PTR(&beam_diagram_obj)},
    {MP_ROM_QSTR(MP_QSTR_info), MP_ROM_PTR(&beam_info_obj)},
    {MP_ROM_QSTR(MP_QSTR_free), MP_ROM_PTR(&beam_del_obj)},
};
static MP_DEFINE_CONST_DICT(beam_locals, beam_locals_table);

MP_DEFINE_CONST_OBJ_TYPE(
    picosolve_beam_type,
    MP_QSTR_Beam,
    MP_TYPE_FLAG_NONE,
    make_new, beam_make_new,
    locals_dict, &beam_locals);

static const mp_rom_map_elem_t picosolve_globals_table[] = {
    {MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_picosolve)},
    {MP_ROM_QSTR(MP_QSTR_Beam), MP_ROM_PTR(&picosolve_beam_type)},
    {MP_ROM_QSTR(MP_QSTR_SolveError), MP_ROM_PTR(&mp_type_SolveError)},
    {MP_ROM_QSTR(MP_QSTR_UY), MP_ROM_INT(PS_UY)},
    {MP_ROM_QSTR(MP_QSTR_RZ), MP_ROM_INT(PS_RZ)},
    {MP_ROM_QSTR(MP_QSTR_RELEASE_START), MP_ROM_INT(PS_RELEASE_START)},
    {MP_ROM_QSTR(MP_QSTR_RELEASE_END), MP_ROM_INT(PS_RELEASE_END)},
    {MP_ROM_QSTR(MP_QSTR_AUTO), MP_ROM_INT(PRECISION_AUTO)},
    {MP_ROM_QSTR(MP_QSTR_DOUBLE), MP_ROM_INT(PS_DOUBLE)},
    {MP_ROM_QSTR(MP_QSTR_SINGLE), MP_ROM_INT(PS_SINGLE)},
};
static MP_DEFINE_CONST_DICT(picosolve_globals, picosolve_globals_table);

const mp_obj_module_t picosolve_module = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&picosolve_globals,
};

MP_REGISTER_MODULE(MP_QSTR_picosolve, picosolve_module);
