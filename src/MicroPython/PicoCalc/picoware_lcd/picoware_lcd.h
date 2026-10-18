#pragma once

#ifdef __cplusplus
extern "C"
{
#endif

#include "lcd.h"
#include "../picoware_psram/psram_qspi.h"
#include "../../font/font_mp.h"
#include "../../gfx/gfx_lcd.h"

// Display constants
#define DISPLAY_WIDTH 320
#define DISPLAY_HEIGHT 320
#define PALETTE_SIZE 256

// Where the screen image lives. PSRAM is the default and keeps 100 KB of RAM
// free; SRAM draws about 2.5x faster (Settings > Fast Drawing, or per app).
#define LCD_MODE_PSRAM 0
#define LCD_MODE_SRAM 1

    // Core display functions. lcd_swap returns the number of rows sent.
    void picocalc_lcd_init(void);
    void lcd_deinit(void);
    int lcd_swap(void);
    // Send every row on the next swap, e.g. after something else drew on the panel.
    void lcd_invalidate(void);

    // Drawing functions (lcd_draw_*, lcd_fill*, blits, text) are in gfx_lcd.h.

    // Experimental: send 12 bits per pixel instead of 16 (25% less to send).
    // Returns false for anything but 12 or 16.
    bool lcd_set_panel_bits(uint8_t bits);

    void lcd_set_mode(uint8_t mode);
    uint8_t lcd_get_mode(void);

    // reads from a PSRAM address and writes to the LCD
    void lcd_psram(uint16_t x, uint16_t y, uint16_t width, uint16_t height, uint32_t addr);

    // reads one row of 16-bit pixels from a PSRAM address into a caller-provided buffer
    // returns true on success, false if PSRAM is not initialized
    bool lcd_psram_read_row(uint32_t addr, uint16_t row, uint16_t width, uint16_t *dst);

    // External PSRAM instance access
    extern psram_qspi_inst_t *picoware_get_psram_instance(void);

#ifdef __cplusplus
}
#endif
