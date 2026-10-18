#include "mesh.h"
#include <math.h>

/* Graph3D's area test, in its order of operations. */
static bool has_area(const float *a, const float *b, const float *c)
{
    const float x = (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]);
    const float y = (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]);
    const float z = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
    return !(x * x + y * y + z * z < PS_MESH_DEGENERATE);
}

static void put(float *out, const float *a, const float *b, const float *c)
{
    for (int k = 0; k < 3; k++)
    {
        out[k] = a[k];
        out[3 + k] = b[k];
        out[6 + k] = c[k];
    }
}

int ps_grid_strip(const float *row0, const float *row1, const float *xs, int n,
                  float y0, float y1, float *out, int capacity)
{
    int count = 0;
    for (int i = 0; i + 1 < n; i++)
    {
        const float a[3] = {xs[i], y0, row0[i]}, b[3] = {xs[i + 1], y0, row0[i + 1]};
        const float c[3] = {xs[i], y1, row1[i]}, d[3] = {xs[i + 1], y1, row1[i + 1]};
        const float *tri[2][3] = {{a, b, c}, {b, d, c}};
        for (int t = 0; t < 2; t++)
        {
            if (!isfinite(tri[t][0][2]) || !isfinite(tri[t][1][2]) || !isfinite(tri[t][2][2]))
                continue;
            if (!has_area(tri[t][0], tri[t][1], tri[t][2]) || count >= capacity)
                continue;
            put(out + 9 * count, tri[t][0], tri[t][1], tri[t][2]);
            count++;
        }
    }
    return count;
}

/* Corners of a cube split into six tetrahedra around the 0-6 diagonal. */
static const uint8_t TETRA[6][4] = {{0, 1, 2, 6}, {0, 2, 3, 6}, {0, 3, 7, 6},
                                    {0, 7, 4, 6}, {0, 4, 5, 6}, {0, 5, 1, 6}};

static void cross_point(const float *p, const float *v, int i, int j, float *out)
{
    const float t = v[i] / (v[i] - v[j]);
    for (int k = 0; k < 3; k++)
        out[k] = p[3 * i + k] + t * (p[3 * j + k] - p[3 * i + k]);
}

typedef struct
{
    float *triangles, *centres, *limits;
    int count;
} sink;

static void emit(sink *s, const float *a, const float *b, const float *c, float limit)
{
    if (!has_area(a, b, c))
        return;
    put(s->triangles + 9 * s->count, a, b, c);
    for (int k = 0; k < 3; k++)
        s->centres[3 * s->count + k] = (a[k] + b[k] + c[k]) / 3.0f;
    s->limits[s->count] = limit;
    s->count++;
}

/* One tetrahedron (Graph3D's _tetra_triangles): p 4 points, v 4 values. */
static void tetra(sink *s, const float *p, const float *v)
{
    int inside[4], outside[4], ni = 0, no = 0;
    for (int i = 0; i < 4; i++)
    {
        if (v[i] < 0.0f)
            inside[ni++] = i;
        else
            outside[no++] = i;
    }
    if (!ni || !no)
        return;
    float limit = 0.0f;
    for (int i = 0; i < 4; i++)
        limit = fabsf(v[i]) > limit ? fabsf(v[i]) : limit;
    limit = limit * 2.0f + 1e-8f;
    float e1[3], e2[3], e3[3], e4[3];
    if (ni == 1)
    {
        cross_point(p, v, inside[0], outside[0], e1);
        cross_point(p, v, inside[0], outside[1], e2);
        cross_point(p, v, inside[0], outside[2], e3);
        emit(s, e1, e2, e3, limit);
    }
    else if (no == 1)
    {
        cross_point(p, v, outside[0], inside[0], e1);
        cross_point(p, v, outside[0], inside[2], e2);
        cross_point(p, v, outside[0], inside[1], e3);
        emit(s, e1, e2, e3, limit);
    }
    else
    {
        const int a = inside[0], b = inside[1], c = outside[0], d = outside[1];
        cross_point(p, v, a, c, e1); /* ac */
        cross_point(p, v, a, d, e2); /* ad */
        cross_point(p, v, b, c, e3); /* bc */
        cross_point(p, v, b, d, e4); /* bd */
        emit(s, e1, e2, e3, limit);
        emit(s, e2, e4, e3, limit);
    }
}

int ps_iso_slab(const float *prev, const float *cur, const float *coords, int n,
                float z0, float z1, float *triangles, float *centres, float *limits,
                int capacity, int32_t *cube)
{
    sink s = {triangles, centres, limits, 0};
    const int32_t cubes = (int32_t)(n - 1) * (n - 1);
    int32_t q = *cube;
    for (; q < cubes; q++)
    {
        if (s.count + PS_MESH_PER_CUBE > capacity)
            break;
        const int j = q / (n - 1), i = q % (n - 1);
        const int idx[4] = {j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i};
        float v[8];
        bool any_in = false, any_out = false, finite = true;
        for (int k = 0; k < 4; k++)
        {
            v[k] = prev[idx[k]];
            v[4 + k] = cur[idx[k]];
        }
        for (int k = 0; k < 8; k++)
        {
            finite = finite && isfinite(v[k]);
            if (v[k] < 0.0f)
                any_in = true;
            else
                any_out = true;
        }
        if (!finite || !any_in || !any_out)
            continue;
        const float x0 = coords[i], x1 = coords[i + 1], y0 = coords[j], y1 = coords[j + 1];
        const float corner[8][3] = {{x0, y0, z0}, {x1, y0, z0}, {x1, y1, z0}, {x0, y1, z0},
                                    {x0, y0, z1}, {x1, y0, z1}, {x1, y1, z1}, {x0, y1, z1}};
        for (int t = 0; t < 6; t++)
        {
            float p[12], f[4];
            for (int k = 0; k < 4; k++)
            {
                const int c = TETRA[t][k];
                p[3 * k] = corner[c][0];
                p[3 * k + 1] = corner[c][1];
                p[3 * k + 2] = corner[c][2];
                f[k] = v[c];
            }
            tetra(&s, p, f);
        }
    }
    *cube = q;
    return s.count;
}
