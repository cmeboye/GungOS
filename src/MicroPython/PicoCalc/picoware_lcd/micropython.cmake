# Include picoware_lcd module: the panel driver plus the shared gfx drawing core
add_library(usermod_picoware_lcd INTERFACE)

set(GFX_DIR ${CMAKE_CURRENT_LIST_DIR}/../../gfx)

target_sources(usermod_picoware_lcd INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/picoware_lcd.c
    ${CMAKE_CURRENT_LIST_DIR}/lcd.c
    ${GFX_DIR}/gfx.c
    ${GFX_DIR}/gfx_lcd.c
    ${GFX_DIR}/gfx_mesh.c
    ${GFX_DIR}/gfx_plot.c
)

target_include_directories(usermod_picoware_lcd INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
    ${GFX_DIR}
    ${CMAKE_CURRENT_LIST_DIR}/../../font
    ${CMAKE_BINARY_DIR}
)

target_compile_definitions(usermod_picoware_lcd INTERFACE
    MODULE_PICOWARE_LCD_ENABLED=1
)

# The firmware is built for size; drawing and presenting are hot paths.
set_source_files_properties(${GFX_DIR}/gfx.c ${CMAKE_CURRENT_LIST_DIR}/picoware_lcd.c
    PROPERTIES COMPILE_OPTIONS "-O2")
# These reproduce Python's arithmetic exactly: no fused multiply-add.
set_source_files_properties(${GFX_DIR}/gfx_mesh.c ${GFX_DIR}/gfx_plot.c
    PROPERTIES COMPILE_OPTIONS "-O2;-ffp-contract=off")

target_link_libraries(usermod INTERFACE usermod_picoware_lcd)
