#include "contour.h"
#include <math.h>
#include <stdbool.h>

/* A cell's corners in Graph's order: top-left, top-right, bottom-right, bottom-left. */
typedef struct
{
    float x[4], y[4], v[4];
    float centre;
} cell;

static bool load(const float *upper, const float *lower, const float *centres, const float *xs,
                 int i, float y0, float y1, cell *c)
{
    c->x[0] = xs[i], c->y[0] = y0, c->v[0] = upper[i];
    c->x[1] = xs[i + 1], c->y[1] = y0, c->v[1] = upper[i + 1];
    c->x[2] = xs[i + 1], c->y[2] = y1, c->v[2] = lower[i + 1];
    c->x[3] = xs[i], c->y[3] = y1, c->v[3] = lower[i];
    c->centre = centres[i];
    if (!isfinite(c->centre))
        return false;
    for (int k = 0; k < 4; k++)
        if (!isfinite(c->v[k]))
            return false;
    return true;
}

/* Does edge k (corner k to k + 1) change sign, as Graph decides it? */
static bool changes_sign(const cell *c, int k)
{
    const float va = c->v[k], vb = c->v[(k + 1) & 3];
    if (va == vb)
        return false;
    return (va <= 0.0f && 0.0f <= vb) || (vb <= 0.0f && 0.0f <= va);
}

int ps_contour_queries(const float *upper, const float *lower, const float *centres,
                       const float *xs, int n, float y0, float y1, float *queries, int capacity)
{
    int count = 0;
    cell c;
    for (int i = 0; i + 1 < n; i++)
    {
        if (!load(upper, lower, centres, xs, i, y0, y1, &c))
            continue;
        for (int k = 0; k < 4; k++)
        {
            if (!changes_sign(&c, k) || count >= capacity)
                continue;
            const int j = (k + 1) & 3;
            queries[2 * count] = (c.x[k] + c.x[j]) / 2.0f;
            queries[2 * count + 1] = (c.y[k] + c.y[j]) / 2.0f;
            count++;
        }
    }
    return count;
}

int ps_contour_segments(const float *upper, const float *lower, const float *centres,
                        const float *xs, int n, float y0, float y1, const float *mids,
                        float *segments, int capacity)
{
    int count = 0, query = 0;
    cell c;
    for (int i = 0; i + 1 < n; i++)
    {
        if (!load(upper, lower, centres, xs, i, y0, y1, &c))
            continue;
        float px[4], py[4];
        int found = 0;
        for (int k = 0; k < 4; k++)
        {
            if (!changes_sign(&c, k))
                continue;
            const int j = (k + 1) & 3;
            const float va = c.v[k], vb = c.v[j];
            if (mids)
            {
                /* Reject sign changes across poles / undefined midpoints. */
                const float mid = mids[query++];
                const float limit = (fabsf(va) > fabsf(vb) ? fabsf(va) : fabsf(vb)) * 2.0f + 1e-10f;
                if (!isfinite(mid) || fabsf(mid) > limit)
                    continue;
            }
            const float ratio = fabsf(va) / (fabsf(va) + fabsf(vb));
            px[found] = c.x[k] + ratio * (c.x[j] - c.x[k]);
            py[found] = c.y[k] + ratio * (c.y[j] - c.y[k]);
            found++;
        }
        int pairs[2][2], np = 0;
        if (found == 2)
        {
            pairs[0][0] = 0, pairs[0][1] = 1, np = 1;
        }
        else if (found == 4)
        {
            /* Resolve the saddle from the centre's sign. */
            np = 2;
            if ((c.centre >= 0.0f) == (c.v[0] >= 0.0f))
                pairs[0][0] = 0, pairs[0][1] = 1, pairs[1][0] = 2, pairs[1][1] = 3;
            else
                pairs[0][0] = 0, pairs[0][1] = 3, pairs[1][0] = 1, pairs[1][1] = 2;
        }
        for (int p = 0; p < np && count < capacity; p++)
        {
            float *s = segments + 4 * count++;
            s[0] = px[pairs[p][0]], s[1] = py[pairs[p][0]];
            s[2] = px[pairs[p][1]], s[3] = py[pairs[p][1]];
        }
    }
    return count;
}
