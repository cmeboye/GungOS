#pragma once
#include <stdbool.h>

/*
 * Drawing is the shared gfx core (../gfx/gfx_lcd.h) on both the firmware and
 * the desktop simulator, so the simulator shows the device's exact pixels.
 * Only setup, presenting, modes and the backlight differ per platform.
 */
#if defined(PICOCALC) || defined(DESKTOP)
#define LCD_MP_WIDTH 320
#define LCD_MP_HEIGHT 320
#define LCD_MP_CHAR lcd_draw_char
#define LCD_MP_CIRCLE lcd_draw_circle
#define LCD_MP_CLEAR lcd_fill
#define LCD_MP_FILL_CIRCLE lcd_fill_circle
#define LCD_MP_FILL_RECTANGLE lcd_fill_rect
#define LCD_MP_FILL_ROUND_RECTANGLE lcd_fill_round_rectangle
#define LCD_MP_FILL_TRIANGLE lcd_fill_triangle
#define LCD_MP_FILL_TRIANGLE_ALPHA lcd_fill_triangle_alpha
#define LCD_MP_BLIT picocalc_lcd_blit
#define LCD_MP_BLIT_16BIT lcd_blit_16bit
#define LCD_MP_LINE lcd_draw_line
#define LCD_MP_PIXEL lcd_draw_pixel
#define LCD_MP_READ_ROW lcd_read_row
#define LCD_MP_RECTANGLE lcd_draw_rect
#define LCD_MP_TEXT lcd_draw_text
#define LCD_MP_TRIANGLE lcd_draw_triangle
#define LCD_MP_POLYGON lcd_polygon
#define LCD_MP_FILL_POLYGON lcd_fill_polygon
#define LCD_MP_FILL_POLYGON_ALPHA lcd_fill_polygon_alpha
#endif

#if defined(PICOCALC)
#define LCD_INCLUDE "../PicoCalc/picoware_lcd/picoware_lcd.h"
#define LCD_MP_INIT picocalc_lcd_init
#define LCD_MP_DEINIT lcd_deinit
#define LCD_MP_PSRAM lcd_psram
#define LCD_MP_PSRAM_READ_ROW lcd_psram_read_row
#include "../PicoCalc/picoware_keyboard/southbridge.h"
#define LCD_MP_SET_BRIGHTNESS sb_write_lcd_backlight
#define LCD_MP_SET_MODE lcd_set_mode
#define LCD_MP_GET_MODE lcd_get_mode
#define LCD_MP_SET_PANEL_BITS lcd_set_panel_bits
#define LCD_SWAP lcd_swap
#endif

#ifdef DESKTOP
#define LCD_INCLUDE "../Desktop/gfx_desktop.h"
#include "../font/font_mp.h"
#include "../Desktop/desktop_bridge.h"
#define LCD_MP_INIT desktop_lcd_init
#define LCD_MP_DEINIT desktop_lcd_deinit
#define LCD_MP_SET_BRIGHTNESS desktop_lcd_set_brightness
#define LCD_MP_SET_RGB_LED desktop_lcd_set_rgb_led
#define LCD_MP_SET_MODE desktop_lcd_set_mode
#define LCD_MP_GET_MODE desktop_lcd_get_mode
#define LCD_MP_SET_PANEL_BITS desktop_lcd_set_panel_bits
#define LCD_SWAP desktop_lcd_swap
#define storage_file_open desktop_storage_file_open
#define storage_file_read_file_chunk desktop_storage_file_read_file_chunk
#define storage_file_write_open desktop_storage_file_write_open
#define storage_file_close desktop_storage_file_close
#define storage_file_write_file_chunk desktop_storage_file_write_file_chunk
#define LOG_MESSAGE(...) mp_printf(&mp_plat_print, __VA_ARGS__)
#endif

// Present what changed; evaluates to the number of rows sent.
#define LCD_MP_SWAP() LCD_SWAP()
