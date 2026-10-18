#include "psram_qspi.h"
#include <string.h>
#include <assert.h>
static uint8_t memory[8*1024*1024];
psram_qspi_inst_t psram_qspi_init(PIO pio,int sm,float clkdiv){(void)pio;(void)sm;(void)clkdiv;return (psram_qspi_inst_t){1};}
void psram_qspi_deinit(psram_qspi_inst_t *q){q->active=0;}
int psram_qspi_test(psram_qspi_inst_t *q){return q->active?0:-1;}
void psram_qspi_write(psram_qspi_inst_t *q,uint32_t a,const uint8_t *s,size_t n){assert(q->active && a+n<=sizeof(memory));memcpy(memory+a,s,n);}
void psram_qspi_read(psram_qspi_inst_t *q,uint32_t a,uint8_t *d,size_t n){assert(q->active && a+n<=sizeof(memory));memcpy(d,memory+a,n);}
void psram_qspi_write8(psram_qspi_inst_t *q,uint32_t a,uint8_t v){psram_qspi_write(q,a,(const uint8_t *)&v,sizeof(v));}
uint8_t psram_qspi_read8(psram_qspi_inst_t *q,uint32_t a){uint8_t v;psram_qspi_read(q,a,(uint8_t *)&v,sizeof(v));return v;}
void psram_qspi_write16(psram_qspi_inst_t *q,uint32_t a,uint16_t v){psram_qspi_write(q,a,(const uint8_t *)&v,sizeof(v));}
uint16_t psram_qspi_read16(psram_qspi_inst_t *q,uint32_t a){uint16_t v;psram_qspi_read(q,a,(uint8_t *)&v,sizeof(v));return v;}
void psram_qspi_write32(psram_qspi_inst_t *q,uint32_t a,uint32_t v){psram_qspi_write(q,a,(const uint8_t *)&v,sizeof(v));}
uint32_t psram_qspi_read32(psram_qspi_inst_t *q,uint32_t a){uint32_t v;psram_qspi_read(q,a,(uint8_t *)&v,sizeof(v));return v;}
