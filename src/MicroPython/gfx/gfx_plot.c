#include "gfx_plot.h"
#include <math.h>

/* Python rounds after every operation; a fused multiply-add would not, and
 * these functions must reproduce Graph's Python arithmetic exactly. */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#elif defined(__GNUC__)
#pragma GCC optimize("fp-contract=off")
#endif

/* Graph.pixel: world -> screen. */
static void to_pixel(const gfx_plot_frame *f, float x, float y, float *px, float *py)
{
    *px = (float)f->left + (x - f->x_min) / (f->x_max - f->x_min) * (float)f->width;
    *py = (float)f->top + (f->y_max - y) / (f->y_max - f->y_min) * (float)f->height;
}

/* Graph.xy: screen -> world. */
static void to_world(const gfx_plot_frame *f, float px, float py, float *x, float *y)
{
    *x = f->x_min + (px - (float)f->left) / (float)f->width * (f->x_max - f->x_min);
    *y = f->y_max - (py - (float)f->top) / (float)f->height * (f->y_max - f->y_min);
}

/* Expression.include: Python's min/max keep the first unless strictly beyond. */
static void include(gfx_plot_state *st, float x, float y)
{
    if (!st->has_box)
    {
        st->has_box = true;
        st->box[0] = st->box[1] = x;
        st->box[2] = st->box[3] = y;
        return;
    }
    if (x < st->box[0])
        st->box[0] = x;
    if (x > st->box[1])
        st->box[1] = x;
    if (y < st->box[2])
        st->box[2] = y;
    if (y > st->box[3])
        st->box[3] = y;
}

static bool inside(const gfx_plot_frame *f, float px, float py)
{
    return (float)f->left <= px && px <= (float)f->right && (float)f->top <= py && py <= (float)f->bottom;
}

void gfx_plot_line(gfx_surface *s, const gfx_plot_frame *f, float x, float y, float bx, float by,
                   uint16_t color, bool dashed)
{
    const float dx = bx - x, dy = by - y;
    float lo = 0.0f, hi = 1.0f;
    const float p[4] = {-dx, dx, -dy, dy};
    const float q[4] = {x - (float)f->left, (float)f->right - x, y - (float)f->top, (float)f->bottom - y};
    for (int k = 0; k < 4; k++)
    {
        if (p[k] == 0.0f)
        {
            if (q[k] < 0.0f)
                return;
        }
        else
        {
            const float ratio = q[k] / p[k];
            if (p[k] < 0.0f)
                lo = ratio > lo ? ratio : lo;
            else
                hi = ratio < hi ? ratio : hi;
        }
    }
    if (lo > hi)
        return;
    const float x0 = x + lo * dx, y0 = y + lo * dy, x1 = x + hi * dx, y1 = y + hi * dy;
    if (!dashed)
    {
        gfx_line(s, (int)x0, (int)y0, (int)x1, (int)y1, color);
        return;
    }
    const float ax = fabsf(x1 - x0), ay = fabsf(y1 - y0);
    int n = (int)ceilf(ay > ax ? ay : ax);
    if (n < 1)
        n = 1;
    for (int i = 0; i <= n; i++)
    {
        const int px = (int)(x0 + (x1 - x0) * (float)i / (float)n);
        const int py = (int)(y0 + (y1 - y0) * (float)i / (float)n);
        if ((px + py) % 8 < 4)
            gfx_pixel(s, px, py, color);
    }
}

void GFX_HOT(gfx_plot_curve)(gfx_surface *s, const gfx_plot_frame *f, const float *x, const float *y,
                             int count, int first, uint16_t color, uint16_t shade, int relation,
                             bool vertical, int parity, gfx_plot_state *st)
{
    const float max_jump = (float)(f->width > f->height ? f->width : f->height) * 0.65f;
    const bool upper = relation == GFX_PLOT_GREATER || relation == GFX_PLOT_GREATER_EQUAL;
    const bool strict = relation == GFX_PLOT_LESS || relation == GFX_PLOT_GREATER;
    for (int k = 0; k < count; k++)
    {
        const int i = first + k;
        const float wx = x[k], wy = y[k];
        if (isnan(wx) || isnan(wy) || fabsf(wx) > 1e12f || fabsf(wy) > 1e12f)
        {
            st->has_previous = false;
            continue;
        }
        float px, py;
        to_pixel(f, wx, wy, &px, &py);
        if (relation != GFX_PLOT_EQUAL && i % 2 == parity % 2)
        {
            if (vertical)
            {
                const float row = (float)(f->top + i);
                if (upper)
                    gfx_plot_line(s, f, px, row, (float)f->right, row, shade, false);
                else
                    gfx_plot_line(s, f, (float)f->left, row, px, row, shade, false);
            }
            else
            {
                const float column = (float)(f->left + i);
                if (upper)
                    gfx_plot_line(s, f, column, (float)f->top, column, py, shade, false);
                else
                    gfx_plot_line(s, f, column, py, column, (float)f->bottom, shade, false);
            }
        }
        const bool in = inside(f, px, py);
        if (st->has_previous)
        {
            const float jx = fabsf(px - st->previous_x), jy = fabsf(py - st->previous_y);
            if ((jy > jx ? jy : jx) <= max_jump && (!strict || i % 8 < 4))
                gfx_plot_line(s, f, st->previous_x, st->previous_y, px, py, color, false);
        }
        else if (in)
            gfx_pixel(s, (int)px, (int)py, color);
        if (in)
            include(st, wx, wy);
        st->has_previous = true;
        st->previous_x = px;
        st->previous_y = py;
    }
}

void gfx_plot_segments(gfx_surface *s, const gfx_plot_frame *f, const float *segments, int count,
                       uint16_t color, bool dashed, gfx_plot_state *st)
{
    for (int i = 0; i < count; i++)
    {
        const float *g = segments + 4 * i;
        gfx_plot_line(s, f, g[0], g[1], g[2], g[3], color, dashed);
        float wx, wy;
        to_world(f, g[0], g[1], &wx, &wy);
        include(st, wx, wy);
        to_world(f, g[2], g[3], &wx, &wy);
        include(st, wx, wy);
    }
}
