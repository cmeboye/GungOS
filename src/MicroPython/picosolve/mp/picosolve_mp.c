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
 *   f = ps.Formula("sin(x)*cos(y)", ("x", "y"), constants={"pi": math.pi})
 *   f(1.0, 2.0) -> float, or None where Python would raise or not be finite
 *   f.map(out, xs, 0.5)      # array('f') inputs or scalars -> results kept
 *   f.points(out, xyz, n)    # n interleaved points
 *   Formula(..., fallback=fn) # fn(*values): Python's answer for points whose
 *                             # whole numbers outgrow float32 (else undefined)
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
#include "../geom/mesh.h"
#include "../geom/contour.h"
#include "../expr/formula.h"
#include <math.h>
#include "py/parsenum.h"

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

/* The model, refusing one whose memory free() released. */
static beam_obj_t *beam(mp_obj_t self)
{
    beam_obj_t *b = MP_OBJ_TO_PTR(self);
    if (b->model_block == NULL)
        mp_raise_ValueError(MP_ERROR_TEXT("model memory was released by free()"));
    return b;
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

/* Replace a block. The old one goes first, since memory is tight; the slot
 * is empty while the new one is requested, so if that raises MemoryError
 * nothing is left pointing at freed memory. */
static void replace(void **slot, size_t *slot_bytes, size_t bytes)
{
    if (*slot)
        m_free(*slot);
    *slot = NULL;
    *slot_bytes = 0;
    if (bytes)
    {
        *slot = m_malloc(bytes);
        *slot_bytes = bytes;
    }
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
    b->ready = false; /* until the block exists */
    replace(&b->value_block, &b->value_bytes, ps_model_value_bytes(&b->m, precision) + 8);
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
    /* The numbering and values are rebuilt: nothing may use the old ones. */
    b->ready = false;
    b->m.state = PS_STATE_EDITED;
    replace(&b->value_block, &b->value_bytes, 0);
    replace(&b->index_block, &b->index_bytes, ps_model_index_bytes(&b->m));
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
    beam_obj_t *b = MP_OBJ_TO_PTR(self); /* never raises: may run on core 1 */
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
        b->ready = true;
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
    beam_obj_t *b = MP_OBJ_TO_PTR(self);
    mp_obj_t items[2] = {mp_obj_new_int(b->ctl.done), mp_obj_new_int(b->ctl.total)};
    return mp_obj_new_tuple(2, items);
}
static MP_DEFINE_CONST_FUN_OBJ_1(beam_progress_obj, beam_progress);

static mp_obj_t beam_cancel(mp_obj_t self)
{
    ((beam_obj_t *)MP_OBJ_TO_PTR(self))->ctl.cancel = 1;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(beam_cancel_obj, beam_cancel);

static mp_obj_t beam_busy(mp_obj_t self)
{
    return mp_obj_new_bool(((beam_obj_t *)MP_OBJ_TO_PTR(self))->busy);
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

/* free(): release the model's memory now. The model can no longer be used;
 * calling free() again does nothing. */
static mp_obj_t beam_del(mp_obj_t self)
{
    beam_obj_t *b = MP_OBJ_TO_PTR(self);
    if (b->busy)
        return mp_const_none; /* never free memory a solve is using */
    b->ready = false;
    b->m.state = PS_STATE_EDITED;
    replace(&b->value_block, &b->value_bytes, 0);
    replace(&b->index_block, &b->index_bytes, 0);
    replace(&b->model_block, &b->model_bytes, 0);
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

/* ------------------------------------------------------------------------ */
/* Geometry for plots: sampled surfaces and implicit (iso)surfaces           */
/* ------------------------------------------------------------------------ */

static float *floats(mp_obj_t obj, size_t need, bool write, const char *what)
{
    mp_buffer_info_t info;
    mp_get_buffer_raise(obj, &info, write ? MP_BUFFER_WRITE : MP_BUFFER_READ);
    if (info.typecode != 'f' || info.len < need * sizeof(float))
        mp_raise_msg_varg(&mp_type_ValueError, MP_ERROR_TEXT("%s must be array('f') of at least %d floats"),
                          what, (int)need);
    return info.buf;
}

/* grid_strip(row0, row1, xs, y0, y1, out) -> triangles written to out
 * (9 floats each, room for 2 * (len(xs) - 1)). */
static mp_obj_t geom_grid_strip(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t xs_info;
    mp_get_buffer_raise(args[2], &xs_info, MP_BUFFER_READ);
    const size_t n = xs_info.len / sizeof(float);
    const float *xs = floats(args[2], n, false, "xs");
    const float *row0 = floats(args[0], n, false, "row0");
    const float *row1 = floats(args[1], n, false, "row1");
    mp_buffer_info_t out_info;
    mp_get_buffer_raise(args[5], &out_info, MP_BUFFER_WRITE);
    const int capacity = (int)(out_info.len / (9 * sizeof(float)));
    float *out = floats(args[5], 9, true, "out");
    if (n < 2 || capacity < 2 * ((int)n - 1))
        mp_raise_ValueError(MP_ERROR_TEXT("out needs room for 2 * (len(xs) - 1) triangles"));
    return mp_obj_new_int(ps_grid_strip(row0, row1, xs, (int)n, (float)mp_obj_get_float(args[3]),
                                        (float)mp_obj_get_float(args[4]), out, capacity));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(geom_grid_strip_obj, 6, 6, geom_grid_strip);

/* iso_slab(prev, cur, coords, z0, z1, triangles, centres, limits, cube) ->
 * (count, next_cube): marching tetrahedra between two sampled planes. */
static mp_obj_t geom_iso_slab(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t c_info;
    mp_get_buffer_raise(args[2], &c_info, MP_BUFFER_READ);
    const size_t n = c_info.len / sizeof(float);
    if (n < 2)
        mp_raise_ValueError(MP_ERROR_TEXT("need at least 2 coordinates"));
    const float *coords = floats(args[2], n, false, "coords");
    const float *prev = floats(args[0], n * n, false, "prev");
    const float *cur = floats(args[1], n * n, false, "cur");
    mp_buffer_info_t t_info;
    mp_get_buffer_raise(args[5], &t_info, MP_BUFFER_WRITE);
    const int capacity = (int)(t_info.len / (9 * sizeof(float)));
    if (capacity < PS_MESH_PER_CUBE)
        mp_raise_ValueError(MP_ERROR_TEXT("triangles needs room for at least 12 triangles"));
    float *triangles = floats(args[5], (size_t)capacity * 9, true, "triangles");
    float *centres = floats(args[6], (size_t)capacity * 3, true, "centres");
    float *limits = floats(args[7], (size_t)capacity, true, "limits");
    int32_t cube = (int32_t)mp_obj_get_int(args[8]);
    if (cube < 0)
        cube = 0;
    const int count = ps_iso_slab(prev, cur, coords, (int)n, (float)mp_obj_get_float(args[3]),
                                  (float)mp_obj_get_float(args[4]), triangles, centres, limits, capacity, &cube);
    mp_obj_t items[2] = {mp_obj_new_int(count), mp_obj_new_int(cube)};
    return mp_obj_new_tuple(2, items);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(geom_iso_slab_obj, 9, 9, geom_iso_slab);

typedef struct
{
    const float *upper, *lower, *centres, *xs;
    int n;
    float y0, y1;
} contour_args;

static void contour_inputs(const mp_obj_t *args, contour_args *c)
{
    mp_buffer_info_t xs_info;
    mp_get_buffer_raise(args[3], &xs_info, MP_BUFFER_READ);
    c->n = (int)(xs_info.len / sizeof(float));
    if (c->n < 2)
        mp_raise_ValueError(MP_ERROR_TEXT("need at least 2 samples"));
    c->xs = floats(args[3], (size_t)c->n, false, "xs");
    c->upper = floats(args[0], (size_t)c->n, false, "upper");
    c->lower = floats(args[1], (size_t)c->n, false, "lower");
    c->centres = floats(args[2], (size_t)c->n - 1, false, "centres");
    c->y0 = (float)mp_obj_get_float(args[4]);
    c->y1 = (float)mp_obj_get_float(args[5]);
}

/* contour_queries(upper, lower, centres, xs, y0, y1, queries) -> count of
 * edge midpoints (x, y pairs) to evaluate for the pole check. */
static mp_obj_t geom_contour_queries(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    contour_args c;
    contour_inputs(args, &c);
    mp_buffer_info_t q;
    mp_get_buffer_raise(args[6], &q, MP_BUFFER_WRITE);
    const int capacity = (int)(q.len / (2 * sizeof(float)));
    if (capacity < 4 * (c.n - 1))
        mp_raise_ValueError(MP_ERROR_TEXT("queries needs room for 4 points per cell"));
    float *queries = floats(args[6], (size_t)capacity * 2, true, "queries");
    return mp_obj_new_int(ps_contour_queries(c.upper, c.lower, c.centres, c.xs, c.n, c.y0, c.y1, queries, capacity));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(geom_contour_queries_obj, 7, 7, geom_contour_queries);

/* contour_segments(upper, lower, centres, xs, y0, y1, mids, segments) ->
 * count of segments (x0, y0, x1, y1). mids: the queried values, or None. */
static mp_obj_t geom_contour_segments(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    contour_args c;
    contour_inputs(args, &c);
    const float *mids = NULL;
    if (args[6] != mp_const_none)
    {
        mp_buffer_info_t m;
        mp_get_buffer_raise(args[6], &m, MP_BUFFER_READ);
        mids = floats(args[6], m.len / sizeof(float), false, "mids");
    }
    mp_buffer_info_t s;
    mp_get_buffer_raise(args[7], &s, MP_BUFFER_WRITE);
    const int capacity = (int)(s.len / (4 * sizeof(float)));
    if (capacity < 2 * (c.n - 1))
        mp_raise_ValueError(MP_ERROR_TEXT("segments needs room for 2 per cell"));
    float *segments = floats(args[7], (size_t)capacity * 4, true, "segments");
    return mp_obj_new_int(ps_contour_segments(c.upper, c.lower, c.centres, c.xs, c.n, c.y0, c.y1, mids,
                                              segments, capacity));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(geom_contour_segments_obj, 8, 8, geom_contour_segments);

/* ------------------------------------------------------------------------ */
/* Formulas: compiled once, evaluated at many points (see expr/formula.h)    */
/* ------------------------------------------------------------------------ */

#define FORMULA_MAX_NAMES PSF_MAX_CONSTANTS

typedef struct
{
    mp_obj_base_t base;
    float limit;
    void *scratch;
    mp_obj_t fallback; /* Python's evaluation, for points flagged inexact */
    psf_program program;
} formula_obj_t;

#define FORMULA_CHUNK 128

const mp_obj_type_t picosolve_formula_type;

/* Number literals become floats exactly as the interpreter's lexer makes them. */
static float formula_number(const char *text, int length, bool integer, void *context)
{
    (void)context;
    mp_obj_t v = integer ? mp_parse_num_integer(text, (size_t)length, 10, NULL)
                         : mp_parse_num_float(text, (size_t)length, false, NULL);
    return (float)mp_obj_get_float(v);
}

/* A dict of names: keys into names[], values as floats or strings. */
static int formula_names(mp_obj_t dict, const char **names, float *values, const char **texts)
{
    if (dict == mp_const_none)
        return 0;
    mp_map_t *map = mp_obj_dict_get_map(dict);
    int count = 0;
    for (size_t i = 0; i < map->alloc; i++)
    {
        if (!mp_map_slot_is_filled(map, i))
            continue;
        if (count >= FORMULA_MAX_NAMES)
            mp_raise_ValueError(MP_ERROR_TEXT("too many names"));
        names[count] = mp_obj_str_get_str(map->table[i].key);
        if (values)
            values[count] = (float)mp_obj_get_float(map->table[i].value);
        else
            texts[count] = mp_obj_str_get_str(map->table[i].value);
        count++;
    }
    return count;
}

static mp_obj_t formula_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *all_args)
{
    enum { ARG_text, ARG_variables, ARG_constants, ARG_derived, ARG_limit, ARG_fallback };
    static const mp_arg_t allowed[] = {
        {MP_QSTR_text, MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL}},
        {MP_QSTR_variables, MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL}},
        {MP_QSTR_constants, MP_ARG_OBJ, {.u_obj = mp_const_none}},
        {MP_QSTR_derived, MP_ARG_OBJ, {.u_obj = mp_const_none}},
        {MP_QSTR_limit, MP_ARG_OBJ, {.u_obj = mp_const_none}},
        {MP_QSTR_fallback, MP_ARG_OBJ, {.u_obj = mp_const_none}},
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed)];
    mp_arg_parse_all_kw_array(n_args, n_kw, all_args, MP_ARRAY_SIZE(allowed), allowed, args);

    size_t length;
    const char *text = mp_obj_str_get_data(args[ARG_text].u_obj, &length);
    size_t variable_count;
    mp_obj_t *variable_objs;
    mp_obj_get_array(args[ARG_variables].u_obj, &variable_count, &variable_objs);
    if (variable_count > PSF_MAX_VARIABLES)
        mp_raise_ValueError(MP_ERROR_TEXT("too many variables"));
    const char *variables[PSF_MAX_VARIABLES];
    for (size_t i = 0; i < variable_count; i++)
        variables[i] = mp_obj_str_get_str(variable_objs[i]);
    const char *constant_names[FORMULA_MAX_NAMES], *derived_names[FORMULA_MAX_NAMES];
    const char *derived_texts[FORMULA_MAX_NAMES];
    float constant_values[FORMULA_MAX_NAMES];

    psf_options o = {0};
    o.variables = variables;
    o.variable_count = (int)variable_count;
    o.constant_names = constant_names;
    o.constant_values = constant_values;
    o.constant_count = formula_names(args[ARG_constants].u_obj, constant_names, constant_values, NULL);
    o.derived_names = derived_names;
    o.derived_texts = derived_texts;
    o.derived_count = formula_names(args[ARG_derived].u_obj, derived_names, NULL, derived_texts);
    o.number = formula_number;
    o.pow_fix_nan = MICROPY_PY_MATH_POW_FIX_NAN;
    o.atan2_fix_infnan = MICROPY_PY_MATH_ATAN2_FIX_INFNAN;

    formula_obj_t *f = mp_obj_malloc(formula_obj_t, type);
    f->limit = args[ARG_limit].u_obj == mp_const_none ? INFINITY : (float)mp_obj_get_float(args[ARG_limit].u_obj);
    f->fallback = args[ARG_fallback].u_obj;
    f->scratch = NULL;
    int at = 0;
    const psf_status status = psf_compile(&f->program, text, (int)length, &o, &at);
    if (status != PSF_OK)
    {
        static const char *const reasons[] = {"", "syntax", "name", "arguments", "unsupported", "too long"};
        mp_raise_msg_varg(&mp_type_ValueError, MP_ERROR_TEXT("formula not compiled (%s at %d)"),
                          reasons[status], at);
    }
    f->scratch = m_new(uint8_t, psf_scratch_bytes(&f->program));
    return MP_OBJ_FROM_PTR(f);
}

static bool formula_keep(const formula_obj_t *f, float v)
{
    return isfinite(v) && fabsf(v) <= f->limit;
}

/* Evaluate count points into out; points flagged inexact are evaluated by
 * the fallback (or stay undefined without one). Returns the results kept. */
static int formula_run(formula_obj_t *f, const psf_input *inputs, int count, float *out)
{
    const int variables = f->program.variable_count;
    uint8_t flags[FORMULA_CHUNK];
    int kept = 0;
    for (int base = 0; base < count; base += FORMULA_CHUNK)
    {
        const int n = count - base < FORMULA_CHUNK ? count - base : FORMULA_CHUNK;
        psf_input chunk[PSF_MAX_VARIABLES];
        for (int v = 0; v < variables; v++)
        {
            chunk[v] = inputs[v];
            if (chunk[v].data)
                chunk[v].data += (ptrdiff_t)base * chunk[v].stride;
        }
        kept += psf_eval(&f->program, chunk, n, f->limit, out + base, flags, f->scratch);
        if (f->fallback == mp_const_none)
            continue;
        for (int i = 0; i < n; i++)
        {
            if (!flags[i])
                continue;
            mp_obj_t values[PSF_MAX_VARIABLES];
            for (int v = 0; v < variables; v++)
                values[v] = mp_obj_new_float(chunk[v].data ? chunk[v].data[(ptrdiff_t)i * chunk[v].stride]
                                                           : chunk[v].value);
            const mp_obj_t r = mp_call_function_n_kw(f->fallback, (size_t)variables, 0, values);
            float value = r == mp_const_none ? NAN : (float)mp_obj_get_float(r);
            if (formula_keep(f, value))
                kept++;
            else
                value = NAN;
            out[base + i] = value;
        }
    }
    return kept;
}

/* f(*values) -> float, or None when undefined there. A point left to the
 * fallback returns its answer unchanged (a Python int stays exact). */
static mp_obj_t formula_call(mp_obj_t self_in, size_t n_args, size_t n_kw, const mp_obj_t *args)
{
    formula_obj_t *f = MP_OBJ_TO_PTR(self_in);
    mp_arg_check_num(n_args, n_kw, f->program.variable_count, f->program.variable_count, false);
    psf_input inputs[PSF_MAX_VARIABLES];
    for (size_t i = 0; i < n_args; i++)
        inputs[i] = (psf_input){NULL, 0, (float)mp_obj_get_float(args[i])};
    float out;
    uint8_t flag = 0;
    if (psf_eval(&f->program, inputs, 1, f->limit, &out, &flag, f->scratch))
        return mp_obj_new_float(out);
    if (!flag || f->fallback == mp_const_none)
        return mp_const_none;
    const mp_obj_t r = mp_call_function_n_kw(f->fallback, n_args, 0, args);
    return r != mp_const_none && formula_keep(f, (float)mp_obj_get_float(r)) ? r : mp_const_none;
}

/* map(out, *inputs) -> results kept; each input is array('f') or a number. */
static mp_obj_t formula_map(size_t n_args, const mp_obj_t *args)
{
    formula_obj_t *f = MP_OBJ_TO_PTR(args[0]);
    if (n_args != 2 + (size_t)f->program.variable_count)
        mp_raise_TypeError(MP_ERROR_TEXT("map(out, one input per variable)"));
    mp_buffer_info_t out_info;
    mp_get_buffer_raise(args[1], &out_info, MP_BUFFER_WRITE);
    const size_t count = out_info.len / sizeof(float);
    float *out = floats(args[1], count, true, "out");
    psf_input inputs[PSF_MAX_VARIABLES];
    for (size_t i = 0; i < (size_t)f->program.variable_count; i++)
    {
        mp_obj_t a = args[2 + i];
        if (mp_obj_is_float(a) || mp_obj_is_int(a))
            inputs[i] = (psf_input){NULL, 0, (float)mp_obj_get_float(a)};
        else
            inputs[i] = (psf_input){floats(a, count, false, "input"), 1, 0.0f};
    }
    return mp_obj_new_int(formula_run(f, inputs, (int)count, out));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(formula_map_obj, 2, 2 + PSF_MAX_VARIABLES, formula_map);

/* points(out, flat, count) -> results kept; flat holds count interleaved points. */
static mp_obj_t formula_points(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    formula_obj_t *f = MP_OBJ_TO_PTR(args[0]);
    const mp_int_t count = mp_obj_get_int(args[3]);
    if (count < 0)
        mp_raise_ValueError(MP_ERROR_TEXT("count must not be negative"));
    const int stride = f->program.variable_count;
    float *out = floats(args[1], (size_t)count, true, "out");
    const float *flat = floats(args[2], (size_t)count * (size_t)stride, false, "points");
    psf_input inputs[PSF_MAX_VARIABLES];
    for (int i = 0; i < stride; i++)
        inputs[i] = (psf_input){flat + i, stride, 0.0f};
    return mp_obj_new_int(formula_run(f, inputs, (int)count, out));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(formula_points_obj, 4, 4, formula_points);

static const mp_rom_map_elem_t formula_locals_table[] = {
    {MP_ROM_QSTR(MP_QSTR_map), MP_ROM_PTR(&formula_map_obj)},
    {MP_ROM_QSTR(MP_QSTR_points), MP_ROM_PTR(&formula_points_obj)},
};
static MP_DEFINE_CONST_DICT(formula_locals, formula_locals_table);

MP_DEFINE_CONST_OBJ_TYPE(
    picosolve_formula_type,
    MP_QSTR_Formula,
    MP_TYPE_FLAG_NONE,
    make_new, formula_make_new,
    call, formula_call,
    locals_dict, &formula_locals);

static const mp_rom_map_elem_t picosolve_globals_table[] = {
    {MP_ROM_QSTR(MP_QSTR_grid_strip), MP_ROM_PTR(&geom_grid_strip_obj)},
    {MP_ROM_QSTR(MP_QSTR_contour_queries), MP_ROM_PTR(&geom_contour_queries_obj)},
    {MP_ROM_QSTR(MP_QSTR_contour_segments), MP_ROM_PTR(&geom_contour_segments_obj)},
    {MP_ROM_QSTR(MP_QSTR_iso_slab), MP_ROM_PTR(&geom_iso_slab_obj)},
    {MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_picosolve)},
    {MP_ROM_QSTR(MP_QSTR_Beam), MP_ROM_PTR(&picosolve_beam_type)},
    {MP_ROM_QSTR(MP_QSTR_Formula), MP_ROM_PTR(&picosolve_formula_type)},
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
