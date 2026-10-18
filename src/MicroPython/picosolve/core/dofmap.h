/*
 * Equation numbering for any element type: which degrees of freedom (DOFs)
 * are unknowns, in what order, and how much skyline storage they need.
 *
 * The model marks each DOF before numbering: free (0), fixed (PS_DOF_FIXED)
 * or dropped (PS_DOF_DROPPED, e.g. a rotation with no stiffness at a hinge).
 * Numbering then reorders the nodes (reverse Cuthill-McKee, kept only if it
 * beats the user's order) and replaces each free DOF's mark with its
 * equation number.
 */
#ifndef PICOSOLVE_DOFMAP_H
#define PICOSOLVE_DOFMAP_H

#include "ps_base.h"

#define PS_DOF_FIXED (-1)
#define PS_DOF_DROPPED (-2)
#define PS_MAX_ELEMENT_NODES 4

/* Write element e's node indices to nodes; return how many (<= PS_MAX_ELEMENT_NODES). */
typedef int (*ps_element_nodes)(const void *model, int32_t element, int32_t *nodes);

typedef struct
{
    int32_t nodes, dpn;
    int32_t *dof;   /* nodes * dpn: equation number, or a negative mark */
    uint32_t *ptr;  /* skyline column offsets, nodes * dpn + 1 */
    /* Scratch for numbering only: valid until ps_dofmap_number returns and
     * the caller releases it. */
    int32_t *xadj, *adj, *perm, *level;
    uint8_t *mask;
    int32_t edge_capacity;
    int32_t equations;
    uint32_t profile;
} ps_dofmap;

/* The numbering itself (kept), and scratch used only while numbering.
 * edges: room for node adjacencies, sum over elements of k * (k - 1). */
size_t ps_dofmap_bytes(int32_t nodes, int32_t dpn);
size_t ps_dofmap_scratch_bytes(int32_t nodes, int32_t edges);
void ps_dofmap_init(ps_dofmap *map, void *block, void *scratch, int32_t nodes, int32_t dpn, int32_t edges);

/* Number the free DOFs and size the skyline. Marks in map->dof must be set. */
ps_status ps_dofmap_number(ps_dofmap *map, int32_t elements, ps_element_nodes nodes_of,
                           const void *model);

/* Equation numbers of an element's DOFs, node by node; -1 where not free. */
void ps_dofmap_equations(const ps_dofmap *map, const int32_t *nodes, int count, int32_t *eq);

#endif
