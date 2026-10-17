/*
 * The display drawing API used by the lcd binding and other native modules
 * (vt, textbox, jpeg, uf2loader), implemented on the shared gfx core.
 *
 * Shared by the firmware and the desktop simulator. Each platform provides
 * the rest: setting up gfx_screen's storage, presenting (swap), and modes.
 * Coordinates arrive as uint16_t from the binding and are read as signed,
 * so shapes that cross the left or top edge are clipped correctly.
 */
#ifndef GFX_LCD_H
#define GFX_LCD_H

#include "gfx.h"
#include "font.h"

extern gfx_surface gfx_screen;
/* What the display currently shows, one hash per row (see gfx_present). */
extern uint32_t gfx_screen_hash[GFX_MAX_HEIGHT];

void lcd_draw_pixel(uint16_t x, uint16_t y, uint16_t color);
void lcd_fill(uint16_t color);
void picocalc_lcd_blit(uint16_t x, uint16_t y, uint16_t width, uint16_t height, const uint8_t *buffer);
void lcd_blit_16bit(uint16_t x, uint16_t y, uint16_t width, uint16_t height, const uint16_t *buffer);
void lcd_draw_line(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2, uint16_t color);
void lcd_draw_rect(uint16_t x, uint16_t y, uint16_t width, uint16_t height, uint16_t color);
void lcd_fill_rect(uint16_t x, uint16_t y, uint16_t width, uint16_t height, uint16_t color);
void lcd_draw_circle(uint16_t center_x, uint16_t center_y, uint16_t radius, uint16_t color);
void lcd_fill_circle(uint16_t center_x, uint16_t center_y, uint16_t radius, uint16_t color);
void lcd_fill_triangle(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2, uint16_t x3, uint16_t y3, uint16_t color);
void lcd_fill_triangle_alpha(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2, uint16_t x3, uint16_t y3, uint16_t color, uint8_t alpha);
void lcd_fill_round_rectangle(uint16_t x, uint16_t y, uint16_t width, uint16_t height, uint16_t radius, uint16_t color);
void lcd_draw_triangle(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2, uint16_t x3, uint16_t y3, uint16_t color);
void lcd_polygon(uint16_t x[], uint16_t y[], int count, uint16_t color);
void lcd_fill_polygon(uint16_t x[], uint16_t y[], int count, uint16_t color);
void lcd_fill_polygon_alpha(uint16_t x[], uint16_t y[], int count, uint16_t color, uint8_t alpha);
void lcd_draw_char(uint16_t x, uint16_t y, char c, uint16_t color, FontSize size);
void lcd_draw_text(uint16_t x, uint16_t y, const char *text, uint16_t color, FontSize size);
/* One row of the image as RGB332, 1 byte per pixel. */
bool lcd_read_row(uint16_t row, uint8_t *dst);

#endif
