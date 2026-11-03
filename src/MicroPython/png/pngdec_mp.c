#include "py/runtime.h"
#include "py/stream.h"
#include "../gfx/gfx_lcd.h"
#include "png_core.h"

extern const mp_obj_type_t gungos_bounded_reader_type;

typedef struct { int x,y,w,h;gungos_png_info *info; } png_destination;
static int png_read(void *input, uint8_t *dst, int count) {
    int error=0;
    mp_uint_t n=mp_stream_read_exactly(MP_OBJ_FROM_PTR(input),dst,count,&error);
    if (n==MP_STREAM_ERROR) mp_raise_OSError(error);
    return n;
}
static int png_row(void *destination, int y, int width, const uint8_t *pixels) {
    png_destination *d=destination;
    picocalc_lcd_blit(d->x+(d->w-d->info->width)/2,d->y+(d->h-d->info->height)/2+y,width,1,pixels);
    /* Keep keyboard/background hooks serviced on long images. */
    mp_event_handle_nowait();
    return 1;
}
static mp_obj_t png_draw(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    mp_get_stream_raise(args[0],MP_STREAM_OP_READ);
    mp_int_t size=mp_obj_get_int(args[1]);
    png_destination dst={.x=mp_obj_get_int(args[2]),.y=mp_obj_get_int(args[3])};
    int w=mp_obj_get_int(args[4]),h=mp_obj_get_int(args[5]);
    gungos_png_info info;dst.w=w;dst.h=h;dst.info=&info;
    uint32_t bg=mp_obj_get_int(args[6]);
    if (size<0 || size>GUNGOS_PNG_INPUT_LIMIT || dst.x<0 || dst.y<0 ||
        w<1 || h<1 || w>320 || h>320 || dst.x>320-w || dst.y>320-h)
        mp_raise_ValueError(MP_ERROR_TEXT("Invalid PNG size or viewport"));
    size_t bytes=gungos_png_workspace_size();
    uint8_t *work=m_new(uint8_t,bytes);
    nlr_buf_t nlr;
    if (nlr_push(&nlr)==0) {
        const char *error=gungos_png_decode(work,png_read,MP_OBJ_TO_PTR(args[0]),size,
            w,h,bg,png_row,&dst,&info);
        nlr_pop();m_del(uint8_t,work,bytes);
        if (error) mp_raise_msg_varg(&mp_type_ValueError,MP_ERROR_TEXT("%s"),error);
    } else { m_del(uint8_t,work,bytes);nlr_jump(nlr.ret_val); }
    mp_obj_t result[4]={mp_obj_new_int(info.source_width),mp_obj_new_int(info.source_height),
        mp_obj_new_int(info.width),mp_obj_new_int(info.height)};
    return mp_obj_new_tuple(4,result);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(png_draw_obj,7,7,png_draw);
static int zip_write(void *output,const uint8_t *data,int count) {
    int error=0;
    mp_uint_t n=mp_stream_write_exactly(MP_OBJ_FROM_PTR(output),data,count,&error);
    if (n==MP_STREAM_ERROR) mp_raise_OSError(error);
    mp_event_handle_nowait();
    return n==(unsigned)count;
}
static mp_obj_t zip_inflate(size_t n_args,const mp_obj_t *args) {
    (void)n_args;
    mp_get_stream_raise(args[0],MP_STREAM_OP_READ);
    mp_get_stream_raise(args[1],MP_STREAM_OP_WRITE);
    mp_int_t compressed=mp_obj_get_int(args[2]),plain=mp_obj_get_int(args[3]);
    uint32_t crc=mp_obj_get_int_truncated(args[4]);
    if (compressed<0 || plain<0 || compressed>GUNGOS_PNG_INPUT_LIMIT || plain>GUNGOS_PNG_INPUT_LIMIT)
        mp_raise_ValueError(MP_ERROR_TEXT("EPUB image exceeds 4 MiB"));
    size_t bytes=gungos_png_workspace_size();uint8_t *work=m_new(uint8_t,bytes);
    nlr_buf_t nlr;
    if (nlr_push(&nlr)==0) {
        const char *error=gungos_zip_inflate(work,png_read,MP_OBJ_TO_PTR(args[0]),compressed,plain,crc,
            zip_write,MP_OBJ_TO_PTR(args[1]));
        nlr_pop();m_del(uint8_t,work,bytes);
        if (error) mp_raise_msg_varg(&mp_type_ValueError,MP_ERROR_TEXT("%s"),error);
    } else { m_del(uint8_t,work,bytes);nlr_jump(nlr.ret_val); }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(zip_inflate_obj,5,5,zip_inflate);
static mp_obj_t png_workspace(void) { return mp_obj_new_int(gungos_png_workspace_size()); }
static MP_DEFINE_CONST_FUN_OBJ_0(png_workspace_obj,png_workspace);
static const mp_rom_map_elem_t png_globals_table[]={
    {MP_ROM_QSTR(MP_QSTR___name__),MP_ROM_QSTR(MP_QSTR_pngdec)},
    {MP_ROM_QSTR(MP_QSTR_inflate_zip),MP_ROM_PTR(&zip_inflate_obj)},
    {MP_ROM_QSTR(MP_QSTR_BoundedReader),MP_ROM_PTR(&gungos_bounded_reader_type)},
    {MP_ROM_QSTR(MP_QSTR_draw),MP_ROM_PTR(&png_draw_obj)},
    {MP_ROM_QSTR(MP_QSTR_workspace_size),MP_ROM_PTR(&png_workspace_obj)},
};
static MP_DEFINE_CONST_DICT(png_globals,png_globals_table);
const mp_obj_module_t pngdec_module={.base={&mp_type_module},.globals=(mp_obj_dict_t *)&png_globals};
MP_REGISTER_MODULE(MP_QSTR_pngdec,pngdec_module);
