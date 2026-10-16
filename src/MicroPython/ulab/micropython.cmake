include(${CMAKE_CURRENT_LIST_DIR}/upstream/code/micropython.cmake)
target_include_directories(usermod_ulab INTERFACE ${CMAKE_CURRENT_LIST_DIR})
target_compile_definitions(usermod_ulab INTERFACE
    ULAB_CONFIG_FILE="picoware_ulab_config.h"
    MICROPY_FLOAT_IMPL=MICROPY_FLOAT_IMPL_FLOAT
)
