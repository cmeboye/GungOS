/* Host stub: the v1 reference only runs in SRAM mode, so PSRAM is inert. */
#pragma once
#include <stdint.h>
#include <stddef.h>
typedef struct { int unused; } psram_qspi_inst_t;
static inline void psram_qspi_write8(psram_qspi_inst_t *q, uint32_t a, uint8_t v) { (void)q, (void)a, (void)v; }
static inline void psram_qspi_write(psram_qspi_inst_t *q, uint32_t a, const uint8_t *s, size_t n) { (void)q, (void)a, (void)s, (void)n; }
static inline void psram_qspi_read(psram_qspi_inst_t *q, uint32_t a, uint8_t *d, size_t n) { (void)q, (void)a, (void)d, (void)n; }
static inline psram_qspi_inst_t psram_qspi_init(int pio, int sm, float div) { (void)pio, (void)sm, (void)div; psram_qspi_inst_t q = {0}; return q; }
static inline void psram_qspi_deinit(psram_qspi_inst_t *q) { (void)q; }
#define pio1 0
