/*
 * Host tests for the gfx drawing core.
 *
 * 1. Pixel equivalence with the v1 device driver (tests/reference), drawing
 *    thousands of random shapes, text and copies with both.
 * 2. The same drawing through a fake external memory (like the device PSRAM,
 *    with scratch copies and transfer counting) gives identical pixels.
 * 3. The deliberate fixes: signed coordinates, rounded rectangles that
 *    cross the screen edge.
 * 4. Presenting: only rows whose content changed are sent.
 *
 * Run tests/run-tests.sh from the gfx folder.
 */
#include "../gfx.h"
#include "font.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* v1 driver API (tests/reference/PicoCalc/picoware_lcd/picoware_lcd_v1.c). */
void lcd_set_mode(uint8_t mode);
void picocalc_lcd_init(void);
void lcd_draw_pixel(uint16_t x, uint16_t y, uint16_t color);
void lcd_fill(uint16_t color);
void picocalc_lcd_blit(uint16_t x, uint16_t y, uint16_t width, uint16_t height, const uint8_t *buffer);
void lcd_blit_16bit(uint16_t x, uint16_t y, uint16_t width, uint16_t height, const uint16_t *buffer);
void lcd_draw_line(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2, uint16_t color);
void lcd_draw_rect(uint16_t x, uint16_t y, uint16_t width, uint16_t height, uint16_t color);
void lcd_fill_rect(uint16_t x, uint16_t y, uint16_t width, uint16_t height, uint16_t color);
void lcd_draw_circle(uint16_t cx, uint16_t cy, uint16_t radius, uint16_t color);
void lcd_fill_circle(uint16_t cx, uint16_t cy, uint16_t radius, uint16_t color);
void lcd_fill_triangle(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2, uint16_t x3, uint16_t y3, uint16_t color);
void lcd_fill_triangle_alpha(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2, uint16_t x3, uint16_t y3, uint16_t color, uint8_t alpha);
void lcd_fill_round_rectangle(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t r, uint16_t color);
void lcd_draw_triangle(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2, uint16_t x3, uint16_t y3, uint16_t color);
void lcd_polygon(uint16_t x[], uint16_t y[], int count, uint16_t color);
void lcd_fill_polygon(uint16_t x[], uint16_t y[], int count, uint16_t color);
void lcd_fill_polygon_alpha(uint16_t x[], uint16_t y[], int count, uint16_t color, uint8_t alpha);
void lcd_draw_char(uint16_t x, uint16_t y, char c, uint16_t color, FontSize size);
void lcd_draw_text(uint16_t x, uint16_t y, const char *text, uint16_t color, FontSize size);
bool lcd_read_row(uint16_t row, uint8_t *dst);

/* Font lookups the v1 file expects from the font module. */

static const FontTable *table(FontSize size)
{
    static const FontTable *const t[] = {&Font8, &Font12, &Font16, &Font20, &Font24};
    return t[size];
}
uint8_t font_get_width(FontSize size) { return table(size)->width; }
uint8_t font_get_height(FontSize size) { return table(size)->height; }
const uint8_t *font_get_data(FontSize size) { return table(size)->table; }
const uint8_t *font_get_character(FontSize size, char c)
{
    const FontTable *f = table(size);
    if (c < 32 || c > 126)
        return NULL;
    return f->table + (size_t)(c - 32) * f->height * ((f->width + 7) / 8);
}

static int failures = 0, checks = 0;
#define CHECK(cond)                                                \
    do                                                             \
    {                                                              \
        checks++;                                                  \
        if (!(cond))                                               \
        {                                                          \
            failures++;                                            \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        }                                                          \
    } while (0)

enum
{
    W = 320,
    H = 320
};

static uint32_t seed = 12345;
static int rnd(int n)
{
    seed = seed * 1103515245u + 12345u;
    return (int)((seed >> 8) % (uint32_t)n);
}

static gfx_font font(FontSize size)
{
    const FontTable *f = table(size);
    gfx_font g = {f->table, f->width, f->height};
    return g;
}

/* ---- surfaces ----------------------------------------------------------- */

static uint8_t sram_pixels[W * H];
static gfx_sram sram = {sram_pixels, W};
static gfx_surface core;

/* Fake external memory: segments are copied through a scratch buffer, like
 * the device PSRAM, and every transfer is counted. */
static uint8_t ext_pixels[W * H];
static uint8_t ext_scratch[W];
static long ext_transfers = 0;

static void ext_fill(void *ctx, int y, int x, int len, uint8_t c)
{
    (void)ctx;
    ext_transfers++;
    memset(ext_pixels + y * W + x, c, (size_t)len);
}
static void ext_write(void *ctx, int y, int x, int len, const uint8_t *src)
{
    (void)ctx;
    ext_transfers++;
    memcpy(ext_pixels + y * W + x, src, (size_t)len);
}
static void ext_read(void *ctx, int y, int x, int len, uint8_t *dst)
{
    (void)ctx;
    ext_transfers++;
    memcpy(dst, ext_pixels + y * W + x, (size_t)len);
}
static uint8_t *ext_edit(void *ctx, int y, int x, int len)
{
    ext_read(ctx, y, x, len, ext_scratch);
    return ext_scratch;
}
static void ext_commit(void *ctx, int y, int x, int len)
{
    ext_write(ctx, y, x, len, ext_scratch);
}
static const gfx_storage ext_storage = {ext_fill, ext_write, ext_read, ext_edit, ext_commit};
static gfx_surface ext;

/* Compare the core (and the external copy) with the v1 reference. */
static int compare(const char *what)
{
    uint8_t row[W];
    for (int y = 0; y < H; y++)
    {
        lcd_read_row((uint16_t)y, row);
        if (memcmp(row, sram_pixels + y * W, W) || memcmp(row, ext_pixels + y * W, W))
        {
            int x = 0;
            while (x < W && row[x] == sram_pixels[y * W + x] && row[x] == ext_pixels[y * W + x])
                x++;
            failures++;
            printf("FAIL %s: row %d col %d: v1 %02x core %02x external %02x\n", what, y, x,
                   row[x], sram_pixels[y * W + x], ext_pixels[y * W + x]);
            return 0;
        }
    }
    checks++;
    return 1;
}

static uint16_t colour(void)
{
    return (uint16_t)rnd(65536);
}

static int coord(void)
{
    return rnd(W);
}

/* ---- 1 + 2: equivalence with v1 ---------------------------------------- */

static void random_text(char *buffer, int length)
{
    static const char alphabet[] = "abcXYZ019 .,;:!?()[]{}<>+-*/=_@#\n ~\x7f\x01";
    for (int i = 0; i < length; i++)
        buffer[i] = alphabet[rnd((int)sizeof(alphabet) - 1)];
    buffer[length] = 0;
}

static void test_equivalence(void)
{
    gfx_clear(&core, 0);
    gfx_clear(&ext, 0);
    lcd_fill(0);
    int16_t px[12], py[12];
    uint16_t ux[12], uy[12];
    int32_t scratch[6 * 12];
    char text[200];
    for (int round = 0; round < 6000; round++)
    {
        const int op = rnd(17);
        const uint16_t c = colour();
        const int x1 = coord(), y1 = coord(), x2 = coord(), y2 = coord(), x3 = coord(), y3 = coord();
        const int rw = 1 + rnd(W - x1), rh = 1 + rnd(H - y1), rr = rnd(40);
        const char *name = "";
        gfx_surface *both[2] = {&core, &ext};
        for (int k = 0; k < 2; k++)
        {
            gfx_surface *s = both[k];
            switch (op)
            {
            case 0:
                name = "pixel";
                gfx_pixel(s, x1, y1, c);
                if (!k)
                    lcd_draw_pixel((uint16_t)x1, (uint16_t)y1, c);
                break;
            case 1:
                name = "line";
                gfx_line(s, x1, y1, x2, y2, c);
                if (!k)
                    lcd_draw_line((uint16_t)x1, (uint16_t)y1, (uint16_t)x2, (uint16_t)y2, c);
                break;
            case 2:
                name = "rect";
                gfx_rect(s, x1, y1, 1 + x2 / 2, 1 + y2 / 2, c);
                if (!k)
                    lcd_draw_rect((uint16_t)x1, (uint16_t)y1, (uint16_t)(1 + x2 / 2), (uint16_t)(1 + y2 / 2), c);
                break;
            case 3:
                name = "fill_rect";
                gfx_fill_rect(s, x1, y1, x2 / 3, y2 / 3, c);
                if (!k)
                    lcd_fill_rect((uint16_t)x1, (uint16_t)y1, (uint16_t)(x2 / 3), (uint16_t)(y2 / 3), c);
                break;
            case 4:
                name = "circle";
                gfx_circle(s, x1, y1, x2 / 4, c);
                if (!k)
                    lcd_draw_circle((uint16_t)x1, (uint16_t)y1, (uint16_t)(x2 / 4), c);
                break;
            case 5:
                name = "fill_circle";
                gfx_fill_circle(s, x1, y1, x2 / 4, c);
                if (!k)
                    lcd_fill_circle((uint16_t)x1, (uint16_t)y1, (uint16_t)(x2 / 4), c);
                break;
            case 6:
                /* Fully on screen: v1 distorts clipped corners (see test_round_rect). */
                name = "fill_round_rect";
                gfx_fill_round_rect(s, x1, y1, rw, rh, rr, c);
                if (!k)
                    lcd_fill_round_rectangle((uint16_t)x1, (uint16_t)y1, (uint16_t)rw, (uint16_t)rh, (uint16_t)rr, c);
                break;
            case 7:
                name = "triangle";
                gfx_triangle(s, x1, y1, x2, y2, x3, y3, c);
                if (!k)
                    lcd_draw_triangle((uint16_t)x1, (uint16_t)y1, (uint16_t)x2, (uint16_t)y2, (uint16_t)x3, (uint16_t)y3, c);
                break;
            case 8:
                name = "fill_triangle";
                gfx_fill_triangle(s, x1, y1, x2, y2, x3, y3, c);
                if (!k)
                    lcd_fill_triangle((uint16_t)x1, (uint16_t)y1, (uint16_t)x2, (uint16_t)y2, (uint16_t)x3, (uint16_t)y3, c);
                break;
            case 9:
            {
                name = "fill_triangle_alpha";
                const uint8_t a = (uint8_t)(x3 * 255 / W);
                gfx_fill_triangle_alpha(s, x1, y1, x2, y2, x3, y3, c, a);
                if (!k)
                    lcd_fill_triangle_alpha((uint16_t)x1, (uint16_t)y1, (uint16_t)x2, (uint16_t)y2, (uint16_t)x3, (uint16_t)y3, c, a);
                break;
            }
            case 10:
            case 11:
            case 12:
            {
                const int n = 2 + (x3 % 10);
                if (!k)
                    for (int i = 0; i < n; i++)
                    {
                        px[i] = (int16_t)coord();
                        py[i] = (int16_t)coord();
                        ux[i] = (uint16_t)px[i];
                        uy[i] = (uint16_t)py[i];
                    }
                const uint8_t a = (uint8_t)(y3 * 255 / H);
                if (op == 10)
                {
                    name = "polygon";
                    gfx_polygon(s, px, py, n, c);
                    if (!k)
                        lcd_polygon(ux, uy, n, c);
                }
                else if (op == 11)
                {
                    name = "fill_polygon";
                    gfx_fill_polygon(s, px, py, n, c, scratch);
                    if (!k)
                        lcd_fill_polygon(ux, uy, n, c);
                }
                else
                {
                    name = "fill_polygon_alpha";
                    gfx_fill_polygon_alpha(s, px, py, n, c, a, scratch);
                    if (!k)
                        lcd_fill_polygon_alpha(ux, uy, n, c, a);
                }
                break;
            }
            case 13:
            {
                name = "char";
                const FontSize f = (FontSize)(x3 % 5);
                const gfx_font gf = font(f);
                const char ch = (char)(28 + y3 % 104);
                gfx_char(s, x1, y1, ch, c, &gf);
                if (!k)
                    lcd_draw_char((uint16_t)x1, (uint16_t)y1, ch, c, f);
                break;
            }
            case 14:
            {
                name = "text";
                const FontSize f = (FontSize)(x3 % 5);
                const gfx_font gf = font(f);
                if (!k)
                    random_text(text, 1 + rnd(120));
                gfx_text(s, x1 / 2, y1, text, c, &gf);
                if (!k)
                    lcd_draw_text((uint16_t)(x1 / 2), (uint16_t)y1, text, c, f);
                break;
            }
            case 15:
            {
                name = "blit8";
                static uint8_t img[60 * 50];
                if (!k)
                    for (int i = 0; i < 60 * 50; i++)
                        img[i] = (uint8_t)rnd(256);
                const int w = 1 + x2 % 60, h = 1 + y2 % 50;
                gfx_blit8(s, x1, y1, w, h, img);
                if (!k)
                    picocalc_lcd_blit((uint16_t)x1, (uint16_t)y1, (uint16_t)w, (uint16_t)h, img);
                break;
            }
            case 16:
            {
                name = "blit16";
                static uint16_t img[60 * 50];
                if (!k)
                    for (int i = 0; i < 60 * 50; i++)
                        img[i] = colour();
                /* On screen only: v1 shears images clipped at the right edge
                 * (see test_blit16_clipping). */
                const int w = 1 + x2 % 60, h = 1 + y2 % 50;
                const int bx = x1 + w > W ? W - w : x1;
                gfx_blit16(s, bx, y1, w, h, img);
                if (!k)
                    lcd_blit_16bit((uint16_t)bx, (uint16_t)y1, (uint16_t)w, (uint16_t)h, img);
                break;
            }
            }
        }
        if (!compare(name))
        {
            printf("  (round %d, op %s)\n", round, name);
            return;
        }
        if (round % 400 == 399)
        {
            gfx_clear(&core, c);
            gfx_clear(&ext, c);
            lcd_fill(c);
        }
    }
}

/* ---- 3: deliberate fixes ------------------------------------------------- */

static void reset(void)
{
    gfx_clear(&core, 0);
}

static int count_colour(uint8_t c, int y0, int y1)
{
    int n = 0;
    for (int i = y0 * W; i < y1 * W; i++)
        n += sram_pixels[i] == c;
    return n;
}

static void test_signed_coordinates(void)
{
    /* v1 drew lines that start left of the screen from the right edge. */
    reset();
    gfx_line(&core, -20, 10, 50, 10, 0xFFFF);
    CHECK(count_colour(0xFF, 0, H) == 51);
    CHECK(sram_pixels[10 * W + 0] == 0xFF && sram_pixels[10 * W + 50] == 0xFF && sram_pixels[10 * W + 51] == 0);

    reset();
    gfx_fill_rect(&core, -10, -10, 30, 30, 0xFFFF);
    CHECK(count_colour(0xFF, 0, H) == 20 * 20);

    reset();
    gfx_fill_triangle(&core, -50, 100, 50, 100, -50, 200, 0xFFFF);
    CHECK(sram_pixels[150 * W + 0] == 0xFF && sram_pixels[150 * W + W - 1] == 0);

    reset();
    const gfx_font f = font(FONT_SIZE_SMALL);
    gfx_text(&core, -3, 0, "W", 0xFFFF, &f);
    CHECK(sram_pixels[0 * W + W - 1] == 0 && count_colour(0xFF, 0, H) > 0);
}

/* Brute-force definition of a filled rounded rectangle. */
static int inside_round_rect(int px, int py, int x, int y, int w, int h, int r)
{
    if (r > w / 2)
        r = w / 2;
    if (r > h / 2)
        r = h / 2;
    if (px < x || px >= x + w || py < y || py >= y + h)
        return 0;
    const int lc = x + r, rc = x + w - r, tc = y + r, bc = y + h - r;
    int cx = px < lc ? lc : px >= rc ? rc : px;
    int cy = py < tc ? tc : py >= bc ? bc : py;
    if ((px < lc || px >= rc) && (py < tc || py >= bc))
        return (px - cx) * (px - cx) + (py - cy) * (py - cy) <= r * r;
    return 1;
}

static void test_round_rect(void)
{
    for (int trial = 0; trial < 300; trial++)
    {
        const int x = rnd(400) - 40, y = rnd(400) - 40, w = 1 + rnd(200), h = 1 + rnd(200), r = 1 + rnd(60);
        reset();
        gfx_fill_round_rect(&core, x, y, w, h, r, 0xFFFF);
        int bad = 0;
        for (int py = 0; py < H; py++)
            for (int px = 0; px < W; px++)
                bad += (sram_pixels[py * W + px] == 0xFF) != inside_round_rect(px, py, x, y, w, h, r);
        if (bad)
        {
            failures++;
            printf("FAIL round rect %d,%d %dx%d r%d: %d pixels differ\n", x, y, w, h, r, bad);
            return;
        }
    }
    checks++;

    /* On screen, v1 agrees with the definition too. */
    for (int trial = 0; trial < 100; trial++)
    {
        const int x = rnd(200), y = rnd(200), w = 1 + rnd(W - x), h = 1 + rnd(H - y), r = 1 + rnd(50);
        lcd_fill(0);
        reset();
        lcd_fill_round_rectangle((uint16_t)x, (uint16_t)y, (uint16_t)w, (uint16_t)h, (uint16_t)r, 0xFFFF);
        gfx_fill_round_rect(&core, x, y, w, h, r, 0xFFFF);
        uint8_t row[W];
        for (int py = 0; py < H; py++)
        {
            lcd_read_row((uint16_t)py, row);
            if (memcmp(row, sram_pixels + py * W, W))
            {
                failures++;
                printf("FAIL round rect vs v1 %d,%d %dx%d r%d row %d\n", x, y, w, h, r, py);
                return;
            }
        }
    }
    checks++;
}

/* v1 stepped through clipped 16-bit images with the clipped width. */
static void test_blit16_clipping(void)
{
    static uint16_t img[40 * 20];
    for (int i = 0; i < 40 * 20; i++)
        img[i] = (uint16_t)(i * 2654435761u >> 16);
    for (int trial = 0; trial < 50; trial++)
    {
        const int x = rnd(W + 60) - 50, y = rnd(H + 40) - 30;
        reset();
        gfx_blit16(&core, x, y, 40, 20, img);
        int bad = 0;
        for (int sy = 0; sy < 20; sy++)
            for (int sx = 0; sx < 40; sx++)
            {
                const int px = x + sx, py = y + sy;
                if (px >= 0 && px < W && py >= 0 && py < H)
                    bad += sram_pixels[py * W + px] != gfx_to332(img[sy * 40 + sx]);
            }
        if (bad)
        {
            failures++;
            printf("FAIL blit16 at %d,%d: %d pixels wrong\n", x, y, bad);
            return;
        }
    }
    checks++;
}

/* ---- 4: presenting ------------------------------------------------------- */

typedef struct
{
    int runs, rows, first_y[16], count[16];
    const uint8_t *image; /* what each sent row must hold */
    int next_y, open, wrong;
} sent_log;

static void record_begin(void *ctx, int y)
{
    sent_log *log = ctx;
    log->wrong += log->open; /* runs never nest */
    log->open = 1;
    if (log->runs < 16)
    {
        log->first_y[log->runs] = y;
        log->count[log->runs] = 0;
    }
    log->next_y = y;
}

static void record_row(void *ctx, int y, const uint8_t *pixels)
{
    sent_log *log = ctx;
    log->wrong += !log->open || y != log->next_y || memcmp(pixels, log->image + y * W, W) != 0;
    log->next_y = y + 1;
    if (log->runs < 16)
        log->count[log->runs]++;
    log->rows++;
}

static void record_end(void *ctx)
{
    sent_log *log = ctx;
    log->wrong += !log->open;
    log->open = 0;
    log->runs++;
}

static const gfx_sink record = {record_begin, record_row, record_end};

static void log_reset(sent_log *log, const uint8_t *image)
{
    memset(log, 0, sizeof(*log));
    log->image = image;
}

static void test_present(void)
{
    static uint32_t hash[H];
    const gfx_font f = font(FONT_SIZE_SMALL);
    sent_log log;

    gfx_clear(&core, 0);
    log_reset(&log, sram_pixels);
    CHECK(gfx_present(&core, hash, true, &record, &log) == H && log.runs == 1 && log.count[0] == H);

    log_reset(&log, sram_pixels);
    CHECK(gfx_present(&core, hash, false, &record, &log) == 0 && log.runs == 0);

    /* Redrawing identical content sends nothing. */
    gfx_clear(&core, 0);
    gfx_text(&core, 10, 100, "Same menu", 0xFFFF, &f);
    log_reset(&log, sram_pixels);
    gfx_present(&core, hash, false, &record, &log);
    CHECK(log.runs == 1 && log.rows > 0 && log.first_y[0] >= 100 && log.first_y[0] + log.rows <= 112);
    gfx_clear(&core, 0);
    gfx_text(&core, 10, 100, "Same menu", 0xFFFF, &f);
    log_reset(&log, sram_pixels);
    CHECK(gfx_present(&core, hash, false, &record, &log) == 0);

    /* Two separate changes: two runs, only their rows. */
    gfx_text(&core, 10, 20, "A", 0xFFFF, &f);
    gfx_fill_rect(&core, 0, 300, 5, 3, 0xF800);
    log_reset(&log, sram_pixels);
    gfx_present(&core, hash, false, &record, &log);
    CHECK(log.runs == 2 && log.first_y[0] >= 20 && log.first_y[0] + log.count[0] <= 32 &&
          log.first_y[1] == 300 && log.count[1] == 3);
    /* Every run was closed and every row held the image's pixels. */
    CHECK(log.wrong == 0 && !log.open);

    /* A run reaching the bottom row is closed too. */
    gfx_fill_rect(&core, 0, H - 4, W, 4, 0x07E0);
    log_reset(&log, sram_pixels);
    gfx_present(&core, hash, false, &record, &log);
    CHECK(log.runs == 1 && log.first_y[0] == H - 4 && log.count[0] == 4 && log.wrong == 0 && !log.open);

    /* Only rows drawn on are read back, once each for hash and sink. */
    gfx_surface_init(&ext, W, H, &ext_storage, NULL);
    static uint32_t ext_hash[H];
    gfx_clear(&ext, 0);
    log_reset(&log, ext_pixels);
    gfx_present(&ext, ext_hash, true, &record, &log);
    CHECK(log.rows == H && log.wrong == 0);
    gfx_pixel(&ext, 5, 5, 0xFFFF);
    gfx_text(&ext, 0, 200, "PSRAM", 0xFFE0, &f);
    ext_transfers = 0;
    log_reset(&log, ext_pixels);
    gfx_present(&ext, ext_hash, false, &record, &log);
    /* One read per dirty row: the pixel's row and every row of the text line. */
    CHECK(log.runs >= 2 && log.first_y[0] == 5 && log.count[0] == 1 && log.wrong == 0 && !log.open &&
          ext_transfers == 1 + f.height);
}

/* ---- transfer counts on external memory ---------------------------------- */

static void report_transfers(void)
{
    const gfx_font f = font(FONT_SIZE_SMALL);
    char line[64];
    long lit = 0;
    gfx_clear(&ext, 0);
    ext_transfers = 0;
    for (int row = 0; row < 26; row++)
    {
        snprintf(line, sizeof(line), "Row %02d: Settings > Display > Brightness %d", row, row * 3);
        gfx_text(&ext, 2, row * 12, line, 0xFFFF, &f);
    }
    for (int i = 0; i < W * H; i++)
        lit += ext_pixels[i] == 0xFF;
    printf("full screen of text: v1 %ld PSRAM transfers (one per lit pixel), core %ld\n",
           lit, ext_transfers);
    CHECK(ext_transfers * 5 < lit);

    ext_transfers = 0;
    gfx_fill_round_rect(&ext, 10, 10, 300, 30, 8, 0x001F);
    printf("300x30 rounded button: v1 ~%d transfers (one per pixel), core %ld\n", 300 * 30, ext_transfers);
}

int main(int argc, char **argv)
{
    if (argc > 1)
        seed = (uint32_t)strtoul(argv[1], NULL, 10);
    gfx_init_palette();
    lcd_set_mode(1);
    picocalc_lcd_init();
    gfx_surface_init(&core, W, H, &gfx_sram_storage, &sram);
    gfx_surface_init(&ext, W, H, &ext_storage, NULL);

    test_equivalence();
    test_signed_coordinates();
    test_round_rect();
    test_blit16_clipping();
    test_present();
    report_transfers();
    printf("%s: %d checks, %d failures\n", failures ? "FAIL" : "PASS", checks, failures);
    return failures ? 1 : 0;
}
