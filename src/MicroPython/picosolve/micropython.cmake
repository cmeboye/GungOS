# picosolve: the built-in solver kernel (see README.md) and its binding.
add_library(usermod_picosolve INTERFACE)

set(PICOSOLVE_DIR ${CMAKE_CURRENT_LIST_DIR})
set(PICOSOLVE_KERNEL
    ${PICOSOLVE_DIR}/core/skyline.c
    ${PICOSOLVE_DIR}/core/order.c
    ${PICOSOLVE_DIR}/core/dense.c
    ${PICOSOLVE_DIR}/core/dofmap.c
    ${PICOSOLVE_DIR}/fe/beam.c
    ${PICOSOLVE_DIR}/fe/model.c
    ${PICOSOLVE_DIR}/geom/mesh.c
    ${PICOSOLVE_DIR}/geom/contour.c
    ${PICOSOLVE_DIR}/expr/formula.c
)

target_sources(usermod_picosolve INTERFACE
    ${PICOSOLVE_KERNEL}
    ${PICOSOLVE_DIR}/mp/picosolve_mp.c
)

target_include_directories(usermod_picosolve INTERFACE ${PICOSOLVE_DIR})

# The firmware is built for size; the solver's loops are the point of it.
set_source_files_properties(${PICOSOLVE_KERNEL} PROPERTIES COMPILE_OPTIONS "-O2")
# The formula evaluator reproduces Python's arithmetic exactly: no fused multiply-add.
set_source_files_properties(${PICOSOLVE_DIR}/expr/formula.c PROPERTIES COMPILE_OPTIONS "-O2;-ffp-contract=off")

target_link_libraries(usermod INTERFACE usermod_picosolve)
