#pragma once
#include <stdbool.h>
#include "psram_qspi.h"
#define PSRAM_FRAMEBUFFER_ADDR 0x000000
#define PSRAM_ROW_SIZE 320
#define PSRAM_BUFFER_SIZE (320 * 320)
#define PSRAM_CHUNK_SIZE 64
extern bool psram_initialized;
extern psram_qspi_inst_t psram_instance;
