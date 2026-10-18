# The device's lcd binding and the shared gfx drawing core, so the simulator
# runs the same drawing code as the firmware.
PICOWARE_MICROPYTHON_DIR := $(USERMOD_DIR)/../../..

SRC_USERMOD += $(USERMOD_DIR)/lcd_mp.c
SRC_USERMOD += $(USERMOD_DIR)/gfx.c
SRC_USERMOD += $(USERMOD_DIR)/gfx_lcd.c
SRC_USERMOD += $(USERMOD_DIR)/gfx_mesh.c
SRC_USERMOD += $(USERMOD_DIR)/gfx_desktop.c

CFLAGS_USERMOD += -I$(PICOWARE_MICROPYTHON_DIR)/font -I$(PICOWARE_MICROPYTHON_DIR)/gfx
