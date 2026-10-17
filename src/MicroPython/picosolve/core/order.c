#include "order.h"

static inline int32_t degree(const int32_t *xadj, int32_t v)
{
    return xadj[v + 1] - xadj[v];
}

/*
 * Breadth-first search from root over nodes whose level is -1, using queue
 * as storage. Returns the depth reached and the lowest-degree node in the
 * last level; levels are reset before returning.
 */
static int32_t search(const int32_t *xadj, const int32_t *adj, int32_t root,
                      int32_t *queue, int32_t *level, int32_t *far)
{
    int32_t head = 0, tail = 1;
    queue[0] = root;
    level[root] = 0;
    while (head < tail)
    {
        int32_t v = queue[head++];
        for (int32_t e = xadj[v]; e < xadj[v + 1]; e++)
        {
            int32_t u = adj[e];
            if (level[u] < 0)
            {
                level[u] = level[v] + 1;
                queue[tail++] = u;
            }
        }
    }
    int32_t depth = level[queue[tail - 1]];
    int32_t best = queue[tail - 1];
    for (int32_t k = tail - 1; k >= 0 && level[queue[k]] == depth; k--)
        if (degree(xadj, queue[k]) < degree(xadj, best))
            best = queue[k];
    for (int32_t k = 0; k < tail; k++)
        level[queue[k]] = -1;
    *far = best;
    return depth;
}

/* George-Liu: walk to a node of (nearly) maximal eccentricity. */
static int32_t peripheral(const int32_t *xadj, const int32_t *adj, int32_t root,
                          int32_t *queue, int32_t *level)
{
    int32_t far;
    int32_t depth = search(xadj, adj, root, queue, level, &far);
    for (int round = 0; round < 8; round++)
    {
        int32_t next;
        int32_t next_depth = search(xadj, adj, far, queue, level, &next);
        if (next_depth <= depth)
            break;
        root = far;
        depth = next_depth;
        far = next;
    }
    return root;
}

void ps_rcm(int32_t n, const int32_t *xadj, const int32_t *adj,
            int32_t *perm, int32_t *level, uint8_t *mask)
{
    for (int32_t v = 0; v < n; v++)
    {
        level[v] = -1;
        mask[v] = 0;
    }
    int32_t filled = 0;
    while (filled < n)
    {
        int32_t start = -1;
        for (int32_t v = 0; v < n; v++)
            if (!mask[v] && (start < 0 || degree(xadj, v) < degree(xadj, start)))
                start = v;
        start = peripheral(xadj, adj, start, perm + filled, level);
        int32_t head = filled, tail = filled + 1;
        perm[filled] = start;
        mask[start] = 1;
        while (head < tail)
        {
            int32_t v = perm[head++];
            int32_t first = tail;
            for (int32_t e = xadj[v]; e < xadj[v + 1]; e++)
            {
                int32_t u = adj[e];
                if (!mask[u])
                {
                    mask[u] = 1;
                    perm[tail++] = u;
                }
            }
            /* Neighbours enter in order of increasing degree. */
            for (int32_t a = first + 1; a < tail; a++)
            {
                int32_t u = perm[a], b = a;
                while (b > first && degree(xadj, perm[b - 1]) > degree(xadj, u))
                {
                    perm[b] = perm[b - 1];
                    b--;
                }
                perm[b] = u;
            }
        }
        filled = tail;
    }
    for (int32_t a = 0, b = n - 1; a < b; a++, b--)
    {
        int32_t t = perm[a];
        perm[a] = perm[b];
        perm[b] = t;
    }
}
