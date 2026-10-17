# v1 drawing reference

`PicoCalc/picoware_lcd/picoware_lcd_v1.c` is the GungOS v1.0 device drawing
code, unchanged. The headers around it are host stubs, so it compiles on the
Mac in its SRAM ("heap") mode. `test_gfx.c` draws the same shapes with both
it and the new core and requires identical pixels, except for the bugs the
new core fixes on purpose (each has its own test).

Do not edit the v1 file; it is the yardstick.
