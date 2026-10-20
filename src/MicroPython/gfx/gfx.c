#include "gfx.h"
#include <string.h>

uint16_t gfx_palette[256];

/* ------------------------------------------------------------------------ */
/* Colours                                                                  */
/* ------------------------------------------------------------------------ */

void gfx_init_palette(void)
{
    for (int i = 0; i < 256; i++)
    {
        uint8_t r8 = (uint8_t)((((i >> 5) & 0x07) * 255) / 7);
        uint8_t g8 = (uint8_t)((((i >> 2) & 0x07) * 255) / 7);
        uint8_t b8 = (uint8_t)(((i & 0x03) * 255) / 3);
        gfx_palette[i] = (uint16_t)(((r8 & 0xF8) << 8) | ((g8 & 0xFC) << 3) | (b8 >> 3));
    }
}

uint8_t gfx_to332(uint16_t color)
{
    return (uint8_t)(((color & 0xE000) >> 8) | ((color & 0x0700) >> 6) | ((color & 0x0018) >> 3));
}

/* Blend an RGB565 source over an RGB332 pixel, as the v1 driver did. */
static uint8_t blend(uint8_t dst, uint16_t color, uint8_t alpha)
{
    const uint16_t d = gfx_palette[dst];
    const unsigned inv = 255u - alpha;
    const unsigned r = (((color >> 11) & 0x1Fu) * alpha + ((d >> 11) & 0x1Fu) * inv) / 255u;
    const unsigned g = (((color >> 5) & 0x3Fu) * alpha + ((d >> 5) & 0x3Fu) * inv) / 255u;
    const unsigned b = ((color & 0x1Fu) * alpha + (d & 0x1Fu) * inv) / 255u;
    return gfx_to332((uint16_t)((r << 11) | (g << 5) | b));
}

/* ------------------------------------------------------------------------ */
/* Storage in ordinary memory                                               */
/* ------------------------------------------------------------------------ */

static inline uint8_t *sram_at(void *ctx, int y, int x)
{
    gfx_sram *m = ctx;
    return m->pixels + (size_t)y * (size_t)m->stride + (size_t)x;
}

static void GFX_HOT(sram_fill)(void *ctx, int y, int x, int len, uint8_t color)
{
    memset(sram_at(ctx, y, x), color, (size_t)len);
}

static void sram_write(void *ctx, int y, int x, int len, const uint8_t *src)
{
    memcpy(sram_at(ctx, y, x), src, (size_t)len);
}

static void sram_read(void *ctx, int y, int x, int len, uint8_t *dst)
{
    memcpy(dst, sram_at(ctx, y, x), (size_t)len);
}

static uint8_t *GFX_HOT(sram_edit)(void *ctx, int y, int x, int len)
{
    (void)len;
    return sram_at(ctx, y, x);
}

static void sram_commit(void *ctx, int y, int x, int len)
{
    (void)ctx;
    (void)y;
    (void)x;
    (void)len;
}

const gfx_storage gfx_sram_storage = {sram_fill, sram_write, sram_read, sram_edit, sram_commit};

/* ------------------------------------------------------------------------ */
/* Surface and spans                                                        */
/* ------------------------------------------------------------------------ */

void gfx_surface_init(gfx_surface *s, int width, int height,
                      const gfx_storage *storage, void *ctx)
{
    s->width = width > GFX_MAX_WIDTH ? GFX_MAX_WIDTH : width;
    s->height = height > GFX_MAX_HEIGHT ? GFX_MAX_HEIGHT : height;
    s->storage = storage;
    s->ctx = ctx;
    for (int y = 0; y < GFX_MAX_HEIGHT; y++)
        s->dirty[y] = 0;
}

static inline void touch(gfx_surface *s, int y)
{
    s->dirty[y] = 1;
}

void gfx_mark_all_dirty(gfx_surface *s)
{
    for (int y = 0; y < s->height; y++)
        touch(s, y);
}

/* Clip [x0, x1] on row y to the surface; false when nothing is left. */
static inline bool clip_span(const gfx_surface *s, int y, int *x0, int *x1)
{
    if (y < 0 || y >= s->height)
        return false;
    if (*x0 < 0)
        *x0 = 0;
    if (*x1 >= s->width)
        *x1 = s->width - 1;
    return *x1 >= *x0;
}

/* Fill the inclusive span [x0, x1] of row y. */
static void GFX_HOT(span)(gfx_surface *s, int y, int x0, int x1, uint8_t c)
{
    if (!clip_span(s, y, &x0, &x1))
        return;
    touch(s, y);
    s->storage->fill(s->ctx, y, x0, x1 - x0 + 1, c);
}

/* Blend the inclusive span [x0, x1] of row y. */
static void blend_span(gfx_surface *s, int y, int x0, int x1, uint16_t color, uint8_t alpha)
{
    if (!clip_span(s, y, &x0, &x1))
        return;
    touch(s, y);
    const int len = x1 - x0 + 1;
    uint8_t *p = s->storage->edit(s->ctx, y, x0, len);
    for (int i = 0; i < len; i++)
        p[i] = blend(p[i], color, alpha);
    s->storage->commit(s->ctx, y, x0, len);
}

/* ------------------------------------------------------------------------ */
/* Basic shapes                                                             */
/* ------------------------------------------------------------------------ */

void gfx_clear(gfx_surface *s, uint16_t color)
{
    const uint8_t c = gfx_to332(color);
    for (int y = 0; y < s->height; y++)
        span(s, y, 0, s->width - 1, c);
}

void gfx_pixel(gfx_surface *s, int x, int y, uint16_t color)
{
    span(s, y, x, x, gfx_to332(color));
}

/*
 * Bresenham, as in v1, but consecutive pixels on one row are written as a
 * single span: a shallow line costs one write per row instead of per pixel.
 */
static void GFX_HOT(line332)(gfx_surface *s, int x1, int y1, int x2, int y2, uint8_t c)
{
    if (y1 == y2)
    {
        span(s, y1, x1 < x2 ? x1 : x2, x1 < x2 ? x2 : x1, c);
        return;
    }
    const int dx = x2 > x1 ? x2 - x1 : x1 - x2;
    const int dy = y2 > y1 ? y2 - y1 : y1 - y2;
    const int sx = x1 < x2 ? 1 : -1;
    const int sy = y1 < y2 ? 1 : -1;
    int err = dx - dy;
    int run_y = y1, run_a = x1, run_b = x1;
    for (;;)
    {
        if (y1 != run_y)
        {
            span(s, run_y, run_a < run_b ? run_a : run_b, run_a < run_b ? run_b : run_a, c);
            run_y = y1;
            run_a = run_b = x1;
        }
        else
            run_b = x1;
        if (x1 == x2 && y1 == y2)
            break;
        const int e2 = 2 * err;
        if (e2 > -dy)
        {
            err -= dy;
            x1 += sx;
        }
        if (e2 < dx)
        {
            err += dx;
            y1 += sy;
        }
    }
    span(s, run_y, run_a < run_b ? run_a : run_b, run_a < run_b ? run_b : run_a, c);
}

void gfx_line(gfx_surface *s, int x1, int y1, int x2, int y2, uint16_t color)
{
    line332(s, x1, y1, x2, y2, gfx_to332(color));
}

void gfx_rect(gfx_surface *s, int x, int y, int width, int height, uint16_t color)
{
    if (width <= 0 || height <= 0)
        return;
    const uint8_t c = gfx_to332(color);
    line332(s, x, y, x + width - 1, y, c);
    line332(s, x, y + height - 1, x + width - 1, y + height - 1, c);
    line332(s, x, y, x, y + height - 1, c);
    line332(s, x + width - 1, y, x + width - 1, y + height - 1, c);
}

void gfx_fill_rect(gfx_surface *s, int x, int y, int width, int height, uint16_t color)
{
    if (width <= 0 || height <= 0)
        return;
    const uint8_t c = gfx_to332(color);
    int y0 = y < 0 ? 0 : y;
    int y1 = y + height > s->height ? s->height : y + height;
    for (int row = y0; row < y1; row++)
        span(s, row, x, x + width - 1, c);
}

void GFX_HOT(gfx_stipple)(gfx_surface *s, int x0, int y0, int x1, int y1, int period, int phase,
                          uint16_t color)
{
    if (period < 1)
        return;
    const uint8_t c = gfx_to332(color);
    if (x0 < 0)
        x0 = 0;
    if (x1 > s->width)
        x1 = s->width;
    if (y0 < 0)
        y0 = 0;
    if (y1 > s->height)
        y1 = s->height;
    for (int y = y0; y < y1; y++)
    {
        int offset = (phase - y - x0) % period;
        if (offset < 0)
            offset += period;
        const int first = x0 + offset;
        if (first >= x1)
            continue;
        const int len = x1 - first;
        touch(s, y);
        uint8_t *p = s->storage->edit(s->ctx, y, first, len);
        for (int i = 0; i < len; i += period)
            p[i] = c;
        s->storage->commit(s->ctx, y, first, len);
    }
}

void gfx_circle(gfx_surface *s, int cx, int cy, int radius, uint16_t color)
{
    if (radius <= 0)
        return;
    const uint8_t c = gfx_to332(color);
    int xv = 0, yv = radius, d = 3 - 2 * radius;
    while (xv <= yv)
    {
        const int pts[8][2] = {
            {cx + xv, cy + yv}, {cx - xv, cy + yv}, {cx + xv, cy - yv}, {cx - xv, cy - yv},
            {cx + yv, cy + xv}, {cx - yv, cy + xv}, {cx + yv, cy - xv}, {cx - yv, cy - xv}};
        for (int i = 0; i < 8; i++)
            span(s, pts[i][1], pts[i][0], pts[i][0], c);
        if (d < 0)
            d += 4 * xv + 6;
        else
        {
            d += 4 * (xv - yv) + 10;
            yv--;
        }
        xv++;
    }
}

void gfx_fill_circle(gfx_surface *s, int cx, int cy, int radius, uint16_t color)
{
    if (radius <= 0)
        return;
    const uint8_t c = gfx_to332(color);
    int xv = 0, yv = radius, d = 3 - 2 * radius;
    while (xv <= yv)
    {
        span(s, cy + yv, cx - xv, cx + xv, c);
        span(s, cy - yv, cx - xv, cx + xv, c);
        span(s, cy + xv, cx - yv, cx + yv, c);
        span(s, cy - xv, cx - yv, cx + yv, c);
        if (d < 0)
            d += 4 * xv + 6;
        else
        {
            d += 4 * (xv - yv) + 10;
            yv--;
        }
        xv++;
    }
}

static int isqrt(int v)
{
    if (v <= 0)
        return 0;
    int r = 0;
    while ((r + 1) * (r + 1) <= v)
        r++;
    return r;
}

/*
 * One span per row. A corner pixel is kept when it lies within radius of
 * the corner's centre, the same test v1 applied pixel by pixel. Unlike v1,
 * the corners belong to the whole rectangle, so a rectangle that crosses
 * the screen edge keeps its shape instead of growing new corners there.
 */
void gfx_fill_round_rect(gfx_surface *s, int x, int y, int width, int height,
                         int radius, uint16_t color)
{
    if (width <= 0 || height <= 0 || radius <= 0)
        return;
    int r = radius;
    if (r > width / 2)
        r = width / 2;
    if (r > height / 2)
        r = height / 2;
    const uint8_t c = gfx_to332(color);
    const int left_c = x + r, right_c = x + width - r;
    const int top_c = y + r, bottom_c = y + height - r;
    const int y0 = y < 0 ? 0 : y;
    const int y1 = y + height > s->height ? s->height : y + height;
    for (int py = y0; py < y1; py++)
    {
        int a = x, b = x + width - 1;
        int dy = py < top_c ? py - top_c : py >= bottom_c ? py - bottom_c : 0;
        if (py < top_c || py >= bottom_c)
        {
            const int k = isqrt(r * r - dy * dy);
            if (left_c - k > a)
                a = left_c - k;
            if (right_c + k < b)
                b = right_c + k;
        }
        span(s, py, a, b, c);
    }
}

void gfx_triangle(gfx_surface *s, int x1, int y1, int x2, int y2, int x3, int y3,
                  uint16_t color)
{
    const uint8_t c = gfx_to332(color);
    line332(s, x1, y1, x2, y2, c);
    line332(s, x2, y2, x3, y3, c);
    line332(s, x3, y3, x1, y1, c);
}

static void swapf(float *a, float *b)
{
    float t = *a;
    *a = *b;
    *b = t;
}

void gfx_fill_triangle(gfx_surface *s, int x1, int y1, int x2, int y2, int x3, int y3,
                       uint16_t color)
{
    float p1x = (float)x1, p1y = (float)y1;
    float p2x = (float)x2, p2y = (float)y2;
    float p3x = (float)x3, p3y = (float)y3;
    const uint8_t c = gfx_to332(color);
    if (p1y > p2y)
    {
        swapf(&p1x, &p2x);
        swapf(&p1y, &p2y);
    }
    if (p2y > p3y)
    {
        swapf(&p2x, &p3x);
        swapf(&p2y, &p3y);
    }
    if (p1y > p2y)
    {
        swapf(&p1x, &p2x);
        swapf(&p1y, &p2y);
    }
    const int iy1 = (int)p1y, iy2 = (int)p2y, iy3 = (int)p3y;
    if (iy1 == iy3)
        return;
    const int first = iy1 < 0 ? 0 : iy1;
    const int last = iy3 >= s->height ? s->height - 1 : iy3;
    for (int sy = first; sy <= last; sy++)
    {
        float x_long = p1x + (p3x - p1x) * (float)(sy - iy1) / (float)(iy3 - iy1);
        float x_short;
        if (sy <= iy2)
            x_short = iy2 != iy1 ? p1x + (p2x - p1x) * (float)(sy - iy1) / (float)(iy2 - iy1) : p1x;
        else
            x_short = iy3 != iy2 ? p2x + (p3x - p2x) * (float)(sy - iy2) / (float)(iy3 - iy2) : p2x;
        const int a = (int)(x_long < x_short ? x_long : x_short);
        const int b = (int)(x_long > x_short ? x_long : x_short);
        span(s, sy, a, b, c);
    }
}

void gfx_fill_triangle_alpha(gfx_surface *s, int x1, int y1, int x2, int y2,
                             int x3, int y3, uint16_t color, uint8_t alpha)
{
    if (alpha == 0)
        return;
    if (alpha == 255)
    {
        gfx_fill_triangle(s, x1, y1, x2, y2, x3, y3, color);
        return;
    }
    int t;
    if (y1 > y2)
    {
        t = x1, x1 = x2, x2 = t;
        t = y1, y1 = y2, y2 = t;
    }
    if (y1 > y3)
    {
        t = x1, x1 = x3, x3 = t;
        t = y1, y1 = y3, y3 = t;
    }
    if (y2 > y3)
    {
        t = x2, x2 = x3, x3 = t;
        t = y2, y2 = y3, y3 = t;
    }
    const int total = y3 - y1;
    if (total == 0)
        return;
    /* As in v1, the bottom row (y3) is not drawn. */
    for (int i = 0; i < total; i++)
    {
        const int cur_y = y1 + i;
        if (cur_y < 0)
            continue;
        if (cur_y >= s->height)
            break;
        const bool second = i > y2 - y1 || y2 == y1;
        const int seg = second ? y3 - y2 : y2 - y1;
        const float tt = (float)i / (float)total;
        const float beta = (float)(i - (second ? y2 - y1 : 0)) / (float)seg;
        int ax = (int)((float)x1 + (float)(x3 - x1) * tt);
        int bx = second ? (int)((float)x2 + (float)(x3 - x2) * beta)
                        : (int)((float)x1 + (float)(x2 - x1) * beta);
        if (ax > bx)
        {
            t = ax, ax = bx, bx = t;
        }
        blend_span(s, cur_y, ax, bx, color, alpha);
    }
}

void gfx_polygon(gfx_surface *s, const int16_t *x, const int16_t *y, int count,
                 uint16_t color)
{
    if (count < 2)
        return;
    const uint8_t c = gfx_to332(color);
    int px = x[count - 1], py = y[count - 1];
    for (int i = 0; i < count; i++)
    {
        line332(s, px, py, x[i], y[i], c);
        px = x[i];
        py = y[i];
    }
}

/*
 * Scanline polygon fill in 18.14 fixed point, ported from v1. Calls plot()
 * for each inclusive span. scratch holds 6 * count ints.
 */
typedef struct
{
    gfx_surface *s;
    uint8_t color332;
    uint16_t color565;
    uint8_t alpha;
} poly_paint;

static void poly_span(const poly_paint *p, int y, int a, int b)
{
    if (p->alpha == 255)
        span(p->s, y, a, b, p->color332);
    else
        blend_span(p->s, y, a, b, p->color565, p->alpha);
}

static void poly_fill(const poly_paint *p, const int16_t *x, const int16_t *y, int count,
                      int32_t *scratch)
{
    int32_t *xtop = scratch, *dxf = scratch + count, *ys = scratch + 2 * count;
    int32_t *xa = scratch + 3 * count, *dxa = scratch + 4 * count, *xs = scratch + 5 * count;
    const int height = p->s->height, width = p->s->width;
    for (int i = 0; i < count; i++)
    {
        const int j = i + 1 == count ? 0 : i + 1;
        const int y0 = y[i], y1 = y[j], x0 = x[i], x1 = x[j];
        const int top_x = y0 <= y1 ? x0 : x1;
        const int bot_x = y0 <= y1 ? x1 : x0;
        const int rows = y0 <= y1 ? y1 - y0 : y0 - y1;
        xtop[i] = (int32_t)((uint32_t)top_x << 14);
        dxf[i] = rows ? (int32_t)(((int64_t)(bot_x - top_x) * 16384) / rows) : 0;
        ys[i] = y[i];
    }
    for (int a = 1; a < count; a++)
    {
        const int32_t v = ys[a];
        int b = a - 1;
        while (b >= 0 && ys[b] > v)
        {
            ys[b + 1] = ys[b];
            b--;
        }
        ys[b + 1] = v;
    }
    for (int band = 0; band + 1 < count; band++)
    {
        const int ya = ys[band], yb = ys[band + 1];
        if (ya == yb)
            continue;
        const int row0 = ya < 0 ? 0 : ya;
        const int row1 = yb > height ? height : yb;
        if (row0 >= row1)
            continue;
        int n = 0;
        for (int i = 0; i < count; i++)
        {
            const int j = i + 1 == count ? 0 : i + 1;
            const int y0 = y[i], y1 = y[j];
            const int top = y0 < y1 ? y0 : y1;
            const int bot = y0 < y1 ? y1 : y0;
            if (top <= ya && bot > ya)
            {
                xa[n] = xtop[i] + (row0 - top) * dxf[i];
                dxa[n] = dxf[i];
                n++;
            }
        }
        if (n < 2)
            continue;
        for (int a = 1; a < n; a++)
        {
            const int32_t v = xa[a], sl = dxa[a];
            int k = a - 1;
            while (k >= 0 && (xa[k] > v || (xa[k] == v && dxa[k] > sl)))
            {
                xa[k + 1] = xa[k];
                dxa[k + 1] = dxa[k];
                k--;
            }
            xa[k + 1] = v;
            dxa[k + 1] = sl;
        }
        if (n == 2 && p->alpha == 255)
        {
            /* v1's opaque fill skips rows where the two edges have crossed. */
            int32_t xl = xa[0], xr = xa[1];
            for (int py = row0; py < row1; py++)
            {
                const int a = xl >> 14, b = xr >> 14;
                xl += dxa[0];
                xr += dxa[1];
                if (b < 0 || a >= width || b < a)
                    continue;
                poly_span(p, py, a, b);
            }
            continue;
        }
        for (int py = row0; py < row1; py++)
        {
            for (int k = 0; k < n; k++)
            {
                xs[k] = xa[k] >> 14;
                xa[k] += dxa[k];
            }
            for (int a = 1; a < n; a++)
            {
                const int32_t v = xs[a];
                int k = a - 1;
                while (k >= 0 && xs[k] > v)
                {
                    xs[k + 1] = xs[k];
                    k--;
                }
                xs[k + 1] = v;
            }
            for (int k = 0; k + 1 < n; k += 2)
            {
                const int a = xs[k], b = xs[k + 1];
                if (b < 0 || a >= width || b < a)
                    continue;
                poly_span(p, py, a, b);
            }
        }
    }
}

void gfx_fill_polygon(gfx_surface *s, const int16_t *x, const int16_t *y, int count,
                      uint16_t color, int32_t *scratch)
{
    if (count < 3)
        return;
    const poly_paint p = {s, gfx_to332(color), color, 255};
    poly_fill(&p, x, y, count, scratch);
}

void gfx_fill_polygon_alpha(gfx_surface *s, const int16_t *x, const int16_t *y,
                            int count, uint16_t color, uint8_t alpha, int32_t *scratch)
{
    if (count < 3 || alpha == 0)
        return;
    const poly_paint p = {s, gfx_to332(color), color, alpha};
    poly_fill(&p, x, y, count, scratch);
}

/* ------------------------------------------------------------------------ */
/* Text                                                                     */
/* ------------------------------------------------------------------------ */

static inline const uint8_t *glyph(const gfx_font *font, int code)
{
    const int bytes_per_row = (font->width + 7) / 8;
    return font->data + (size_t)(code - 32) * font->height * bytes_per_row;
}

/* Set the lit pixels of one glyph row into a row segment starting at base_x. */
static void glyph_row(const gfx_font *font, int code, int row, uint8_t *seg,
                      int seg_x, int glyph_x, int width, uint8_t c)
{
    const int bytes_per_row = (font->width + 7) / 8;
    const uint8_t *bits = glyph(font, code) + row * bytes_per_row;
    for (int col = 0; col < font->width; col++)
    {
        if (!(bits[col >> 3] & (0x80 >> (col & 7))))
            continue;
        const int px = glyph_x + col;
        if (px >= 0 && px < width)
            seg[px - seg_x] = c;
    }
}

void gfx_char(gfx_surface *s, int x, int y, char ch, uint16_t color, const gfx_font *font)
{
    const int code = (int)(unsigned char)ch;
    if (code < 32 || code > 126)
        return;
    if (x + font->width > s->width || y + font->height > s->height)
        return;
    const uint8_t c = gfx_to332(color);
    int a = x < 0 ? 0 : x;
    const int b = x + font->width - 1;
    if (b < a)
        return;
    for (int row = 0; row < font->height; row++)
    {
        const int py = y + row;
        if (py < 0)
            continue;
        touch(s, py);
        uint8_t *seg = s->storage->edit(s->ctx, py, a, b - a + 1);
        glyph_row(font, code, row, seg, a, x, s->width, c);
        s->storage->commit(s->ctx, py, a, b - a + 1);
    }
}

/*
 * Layout follows v1 exactly: '\n' starts a new line, a space only advances,
 * a glyph that would cross the right edge wraps to the next line, and
 * drawing stops at the bottom edge. Glyphs that share a line are drawn
 * together, one row segment at a time, so external storage sees two
 * transfers per pixel row instead of one per lit pixel.
 */
void gfx_text(gfx_surface *s, int x, int y, const char *text, uint16_t color,
              const gfx_font *font)
{
    if (!text)
        return;
    const int w = font->width, h = font->height, spacing = w + 1;
    const uint8_t c = gfx_to332(color);
    int cx = x, cy = y;
    const char *p = text;
    while (*p)
    {
        /* Collect the glyphs drawn on the current line: [first, end). */
        const char *first = NULL, *end = p;
        int line_y = 0, seg_a = 0, seg_b = -1, start_x = 0;
        bool stop = false;
        while (*end)
        {
            const char ch = *end;
            if (ch == '\n')
            {
                if (first)
                    break;
                cx = x;
                cy += h;
                end++;
                continue;
            }
            if (ch == ' ')
            {
                cx += spacing;
                end++;
                continue;
            }
            if (cy + h > s->height)
            {
                stop = true;
                break;
            }
            if (cx + w > s->width)
            {
                if (first)
                    break; /* the wrap starts the next line */
                cx = x;
                cy += h;
                if (cy + h > s->height)
                {
                    stop = true;
                    break;
                }
            }
            if (!first)
            {
                first = end;
                line_y = cy;
                start_x = cx;
                seg_a = cx;
            }
            seg_b = cx + w - 1;
            cx += spacing;
            end++;
        }
        if (first)
        {
            int a = seg_a < 0 ? 0 : seg_a;
            int b = seg_b >= s->width ? s->width - 1 : seg_b;
            for (int row = 0; row < h && a <= b; row++)
            {
                const int py = line_y + row;
                if (py < 0 || py >= s->height)
                    continue;
                touch(s, py);
                uint8_t *seg = s->storage->edit(s->ctx, py, a, b - a + 1);
                int gx = start_x;
                for (const char *q = first; q < end; q++)
                {
                    if (*q == ' ')
                    {
                        gx += spacing;
                        continue;
                    }
                    int code = (int)(unsigned char)*q;
                    if (code < 32 || code > 126)
                        code = 32;
                    glyph_row(font, code, row, seg, a, gx, s->width, c);
                    gx += spacing;
                }
                s->storage->commit(s->ctx, py, a, b - a + 1);
            }
        }
        if (stop)
            return;
        p = end;
    }
}

/* ------------------------------------------------------------------------ */
/* Pixel copies                                                             */
/* ------------------------------------------------------------------------ */

void gfx_blit8(gfx_surface *s, int x, int y, int width, int height, const uint8_t *src)
{
    if (!src || width <= 0 || height <= 0)
        return;
    const int sx = x < 0 ? -x : 0, sy = y < 0 ? -y : 0;
    const int dx = x < 0 ? 0 : x, dy = y < 0 ? 0 : y;
    int w = width - sx, hgt = height - sy;
    if (dx + w > s->width)
        w = s->width - dx;
    if (dy + hgt > s->height)
        hgt = s->height - dy;
    if (w <= 0 || hgt <= 0)
        return;
    for (int row = 0; row < hgt; row++)
    {
        touch(s, dy + row);
        s->storage->write(s->ctx, dy + row, dx, w, src + (size_t)(sy + row) * (size_t)width + (size_t)sx);
    }
}

void gfx_blit16(gfx_surface *s, int x, int y, int width, int height, const uint16_t *src)
{
    if (!src || width <= 0 || height <= 0)
        return;
    const int sx = x < 0 ? -x : 0, sy = y < 0 ? -y : 0;
    const int dx = x < 0 ? 0 : x, dy = y < 0 ? 0 : y;
    int w = width - sx, hgt = height - sy;
    if (dx + w > s->width)
        w = s->width - dx;
    if (dy + hgt > s->height)
        hgt = s->height - dy;
    if (w <= 0 || hgt <= 0)
        return;
    uint8_t row332[GFX_MAX_WIDTH];
    for (int row = 0; row < hgt; row++)
    {
        const uint16_t *line = src + (size_t)(sy + row) * (size_t)width + (size_t)sx;
        for (int i = 0; i < w; i++)
            row332[i] = gfx_to332(line[i]);
        touch(s, dy + row);
        s->storage->write(s->ctx, dy + row, dx, w, row332);
    }
}

void gfx_read_row(gfx_surface *s, int y, uint8_t *dst)
{
    if (y < 0 || y >= s->height)
        return;
    s->storage->read(s->ctx, y, 0, s->width, dst);
}

/* ------------------------------------------------------------------------ */
/* Presenting changed rows                                                  */
/* ------------------------------------------------------------------------ */

static uint32_t GFX_HOT(row_hash)(const uint8_t *p, int n)
{
    uint32_t h = 2166136261u;
    int i = 0;
    for (; i + 4 <= n; i += 4)
    {
        uint32_t w;
        memcpy(&w, p + i, 4);
        h = (h ^ w) * 16777619u;
        h ^= h >> 15;
    }
    for (; i < n; i++)
        h = (h ^ p[i]) * 16777619u;
    return h ^ (h >> 16);
}

int gfx_present(gfx_surface *s, uint32_t *hash, bool force, const gfx_sink *sink, void *ctx)
{
    uint8_t copy[GFX_MAX_WIDTH];
    /* Ordinary memory is hashed and sent in place; other storage is read
     * into copy once, for both. */
    const bool in_place = s->storage == &gfx_sram_storage;
    int sent = 0;
    bool in_run = false;
    for (int y = 0; y < s->height; y++)
    {
        bool changed = false;
        const uint8_t *row = copy;
        if (force || s->dirty[y])
        {
            /* Clear the mark first: drawing that lands after this read marks
             * the row again for the next present. */
            s->dirty[y] = 0;
            if (in_place)
                row = sram_at(s->ctx, y, 0);
            else
                s->storage->read(s->ctx, y, 0, s->width, copy);
            const uint32_t h = row_hash(row, s->width);
            changed = force || h != hash[y];
            hash[y] = h;
        }
        if (changed)
        {
            if (!in_run)
                sink->begin(ctx, y);
            in_run = true;
            sink->row(ctx, y, row);
            sent++;
        }
        else if (in_run)
        {
            sink->end(ctx);
            in_run = false;
        }
    }
    if (in_run)
        sink->end(ctx);
    return sent;
}
