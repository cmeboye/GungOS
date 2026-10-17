/*
 * PicoCalc display: where the screen image lives, and getting it to the panel.
 *
 * Drawing itself is the shared gfx core (../../gfx), the same code the desktop
 * simulator runs. This file provides:
 *   - storage for the 8-bit (RGB332) image: on-chip SRAM by default, or the
 *     external PSRAM to free about 100 KB of RAM for large jobs;
 *   - presenting: only rows that changed since the last swap are converted
 *     to RGB565 and sent, by DMA, while the CPU converts the next block.
 *
 * Based on the Picoware LCD library, Copyright © 2025 JBlanked.
 */
#include <string.h>

#include "picoware_lcd.h"
#include "../picoware_psram/psram_qspi.h"
#include "../picoware_psram/picoware_psram_shared.h"
#include "py/runtime.h"

#include "../../log/log_mp.h"

// Rows converted and sent per DMA transfer; two buffers alternate.
#define LCD_STREAM_LINES 8

static bool module_initialized = false;
static uint8_t lcd_mode = LCD_MODE_SRAM; // requested, and current once initialized
static bool full_refresh = true;          // panel content unknown: send everything

static uint8_t *sram_pixels = NULL;
static gfx_sram sram_image;
#define IMAGE_SIZE (DISPLAY_WIDTH * DISPLAY_HEIGHT)

// RGB332 -> RGB565 with the bytes swapped, so memory holds the high byte
// first, as the panel expects.
static uint16_t palette_be[256] __attribute__((aligned(4)));
static uint16_t stream_buffer[2][DISPLAY_WIDTH * LCD_STREAM_LINES] __attribute__((aligned(4)));
static uint8_t row_buffer[DISPLAY_WIDTH] __attribute__((aligned(4)));

// ---------------------------------------------------------------------------
// PSRAM storage
// ---------------------------------------------------------------------------

static uint8_t psram_scratch[DISPLAY_WIDTH] __attribute__((aligned(4)));

static void psram_ready(void)
{
    if (!psram_initialized)
    {
        psram_instance = psram_qspi_init(pio1, -1, 1.0f);
        psram_initialized = true;
    }
}

static inline uint32_t image_addr(int y, int x)
{
    return PSRAM_FRAMEBUFFER_ADDR + (uint32_t)y * PSRAM_ROW_SIZE + (uint32_t)x;
}

static void psram_put(uint32_t addr, const uint8_t *src, int len)
{
    while (len > 0)
    {
        int n = len > PSRAM_CHUNK_SIZE ? PSRAM_CHUNK_SIZE : len;
        psram_qspi_write(&psram_instance, addr, src, (size_t)n);
        addr += (uint32_t)n;
        src += n;
        len -= n;
    }
}

static void psram_get(uint32_t addr, uint8_t *dst, int len)
{
    while (len > 0)
    {
        int n = len > PSRAM_CHUNK_SIZE ? PSRAM_CHUNK_SIZE : len;
        psram_qspi_read(&psram_instance, addr, dst, (size_t)n);
        addr += (uint32_t)n;
        dst += n;
        len -= n;
    }
}

static void psram_fill(void *ctx, int y, int x, int len, uint8_t color)
{
    (void)ctx;
    memset(psram_scratch, color, (size_t)len);
    psram_put(image_addr(y, x), psram_scratch, len);
}

static void psram_write(void *ctx, int y, int x, int len, const uint8_t *src)
{
    (void)ctx;
    psram_put(image_addr(y, x), src, len);
}

static void psram_read(void *ctx, int y, int x, int len, uint8_t *dst)
{
    (void)ctx;
    psram_get(image_addr(y, x), dst, len);
}

static uint8_t *psram_edit(void *ctx, int y, int x, int len)
{
    (void)ctx;
    psram_get(image_addr(y, x), psram_scratch, len);
    return psram_scratch;
}

static void psram_commit(void *ctx, int y, int x, int len)
{
    (void)ctx;
    psram_put(image_addr(y, x), psram_scratch, len);
}

static const gfx_storage psram_storage = {psram_fill, psram_write, psram_read, psram_edit, psram_commit};

// ---------------------------------------------------------------------------
// Modes
// ---------------------------------------------------------------------------

// The image keeps its content across a switch, so nothing needs resending.
static bool use_sram(void)
{
    uint8_t *pixels = (uint8_t *)m_tracked_calloc(1, IMAGE_SIZE);
    if (pixels == NULL)
        return false;
    if (module_initialized && lcd_mode == LCD_MODE_PSRAM)
        for (int y = 0; y < DISPLAY_HEIGHT; y++)
            psram_get(image_addr(y, 0), pixels + y * DISPLAY_WIDTH, DISPLAY_WIDTH);
    sram_pixels = pixels;
    sram_image.pixels = pixels;
    sram_image.stride = DISPLAY_WIDTH;
    gfx_surface_init(&gfx_screen, DISPLAY_WIDTH, DISPLAY_HEIGHT, &gfx_sram_storage, &sram_image);
    lcd_mode = LCD_MODE_SRAM;
    return true;
}

static void use_psram(void)
{
    psram_ready();
    if (sram_pixels != NULL)
    {
        for (int y = 0; y < DISPLAY_HEIGHT; y++)
            psram_put(image_addr(y, 0), sram_pixels + y * DISPLAY_WIDTH, DISPLAY_WIDTH);
        m_tracked_free(sram_pixels);
        sram_pixels = NULL;
    }
    gfx_surface_init(&gfx_screen, DISPLAY_WIDTH, DISPLAY_HEIGHT, &psram_storage, NULL);
    lcd_mode = LCD_MODE_PSRAM;
}

void lcd_set_mode(uint8_t mode)
{
    if (mode != LCD_MODE_SRAM && mode != LCD_MODE_PSRAM)
        return;
    if (!module_initialized)
    {
        lcd_mode = mode; // applied by picocalc_lcd_init
        return;
    }
    if (mode == lcd_mode)
        return;
    if (mode == LCD_MODE_SRAM)
    {
        if (!use_sram())
            LOG_MESSAGE("Not enough RAM for the SRAM screen image; staying in PSRAM mode");
    }
    else
        use_psram();
}

uint8_t lcd_get_mode(void)
{
    return lcd_mode;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

void picocalc_lcd_init(void)
{
    if (!module_initialized)
    {
        lcd_init();
        gfx_init_palette();
        for (int i = 0; i < 256; i++)
        {
            uint16_t c = gfx_palette[i];
            palette_be[i] = (uint16_t)((c >> 8) | (c << 8));
        }
    }
    if (sram_pixels == NULL && lcd_mode == LCD_MODE_SRAM && !use_sram())
    {
        LOG_MESSAGE("Not enough RAM for the SRAM screen image; using PSRAM");
        use_psram();
    }
    else if (lcd_mode == LCD_MODE_PSRAM)
        use_psram();
    module_initialized = true;
    full_refresh = true;
}

void lcd_deinit(void)
{
    if (module_initialized)
    {
        if (sram_pixels != NULL)
        {
            m_tracked_free(sram_pixels);
            sram_pixels = NULL;
        }
        if (psram_initialized)
        {
            psram_qspi_deinit(&psram_instance);
            psram_initialized = false;
        }
        module_initialized = false;
    }
}

void lcd_invalidate(void)
{
    full_refresh = true;
}

// Send rows [y, y + rows) as one window, converting the next block while
// DMA sends the current one.
static void send_rows(void *ctx, int y, int rows)
{
    (void)ctx;
    lcd_stream_begin(0, (uint16_t)y, DISPLAY_WIDTH - 1, (uint16_t)(y + rows - 1));
    int which = 0;
    for (int done = 0; done < rows; done += LCD_STREAM_LINES)
    {
        const int lines = rows - done < LCD_STREAM_LINES ? rows - done : LCD_STREAM_LINES;
        uint16_t *out = stream_buffer[which];
        for (int line = 0; line < lines; line++)
        {
            const int row = y + done + line;
            const uint8_t *src;
            if (sram_pixels != NULL)
                src = sram_pixels + row * DISPLAY_WIDTH;
            else
            {
                psram_get(image_addr(row, 0), row_buffer, DISPLAY_WIDTH);
                src = row_buffer;
            }
            uint16_t *dst = out + line * DISPLAY_WIDTH;
            for (int col = 0; col < DISPLAY_WIDTH; col++)
                dst[col] = palette_be[src[col]];
        }
        lcd_stream_bytes((const uint8_t *)out, (size_t)lines * DISPLAY_WIDTH * 2);
        which ^= 1;
    }
    lcd_stream_end();
}

int lcd_swap(void)
{
    if (!module_initialized)
        return 0;
    const int rows = gfx_present(&gfx_screen, gfx_screen_hash, full_refresh, send_rows, NULL);
    full_refresh = false;
    return rows;
}

void lcd_psram(uint16_t x, uint16_t y, uint16_t width, uint16_t height, uint32_t addr)
{
    if (x >= DISPLAY_WIDTH || y >= DISPLAY_HEIGHT || width == 0)
        return;
    psram_ready();

    uint32_t row_bytes = (uint32_t)width * 2;
    uint16_t lcd_row_buffer[width];

    for (uint16_t row = 0; row < height; row++)
    {
        uint16_t cur_y = y + row;
        if (cur_y >= DISPLAY_HEIGHT)
            break;
        psram_get(addr + row * row_bytes, (uint8_t *)lcd_row_buffer, (int)row_bytes);
        lcd_blit_16bit(x, cur_y, width, 1, lcd_row_buffer);
    }
}

bool lcd_psram_read_row(uint32_t addr, uint16_t row, uint16_t width, uint16_t *dst)
{
    if (!dst)
        return false;
    psram_ready();
    uint32_t row_bytes = (uint32_t)width * 2;
    psram_get(addr + (uint32_t)row * row_bytes, (uint8_t *)dst, (int)row_bytes);
    return true;
}

psram_qspi_inst_t *picoware_get_psram_instance(void)
{
    return psram_initialized ? &psram_instance : NULL;
}
