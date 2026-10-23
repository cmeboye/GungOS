/*
 * picosolve MicroPython binding: the Circuit model (see fe/circuit.h).
 *
 *   C = ps.Circuit
 *   c = C(nodes, elements, values=0, probes=8)  # values: room for all element
 *                                               # and waveform values (0: 4 each + 32)
 *   c.element(i, C.R, (a, b), (1e3,))           # F and H: ctrl=j
 *   c.wave(i, C.PULSE, (v1, v2, td, tr, tf, pw, per))
 *   c.probe(k, C.VOLTAGE, a, b=0); c.probe(k, C.CURRENT, element, terminal)
 *   c.op(); c.voltage(node); c.current(element, terminal)
 *   c.dc(source, start, stop, points); c.tran(stop, points, hmax=0, uic=False)
 *   while not c.run(30): show(c.progress())     # ms per slice; True when done
 *   c.trace(k, out)       # probe k's samples so far into array('f'); -> count
 *   c.error() -> (node, element) the last problem named, -1 where none
 *   c.info() -> dict: equations, entries, factors, bytes, iterations, steps, rejected
 *   c.free()
 *
 * The matrix order and pattern are built on the first analysis after an
 * edit. Every block lives on the MicroPython heap with the object; the LU
 * block is enlarged and the call repeated whenever the kernel asks.
 * Problems raise picosolve.SolveError naming the node or element at fault.
 */
#include "py/runtime.h"
#include "py/mphal.h"
#include "../fe/circuit.h"
#include <math.h>

extern const mp_obj_type_t mp_type_SolveError;

enum
{
    MODEL,
    INDEX,
    VALUES,
    LU,
    OUT,
    BLOCKS
};

typedef struct
{
    mp_obj_base_t base;
    ps_cir c;
    void *block[BLOCKS];
    size_t bytes[BLOCKS];
    int32_t cap;
} circuit_obj_t;

static circuit_obj_t *circuit(mp_obj_t self)
{
    circuit_obj_t *k = MP_OBJ_TO_PTR(self);
    if (k->block[MODEL] == NULL)
        mp_raise_ValueError(MP_ERROR_TEXT("circuit memory was released by free()"));
    return k;
}

/* Replace a block, the old one first since memory is tight. */
static void *replace(circuit_obj_t *k, int which, size_t bytes)
{
    if (k->block[which])
        m_free(k->block[which]);
    k->block[which] = NULL;
    k->bytes[which] = 0;
    if (bytes)
    {
        k->block[which] = m_malloc(bytes);
        k->bytes[which] = bytes;
    }
    return k->block[which];
}

static void raise_status(circuit_obj_t *k, ps_status status)
{
    const int node = (int)k->c.error_node, element = (int)k->c.error_element;
    switch (status)
    {
    case PS_OK:
    case PS_PENDING:
        return;
    case PS_CANCELLED:
        mp_raise_msg(&mp_type_SolveError, MP_ERROR_TEXT("analysis cancelled"));
    case PS_ERR_UNCONNECTED:
        mp_raise_msg_varg(&mp_type_SolveError, MP_ERROR_TEXT("node %d is not connected"), node);
    case PS_ERR_SINGULAR:
        if (node > 0)
            mp_raise_msg_varg(&mp_type_SolveError, MP_ERROR_TEXT("node %d has no DC path to ground"), node);
        if (element >= 0)
            mp_raise_msg_varg(&mp_type_SolveError,
                              MP_ERROR_TEXT("element %d: its voltage is set twice (shorted, or a loop of sources)"),
                              element);
        mp_raise_msg(&mp_type_SolveError, MP_ERROR_TEXT("the circuit has no unique solution"));
    case PS_ERR_CONVERGENCE:
        if (k->c.analysis == PS_AN_TRAN)
            mp_raise_msg_varg(&mp_type_SolveError, MP_ERROR_TEXT("no convergence at t = %g s"), (double)k->c.time);
        if (k->c.analysis == PS_AN_DC)
            mp_raise_msg_varg(&mp_type_SolveError, MP_ERROR_TEXT("no convergence at sweep point %d"),
                              (int)k->c.done + 1);
        mp_raise_msg(&mp_type_SolveError, MP_ERROR_TEXT("the operating point does not converge"));
    case PS_ERR_TIMESTEP:
        mp_raise_msg_varg(&mp_type_SolveError, MP_ERROR_TEXT("time step too small at t = %g s"), (double)k->c.time);
    case PS_ERR_STATE:
        mp_raise_msg(&mp_type_SolveError, MP_ERROR_TEXT("run an analysis first"));
    case PS_ERR_ARGUMENT:
        if (element >= 0)
            mp_raise_msg_varg(&mp_type_SolveError,
                              MP_ERROR_TEXT("element %d: missing, bad nodes or values, or no branch to control it"),
                              element);
        mp_raise_ValueError(MP_ERROR_TEXT("invalid index or value"));
    default:
        mp_raise_ValueError(MP_ERROR_TEXT("invalid value"));
    }
}

/* ------------------------------------------------------------------------ */
/* Building                                                                 */
/* ------------------------------------------------------------------------ */

static mp_obj_t circuit_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *all)
{
    enum
    {
        ARG_nodes,
        ARG_elements,
        ARG_values,
        ARG_probes
    };
    static const mp_arg_t allowed[] = {
        {MP_QSTR_nodes, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0}},
        {MP_QSTR_elements, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0}},
        {MP_QSTR_values, MP_ARG_INT, {.u_int = 0}},
        {MP_QSTR_probes, MP_ARG_INT, {.u_int = 8}},
    };
    mp_arg_val_t a[MP_ARRAY_SIZE(allowed)];
    mp_arg_parse_all_kw_array(n_args, n_kw, all, MP_ARRAY_SIZE(allowed), allowed, a);
    const mp_int_t nodes = a[ARG_nodes].u_int, elements = a[ARG_elements].u_int, probes = a[ARG_probes].u_int;
    mp_int_t values = a[ARG_values].u_int;
    if (values <= 0)
        values = 4 * elements + 32;
    if (nodes < 2 || nodes > 4000 || elements < 1 || elements > 4000 || values > 1000000 || probes < 0 ||
        probes > 64)
        mp_raise_ValueError(MP_ERROR_TEXT("need 2+ nodes, 1+ elements and 0-64 probes"));
    circuit_obj_t *k = mp_obj_malloc(circuit_obj_t, type);
    for (int i = 0; i < BLOCKS; i++)
    {
        k->block[i] = NULL;
        k->bytes[i] = 0;
    }
    k->cap = 0;
    replace(k, MODEL, ps_cir_bytes(nodes, elements, values, probes));
    if (ps_cir_init(&k->c, k->block[MODEL], nodes, elements, values, probes) != PS_OK)
        mp_raise_ValueError(MP_ERROR_TEXT("invalid circuit size"));
    return MP_OBJ_FROM_PTR(k);
}

/* A tuple or list of numbers as doubles; at most limit of them. */
static size_t numbers(mp_obj_t seq, double *out, size_t limit)
{
    size_t count;
    mp_obj_t *items;
    mp_obj_get_array(seq, &count, &items);
    if (count > limit)
        mp_raise_ValueError(MP_ERROR_TEXT("too many values"));
    for (size_t i = 0; i < count; i++)
        out[i] = (double)mp_obj_get_float(items[i]);
    return count;
}

static void edit(circuit_obj_t *k, ps_status status)
{
    replace(k, OUT, 0);
    if (status != PS_OK)
        raise_status(k, status);
}

/* element(i, kind, nodes, values, ctrl=-1) */
static mp_obj_t circuit_element(size_t n, const mp_obj_t *args)
{
    circuit_obj_t *k = circuit(args[0]);
    size_t count;
    mp_obj_t *items;
    mp_obj_get_array(args[3], &count, &items);
    if (count > PS_EL_TERMINALS)
        mp_raise_ValueError(MP_ERROR_TEXT("at most 4 nodes"));
    int32_t nodes[PS_EL_TERMINALS];
    for (size_t i = 0; i < count; i++)
        nodes[i] = (int32_t)mp_obj_get_int(items[i]);
    double values[8];
    const size_t nvalues = numbers(args[4], values, 8);
    edit(k, ps_cir_element(&k->c, mp_obj_get_int(args[1]), (ps_el_kind)mp_obj_get_int(args[2]), nodes, (int)count,
                           values, (int)nvalues, n > 5 ? mp_obj_get_int(args[5]) : -1));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(circuit_element_obj, 5, 6, circuit_element);

/* wave(i, shape, values) for a V or I source. */
static mp_obj_t circuit_wave(size_t n, const mp_obj_t *args)
{
    (void)n;
    circuit_obj_t *k = circuit(args[0]);
    size_t count;
    mp_obj_t *items;
    mp_obj_get_array(args[3], &count, &items);
    if (count > 254)
        mp_raise_ValueError(MP_ERROR_TEXT("at most 127 PWL points"));
    double *values = m_new(double, count + 1);
    for (size_t i = 0; i < count; i++)
        values[i] = (double)mp_obj_get_float(items[i]);
    const ps_status status = ps_cir_wave(&k->c, mp_obj_get_int(args[1]), (ps_wave)mp_obj_get_int(args[2]), values,
                                         (int)count);
    m_del(double, values, count + 1);
    edit(k, status);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(circuit_wave_obj, 4, 4, circuit_wave);

/* probe(k, VOLTAGE, a, b=0) or probe(k, CURRENT, element, terminal) */
static mp_obj_t circuit_probe(size_t n, const mp_obj_t *args)
{
    circuit_obj_t *k = circuit(args[0]);
    edit(k, ps_cir_probe(&k->c, mp_obj_get_int(args[1]), (ps_probe_kind)mp_obj_get_int(args[2]),
                         mp_obj_get_int(args[3]), n > 4 ? mp_obj_get_int(args[4]) : 0));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(circuit_probe_obj, 4, 5, circuit_probe);

/* ------------------------------------------------------------------------ */
/* Analyses                                                                 */
/* ------------------------------------------------------------------------ */

/* Pattern, order and the solve blocks, built once per edit. */
static void prepare(circuit_obj_t *k)
{
    if (k->c.prepared)
        return;
    replace(k, VALUES, 0);
    replace(k, LU, 0);
    replace(k, INDEX, ps_cir_index_bytes(&k->c));
    /* The scratch block is gone before the solve blocks are requested. */
    const size_t scratch_bytes = ps_cir_scratch_bytes(&k->c);
    void *scratch = m_malloc(scratch_bytes);
    const ps_status status = ps_cir_prepare(&k->c, k->block[INDEX], scratch);
    m_free(scratch);
    raise_status(k, status);
    replace(k, VALUES, ps_cir_value_bytes(&k->c));
    k->cap = ps_cir_lu_capacity(&k->c);
    replace(k, LU, ps_lu_bytes(k->c.n, k->cap));
    ps_cir_attach(&k->c, k->block[VALUES], k->block[LU], k->cap);
}

/* Enlarge the LU block by half after PS_ERR_SPACE; the factors are
 * rebuilt anyway. */
static void grow(circuit_obj_t *k)
{
    const int32_t n = k->c.n, full = (int32_t)(((int64_t)n * (n + 1)) / 2);
    const int32_t more = k->cap + k->cap / 2 + 8;
    k->cap = more < full ? more : full;
    replace(k, LU, ps_lu_bytes(n, k->cap));
    ps_cir_attach_lu(&k->c, k->block[LU], k->cap);
}

static float *output(circuit_obj_t *k, mp_int_t points)
{
    if (points < 1 || points > 100000)
        mp_raise_ValueError(MP_ERROR_TEXT("points must be 1-100000"));
    return replace(k, OUT, (size_t)points * (size_t)k->c.probes * sizeof(float) + sizeof(float));
}

static mp_obj_t circuit_op(mp_obj_t self)
{
    circuit_obj_t *k = circuit(self);
    prepare(k);
    replace(k, OUT, 0);
    ps_status status;
    while ((status = ps_cir_op(&k->c)) == PS_ERR_SPACE)
        grow(k);
    raise_status(k, status);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(circuit_op_obj, circuit_op);

/* dc(source, start, stop, points): sweep a V or I source's value. */
static mp_obj_t circuit_dc(size_t n, const mp_obj_t *args)
{
    (void)n;
    circuit_obj_t *k = circuit(args[0]);
    prepare(k);
    const mp_int_t points = mp_obj_get_int(args[4]);
    float *out = output(k, points);
    ps_status status;
    while ((status = ps_cir_dc(&k->c, mp_obj_get_int(args[1]), (double)mp_obj_get_float(args[2]),
                               (double)mp_obj_get_float(args[3]), points, out)) == PS_ERR_SPACE)
        grow(k);
    raise_status(k, status);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(circuit_dc_obj, 5, 5, circuit_dc);

/* tran(stop, points, hmax=0, uic=False): the operating point (unless uic)
 * is solved here; run() then steps in time. */
static mp_obj_t circuit_tran(size_t n, const mp_obj_t *args)
{
    circuit_obj_t *k = circuit(args[0]);
    prepare(k);
    const mp_int_t points = mp_obj_get_int(args[2]);
    float *out = output(k, points);
    const double hmax = n > 3 ? (double)mp_obj_get_float(args[3]) : 0.0;
    const int uic = n > 4 && mp_obj_is_true(args[4]);
    ps_status status;
    while ((status = ps_cir_tran(&k->c, (double)mp_obj_get_float(args[1]), points, hmax, uic, out)) == PS_ERR_SPACE)
        grow(k);
    raise_status(k, status);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(circuit_tran_obj, 3, 5, circuit_tran);

/* run(ms=30) -> True once the sweep or transient is complete. */
static mp_obj_t circuit_run(size_t n, const mp_obj_t *args)
{
    circuit_obj_t *k = circuit(args[0]);
    const mp_int_t budget = n > 1 ? mp_obj_get_int(args[1]) : 30;
    const mp_uint_t start = mp_hal_ticks_ms();
    for (;;)
    {
        const ps_status status = ps_cir_run(&k->c, 1, NULL);
        if (status == PS_ERR_SPACE)
            grow(k);
        else if (status == PS_OK)
            return mp_const_true;
        else if (status != PS_PENDING)
            raise_status(k, status);
        else if ((mp_int_t)(mp_hal_ticks_ms() - start) >= budget)
            return mp_const_false;
    }
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(circuit_run_obj, 1, 2, circuit_run);

static mp_obj_t circuit_progress(mp_obj_t self)
{
    circuit_obj_t *k = circuit(self);
    mp_obj_t items[2] = {mp_obj_new_int(k->c.done), mp_obj_new_int(k->c.points)};
    return mp_obj_new_tuple(2, items);
}
static MP_DEFINE_CONST_FUN_OBJ_1(circuit_progress_obj, circuit_progress);

/* ------------------------------------------------------------------------ */
/* Results                                                                  */
/* ------------------------------------------------------------------------ */

static mp_obj_t value_or_raise(circuit_obj_t *k, double value)
{
    if (k->c.analysis == PS_AN_NONE)
        raise_status(k, PS_ERR_STATE);
    if (isnan(value))
        mp_raise_ValueError(MP_ERROR_TEXT("no such node, element or terminal"));
    return mp_obj_new_float((mp_float_t)value);
}

static mp_obj_t circuit_voltage(mp_obj_t self, mp_obj_t node)
{
    circuit_obj_t *k = circuit(self);
    return value_or_raise(k, ps_cir_voltage(&k->c, mp_obj_get_int(node)));
}
static MP_DEFINE_CONST_FUN_OBJ_2(circuit_voltage_obj, circuit_voltage);

static mp_obj_t circuit_current(mp_obj_t self, mp_obj_t element, mp_obj_t terminal)
{
    circuit_obj_t *k = circuit(self);
    return value_or_raise(k, ps_cir_current(&k->c, mp_obj_get_int(element), mp_obj_get_int(terminal)));
}
static MP_DEFINE_CONST_FUN_OBJ_3(circuit_current_obj, circuit_current);

/* trace(k, out) -> samples recorded so far, copied into array('f') out. */
static mp_obj_t circuit_trace(mp_obj_t self, mp_obj_t probe, mp_obj_t out)
{
    circuit_obj_t *k = circuit(self);
    const mp_int_t p = mp_obj_get_int(probe);
    if (k->block[OUT] == NULL)
        raise_status(k, PS_ERR_STATE);
    if (p < 0 || p >= k->c.probes)
        mp_raise_ValueError(MP_ERROR_TEXT("no such probe"));
    mp_buffer_info_t info;
    mp_get_buffer_raise(out, &info, MP_BUFFER_WRITE);
    const size_t count = (size_t)k->c.done;
    if (info.typecode != 'f' || info.len < count * sizeof(float))
        mp_raise_msg_varg(&mp_type_ValueError, MP_ERROR_TEXT("out must be array('f') of at least %d floats"),
                          (int)count);
    const float *from = k->c.out + (size_t)p * (size_t)k->c.points;
    float *to = info.buf;
    for (size_t i = 0; i < count; i++)
        to[i] = from[i];
    return mp_obj_new_int((mp_int_t)count);
}
static MP_DEFINE_CONST_FUN_OBJ_3(circuit_trace_obj, circuit_trace);

static mp_obj_t circuit_error(mp_obj_t self)
{
    circuit_obj_t *k = circuit(self);
    mp_obj_t items[2] = {mp_obj_new_int(k->c.error_node), mp_obj_new_int(k->c.error_element)};
    return mp_obj_new_tuple(2, items);
}
static MP_DEFINE_CONST_FUN_OBJ_1(circuit_error_obj, circuit_error);

static mp_obj_t circuit_info(mp_obj_t self)
{
    circuit_obj_t *k = circuit(self);
    size_t bytes = 0;
    for (int i = 0; i < BLOCKS; i++)
        bytes += k->bytes[i];
    const int prepared = k->c.prepared, factored = prepared && k->c.analysis != PS_AN_NONE;
    mp_obj_t d = mp_obj_new_dict(7);
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_equations), mp_obj_new_int(prepared ? k->c.n : 0));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_entries), mp_obj_new_int(prepared ? k->c.nnz : 0));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_factors), mp_obj_new_int(factored ? k->c.lu.lnz + k->c.lu.unz : 0));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_bytes), mp_obj_new_int_from_uint(bytes));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_iterations), mp_obj_new_int(k->c.iterations));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_steps), mp_obj_new_int(k->c.steps));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_rejected), mp_obj_new_int(k->c.rejected));
    return d;
}
static MP_DEFINE_CONST_FUN_OBJ_1(circuit_info_obj, circuit_info);

static mp_obj_t circuit_free(mp_obj_t self)
{
    circuit_obj_t *k = MP_OBJ_TO_PTR(self);
    for (int i = BLOCKS - 1; i >= 0; i--)
        replace(k, i, 0);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(circuit_free_obj, circuit_free);

static const mp_rom_map_elem_t circuit_locals_table[] = {
    {MP_ROM_QSTR(MP_QSTR_element), MP_ROM_PTR(&circuit_element_obj)},
    {MP_ROM_QSTR(MP_QSTR_wave), MP_ROM_PTR(&circuit_wave_obj)},
    {MP_ROM_QSTR(MP_QSTR_probe), MP_ROM_PTR(&circuit_probe_obj)},
    {MP_ROM_QSTR(MP_QSTR_op), MP_ROM_PTR(&circuit_op_obj)},
    {MP_ROM_QSTR(MP_QSTR_dc), MP_ROM_PTR(&circuit_dc_obj)},
    {MP_ROM_QSTR(MP_QSTR_tran), MP_ROM_PTR(&circuit_tran_obj)},
    {MP_ROM_QSTR(MP_QSTR_run), MP_ROM_PTR(&circuit_run_obj)},
    {MP_ROM_QSTR(MP_QSTR_progress), MP_ROM_PTR(&circuit_progress_obj)},
    {MP_ROM_QSTR(MP_QSTR_voltage), MP_ROM_PTR(&circuit_voltage_obj)},
    {MP_ROM_QSTR(MP_QSTR_current), MP_ROM_PTR(&circuit_current_obj)},
    {MP_ROM_QSTR(MP_QSTR_trace), MP_ROM_PTR(&circuit_trace_obj)},
    {MP_ROM_QSTR(MP_QSTR_error), MP_ROM_PTR(&circuit_error_obj)},
    {MP_ROM_QSTR(MP_QSTR_info), MP_ROM_PTR(&circuit_info_obj)},
    {MP_ROM_QSTR(MP_QSTR_free), MP_ROM_PTR(&circuit_free_obj)},
    {MP_ROM_QSTR(MP_QSTR_R), MP_ROM_INT(PS_EL_R)},
    {MP_ROM_QSTR(MP_QSTR_C), MP_ROM_INT(PS_EL_C)},
    {MP_ROM_QSTR(MP_QSTR_L), MP_ROM_INT(PS_EL_L)},
    {MP_ROM_QSTR(MP_QSTR_V), MP_ROM_INT(PS_EL_V)},
    {MP_ROM_QSTR(MP_QSTR_I), MP_ROM_INT(PS_EL_I)},
    {MP_ROM_QSTR(MP_QSTR_D), MP_ROM_INT(PS_EL_D)},
    {MP_ROM_QSTR(MP_QSTR_NPN), MP_ROM_INT(PS_EL_NPN)},
    {MP_ROM_QSTR(MP_QSTR_PNP), MP_ROM_INT(PS_EL_PNP)},
    {MP_ROM_QSTR(MP_QSTR_NMOS), MP_ROM_INT(PS_EL_NMOS)},
    {MP_ROM_QSTR(MP_QSTR_PMOS), MP_ROM_INT(PS_EL_PMOS)},
    {MP_ROM_QSTR(MP_QSTR_E), MP_ROM_INT(PS_EL_E)},
    {MP_ROM_QSTR(MP_QSTR_G), MP_ROM_INT(PS_EL_G)},
    {MP_ROM_QSTR(MP_QSTR_F), MP_ROM_INT(PS_EL_F)},
    {MP_ROM_QSTR(MP_QSTR_H), MP_ROM_INT(PS_EL_H)},
    {MP_ROM_QSTR(MP_QSTR_OPAMP), MP_ROM_INT(PS_EL_OPAMP)},
    {MP_ROM_QSTR(MP_QSTR_SW), MP_ROM_INT(PS_EL_SW)},
    {MP_ROM_QSTR(MP_QSTR_DC), MP_ROM_INT(PS_WAVE_DC)},
    {MP_ROM_QSTR(MP_QSTR_PULSE), MP_ROM_INT(PS_WAVE_PULSE)},
    {MP_ROM_QSTR(MP_QSTR_SIN), MP_ROM_INT(PS_WAVE_SIN)},
    {MP_ROM_QSTR(MP_QSTR_PWL), MP_ROM_INT(PS_WAVE_PWL)},
    {MP_ROM_QSTR(MP_QSTR_VOLTAGE), MP_ROM_INT(PS_PROBE_V)},
    {MP_ROM_QSTR(MP_QSTR_CURRENT), MP_ROM_INT(PS_PROBE_I)},
};
static MP_DEFINE_CONST_DICT(circuit_locals, circuit_locals_table);

MP_DEFINE_CONST_OBJ_TYPE(
    picosolve_circuit_type,
    MP_QSTR_Circuit,
    MP_TYPE_FLAG_NONE,
    make_new, circuit_make_new,
    locals_dict, &circuit_locals);
