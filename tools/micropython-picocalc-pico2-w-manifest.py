import os
include("$(BOARD_DIR)/manifest.py")
source = os.environ["PICOWARE_SOURCE_DIR"] + "/src/MicroPython"
freeze(source, "main.py")
modules = []
for directory, _, names in os.walk(source + "/picoware"):
    for name in names:
        if not name.endswith(".py"):
            continue
        relative = os.path.relpath(os.path.join(directory, name), source).replace(os.sep, "/")
        modules.append(relative)
freeze(source, sorted(modules))
