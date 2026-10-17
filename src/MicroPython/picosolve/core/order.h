/*
 * Reverse Cuthill-McKee node ordering, so the skyline stays narrow however
 * the user numbered the nodes.
 */
#ifndef PICOSOLVE_ORDER_H
#define PICOSOLVE_ORDER_H

#include "ps_base.h"

/*
 * Order the n nodes of the graph given in compressed form (neighbours of v
 * are adj[xadj[v] .. xadj[v+1]-1]). perm[new] = old. level and mask are
 * scratch arrays of n entries each. Disconnected parts are ordered in turn.
 */
void ps_rcm(int32_t n, const int32_t *xadj, const int32_t *adj,
            int32_t *perm, int32_t *level, uint8_t *mask);

#endif
