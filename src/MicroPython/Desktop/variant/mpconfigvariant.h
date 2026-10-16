#pragma once

#define MICROPY_CONFIG_ROM_LEVEL (MICROPY_CONFIG_ROM_LEVEL_EXTRA_FEATURES)

#include "ports/unix/variants/mpconfigvariant_common.h"

/* Match the PicoCalc RP2 firmware's current numerical precision. */
#undef MICROPY_FLOAT_IMPL
#define MICROPY_FLOAT_IMPL (MICROPY_FLOAT_IMPL_FLOAT)

/* Picoware native modules use the embedded-port allocator API. */
#undef MICROPY_MALLOC_USES_ALLOCATED_SIZE
#define MICROPY_MALLOC_USES_ALLOCATED_SIZE (0)
#undef MICROPY_MEM_STATS
#define MICROPY_MEM_STATS (0)
