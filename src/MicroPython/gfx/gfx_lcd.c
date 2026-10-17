#include "gfx_lcd.h"
#include "py/runtime.h"

gfx_surface gfx_screen;
uint32_t gfx_screen_hash[GFX_MAX_HEIGHT];

static inline int s16(uint16_t v)
{
    return (int16_t)v;
}

static gfx_font font_for(FontSize size)
{
    static const FontTable *const tables[] = {&Font8, &Font12, &Font16, &Font20, &Font24};
    const FontTable *t = tables[(unsigned)size < 5 ? size : 0];
    gfx_font f = {t->table, t->width, t->height};
    return f;
}

void lcd_draw_pixel(uint16_t x, uint16_t y, uint16_t color)
{
    gfx_pixel(&gfx_screen, s16(x), s16(y), color);
}

void lcd_fill(uint16_t color)
{
    gfx_clear(&gfx_screen, color);
}

void picocalc_lcd_blit(uint16_t x, uint16_t y, uint16_t width, uint16_t height, const uint8_t *buffer)
{
    gfx_blit8(&gfx_screen, s16(x), s16(y), width, height, buffer);
}

void lcd_blit_16bit(uint16_t x, uint16_t y, uint16_t width, uint16_t height, const uint16_t *buffer)
{
    gfx_blit16(&gfx_screen, s16(x), s16(y), width, height, buffer);
}

void lcd_draw_line(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2, uint16_t color)
{
    gfx_line(&gfx_screen, s16(x1), s16(y1), s16(x2), s16(y2), color);
}

void lcd_draw_rect(uint16_t x, uint16_t y, uint16_t width, uint16_t height, uint16_t color)
{
    gfx_rect(&gfx_screen, s16(x), s16(y), width, height, color);
}

void lcd_fill_rect(uint16_t x, uint16_t y, uint16_t width, uint16_t height, uint16_t color)
{
    gfx_fill_rect(&gfx_screen, s16(x), s16(y), width, height, color);
}

void lcd_draw_circle(uint16_t center_x, uint16_t center_y, uint16_t radius, uint16_t color)
{
    gfx_circle(&gfx_screen, s16(center_x), s16(center_y), radius, color);
}

void lcd_fill_circle(uint16_t center_x, uint16_t center_y, uint16_t radius, uint16_t color)
{
    gfx_fill_circle(&gfx_screen, s16(center_x), s16(center_y), radius, color);
}

void lcd_fill_triangle(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2, uint16_t x3, uint16_t y3, uint16_t color)
{
    gfx_fill_triangle(&gfx_screen, s16(x1), s16(y1), s16(x2), s16(y2), s16(x3), s16(y3), color);
}

void lcd_fill_triangle_alpha(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2, uint16_t x3, uint16_t y3, uint16_t color, uint8_t alpha)
{
    gfx_fill_triangle_alpha(&gfx_screen, s16(x1), s16(y1), s16(x2), s16(y2), s16(x3), s16(y3), color, alpha);
}

void lcd_fill_round_rectangle(uint16_t x, uint16_t y, uint16_t width, uint16_t height, uint16_t radius, uint16_t color)
{
    gfx_fill_round_rect(&gfx_screen, s16(x), s16(y), width, height, radius, color);
}

void lcd_draw_triangle(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2, uint16_t x3, uint16_t y3, uint16_t color)
{
    gfx_triangle(&gfx_screen, s16(x1), s16(y1), s16(x2), s16(y2), s16(x3), s16(y3), color);
}

/* The binding passes uint16_t arrays; the same bits read as int16_t give
 * signed coordinates without copying. */
void lcd_polygon(uint16_t x[], uint16_t y[], int count, uint16_t color)
{
    gfx_polygon(&gfx_screen, (const int16_t *)x, (const int16_t *)y, count, color);
}

#define STACK_POLYGON 32

static void fill_polygon(uint16_t x[], uint16_t y[], int count, uint16_t color, uint8_t alpha)
{
    if (count < 3)
        return;
    int32_t stack[6 * STACK_POLYGON];
    int32_t *scratch = count <= STACK_POLYGON ? stack : m_new(int32_t, 6 * (size_t)count);
    gfx_fill_polygon_alpha(&gfx_screen, (const int16_t *)x, (const int16_t *)y, count, color, alpha, scratch);
    if (scratch != stack)
        m_del(int32_t, scratch, 6 * (size_t)count);
}

void lcd_fill_polygon(uint16_t x[], uint16_t y[], int count, uint16_t color)
{
    fill_polygon(x, y, count, color, 255);
}

void lcd_fill_polygon_alpha(uint16_t x[], uint16_t y[], int count, uint16_t color, uint8_t alpha)
{
    fill_polygon(x, y, count, color, alpha);
}

void lcd_draw_char(uint16_t x, uint16_t y, char c, uint16_t color, FontSize size)
{
    const gfx_font f = font_for(size);
    gfx_char(&gfx_screen, s16(x), s16(y), c, color, &f);
}

void lcd_draw_text(uint16_t x, uint16_t y, const char *text, uint16_t color, FontSize size)
{
    const gfx_font f = font_for(size);
    gfx_text(&gfx_screen, s16(x), s16(y), text, color, &f);
}

bool lcd_read_row(uint16_t row, uint8_t *dst)
{
    if (row >= gfx_screen.height || !dst)
        return false;
    gfx_read_row(&gfx_screen, row, dst);
    return true;
}
