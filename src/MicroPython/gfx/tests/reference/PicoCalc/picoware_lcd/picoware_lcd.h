/* Host stub: the v1 driver's public header without hardware includes. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "font.h"
#include "../picoware_psram/psram_qspi.h"
#define DISPLAY_WIDTH 320
#define DISPLAY_HEIGHT 320
#define __force_inline inline
uint8_t font_get_width(FontSize size);
uint8_t font_get_height(FontSize size);
const uint8_t *font_get_data(FontSize size);
const uint8_t *font_get_character(FontSize size, char c);
static inline void lcd_init(void) {}
static inline void lcd_blit(uint16_t *p, uint16_t x, uint16_t y, uint16_t w, uint16_t h)
{
    (void)p, (void)x, (void)y, (void)w, (void)h;
}
void lcd_set_mode(uint8_t mode);
void picocalc_lcd_init(void);
void picoware_lcd_swap_region(uint16_t x, uint16_t y, uint16_t width, uint16_t height);
