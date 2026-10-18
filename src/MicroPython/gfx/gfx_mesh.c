#include "gfx_mesh.h"
#include <math.h>

/* A projected vertex: screen position, depth from the camera, rotated point. */
typedef struct
{
    float sx, sy, zc;
    float x1, y2, z2;
} projected;

typedef struct
{
    float cy, sy, cp, sp;
    const gfx_mesh_view *v;
} camera;

/* False when the point is behind the near limit or absurdly far off screen. */
static bool project(const camera *c, float x, float y_up, float z_depth, projected *p)
{
    const float x1 = x * c->cy - z_depth * c->sy;
    const float z1 = x * c->sy + z_depth * c->cy;
    const float y2 = y_up * c->cp - z1 * c->sp;
    const float z2 = y_up * c->sp + z1 * c->cp;
    const float zc = c->v->cam - z2;
    if (zc < 0.45f)
        return false;
    const float scale = c->v->focal / zc;
    const float sx = c->v->cx + x1 * scale;
    const float sy = c->v->cy - y2 * scale;
    if (!(fabsf(sx) < 1000000.0f) || !(fabsf(sy) < 1000000.0f))
        return false;
    p->sx = (float)(int)sx; /* Python's int(): truncate toward zero */
    p->sy = (float)(int)sy;
    p->zc = zc;
    p->x1 = x1;
    p->y2 = y2;
    p->z2 = z2;
    return true;
}

static bool world(const camera *c, const float *vertex, projected *p)
{
    return project(c, vertex[0], (vertex[2] - c->v->z_center) * c->v->z_scale, vertex[1], p);
}

static int outcode(const gfx_mesh_view *v, float x, float y)
{
    int code = 0;
    if (x < (float)v->clip_x0)
        code |= 1;
    else if (x > (float)v->clip_x1)
        code |= 2;
    if (y < (float)v->clip_y0)
        code |= 4;
    else if (y > (float)v->clip_y1)
        code |= 8;
    return code;
}

bool gfx_clip_line(float *x0, float *y0, float *x1, float *y1,
                   int xmin, int ymin, int xmax, int ymax)
{
    gfx_mesh_view v;
    v.clip_x0 = xmin;
    v.clip_y0 = ymin;
    v.clip_x1 = xmax;
    v.clip_y1 = ymax;
    int c0 = outcode(&v, *x0, *y0), c1 = outcode(&v, *x1, *y1);
    for (int guard = 0; guard < 16; guard++)
    {
        if (!(c0 | c1))
            return true;
        if (c0 & c1)
            return false;
        const int c = c0 ? c0 : c1;
        float x, y;
        if (c & 8)
        {
            x = *y1 != *y0 ? *x0 + (*x1 - *x0) * ((float)ymax - *y0) / (*y1 - *y0) : *x0;
            y = (float)ymax;
        }
        else if (c & 4)
        {
            x = *y1 != *y0 ? *x0 + (*x1 - *x0) * ((float)ymin - *y0) / (*y1 - *y0) : *x0;
            y = (float)ymin;
        }
        else if (c & 2)
        {
            y = *x1 != *x0 ? *y0 + (*y1 - *y0) * ((float)xmax - *x0) / (*x1 - *x0) : *y0;
            x = (float)xmax;
        }
        else
        {
            y = *x1 != *x0 ? *y0 + (*y1 - *y0) * ((float)xmin - *x0) / (*x1 - *x0) : *y0;
            x = (float)xmin;
        }
        if (c == c0)
        {
            *x0 = x;
            *y0 = y;
            c0 = outcode(&v, x, y);
        }
        else
        {
            *x1 = x;
            *y1 = y;
            c1 = outcode(&v, x, y);
        }
    }
    return false;
}

static void edge(gfx_surface *s, const gfx_mesh_view *v, const projected *a, const projected *b,
                 uint16_t color)
{
    float x0 = a->sx, y0 = a->sy, x1 = b->sx, y1 = b->sy;
    if (gfx_clip_line(&x0, &y0, &x1, &y1, v->clip_x0, v->clip_y0, v->clip_x1, v->clip_y1))
        gfx_line(s, (int)x0, (int)y0, (int)x1, (int)y1, color);
}

/* Sutherland-Hodgman against the four window edges, then a triangle fan. */
static void fill_clipped(gfx_surface *s, const gfx_mesh_view *v, const projected *a,
                         const projected *b, const projected *c, uint16_t color)
{
    float px[8], py[8], qx[8], qy[8];
    int n = 3;
    px[0] = a->sx, py[0] = a->sy;
    px[1] = b->sx, py[1] = b->sy;
    px[2] = c->sx, py[2] = c->sy;
    const float edges[4] = {(float)v->clip_x0, (float)v->clip_x1, (float)v->clip_y0, (float)v->clip_y1};
    for (int e = 0; e < 4 && n > 0; e++)
    {
        const int axis = e < 2 ? 0 : 1;
        const bool greater = (e & 1) == 0;
        const float limit = edges[e];
        int m = 0;
        float lx = px[n - 1], ly = py[n - 1];
        float lv = axis ? ly : lx;
        bool last_in = greater ? lv >= limit : lv <= limit;
        for (int i = 0; i < n; i++)
        {
            const float cv = axis ? py[i] : px[i];
            const bool in = greater ? cv >= limit : cv <= limit;
            if (in != last_in && m < 8)
            {
                const float ratio = (limit - lv) / (cv - lv);
                qx[m] = lx + ratio * (px[i] - lx);
                qy[m] = ly + ratio * (py[i] - ly);
                m++;
            }
            if (in && m < 8)
            {
                qx[m] = px[i];
                qy[m] = py[i];
                m++;
            }
            lx = px[i], ly = py[i], lv = cv, last_in = in;
        }
        for (int i = 0; i < m; i++)
            px[i] = qx[i], py[i] = qy[i];
        n = m;
    }
    for (int i = 1; i + 1 < n; i++)
    {
        int xy[6];
        const int idx[3] = {0, i, i + 1};
        for (int k = 0; k < 3; k++)
        {
            int x = (int)px[idx[k]], y = (int)py[idx[k]];
            xy[2 * k] = x < v->clip_x0 ? v->clip_x0 : x > v->clip_x1 ? v->clip_x1 : x;
            xy[2 * k + 1] = y < v->clip_y0 ? v->clip_y0 : y > v->clip_y1 ? v->clip_y1 : y;
        }
        gfx_fill_triangle(s, xy[0], xy[1], xy[2], xy[3], xy[4], xy[5], color);
    }
}

/* Brightness of a face under a fixed light, 0.38 (edge-on) to 1. */
static float face_shade(const projected *p0, const projected *p1, const projected *p2)
{
    const float ux = p1->x1 - p0->x1, uy = p1->y2 - p0->y2, uz = p1->z2 - p0->z2;
    const float vx = p2->x1 - p0->x1, vy = p2->y2 - p0->y2, vz = p2->z2 - p0->z2;
    const float nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    const float length = sqrtf(nx * nx + ny * ny + nz * nz);
    if (length < 1e-8f)
        return 0.55f;
    float nd = (nx * 0.35f + ny * 0.82f + nz * 0.25f) / length;
    if (nd < 0.0f)
        nd = -nd;
    return 0.38f + 0.62f * nd;
}

static uint16_t shade_color(const uint8_t *ramp, bool alt, float t, float shade)
{
    if (!(t > 0.0f))
        t = 0.0f;
    else if (t > 1.0f)
        t = 1.0f;
    const uint8_t *rgb = ramp + (alt ? 768 : 0) + 3 * (int)(t * 255.0f + 0.5f);
    int r = (int)((float)rgb[0] * shade), g = (int)((float)rgb[1] * shade), b = (int)((float)rgb[2] * shade);
    r = r < 0 ? 0 : r > 255 ? 255 : r;
    g = g < 0 ? 0 : g > 255 ? 255 : g;
    b = b < 0 ? 0 : b > 255 ? 255 : b;
    return (uint16_t)(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

/* Heapsort of order[] by depth, far (large) first. No recursion, no globals. */
static void sort_far_first(int32_t *order, const float *depth, int n)
{
#define LESS(i, j) (depth[order[i]] < depth[order[j]])
    for (int start = n / 2 - 1; start >= 0; start--)
        for (int root = start;;)
        {
            int child = 2 * root + 1;
            if (child >= n)
                break;
            if (child + 1 < n && LESS(child + 1, child))
                child++;
            if (!LESS(child, root))
                break;
            int32_t t = order[root];
            order[root] = order[child];
            order[child] = t;
            root = child;
        }
    /* Min-heap: repeatedly move the smallest to the end, leaving descending order. */
    for (int end = n - 1; end > 0; end--)
    {
        int32_t t = order[0];
        order[0] = order[end];
        order[end] = t;
        for (int root = 0;;)
        {
            int child = 2 * root + 1;
            if (child >= end)
                break;
            if (child + 1 < end && LESS(child + 1, child))
                child++;
            if (!LESS(child, root))
                break;
            t = order[root];
            order[root] = order[child];
            order[child] = t;
            root = child;
        }
    }
#undef LESS
}

int gfx_mesh(gfx_surface *s, const float *triangles, const uint8_t *flags, int count,
             const gfx_mesh_view *view, const uint8_t *ramp,
             int32_t *order, float *depth)
{
    camera c = {cosf(view->yaw), sinf(view->yaw), cosf(view->pitch), sinf(view->pitch), view};
    for (int i = 0; i < count; i++)
    {
        const float *t = triangles + 9 * i;
        const float centre[3] = {(t[0] + t[3] + t[6]) / 3.0f, (t[1] + t[4] + t[7]) / 3.0f,
                                 (t[2] + t[5] + t[8]) / 3.0f};
        projected p;
        depth[i] = world(&c, centre, &p) ? p.zc : -1.0f;
        order[i] = i;
    }
    sort_far_first(order, depth, count);
    const float span = view->z_max - view->z_min > 1e-9f ? view->z_max - view->z_min : 1e-9f;
    const int stride = view->stride > 1 ? view->stride : 1;
    int drawn = 0;
    for (int k = 0; k < count; k += stride)
    {
        const int index = order[k];
        const float *t = triangles + 9 * index;
        projected a, b, d;
        if (!world(&c, t, &a) || !world(&c, t + 3, &b) || !world(&c, t + 6, &d))
            continue;
        if (outcode(view, a.sx, a.sy) & outcode(view, b.sx, b.sy) & outcode(view, d.sx, d.sy))
            continue;
        const float height = ((t[2] + t[5] + t[8]) / 3.0f - view->z_min) / span;
        const bool alt = flags[index] != 0;
        if (view->solid)
            fill_clipped(s, view, &a, &b, &d, shade_color(ramp, alt, height, face_shade(&a, &b, &d)));
        const uint16_t wire = view->solid ? (alt ? view->wire_alt : view->wire)
                                          : shade_color(ramp, alt, height, 1.0f);
        edge(s, view, &a, &b, wire);
        edge(s, view, &b, &d, wire);
        edge(s, view, &d, &a, wire);
        drawn++;
    }
    return drawn;
}
