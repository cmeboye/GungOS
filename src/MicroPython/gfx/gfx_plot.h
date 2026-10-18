/*
 * gfx_plot - Graph's per-point drawing, moved from Python.
 *
 * Curves y = f(x), x = f(y) and parametric pairs, with inequality shading,
 * and contour segments of implicit curves. The arithmetic is Graph's own
 * (engtools/plots/plot2d.py: pixel, xy, line), step for step in float32,
 * so the pixels match what Python drew exactly.
 */
#ifndef GFX_PLOT_H
#define GFX_PLOT_H

#include "gfx.h"

/* The plot window: world bounds and its pixel rectangle. */
typedef struct
{
    float x_min, x_max, y_min, y_max;
    int left, top, right, bottom, width, height; /* width, height: Graph's pw, ph */
} gfx_plot_frame;

/* Carried from one batch of points to the next. */
typedef struct
{
    bool has_previous;
    float previous_x, previous_y; /* pixel position of the last point */
    bool has_box;
    float box[4]; /* world extent of the points drawn: x min, x max, y min, y max */
} gfx_plot_state;

enum
{
    GFX_PLOT_EQUAL,
    GFX_PLOT_LESS,
    GFX_PLOT_LESS_EQUAL,
    GFX_PLOT_GREATER,
    GFX_PLOT_GREATER_EQUAL
};

/* Graph.line: clip a segment to the window (Liang-Barsky) and draw it,
 * solid or dotted. */
void gfx_plot_line(gfx_surface *s, const gfx_plot_frame *f, float ax, float ay, float bx, float by,
                   uint16_t color, bool dashed);

/*
 * Graph.explicit_batch for points first .. first + count - 1: x[i], y[i] in
 * world units, NaN where undefined. vertical: x = f(y) curves (shading runs
 * across). parity: the expression's position, which interleaves shading of
 * overlapping inequalities.
 */
void gfx_plot_curve(gfx_surface *s, const gfx_plot_frame *f, const float *x, const float *y, int count,
                    int first, uint16_t color, uint16_t shade, int relation, bool vertical, int parity,
                    gfx_plot_state *state);

/* Contour segments (x0, y0, x1, y1 in pixels, 4 floats each): draw each and
 * extend the world extent by both ends, as Graph.implicit_row does. */
void gfx_plot_segments(gfx_surface *s, const gfx_plot_frame *f, const float *segments, int count,
                       uint16_t color, bool dashed, gfx_plot_state *state);

#endif
