/*
 * Circuit simulation by modified nodal analysis: operating point, DC sweep
 * and transient, with Newton iterations for the nonlinear devices.
 *
 * Node 0 is ground. Each other node is an unknown voltage; voltage sources,
 * inductors, E and H sources and op-amps add their branch current as an
 * unknown. The matrix is factored by the general sparse LU (core/sparse).
 *
 * Elements, their terminals (in order) and values (in order):
 *   R  a b        R (ohm)              C  a b        C (F), v0 (V, uic)
 *   L  a b        L (H), i0 (A, uic)   V  + -        dc (V)
 *   I  + -        dc (A, flows + to - through it)
 *   D  anode cathode                   Is (A), N
 *   NPN/PNP  c b e                     Is (A), BF, BR, VAF (V, 0 = none)
 *   NMOS/PMOS  d g s (body on s)       VTO (V), KP (A/V^2, W/L included), LAMBDA (1/V)
 *   E  + - c+ c-   gain (V/V)          G  + - c+ c-  gm (A/V, flows + to -)
 *   F  + -         gain (A/A)          H  + -        r (V/A)
 *      F and H are controlled by the current of another element (ctrl) that
 *      has a branch: V, L, E, H or op-amp.
 *   OPAMP  in+ in- out    A (open-loop gain, 0 = ideal); out is driven
 *      against ground with no limit.
 *   SW  + - c+ c-  Ron, Roff (ohm), Vt, Vh (V): conducts as c+ - c- rises
 *      through Vt - Vh .. Vt + Vh, smoothly (Vh = 0: a hard switch).
 * PMOS takes a negative VTO, as SPICE does.
 *
 * V and I sources take a waveform, by default the dc value:
 *   PULSE  v1 v2 td tr tf pw per  (tr or tf 0: a millionth of the run)
 *   SIN    vo va freq td theta phase(deg)
 *   PWL    t0 v0 t1 v1 ...        (times not decreasing)
 * The operating point and DC sweep use the value at t = 0.
 *
 * Currents are positive into an element at the terminal asked for. A probe
 * records V(a) - V(b), or the current into element e at terminal t.
 *
 * Memory: four caller-owned blocks. model (ps_cir_bytes) holds elements,
 * values and probes. index (ps_cir_index_bytes) holds the matrix pattern
 * and order, built by ps_cir_prepare with a scratch block it releases.
 * values (ps_cir_value_bytes) holds vectors and device states; lu
 * (ps_lu_bytes for cap) the factors; out holds points x probes floats.
 * Nothing is allocated while solving.
 *
 * Units: SI throughout.
 */
#ifndef PICOSOLVE_CIRCUIT_H
#define PICOSOLVE_CIRCUIT_H

#include "../core/ps_base.h"
#include "../core/sparse.h"

typedef enum
{
    PS_EL_R,
    PS_EL_C,
    PS_EL_L,
    PS_EL_V,
    PS_EL_I,
    PS_EL_D,
    PS_EL_NPN,
    PS_EL_PNP,
    PS_EL_NMOS,
    PS_EL_PMOS,
    PS_EL_E,
    PS_EL_G,
    PS_EL_F,
    PS_EL_H,
    PS_EL_OPAMP,
    PS_EL_SW,
    PS_EL_KINDS
} ps_el_kind;

typedef enum
{
    PS_WAVE_DC,
    PS_WAVE_PULSE,
    PS_WAVE_SIN,
    PS_WAVE_PWL,
} ps_wave;

typedef enum
{
    PS_PROBE_V,
    PS_PROBE_I,
} ps_probe_kind;

typedef enum
{
    PS_AN_NONE,
    PS_AN_OP,
    PS_AN_DC,
    PS_AN_TRAN,
} ps_analysis;

#define PS_EL_TERMINALS 4

typedef struct
{
    uint8_t kind, wave, values, wave_values;
    int16_t node[PS_EL_TERMINALS];
    int16_t ctrl;   /* F, H: controlling element; else -1 */
    int16_t branch; /* own branch unknown, or -1 (prepare) */
    int16_t slot;   /* first matrix slot (prepare) */
    int16_t state;  /* first state value (prepare) */
    int32_t value;  /* first value in the pool */
    int32_t wave_value; /* first waveform value in the pool */
} ps_el;

typedef struct
{
    uint8_t kind;
    int16_t a, b; /* nodes, or element and terminal */
} ps_probe;

typedef struct
{
    /* model block */
    int32_t nodes, elements, pool_size, pool_used, probes;
    ps_el *el;
    float *pool; /* float32 values, as from Python */
    ps_probe *probe;
    /* index block */
    int32_t n, nnz, slots, states;
    int32_t *ap;
    ps_row *ai, *q, *slot;
    int8_t linear, prepared;
    /* values block: unknown vectors have n + 1 entries, the last one
     * standing for ground (always 0 in x) */
    double *ax, *rhs, *x, *xp, *w, *work, *state;
    ps_lu lu;
    /* out block */
    float *out;
    int32_t points;
    /* options */
    double reltol, vntol, abstol, gmin, gshunt;
    /* analysis */
    ps_analysis analysis;
    int32_t sweep, done; /* swept source; points recorded */
    double start, stop;  /* DC sweep */
    double tstop, hmax, h, hprev, time; /* transient */
    int8_t mode, fresh, first, have_prev;
    double srcfact, gstep, sweep_value; /* source scale, homotopy shunt */
    /* statistics */
    int32_t iterations, steps, rejected;
    /* error */
    int32_t error_node, error_element;
} ps_cir;

size_t ps_cir_bytes(int32_t nodes, int32_t elements, int32_t values, int32_t probes);
ps_status ps_cir_init(ps_cir *c, void *block, int32_t nodes, int32_t elements, int32_t values, int32_t probes);
/* Element e of kind with count terminals and count values (see above). */
ps_status ps_cir_element(ps_cir *c, int32_t e, ps_el_kind kind, const int32_t *nodes, int count,
                         const double *values, int nvalues, int32_t ctrl);
ps_status ps_cir_wave(ps_cir *c, int32_t e, ps_wave wave, const double *values, int count);
ps_status ps_cir_probe(ps_cir *c, int32_t k, ps_probe_kind kind, int32_t a, int32_t b);

/* Check the circuit and build its matrix pattern and order. */
size_t ps_cir_index_bytes(const ps_cir *c);
size_t ps_cir_scratch_bytes(const ps_cir *c);
ps_status ps_cir_prepare(ps_cir *c, void *index, void *scratch);
size_t ps_cir_value_bytes(const ps_cir *c);
/* A first guess at the LU capacity; grow it on PS_ERR_SPACE. */
int32_t ps_cir_lu_capacity(const ps_cir *c);
void ps_cir_attach(ps_cir *c, void *values, void *lu, int32_t cap);
/* Swap in a larger LU block, keeping the analysis where it was. */
void ps_cir_attach_lu(ps_cir *c, void *lu, int32_t cap);

/* Analyses: begin, then run until it returns PS_OK (or an error). Each run
 * call does at most steps time steps or sweep points and returns PS_PENDING
 * while work remains. out holds points * probes floats (none for op). */
ps_status ps_cir_op(ps_cir *c);
ps_status ps_cir_dc(ps_cir *c, int32_t source, double start, double stop, int32_t points, float *out);
ps_status ps_cir_tran(ps_cir *c, double stop, int32_t points, double hmax, int uic, float *out);
ps_status ps_cir_run(ps_cir *c, int32_t steps, ps_control *ctl);

/* Results of the last solution: node voltage, current into element e at
 * terminal t, and a probe's value. */
double ps_cir_voltage(const ps_cir *c, int32_t node);
double ps_cir_current(const ps_cir *c, int32_t e, int t);
double ps_cir_probe_value(const ps_cir *c, int32_t k);
int ps_cir_terminals(ps_el_kind kind);

#endif
