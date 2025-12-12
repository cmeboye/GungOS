"""
os_core.py – Core loop for PicoCalc OS

- Entry point: main()
- Sets up basic state
- Runs shell loop
- Dispatches to commands.handle_command()
- Falls back to Python eval/exec when a line is not a shell command
- Provides app launcher: /sd/apps/<appname>/app.py
"""

import os
import sys
import time
import gc

import fs_utils  # /sd/lib/fs_utils.py

if '/sd/lib' not in sys.path:
    sys.path.append('/sd/lib')


# --- Platform helpers ---

def _print_exc(exc):
    """MicroPython-friendly exception printer with a safe fallback."""
    try:
        sys.print_exception(exc)
    except Exception:
        try:
            import traceback

            traceback.print_exception(type(exc), exc, exc.__traceback__)
        except Exception:
            print(exc)


def _dir_exists(path):
    try:
        os.listdir(path)
        return True
    except Exception:
        return False


def _detect_sd_root():
    """
    Resolve the SD root.

    Prefer /sd (device), but fall back to the repo's sd/ folder so the shell
    can run on a desktop for testing.
    """
    candidates = ["/sd", "sd"]
    try:
        here = __file__
        base_dir = here.rsplit("/", 1)[0]
        # If running from .../sd/lib/os_core.py, walk up to .../sd
        candidates.insert(1, base_dir.rsplit("/", 1)[0])
    except Exception:
        pass

    for path in candidates:
        if _dir_exists(path):
            return path.rstrip("/") or "/"

    return "/sd"


def _detect_apps_root(sd_root):
    """
    Resolve apps directory.

    Prefer /sd/apps, but fall back to /sd/app if that's what's present.
    """
    candidates = [sd_root + "/apps", sd_root + "/app"]
    for path in candidates:
        if _dir_exists(path):
            return path
    return candidates[0]

# --- OS metadata ---

OS_NAME = "PicoCalcOS"
OS_VERSION = "0.1.1"

# --- Paths ---

SD_ROOT   = _detect_sd_root()
APPS_ROOT = _detect_apps_root(SD_ROOT)
DATA_ROOT = SD_ROOT + "/data"
CONFIG_DIR = SD_ROOT + "/etc"
LOG_DIR   = SD_ROOT + "/logs"
LEGACY_LOG_DIR = DATA_ROOT + "/logs"  # kept for backward compatibility
LOG_FILE  = LOG_DIR + "/os.log"
HIST_FILE = CONFIG_DIR + "/history"
ALIAS_FILE = CONFIG_DIR + "/aliases"
COLOR_FILE = CONFIG_DIR + "/color"
HIST_MAX  = 200

# --- Shared state ---

STATE = {
    "running": True,
    "history": [],
    "aliases": {},
    "history_dirty": 0,
    "color_pref": "",
}

# Python REPL environment for eval/exec fallback
PY_ENV = {"__name__": "__main__", "os": os, "sys": sys, "gc": gc, "time": time}
try:
    import machine  # type: ignore

    PY_ENV["machine"] = machine
except Exception:
    # Not available on desktop
    pass


# --- Helpers ---

def _ensure_dir(path):
    """Create directory if it does not exist. Ignore errors."""
    try:
        os.listdir(path)
    except OSError:
        try:
            os.mkdir(path)
        except OSError:
            pass


def log(msg):
    """Append a log line to /sd/logs/os.log (best-effort)."""
    try:
        _ensure_dir(LOG_DIR)
        _ensure_dir(LEGACY_LOG_DIR)
        ts = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time())
        line = "[{}] {}\n".format(ts, msg)
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except Exception:
        # Logging should never crash anything
        pass


def load_history():
    entries = []
    try:
        with open(HIST_FILE, "r") as f:
            for line in f:
                cleaned = line.rstrip("\n")
                if cleaned:
                    entries.append(cleaned)
    except OSError:
        return entries
    except Exception as e:
        log("load_history error: {}".format(e))
    return entries[-HIST_MAX:]


def flush_history():
    try:
        _ensure_dir(CONFIG_DIR)
        hist = STATE.get("history", [])
        with open(HIST_FILE, "w") as f:
            for item in hist[-HIST_MAX:]:
                f.write(item + "\n")
        STATE["history_dirty"] = 0
    except Exception:
        # Best-effort only
        pass


def add_history(line):
    if not line:
        return
    hist = STATE.get("history", [])
    hist.append(line)
    if len(hist) > HIST_MAX:
        del hist[0 : len(hist) - HIST_MAX]
    STATE["history_dirty"] = STATE.get("history_dirty", 0) + 1
    if STATE["history_dirty"] >= 10:
        flush_history()


def expand_history_shorthand(line):
    """Handle !! and !N history expansions."""
    hist = STATE.get("history", [])
    if line == "!!":
        if hist:
            return hist[-1]
        print("No history yet")
        return ""
    if line.startswith("!") and len(line) > 1 and line[1:].isdigit():
        idx = int(line[1:]) - 1
        if 0 <= idx < len(hist):
            return hist[idx]
        print("No such history entry:", line)
        return ""
    return line


def load_aliases():
    aliases = {}
    try:
        with open(ALIAS_FILE, "r") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" not in stripped:
                    continue
                name, value = stripped.split("=", 1)
                name = name.strip()
                value = value.strip()
                if name:
                    aliases[name] = value
    except OSError:
        return aliases
    except Exception as e:
        log("load_aliases error: {}".format(e))
    return aliases


def save_aliases(aliases):
    try:
        _ensure_dir(CONFIG_DIR)
        with open(ALIAS_FILE, "w") as f:
            for name, value in aliases.items():
                f.write("{}={}\n".format(name, value))
    except Exception:
        log("save_aliases failed")


def apply_aliases(line):
    aliases = STATE.get("aliases", {})
    if not line:
        return line
    parts = line.split()
    if not parts:
        return line
    replacement = aliases.get(parts[0])
    if not replacement:
        return line
    tail = " ".join(parts[1:])
    return replacement + (" " + tail if tail else "")


def load_color_pref():
    try:
        with open(COLOR_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        return ""


def save_color_pref(code):
    try:
        _ensure_dir(CONFIG_DIR)
        with open(COLOR_FILE, "w") as f:
            f.write(code + "\n")
    except Exception:
        log("save_color_pref failed")


def apply_color_pref(code):
    """Emit ANSI code to set the preferred color, if provided."""
    if not code:
        return
    try:
        print("\x1b[" + code + "m", end="")
    except Exception:
        pass


def list_apps():
    """
    Return a list of available app names.

    Convention:
        /sd/apps/<appname>/app.py
    """
    apps = []
    try:
        entries = os.listdir(APPS_ROOT)
    except OSError:
        return apps

    for name in entries:
        app_dir = APPS_ROOT + "/" + name
        app_main = app_dir + "/app.py"
        try:
            os.stat(app_main)
            apps.append(name)
        except OSError:
            continue

    return apps


def list_app_scripts():
    """
    Return a sorted list of (filename, full_path) for .py files in APPS_ROOT.
    """
    scripts = []
    try:
        entries = os.listdir(APPS_ROOT)
    except OSError:
        return scripts

    for name in entries:
        if not name.endswith(".py"):
            continue
        full = APPS_ROOT + "/" + name
        try:
            mode = os.stat(full)[0]
            # Skip directories posing as .py
            if mode & 0x4000:
                continue
        except Exception:
            continue
        scripts.append((name, full))

    scripts.sort(key=lambda pair: pair[0])
    return scripts


def run_app(appname):
    """
    Load and execute an app from /sd/apps/<appname>/app.py.

    The app runs in its own globals dict (__name__ == "__main__").
    """
    app_path = APPS_ROOT + "/" + appname + "/app.py"

    try:
        with open(app_path, "r") as f:
            code = f.read()
    except OSError:
        print("App not found:", appname)
        return

    print("Running app:", appname)
    log("run_app: {}".format(appname))

    globals_dict = {"__name__": "__main__"}

    try:
        exec(code, globals_dict)
    except Exception as e:
        _print_exc(e)
        print("App '{}' crashed.".format(appname))
        log("App '{}' crashed: {}".format(appname, e))


def run_app_script(target):
    """
    Load and execute a single-file app from APPS_ROOT/<name>.py.

    Accepts either a full path or (name, path) tuple.
    """
    if isinstance(target, tuple):
        name, path = target
    else:
        path = target
        name = path.rsplit("/", 1)[-1] if "/" in path else path

    try:
        with open(path, "r") as f:
            code = f.read()
    except OSError:
        print("App script not found:", path)
        return False

    print("Running app script:", name)
    log("run_app_script: {}".format(name))

    globals_dict = {"__name__": "__main__", "__file__": path}

    try:
        exec(code, globals_dict)
    except Exception as e:
        _print_exc(e)
        print("App script '{}' crashed.".format(name))
        log("App script '{}' crashed: {}".format(name, e))
        return False

    return True


def exec_python(line):
    """
    Evaluate/execute a line of Python in the shared PY_ENV.

    Returns (handled_ok: bool, result_or_None).
    """
    try:
        result = eval(line, PY_ENV, PY_ENV)
    except SyntaxError:
        try:
            exec(line, PY_ENV, PY_ENV)
        except Exception as e:
            _print_exc(e)
            return False, None
        else:
            return True, None
    except Exception as e:
        _print_exc(e)
        return False, None
    else:
        return True, result


# --- Core lifecycle ---

def init_system(quiet=False):
    """
    Basic system initialization.

    - Ensure /sd/data and /sd/data/logs exist
    - Print banner
    """
    _ensure_dir(DATA_ROOT)
    _ensure_dir(LOG_DIR)
    _ensure_dir(LEGACY_LOG_DIR)
    _ensure_dir(CONFIG_DIR)

    if not quiet:
        banner = "{} {} – simple shell".format(OS_NAME, OS_VERSION)
        print(banner)
        print("SD root:", SD_ROOT)
        print("Apps dir:", APPS_ROOT)
        print("Type 'help' for commands.")

    # Load persisted state
    STATE["aliases"] = load_aliases()
    STATE["history"] = load_history()
    STATE["history_dirty"] = 0
    STATE["color_pref"] = load_color_pref()
    apply_color_pref(STATE["color_pref"])

    log("OS init complete")


def main_loop():
    """
    Main shell loop.

    1) Try to interpret the line as a shell command.
    2) If unknown command, try to eval/exec it as Python.
    """
    from commands import handle_command  # local import to avoid circulars

    PROMPT = "pc> "

    while STATE.get("running", True):
        try:
            line = input(PROMPT)
        except EOFError:
            break
        except KeyboardInterrupt:
            print("^C")
            continue

        if not line:
            continue

        full_line = line.strip()
        if not full_line:
            continue

        full_line = expand_history_shorthand(full_line)
        if not full_line:
            continue

        full_line = apply_aliases(full_line)
        add_history(full_line)

        parts = full_line.split()
        cmd = parts[0]
        args = parts[1:]

        # 1) Try shell command first
        try:
            handled = handle_command(cmd, args)
        except Exception as e:
            _print_exc(e)
            print("Command '{}' crashed.".format(cmd))
            log("Command '{}' crashed: {}".format(cmd, e))
            handled = True

        if handled:
            continue

        # 2) Try Python eval/exec in shared environment
        ok, result = exec_python(full_line)
        if ok and result is not None:
            print(result)

    flush_history()


def main(quiet=False):
    """Entry point called from boot.py."""
    gc.collect()
    init_system(quiet=quiet)
    main_loop()
    log("OS main loop exited")
