/* Small mono PCM output and mixer for GungOS; GPL-3.0, Cem Gungor. */
#include "py/runtime.h"
#include "py/mphal.h"
#include <stdint.h>
#include <string.h>
#ifndef DESKTOP
#include "hardware/dma.h"
#include "hardware/pwm.h"
#include "hardware/irq.h"
#include "hardware/clocks.h"
#include "hardware/sync.h"
#include "hardware/structs/pwm.h"
#include "pico/stdlib.h"
#endif

#define CAPACITY 4096u
#define BLOCK 128u
typedef struct {
    mp_obj_base_t base;
    int16_t *ring;
    volatile uint32_t read,write;
    uint32_t rate;
#ifdef DESKTOP
    mp_uint_t last_us;
    uint32_t fraction;
#else
    int channel,timer;
    uint slice;
    uint32_t active;
    uint32_t output[BLOCK];
#endif
} pcm_obj_t;
static pcm_obj_t *owner=NULL;

#ifdef DESKTOP
static void advance(pcm_obj_t *self) {
    mp_uint_t now=mp_hal_ticks_us();
    uint64_t amount=(uint64_t)(now-self->last_us)*self->rate+self->fraction;
    self->last_us=now; self->fraction=amount%1000000u;
    uint32_t count=self->write-self->read;
    uint64_t frames=amount/1000000u;
    self->read+=frames<count?(uint32_t)frames:count;
}
#else
static void schedule(pcm_obj_t *self) {
    uint32_t count=self->write-self->read;
    if (count>BLOCK) count=BLOCK;
    __dmb();
    for (uint32_t i=0;i<BLOCK;i++) {
        int32_t value=i<count?self->ring[(self->read+i)&(CAPACITY-1)]:0;
        uint32_t duty=(uint32_t)((value+32768)>>6);
        self->output[i]=duty|(duty<<16);
    }
    self->read+=count;
    self->active=count;
    dma_channel_set_read_addr(self->channel,self->output,false);
    dma_channel_set_trans_count(self->channel,BLOCK,true);
}
static void irq(void) {
    pcm_obj_t *self=owner;
    if (self && (dma_hw->ints0&(1u<<self->channel))) {
        dma_hw->ints0=1u<<self->channel;
        if (self->ring) schedule(self);
    }
}
static uint32_t pending(pcm_obj_t *self) {
    uint32_t left=dma_hw->ch[self->channel].transfer_count;
    uint32_t consumed=BLOCK-left;
    return self->active>consumed?self->active-consumed:0;
}
#endif

static mp_obj_t stop(mp_obj_t obj) {
    pcm_obj_t *self=MP_OBJ_TO_PTR(obj);
    if (!self->ring) return mp_const_none;
#ifndef DESKTOP
    if (owner==self && self->channel>=0) {
        uint32_t state=save_and_disable_interrupts();
        dma_channel_set_irq0_enabled(self->channel,false);
        dma_channel_abort(self->channel);
        dma_hw->ints0=1u<<self->channel;
        irq_remove_handler(DMA_IRQ_0,irq);
        pwm_set_enabled(self->slice,false);
        gpio_set_function(26,GPIO_FUNC_SIO); gpio_set_dir(26,GPIO_OUT); gpio_put(26,0);
        gpio_set_function(27,GPIO_FUNC_SIO); gpio_set_dir(27,GPIO_OUT); gpio_put(27,0);
        owner=NULL;
        restore_interrupts(state);
        dma_channel_unclaim(self->channel);
        dma_timer_unclaim(self->timer);
    }
#endif
    if (owner==self) owner=NULL;
    m_free(self->ring); self->ring=NULL;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(stop_obj,stop);

static mp_obj_t make_new(const mp_obj_type_t *type,size_t n_args,size_t n_kw,const mp_obj_t *args) {
    mp_arg_check_num(n_args,n_kw,1,1,false);
    int rate=mp_obj_get_int(args[0]);
    if (rate<8000 || rate>48000) mp_raise_ValueError(MP_ERROR_TEXT("PCM rate: 8000..48000"));
    if (owner) mp_raise_msg(&mp_type_RuntimeError,MP_ERROR_TEXT("PCM output is already in use"));
    pcm_obj_t *self=mp_obj_malloc_with_finaliser(pcm_obj_t,type);
    self->ring=NULL; self->read=self->write=0; self->rate=rate;
#ifndef DESKTOP
    self->channel=self->timer=-1; self->active=0;
#endif
    self->ring=m_new(int16_t,CAPACITY);
#ifdef DESKTOP
    self->last_us=mp_hal_ticks_us(); self->fraction=0;
#else
    self->channel=dma_claim_unused_channel(false);
    if (self->channel<0) {m_free(self->ring); self->ring=NULL; mp_raise_msg(&mp_type_RuntimeError,MP_ERROR_TEXT("No DMA channel for PCM"));}
    self->timer=dma_claim_unused_timer(false);
    if (self->timer<0) {dma_channel_unclaim(self->channel);m_free(self->ring);self->ring=NULL;mp_raise_msg(&mp_type_RuntimeError,MP_ERROR_TEXT("No DMA timer for PCM"));}
    uint32_t clock=clock_get_hz(clk_sys);
    uint32_t best_error=UINT32_MAX; uint16_t numerator=1,denominator=1;
    uint32_t limit=(uint64_t)65535u*rate/clock;
    if (!limit) limit=1;
    for (uint32_t n=1;n<=limit;n++) {
        uint32_t d=((uint64_t)clock*n+rate/2)/rate;
        if (!d || d>65535) continue;
        uint32_t actual=(uint64_t)clock*n/d;
        uint32_t error=actual>rate?actual-rate:rate-actual;
        if (error<best_error) {best_error=error;numerator=n;denominator=d;}
    }
    dma_timer_set_fraction(self->timer,numerator,denominator);
    self->slice=pwm_gpio_to_slice_num(26);
    gpio_set_function(26,GPIO_FUNC_PWM);gpio_set_function(27,GPIO_FUNC_PWM);
    pwm_config cfg=pwm_get_default_config();pwm_config_set_wrap(&cfg,1023);pwm_config_set_clkdiv(&cfg,1);
    pwm_init(self->slice,&cfg,true);pwm_set_both_levels(self->slice,512,512);
    dma_channel_config dma=dma_channel_get_default_config(self->channel);
    channel_config_set_transfer_data_size(&dma,DMA_SIZE_32);
    channel_config_set_read_increment(&dma,true);channel_config_set_write_increment(&dma,false);
    channel_config_set_dreq(&dma,dma_get_timer_dreq(self->timer));
    dma_channel_configure(self->channel,&dma,&pwm_hw->slice[self->slice].cc,self->output,BLOCK,false);
    irq_add_shared_handler(DMA_IRQ_0,irq,PICO_SHARED_IRQ_HANDLER_DEFAULT_ORDER_PRIORITY);
    dma_channel_set_irq0_enabled(self->channel,true);irq_set_enabled(DMA_IRQ_0,true);
#endif
    owner=self;
#ifndef DESKTOP
    schedule(self);
#endif
    return MP_OBJ_FROM_PTR(self);
}

static mp_obj_t queued(mp_obj_t obj) {
    pcm_obj_t *self=MP_OBJ_TO_PTR(obj);
    if (!self->ring) return MP_OBJ_NEW_SMALL_INT(0);
#ifdef DESKTOP
    advance(self);
    return mp_obj_new_int_from_uint(self->write-self->read);
#else
    uint32_t state=save_and_disable_interrupts();
    uint32_t count=self->write-self->read+pending(self);
    restore_interrupts(state);
    return mp_obj_new_int_from_uint(count);
#endif
}
static MP_DEFINE_CONST_FUN_OBJ_1(queued_obj,queued);
static mp_obj_t clear(mp_obj_t obj) {
    pcm_obj_t *self=MP_OBJ_TO_PTR(obj);
    if (!self->ring) return mp_const_none;
#ifdef DESKTOP
    self->read=self->write;self->last_us=mp_hal_ticks_us();self->fraction=0;
#else
    uint32_t state=save_and_disable_interrupts();
    self->read=self->write;
    restore_interrupts(state);
#endif
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(clear_obj,clear);
static mp_obj_t write_pcm(mp_obj_t obj,mp_obj_t data) {
    pcm_obj_t *self=MP_OBJ_TO_PTR(obj);
    if (!self->ring) mp_raise_msg(&mp_type_RuntimeError,MP_ERROR_TEXT("PCM output is stopped"));
    mp_buffer_info_t b;mp_get_buffer_raise(data,&b,MP_BUFFER_READ);
    if (b.len&1) mp_raise_ValueError(MP_ERROR_TEXT("PCM needs whole 16-bit samples"));
#ifdef DESKTOP
    advance(self);
#endif
    uint32_t available=CAPACITY-(self->write-self->read),count=b.len/2;
    if (count>available) count=available;
    uint8_t *bytes=b.buf;
    for (uint32_t i=0;i<count;i++) self->ring[(self->write+i)&(CAPACITY-1)]=(int16_t)((uint16_t)bytes[i*2]|((uint16_t)bytes[i*2+1]<<8));
#ifndef DESKTOP
    __dmb();
#endif
    self->write+=count;
    return mp_obj_new_int_from_uint(count);
}
static MP_DEFINE_CONST_FUN_OBJ_2(write_obj,write_pcm);

static int sample(const uint8_t *data,size_t index) {return data?(int16_t)((uint16_t)data[index*2]|((uint16_t)data[index*2+1]<<8)):0;}
static mp_obj_t mix_into(size_t n_args,const mp_obj_t *args) {
    (void)n_args;
    mp_buffer_info_t out,inputs[3];mp_get_buffer_raise(args[0],&out,MP_BUFFER_WRITE);
    if ((out.len&1) || out.len>4096) mp_raise_ValueError(MP_ERROR_TEXT("Mix block: up to 2048 whole samples"));
    for (int i=0;i<3;i++) {
        inputs[i].buf=NULL;
        if (args[i+1]!=mp_const_none) {
            mp_get_buffer_raise(args[i+1],&inputs[i],MP_BUFFER_READ);
            if (inputs[i].len<out.len) mp_raise_ValueError(MP_ERROR_TEXT("Mix input is too short"));
        }
    }
    int volume=mp_obj_get_int(args[4]),music_gain=mp_obj_get_int(args[5]);
    if (volume<0 || volume>100 || music_gain<0 || music_gain>100) mp_raise_ValueError(MP_ERROR_TEXT("Gain: 0..100"));
    uint8_t *dest=out.buf;
    for (size_t i=0;i<out.len/2;i++) {
        int32_t value=sample(inputs[0].buf,i)*music_gain+(sample(inputs[1].buf,i)+sample(inputs[2].buf,i))*64;
        value=value*volume/10000;
        if (value>32767)value=32767;else if(value< -32768)value=-32768;
        dest[i*2]=(uint8_t)value;dest[i*2+1]=(uint8_t)(value>>8);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(mix_obj,6,6,mix_into);
static const mp_rom_map_elem_t locals_table[]={
    {MP_ROM_QSTR(MP_QSTR_write),MP_ROM_PTR(&write_obj)},
    {MP_ROM_QSTR(MP_QSTR_queued),MP_ROM_PTR(&queued_obj)},
    {MP_ROM_QSTR(MP_QSTR_clear),MP_ROM_PTR(&clear_obj)},
    {MP_ROM_QSTR(MP_QSTR_stop),MP_ROM_PTR(&stop_obj)},
    {MP_ROM_QSTR(MP_QSTR___del__),MP_ROM_PTR(&stop_obj)}};
static MP_DEFINE_CONST_DICT(locals_dict,locals_table);
MP_DEFINE_CONST_OBJ_TYPE(pcm_type,MP_QSTR_Player,MP_TYPE_FLAG_NONE,make_new,make_new,locals_dict,&locals_dict);
static const mp_rom_map_elem_t globals_table[]={
    {MP_ROM_QSTR(MP_QSTR___name__),MP_ROM_QSTR(MP_QSTR_picoware_pcm)},
    {MP_ROM_QSTR(MP_QSTR_Player),MP_ROM_PTR(&pcm_type)},
    {MP_ROM_QSTR(MP_QSTR_mix_into),MP_ROM_PTR(&mix_obj)},
    {MP_ROM_QSTR(MP_QSTR_CAPACITY),MP_ROM_INT(CAPACITY)}};
static MP_DEFINE_CONST_DICT(globals_dict,globals_table);
const mp_obj_module_t pcm_module={.base={&mp_type_module},.globals=(mp_obj_dict_t*)&globals_dict};
MP_REGISTER_MODULE(MP_QSTR_picoware_pcm,pcm_module);
