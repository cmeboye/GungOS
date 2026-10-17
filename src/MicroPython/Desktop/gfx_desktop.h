/*
 * Desktop simulator display: the shared gfx core on an SRAM image. Each swap
 * converts the changed rows into an RGB565 frame and hands it to the
 * simulator runtime (sim_runtime.lcd_present), with the number of rows the
 * device would have sent.
 */
#pragma once

#include "py/obj.h"
#include "../gfx/gfx_lcd.h"

void desktop_lcd_init(void);
void desktop_lcd_deinit(void);
void desktop_lcd_register(mp_obj_t lcd);
int desktop_lcd_swap(void);
void desktop_lcd_set_brightness(uint8_t brightness);
void desktop_lcd_set_rgb_led(uint8_t red, uint8_t green, uint8_t blue);
void desktop_lcd_set_mode(uint8_t mode);
uint8_t desktop_lcd_get_mode(void);
bool desktop_lcd_set_panel_bits(uint8_t bits);
