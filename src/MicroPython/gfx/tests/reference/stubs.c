/* Globals the v1 driver expects from the PSRAM module. */
#include <stdbool.h>
#include "PicoCalc/picoware_psram/psram_qspi.h"
bool psram_initialized = false;
psram_qspi_inst_t psram_instance;
