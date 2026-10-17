/*
 * A beam model and its solve: nodes on the x axis, Euler-Bernoulli elements,
 * supports, springs, hinges, load cases and support settlement.
 *
 * Memory comes in three caller-owned blocks, each sized before it is needed:
 *   model  - ps_model_bytes() before ps_model_init()
 *   index  - ps_model_index_bytes() before ps_model_prepare()
 *   values - ps_model_value_bytes() after prepare, before ps_model_solve()
 * Nothing is allocated during the solve, so it can run on the second core.
 * Editing the model afterwards requires prepare and solve again.
 *
 * Units: SI throughout (m, N, N*m, Pa, m^4, N/m for springs and line loads).
 */
#ifndef PICOSOLVE_MODEL_H
#define PICOSOLVE_MODEL_H

#include "../core/ps_base.h"
#include "../core/skyline.h"

/* DOF flags for supports, springs and node loads. */
#define PS_UY 1u
#define PS_RZ 2u
/* Element end releases (hinges) for rotation. */
#define PS_RELEASE_START 1u
#define PS_RELEASE_END 2u

#define PS_BEAM_DOF_PER_NODE 2

typedef enum
{
    PS_LOAD_NODE,   /* force or moment w1 on a node DOF */
    PS_LOAD_SETTLE, /* prescribed displacement w1 of a restrained node DOF */
    PS_LOAD_POINT,  /* element force w1 at a */
    PS_LOAD_MOMENT, /* element counterclockwise moment w1 at a */
    PS_LOAD_LINE,   /* element line load from w1 at a to w2 at b */
} ps_load_kind;

typedef struct
{
    double a, b, w1, w2;
    int32_t target; /* node or element */
    uint8_t kind, load_case, dof;
} ps_load;

typedef enum
{
    PS_STATE_EDITED,
    PS_STATE_PREPARED,
    PS_STATE_SOLVED,
} ps_state;

typedef struct
{
    int32_t nodes, elements, sections, load_capacity, cases;
    int32_t load_count;
    /* model block */
    double *x, *spring, *modulus, *inertia;
    ps_load *load;
    int32_t *connect, *section_of;
    uint8_t *fixed, *release;
    /* index block */
    int32_t *dof; /* equation number, or PS_DOF_FIXED / PS_DOF_FREE_HINGE */
    uint32_t *ptr;
    int32_t *xadj, *adj, *perm, *level;
    uint8_t *mask;
    int32_t equations;
    uint32_t profile;
    /* values block */
    ps_sky sky;
    double *u; /* cases x equations */
    ps_factor_info info;
    ps_state state;
    int32_t error_item, error_dof;
} ps_model;

#define PS_DOF_FIXED (-1)
/* Rotation of a node where every attached element end is a hinge. */
#define PS_DOF_FREE_HINGE (-2)

size_t ps_model_bytes(int32_t nodes, int32_t elements, int32_t sections, int32_t loads);
ps_status ps_model_init(ps_model *m, void *block, int32_t nodes, int32_t elements,
                        int32_t sections, int32_t loads, int32_t cases);

ps_status ps_model_node(ps_model *m, int32_t node, double x);
ps_status ps_model_support(ps_model *m, int32_t node, uint32_t flags);
ps_status ps_model_spring(ps_model *m, int32_t node, uint32_t flag, double stiffness);
ps_status ps_model_section(ps_model *m, int32_t section, double modulus, double inertia);
ps_status ps_model_element(ps_model *m, int32_t element, int32_t start, int32_t end,
                           int32_t section, uint32_t releases);
ps_status ps_model_load(ps_model *m, ps_load_kind kind, int32_t load_case, int32_t target,
                        uint32_t flag, double a, double b, double w1, double w2);
void ps_model_clear_loads(ps_model *m);

size_t ps_model_index_bytes(const ps_model *m);
ps_status ps_model_prepare(ps_model *m, void *block);
size_t ps_model_value_bytes(const ps_model *m);
ps_status ps_model_solve(ps_model *m, void *block, ps_control *ctl);

/* Results: NaN for the rotation of a node where every element end is a hinge. */
double ps_model_displacement(const ps_model *m, int32_t load_case, int32_t node, uint32_t flag);
/* Forces the nodes apply to the element: fy1, m1, fy2, m2. */
ps_status ps_model_end_forces(const ps_model *m, int32_t load_case, int32_t element, double *forces);
/* Support reaction (or spring force) on a node: fy, mz. */
ps_status ps_model_reaction(const ps_model *m, int32_t load_case, int32_t node, double *reaction);
/* At x from the element start: shear, moment, slope, deflection. */
ps_status ps_model_section_at(const ps_model *m, int32_t load_case, int32_t element,
                              double x, double *out);

#endif
