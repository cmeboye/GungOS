/*
 * gfx - the shared drawing core for the PicoCalc display.
 *
 * Pure C with no hardware or MicroPython headers: the firmware and the
 * desktop simulator compile this same code, so the simulator shows the
 * device's exact pixels and the drawing code is tested on the host.
 *
 * Pixels are 8-bit RGB332 (256 colours); drawing calls take RGB565 colours
 * and convert them. The image lives behind a small storage interface, so it
 * can sit in on-chip SRAM (fast, direct memory) or in external PSRAM.
 *
 * Coordinates are signed: shapes that cross the edge are clipped instead of
 * wrapping around.
 */
#ifndef GFX_H
#define GFX_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Hot loops run from SRAM on the device instead of through the flash cache. */
#if defined(PICO_ON_DEVICE) && PICO_ON_DEVICE
#include "pico.h"
#define GFX_HOT(name) __not_in_flash_func(name)
#else
#define GFX_HOT(name) name
#endif

#define GFX_MAX_WIDTH 320
#define GFX_MAX_HEIGHT 320

/*
 * Where the image lives. Every call names one row segment [x, x + len).
 * edit returns a writable copy of the segment holding the current pixels
 * (SRAM: the pixels themselves; PSRAM: a scratch copy), and commit stores it.
 */
typedef struct
{
    void (*fill)(void *ctx, int y, int x, int len, uint8_t color);
    void (*write)(void *ctx, int y, int x, int len, const uint8_t *src);
    void (*read)(void *ctx, int y, int x, int len, uint8_t *dst);
    uint8_t *(*edit)(void *ctx, int y, int x, int len);
    void (*commit)(void *ctx, int y, int x, int len);
} gfx_storage;

typedef struct
{
    int width, height;
    const gfx_storage *storage;
    void *ctx;
    /* Rows drawn on since the last present. One byte per row, so both
     * cores may draw at once (the JPEG decoder does) without losing marks. */
    volatile uint8_t dirty[GFX_MAX_HEIGHT];
} gfx_surface;

/* An image in ordinary memory, rows stride bytes apart. */
typedef struct
{
    uint8_t *pixels;
    int stride;
} gfx_sram;

extern const gfx_storage gfx_sram_storage;

/* Bitmap font: glyphs for ASCII 32..126, rows padded to whole bytes. */
typedef struct
{
    const uint8_t *data;
    uint8_t width, height;
} gfx_font;

/* RGB332 index -> RGB565, the colours the display actually shows. */
extern uint16_t gfx_palette[256];

void gfx_init_palette(void);
uint8_t gfx_to332(uint16_t color);
void gfx_surface_init(gfx_surface *s, int width, int height,
                      const gfx_storage *storage, void *ctx);

void gfx_clear(gfx_surface *s, uint16_t color);
void gfx_pixel(gfx_surface *s, int x, int y, uint16_t color);
void gfx_line(gfx_surface *s, int x1, int y1, int x2, int y2, uint16_t color);
void gfx_rect(gfx_surface *s, int x, int y, int width, int height, uint16_t color);
void gfx_fill_rect(gfx_surface *s, int x, int y, int width, int height, uint16_t color);
/* Shade [x0, x1) x [y0, y1) with a diagonal dot pattern: every pixel where
 * (x + y) mod period == phase. Graph uses it for inequality regions. */
void gfx_stipple(gfx_surface *s, int x0, int y0, int x1, int y1, int period, int phase,
                 uint16_t color);
void gfx_circle(gfx_surface *s, int cx, int cy, int radius, uint16_t color);
void gfx_fill_circle(gfx_surface *s, int cx, int cy, int radius, uint16_t color);
void gfx_fill_round_rect(gfx_surface *s, int x, int y, int width, int height,
                         int radius, uint16_t color);
void gfx_triangle(gfx_surface *s, int x1, int y1, int x2, int y2, int x3, int y3,
                  uint16_t color);
void gfx_fill_triangle(gfx_surface *s, int x1, int y1, int x2, int y2, int x3, int y3,
                       uint16_t color);
void gfx_fill_triangle_alpha(gfx_surface *s, int x1, int y1, int x2, int y2,
                             int x3, int y3, uint16_t color, uint8_t alpha);

/* Polygons: scratch must hold 6 * count ints. */
void gfx_polygon(gfx_surface *s, const int16_t *x, const int16_t *y, int count,
                 uint16_t color);
void gfx_fill_polygon(gfx_surface *s, const int16_t *x, const int16_t *y, int count,
                      uint16_t color, int32_t *scratch);
void gfx_fill_polygon_alpha(gfx_surface *s, const int16_t *x, const int16_t *y,
                            int count, uint16_t color, uint8_t alpha, int32_t *scratch);

void gfx_char(gfx_surface *s, int x, int y, char c, uint16_t color, const gfx_font *font);
void gfx_text(gfx_surface *s, int x, int y, const char *text, uint16_t color,
              const gfx_font *font);

/* Copy RGB332 or RGB565 pixels (width x height, rows packed) onto the image. */
void gfx_blit8(gfx_surface *s, int x, int y, int width, int height, const uint8_t *src);
void gfx_blit16(gfx_surface *s, int x, int y, int width, int height, const uint16_t *src);
void gfx_read_row(gfx_surface *s, int y, uint8_t *dst);
void gfx_mark_all_dirty(gfx_surface *s);

/*
 * Send what changed since the last present. Rows drawn on are hashed and
 * compared with the hash of what the display already shows (hash holds one
 * entry per row and persists between calls); only rows that differ are
 * sent, as runs of consecutive rows. force sends everything, e.g. after the
 * display was reset. Returns the number of rows sent.
 */
typedef void (*gfx_send_rows)(void *ctx, int y, int rows);
int gfx_present(gfx_surface *s, uint32_t *hash, bool force, gfx_send_rows send, void *ctx);

#endif
