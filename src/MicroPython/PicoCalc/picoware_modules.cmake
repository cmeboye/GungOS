# Native support for the custom PicoCalc Python/engineering build.
add_compile_definitions(PICOCALC)
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
