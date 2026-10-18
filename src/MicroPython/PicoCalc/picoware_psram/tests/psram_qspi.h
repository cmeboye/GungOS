#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
typedef int PIO;
#define pio0 0
#define pio1 1
#define __force_inline inline
typedef struct { int active; } psram_qspi_inst_t;
psram_qspi_inst_t psram_qspi_init(PIO pio, int sm, float clkdiv);
void psram_qspi_deinit(psram_qspi_inst_t *q);
int psram_qspi_test(psram_qspi_inst_t *q);
void psram_qspi_write(psram_qspi_inst_t *q,uint32_t addr,const uint8_t *src,size_t count);
void psram_qspi_read(psram_qspi_inst_t *q,uint32_t addr,uint8_t *dst,size_t count);
void psram_qspi_write8(psram_qspi_inst_t *q,uint32_t addr,uint8_t value);
uint8_t psram_qspi_read8(psram_qspi_inst_t *q,uint32_t addr);
void psram_qspi_write16(psram_qspi_inst_t *q,uint32_t addr,uint16_t value);
uint16_t psram_qspi_read16(psram_qspi_inst_t *q,uint32_t addr);
void psram_qspi_write32(psram_qspi_inst_t *q,uint32_t addr,uint32_t value);
uint32_t psram_qspi_read32(psram_qspi_inst_t *q,uint32_t addr);
