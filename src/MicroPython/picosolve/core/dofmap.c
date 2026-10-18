#include "dofmap.h"
#include "order.h"
#include "skyline.h"

static size_t align8(size_t n)
{
    return (n + 7u) & ~(size_t)7u;
}

static void *take(uint8_t **cursor, size_t bytes)
{
    void *p = *cursor;
    *cursor += align8(bytes);
    return p;
}

size_t ps_dofmap_bytes(int32_t nodes, int32_t dpn, int32_t edges)
{
    size_t n = (size_t)nodes, d = (size_t)dpn;
    return align8(n * d * sizeof(int32_t)) + align8((n * d + 1) * sizeof(uint32_t)) +
           align8((n + 1) * sizeof(int32_t)) + align8((size_t)edges * sizeof(int32_t)) +
           2 * align8(n * sizeof(int32_t)) + align8(n);
}

void ps_dofmap_init(ps_dofmap *map, void *block, int32_t nodes, int32_t dpn, int32_t edges)
{
    uint8_t *cursor = block;
    map->nodes = nodes;
    map->dpn = dpn;
    map->edge_capacity = edges;
    map->dof = take(&cursor, (size_t)nodes * (size_t)dpn * sizeof(int32_t));
    map->ptr = take(&cursor, ((size_t)nodes * (size_t)dpn + 1) * sizeof(uint32_t));
    map->xadj = take(&cursor, ((size_t)nodes + 1) * sizeof(int32_t));
    map->adj = take(&cursor, (size_t)edges * sizeof(int32_t));
    map->perm = take(&cursor, (size_t)nodes * sizeof(int32_t));
    map->level = take(&cursor, (size_t)nodes * sizeof(int32_t));
    map->mask = take(&cursor, (size_t)nodes);
    for (int32_t i = 0; i < nodes * dpn; i++)
        map->dof[i] = 0;
    map->equations = 0;
    map->profile = 0;
}

void ps_dofmap_equations(const ps_dofmap *map, const int32_t *nodes, int count, int32_t *eq)
{
    for (int k = 0; k < count; k++)
        for (int d = 0; d < map->dpn; d++)
        {
            int32_t v = map->dof[nodes[k] * map->dpn + d];
            eq[k * map->dpn + d] = v >= 0 ? v : -1;
        }
}

/* Number free DOFs node by node in the given order; return the profile. */
static uint32_t number(ps_dofmap *map, const int32_t *order, int32_t elements,
                       ps_element_nodes nodes_of, const void *model)
{
    int32_t next = 0;
    for (int32_t k = 0; k < map->nodes; k++)
    {
        int32_t node = order ? order[k] : k;
        for (int d = 0; d < map->dpn; d++)
            if (map->dof[node * map->dpn + d] >= 0)
                map->dof[node * map->dpn + d] = next++;
    }
    map->equations = next;
    ps_sky_heights_init(map->ptr, next);
    int32_t nodes[PS_MAX_ELEMENT_NODES];
    int32_t eq[PS_MAX_ELEMENT_NODES * 8];
    for (int32_t e = 0; e < elements; e++)
    {
        int count = nodes_of(model, e, nodes);
        ps_dofmap_equations(map, nodes, count, eq);
        ps_sky_heights_add(map->ptr, eq, count * map->dpn);
    }
    return ps_sky_heights_finish(map->ptr, next);
}

ps_status ps_dofmap_number(ps_dofmap *map, int32_t elements, ps_element_nodes nodes_of,
                           const void *model)
{
    const int32_t nn = map->nodes;
    int32_t nodes[PS_MAX_ELEMENT_NODES];
    /* Node graph in compressed form: count, prefix-sum, fill. */
    for (int32_t i = 0; i <= nn; i++)
        map->xadj[i] = 0;
    int32_t edges = 0;
    for (int32_t e = 0; e < elements; e++)
    {
        int count = nodes_of(model, e, nodes);
        for (int a = 0; a < count; a++)
            map->xadj[nodes[a] + 1] += count - 1;
        edges += count * (count - 1);
    }
    if (edges > map->edge_capacity)
        return PS_ERR_ARGUMENT;
    for (int32_t i = 0; i < nn; i++)
        map->xadj[i + 1] += map->xadj[i];
    for (int32_t i = 0; i < nn; i++)
        map->level[i] = map->xadj[i];
    for (int32_t e = 0; e < elements; e++)
    {
        int count = nodes_of(model, e, nodes);
        for (int a = 0; a < count; a++)
            for (int b = 0; b < count; b++)
                if (a != b)
                    map->adj[map->level[nodes[a]]++] = nodes[b];
    }
    ps_rcm(nn, map->xadj, map->adj, map->perm, map->level, map->mask);
    const uint32_t natural = number(map, NULL, elements, nodes_of, model);
    const uint32_t reordered = number(map, map->perm, elements, nodes_of, model);
    map->profile = reordered < natural ? reordered : number(map, NULL, elements, nodes_of, model);
    return PS_OK;
}
