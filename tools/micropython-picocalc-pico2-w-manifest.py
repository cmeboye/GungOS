import os
import runpy
include("$(BOARD_DIR)/manifest.py")
source = os.environ["PICOWARE_SOURCE_DIR"] + "/src/MicroPython"
freeze(source, "main.py")
profile = runpy.run_path(source + "/picoware/system/features.py")
excluded = tuple(name.replace(".", "/") for name in profile["DISABLED_MODULES"])
modules = []
for directory, _, names in os.walk(source + "/picoware"):
    for name in names:
        if not name.endswith(".py"):
            continue
        relative = os.path.relpath(os.path.join(directory, name), source).replace(os.sep, "/")
        module = relative[:-3]
        if not any(module == item or module.startswith(item + "/") for item in excluded):
            modules.append(relative)
freeze(source, sorted(modules))
