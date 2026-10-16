add_library(usermod_pcm INTERFACE)
target_sources(usermod_pcm INTERFACE ${CMAKE_CURRENT_LIST_DIR}/pcm.c)
target_link_libraries(usermod_pcm INTERFACE hardware_dma hardware_pwm hardware_irq)
target_link_libraries(usermod INTERFACE usermod_pcm)
