/* Buffered, bounded compressed ZIP input for MicroPython's native DeflateIO.
 * The inflater asks for one byte at a time; keep those calls entirely in C. */
#include "py/runtime.h"
#include "py/stream.h"
#include "py/mperrno.h"
#include <string.h>
typedef struct {
    mp_obj_base_t base;
    mp_obj_t source;
    mp_uint_t left;
    uint16_t at,end;
    uint8_t bytes[1024];
} bounded_reader;
static mp_obj_t bounded_new(const mp_obj_type_t *type,size_t n_args,size_t n_kw,const mp_obj_t *args) {
    mp_arg_check_num(n_args,n_kw,2,2,false);
    mp_get_stream_raise(args[0],MP_STREAM_OP_READ);
    mp_int_t size=mp_obj_get_int(args[1]);
    if (size<0) mp_raise_ValueError(MP_ERROR_TEXT("Negative ZIP input size"));
    bounded_reader *r=mp_obj_malloc(bounded_reader,type);
    r->source=args[0];r->left=size;r->at=r->end=0;
    return MP_OBJ_FROM_PTR(r);
}
static mp_uint_t bounded_read(mp_obj_t self,void *buffer,mp_uint_t count,int *error) {
    bounded_reader *r=MP_OBJ_TO_PTR(self);mp_uint_t total=0;uint8_t *dst=buffer;
    if (r->source==MP_OBJ_NULL) { *error=MP_EBADF;return MP_STREAM_ERROR; }
    while (count) {
        if (r->at==r->end) {
            if (!r->left) break;
            mp_uint_t want=r->left<sizeof(r->bytes) ? r->left : sizeof(r->bytes);
            mp_uint_t n=mp_stream_read_exactly(r->source,r->bytes,want,error);
            if (n==MP_STREAM_ERROR) return n;
            if (n!=want) { *error=MP_EIO;return MP_STREAM_ERROR; }
            r->left-=n;r->at=0;r->end=n;
        }
        mp_uint_t n=r->end-r->at;if (n>count) n=count;
        memcpy(dst,r->bytes+r->at,n);r->at+=n;dst+=n;count-=n;total+=n;
    }
    return total;
}
static mp_uint_t bounded_ioctl(mp_obj_t self,mp_uint_t request,uintptr_t arg,int *error) {
    (void)arg;bounded_reader *r=MP_OBJ_TO_PTR(self);
    if (request==MP_STREAM_CLOSE) { r->source=MP_OBJ_NULL;r->left=0;r->at=r->end=0;return 0; }
    *error=MP_EINVAL;return MP_STREAM_ERROR;
}
static mp_obj_t remaining(mp_obj_t self) {
    bounded_reader *r=MP_OBJ_TO_PTR(self);
    return mp_obj_new_int_from_uint(r->left+r->end-r->at);
}
static MP_DEFINE_CONST_FUN_OBJ_1(remaining_obj,remaining);
static const mp_rom_map_elem_t methods[]={
    {MP_ROM_QSTR(MP_QSTR_readinto),MP_ROM_PTR(&mp_stream_readinto_obj)},
    {MP_ROM_QSTR(MP_QSTR_close),MP_ROM_PTR(&mp_stream_close_obj)},
    {MP_ROM_QSTR(MP_QSTR_remaining),MP_ROM_PTR(&remaining_obj)},
};
static MP_DEFINE_CONST_DICT(locals,methods);
static const mp_stream_p_t protocol={.read=bounded_read,.ioctl=bounded_ioctl};
MP_DEFINE_CONST_OBJ_TYPE(gungos_bounded_reader_type,MP_QSTR_BoundedReader,MP_TYPE_FLAG_NONE,
    make_new,bounded_new,protocol,&protocol,locals_dict,&locals);
