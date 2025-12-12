import sys
import os

# Set to True to see verbose boot diagnostics while developing
VERBOSE_BOOT = False


def _print_exc(exc):
    """MicroPython-friendly exception printer with CPython fallback."""
    try:
        sys.print_exception(exc)
    except Exception:
        try:
            import traceback

            traceback.print_exception(type(exc), exc, exc.__traceback__)
        except Exception:
            print(exc)


def _log(msg):
    if VERBOSE_BOOT:
        print(msg)


def _dir_exists(path):
    try:
        os.listdir(path)
        return True
    except Exception:
        return False


def _path_options(rel_path):
    """Return likely absolute/relative paths for a given relative path."""
    rel = rel_path.lstrip("/")
    options = ["/" + rel, rel]
    try:
        base_dir = __file__.rsplit("/", 1)[0]
        options.insert(1, base_dir + "/" + rel)
    except Exception:
        pass
    return options


def _add_first_existing_to_syspath(rel_path):
    """Insert the first existing path option for rel_path into sys.path."""
    for candidate in _path_options(rel_path):
        if _dir_exists(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)
            return candidate
    return None


def _show_boot_logo():
    try:
        import ui_text

        ui_text.print_boot_logo()
    except Exception as e:
        _log("Boot logo unavailable: {}".format(e))


_log("PicoCalc boot: START")

# Make sure SD-based libs are importable (works on device or local clone)
lib_path = _add_first_existing_to_syspath("sd/lib")
modules_path = _add_first_existing_to_syspath("modules")
if lib_path:
    _log("Using lib path: {}".format(lib_path))
if modules_path:
    _log("Using modules path: {}".format(modules_path))

_log("sys.path: {}".format(sys.path))

# Show boot logo (only user-facing output)
_show_boot_logo()

# Start OS core quietly so only the prompt appears after the logo
try:
    import os_core

    os_core.main(quiet=not VERBOSE_BOOT)
except Exception as e:
    print("PicoCalc boot: os_core FAILED")
    _print_exc(e)

_log("PicoCalc boot: END")
