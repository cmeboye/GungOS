#include "gfx_desktop.h"

#include "py/nlr.h"
#include "py/objarray.h"
#include "py/runtime.h"

#define WIDTH 320
#define HEIGHT 320

static uint8_t pixels[WIDTH * HEIGHT];
static gfx_sram image = {pixels, WIDTH};
static uint16_t frame[WIDTH * HEIGHT]; /* what the simulated panel shows */
static bool ready = false;
static bool full_refresh = true;
static uint8_t mode = 1; /* the simulator always draws in SRAM */

/* sim_runtime, or MP_OBJ_NULL when running outside the simulator. */
static mp_obj_t runtime(void)
{
    nlr_buf_t nlr;
    if (nlr_push(&nlr) != 0)
        return MP_OBJ_NULL;
    mp_obj_t module = mp_import_name(MP_QSTR_sim_runtime, mp_const_none, MP_OBJ_NEW_SMALL_INT(0));
    nlr_pop();
    return module;
}

/* Exceptions from the runtime (quitting the simulator) propagate. */
static void notify(qstr name, size_t count, const mp_obj_t *args)
{
    mp_obj_t module = runtime();
    if (module == MP_OBJ_NULL)
        return;
    mp_obj_t function = mp_load_attr(module, name);
    mp_call_function_n_kw(function, count, 0, args);
}

void desktop_lcd_init(void)
{
    if (!ready)
    {
        gfx_init_palette();
        gfx_surface_init(&gfx_screen, WIDTH, HEIGHT, &gfx_sram_storage, &image);
        ready = true;
    }
    full_refresh = true;
}

void desktop_lcd_deinit(void)
{
}

void desktop_lcd_register(mp_obj_t lcd)
{
    notify(MP_QSTR_set_lcd, 1, &lcd);
}

static void send_rows(void *ctx, int y, int rows)
{
    (void)ctx;
    for (int row = y; row < y + rows; row++)
        for (int x = 0; x < WIDTH; x++)
            frame[row * WIDTH + x] = gfx_palette[pixels[row * WIDTH + x]];
}

int desktop_lcd_swap(void)
{
    if (!ready)
        return 0;
    const int rows = gfx_present(&gfx_screen, gfx_screen_hash, full_refresh, send_rows, NULL);
    full_refresh = false;
    mp_obj_t args[2] = {mp_obj_new_bytearray_by_ref(sizeof(frame), frame), mp_obj_new_int(rows)};
    notify(MP_QSTR_lcd_present, 2, args);
    return rows;
}

void desktop_lcd_set_brightness(uint8_t brightness)
{
    mp_obj_t arg = mp_obj_new_int(brightness);
    notify(MP_QSTR_lcd_set_brightness, 1, &arg);
}

void desktop_lcd_set_rgb_led(uint8_t red, uint8_t green, uint8_t blue)
{
    mp_obj_t args[3] = {mp_obj_new_int(red), mp_obj_new_int(green), mp_obj_new_int(blue)};
    notify(MP_QSTR_lcd_set_rgb_led, 3, args);
}

void desktop_lcd_set_mode(uint8_t requested)
{
    if (requested <= 1)
        mode = requested;
}

uint8_t desktop_lcd_get_mode(void)
{
    return mode;
}
