# Keep PNGdec's modified zlib symbols private from other firmware libraries.
add_library(gungos_png_core STATIC
    ${CMAKE_CURRENT_LIST_DIR}/png_core.c
    ${CMAKE_CURRENT_LIST_DIR}/upstream/adler32.c
    ${CMAKE_CURRENT_LIST_DIR}/upstream/crc32.c
    ${CMAKE_CURRENT_LIST_DIR}/upstream/inffast.c
    ${CMAKE_CURRENT_LIST_DIR}/upstream/inflate.c
    ${CMAKE_CURRENT_LIST_DIR}/upstream/inftrees.c
    ${CMAKE_CURRENT_LIST_DIR}/upstream/zutil.c)
target_compile_definitions(gungos_png_core PRIVATE Z_PREFIX)
target_include_directories(gungos_png_core PRIVATE ${CMAKE_CURRENT_LIST_DIR}/upstream)
add_library(usermod_pngdec INTERFACE)
target_sources(usermod_pngdec INTERFACE ${CMAKE_CURRENT_LIST_DIR}/pngdec_mp.c ${CMAKE_CURRENT_LIST_DIR}/bounded_reader.c)
target_link_libraries(usermod_pngdec INTERFACE gungos_png_core)
target_link_libraries(usermod INTERFACE usermod_pngdec)
