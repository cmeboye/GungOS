# Native support for the custom PicoCalc Python/engineering build.
add_compile_definitions(PICOCALC)
# A new str is not first matched against every interned name loaded from SD
# apps (a linear scan that cost ~55 us per string); see py/objstr.c.
add_compile_definitions(MICROPY_STR_REUSE_QSTR=0)
# Look names up in the firmware's sorted lists before scanning the names
# loaded from SD apps one by one; see py/qstr.c.
add_compile_definitions(MICROPY_QSTR_FIND_SORTED_FIRST=1)
list(APPEND MICROPY_DEF_BOARD PICOCALC)

include(${CMAKE_CURRENT_LIST_DIR}/picoware_keyboard/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/picoware_lcd/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/picoware_psram/micropython.cmake)

include(${CMAKE_CURRENT_LIST_DIR}/../font/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../jpeg/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../lcd/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../log/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../response/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../sd/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../textbox/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../uf2loader/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../vector/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../vt/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../ulab/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../pcm/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../picosolve/micropython.cmake)

# GCC 15 diagnoses the unreachable byte tail of Mbed TLS's fixed 16-byte XOR
# as one-past-end in AES/GCM. Keep the diagnostic visible for these upstream
# translation units; do not relax -Werror for firmware or other dependencies.
if(CMAKE_C_COMPILER_ID STREQUAL "GNU" AND CMAKE_C_COMPILER_VERSION VERSION_GREATER_EQUAL "15")
    foreach(source aes.c gcm.c)
        set_property(SOURCE ${MICROPY_DIR}/lib/mbedtls/library/${source}
            APPEND PROPERTY COMPILE_OPTIONS -Wno-error=array-bounds)
    endforeach()
endif()

# GUNGOS_FLASH_MAX_HZ caps the flash clock. MicroPython derives the cap from
# the 150 MHz default clock (75 MHz), so at 240 MHz it divides by 4 and the
# flash runs at 60 MHz; 120000000 gives divisor 2 (120 MHz, chip rated 133).
# The release build uses 120 MHz (tested on hardware 2026-10-20, build C).
if(GUNGOS_FLASH_MAX_HZ)
    add_compile_definitions(MICROPY_HW_FLASH_MAX_FREQ=${GUNGOS_FLASH_MAX_HZ})
endif()

# GUNGOS_FAST_PY=ON compiles the MicroPython core (py/: the interpreter, GC,
# objects) at -O2 instead of the size-optimised -Os; the rest stays -Os.
if(GUNGOS_FAST_PY)
    file(GLOB GUNGOS_PY_SOURCES ${MICROPY_DIR}/py/*.c)
    set_property(SOURCE ${GUNGOS_PY_SOURCES} APPEND PROPERTY COMPILE_OPTIONS -O2)
endif()
