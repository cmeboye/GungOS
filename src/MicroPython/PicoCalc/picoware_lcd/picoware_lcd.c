/*
 * PicoCalc display: where the screen image lives, and getting it to the panel.
 *
 * Drawing itself is the shared gfx core (../../gfx), the same code the desktop
 * simulator runs. This file provides:
 *   - storage for the 8-bit (RGB332) image: external PSRAM by default, or
 *     on-chip SRAM for about 2.5x faster drawing at a cost of 100 KB of RAM
 *     (Settings > Fast Drawing, or apps via ViewManager.request_fast_drawing);
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

// Rows converted and sent per DMA transfer; two buffers alternate. Sending a
// row takes the panel longer than reading and converting one, so two rows
// per buffer keep the DMA busy.
#define LCD_STREAM_LINES 2

static bool module_initialized = false;
static uint8_t lcd_mode = LCD_MODE_PSRAM; // requested, and current once initialized
static bool full_refresh = true;          // panel content unknown: send everything

static uint8_t *sram_pixels = NULL;
static gfx_sram sram_image;
#define IMAGE_SIZE (DISPLAY_WIDTH * DISPLAY_HEIGHT)

// RGB332 -> RGB565 with the bytes swapped, so memory holds the high byte
// first, as the panel expects.
static uint16_t palette_be[256] __attribute__((aligned(4)));
static uint8_t panel_bits = 16;
static uint16_t stream_buffer[2][DISPLAY_WIDTH * LCD_STREAM_LINES] __attribute__((aligned(4)));
static int stream_which;  // buffer being filled
static int stream_lines;  // rows in it so far

// ---------------------------------------------------------------------------
// PSRAM storage
// ---------------------------------------------------------------------------

static uint8_t psram_scratch[DISPLAY_WIDTH] __attribute__((aligned(4)));

// Image bytes per PSRAM transfer. The PIO receives a transfer's length as a
// nibble count in one byte, so a write carries at most 123 bytes ((4 + n) * 2
// <= 255). At the 120 MHz PSRAM clock a 120-byte write holds the chip for about
// 2 us, inside its 8 us refresh limit, and a 320-pixel row takes 3 transfers
// instead of 5. (PSRAM_CHUNK_SIZE stays 64 for the module's other users.)
#define IMAGE_CHUNK 120

// A write's command and data leave in one DMA transfer instead of two:
// [nibbles to write, nibbles to read, quad write, address (3 bytes), data].
static uint8_t psram_tx[6 + IMAGE_CHUNK] __attribute__((aligned(4)));

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

// Send the n data bytes already in psram_tx to addr.
static void psram_send(uint32_t addr, int n)
{
    psram_tx[0] = (uint8_t)((4 + n) * 2);
    psram_tx[1] = 0;
    psram_tx[2] = 0x38u;
    psram_tx[3] = (uint8_t)(addr >> 16);
    psram_tx[4] = (uint8_t)(addr >> 8);
    psram_tx[5] = (uint8_t)addr;
    qspi_write_dma_blocking(&psram_instance, psram_tx, (size_t)(6 + n));
}

static void psram_put(uint32_t addr, const uint8_t *src, int len)
{
    while (len > 0)
    {
        int n = len > IMAGE_CHUNK ? IMAGE_CHUNK : len;
        memcpy(psram_tx + 6, src, (size_t)n);
        psram_send(addr, n);
        addr += (uint32_t)n;
        src += n;
        len -= n;
    }
}

static void psram_get(uint32_t addr, uint8_t *dst, int len)
{
    while (len > 0)
    {
        int n = len > IMAGE_CHUNK ? IMAGE_CHUNK : len;
        psram_qspi_read(&psram_instance, addr, dst, (size_t)n);
        addr += (uint32_t)n;
        dst += n;
        len -= n;
    }
}

static void psram_fill(void *ctx, int y, int x, int len, uint8_t color)
{
    (void)ctx;
    // Every transfer of a fill sends the same bytes: set them once.
    memset(psram_tx + 6, color, (size_t)(len > IMAGE_CHUNK ? IMAGE_CHUNK : len));
    uint32_t addr = image_addr(y, x);
    while (len > 0)
    {
        int n = len > IMAGE_CHUNK ? IMAGE_CHUNK : len;
        psram_send(addr, n);
        addr += (uint32_t)n;
        len -= n;
    }
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
        panel_bits = 16;
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

bool lcd_set_panel_bits(uint8_t bits)
{
    if (bits != 12 && bits != 16)
        return false;
    if (module_initialized)
        lcd_set_pixel_format(bits);
    panel_bits = bits;
    full_refresh = true; // the panel's memory now holds the other format
    return true;
}

void lcd_invalidate(void)
{
    full_refresh = true;
}

// Presenting: each changed row is converted into the buffer being filled; a
// full buffer goes out by DMA while the CPU fills the other one.

static size_t panel_row_bytes(void)
{
    return panel_bits == 12 ? DISPLAY_WIDTH * 3 / 2 : DISPLAY_WIDTH * 2;
}

static void stream_flush(void)
{
    if (stream_lines == 0)
        return;
    lcd_stream_bytes((const uint8_t *)stream_buffer[stream_which], (size_t)stream_lines * panel_row_bytes());
    stream_which ^= 1;
    stream_lines = 0;
}

static void present_begin(void *ctx, int y)
{
    (void)ctx;
    // The run's length is not known yet, so the window reaches the bottom;
    // the panel stops taking pixels when the run ends.
    lcd_stream_begin(0, (uint16_t)y, DISPLAY_WIDTH - 1, DISPLAY_HEIGHT - 1);
    stream_which = 0; // the last run ended with both buffers sent
    stream_lines = 0;
}

// RGB565 -> RGB444 for the experimental 12-bit panel format.
static inline uint16_t rgb444(uint16_t c)
{
    return (uint16_t)(((c >> 12) << 8) | (((c >> 7) & 0x0F) << 4) | ((c >> 1) & 0x0F));
}

static void present_row(void *ctx, int y, const uint8_t *src)
{
    (void)ctx;
    (void)y;
    uint8_t *packed = (uint8_t *)stream_buffer[stream_which] + (size_t)stream_lines * panel_row_bytes();
    if (panel_bits == 12)
    {
        // Two pixels in three bytes: R1G1 B1R2 G2B2.
        uint8_t *dst = packed;
        for (int col = 0; col < DISPLAY_WIDTH; col += 2)
        {
            const uint16_t a = rgb444(gfx_palette[src[col]]), b = rgb444(gfx_palette[src[col + 1]]);
            *dst++ = (uint8_t)(a >> 4);
            *dst++ = (uint8_t)(((a & 0x0F) << 4) | (b >> 8));
            *dst++ = (uint8_t)b;
        }
    }
    else
    {
        uint16_t *dst = (uint16_t *)packed;
        for (int col = 0; col < DISPLAY_WIDTH; col++)
            dst[col] = palette_be[src[col]];
    }
    if (++stream_lines == LCD_STREAM_LINES)
        stream_flush();
}

static void present_end(void *ctx)
{
    (void)ctx;
    stream_flush();
    lcd_stream_end();
}

static const gfx_sink panel_sink = {present_begin, present_row, present_end};

int lcd_swap(void)
{
    if (!module_initialized)
        return 0;
    const int rows = gfx_present(&gfx_screen, gfx_screen_hash, full_refresh, &panel_sink, NULL);
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
