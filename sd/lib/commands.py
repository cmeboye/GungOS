import os
import fs_utils  # /sd/lib/fs_utils.py

try:
    import os_core
    # Current working directory follows detected SD root
    CWD = os_core.SD_ROOT
except Exception:
    # Fallback for standalone use
    CWD = "/sd"


# --- Path helpers ---

def _resolve(path):
    """Resolve a possibly-relative path against CWD, then normalize."""
    global CWD

    if not path:
        return CWD

    # absolute
    if path.startswith("/"):
        return fs_utils.normalize(path)

    # relative
    if CWD.endswith("/"):
        full = CWD + path
    else:
        full = CWD + "/" + path

    return fs_utils.normalize(full)


def _open_in_editor(path):
    """Call MicroPython editor if available."""
    editor = None
    try:
        import builtins  # type: ignore

        editor = getattr(builtins, "edit", None)
    except Exception:
        editor = None

    if editor is None:
        try:
            import picocalc  # type: ignore

            editor = getattr(picocalc, "edit", None)
        except Exception:
            editor = None

    if editor is None:
        print("No editor available on this build.")
        return False

    try:
        editor(path)
        return True
    except Exception as e:
        print("edit error:", e)
        return False


# --- Basic commands ---

def cmd_pwd(args):
    """Print current working directory."""
    print(CWD)


def cmd_cd(args):
    """Change directory: cd [path]."""
    global CWD
    if not args:
        CWD = "/sd"
        return

    target = _resolve(args[0])

    if fs_utils.is_dir(target):
        CWD = target
    else:
        print("Not a directory:", target)


def cmd_ls(args):
    """List directory contents: ls [path]."""
    if args:
        path = _resolve(args[0])
    else:
        path = CWD

    try:
        entries = os.listdir(path)
    except Exception as e:
        print("ls error:", e)
        return

    for name in entries:
        full = path + "/" + name
        if fs_utils.is_dir(full):
            print(name + "/")
        else:
            print(name)


def cmd_tree(args):
    """Show directory tree: tree [path]."""
    if args:
        path = _resolve(args[0])
    else:
        path = CWD

    fs_utils.print_tree(path)


def cmd_cat(args):
    """Print file contents: cat <file>."""
    if not args:
        print("Usage: cat <file>")
        return

    path = _resolve(args[0])

    try:
        with open(path, "r") as f:
            for line in f:
                print(line.rstrip("\n"))
    except Exception as e:
        print("cat error:", e)


# --- File / dir ops ---

def cmd_mkdir(args):
    """Create directory: mkdir <name>."""
    if not args:
        print("Usage: mkdir <dirname>")
        return
    path = _resolve(args[0])
    try:
        os.mkdir(path)
    except Exception as e:
        print("mkdir error:", e)


def cmd_rm(args):
    """Remove file: rm <file> (no directories)."""
    if not args:
        print("Usage: rm <file>")
        return
    path = _resolve(args[0])
    try:
        if fs_utils.is_dir(path):
            print("Refusing to remove directory (no -r yet):", path)
            return
        os.remove(path)
    except Exception as e:
        print("rm error:", e)


def cmd_mv(args):
    """Move/rename: mv <src> <dst>."""
    if len(args) < 2:
        print("Usage: mv <src> <dst>")
        return

    src = _resolve(args[0])
    dst = _resolve(args[1])

    try:
        os.rename(src, dst)
    except Exception as e:
        print("mv error:", e)


def cmd_cp(args):
    """Copy file: cp <src> <dst>."""
    if len(args) < 2:
        print("Usage: cp <src> <dst>")
        return

    src = _resolve(args[0])
    dst = _resolve(args[1])

    try:
        with open(src, "rb") as fsrc:
            data = fsrc.read()
        with open(dst, "wb") as fdst:
            fdst.write(data)
    except Exception as e:
        print("cp error:", e)


def cmd_touch(args):
    """Create empty file or update timestamp: touch <file>."""
    if not args:
        print("Usage: touch <file>")
        return

    path = _resolve(args[0])
    try:
        with open(path, "a"):
            pass
    except Exception as e:
        print("touch error:", e)


# --- System utilities ---

def cmd_clear(args):
    """Clear screen (simple newline spam for now)."""
    for _ in range(30):
        print("")


def cmd_mem(args):
    """Show memory usage."""
    import gc
    gc.collect()
    free = gc.mem_free()
    try:
        alloc = gc.mem_alloc()
        total = free + alloc
        print("Free:", free, "bytes  Used:", alloc, "bytes  Total≈", total)
    except:
        print("Free:", free, "bytes")


def cmd_version(args):
    """Show OS version."""
    try:
        import os_core
        print("OS:", os_core.OS_NAME, os_core.OS_VERSION)
    except:
        print("PicoCalc OS (version unknown)")


def cmd_date(args):
    """Show current date/time."""
    try:
        import time
        print(time.localtime())
    except Exception as e:
        print("date error:", e)


def cmd_history(args):
    """Show recent commands: history [N]."""
    try:
        import os_core
        hist = os_core.STATE.get("history", [])
    except Exception as e:
        print("history error:", e)
        return

    count = 20
    if args and args[0].isdigit():
        count = int(args[0])

    start = max(0, len(hist) - count)
    for idx, entry in enumerate(hist[start:], start + 1):
        print("{} {}".format(idx, entry))


def cmd_alias(args):
    """List or set aliases: alias [name=exp] | alias name value."""
    try:
        import os_core
    except Exception as e:
        print("alias error:", e)
        return

    aliases = os_core.STATE.get("aliases", {})

    if not args:
        for name in sorted(aliases.keys()):
            print("{}={}".format(name, aliases[name]))
        return

    if "=" in args[0]:
        name, value = args[0].split("=", 1)
    elif len(args) >= 2:
        name = args[0]
        value = " ".join(args[1:])
    else:
        print("Usage: alias name=value | alias name value")
        return

    name = name.strip()
    value = value.strip()
    if not name:
        print("alias: empty name")
        return

    aliases[name] = value
    os_core.save_aliases(aliases)
    print("alias set:", name, "=", value)


def cmd_ntp_sync(args):
    """Sync time via net_utils: ntp-sync [host]."""
    host = args[0] if args else "pool.ntp.org"
    try:
        import net_utils
        import os_core
        import time
        ok = net_utils.sync_time(host)
        if ok:
            print("Time synced from", host, time.localtime())
            os_core.log("ntp-sync ok {}".format(host))
        else:
            print("NTP sync failed for", host)
    except Exception as e:
        print("ntp-sync error:", e)


def cmd_logtail(args):
    """Tail a log file: logtail <appname> [N]."""
    if not args:
        print("Usage: logtail <appname> [lines]")
        return

    appname = args[0]
    lines_requested = 20
    if len(args) > 1 and args[1].isdigit():
        lines_requested = int(args[1])

    log_candidates = [
        "/sd/logs/{}.log".format(appname),
        "/sd/data/logs/{}.log".format(appname),
    ]

    content = None
    for path in log_candidates:
        try:
            with open(path, "r") as f:
                content = f.readlines()
            break
        except Exception:
            continue

    if content is None:
        print("Log not found for", appname)
        return

    for line in content[-lines_requested:]:
        print(line.rstrip("\n"))


def cmd_plotdemo(args):
    """Run plotting demo app if installed."""
    try:
        import os_core
        os_core.run_app("plotter")
    except Exception as e:
        print("plotdemo error:", e)


def cmd_color(args):
    """Set text color (persistent): color red|amber|yellow|reset."""
    if not args:
        print("Usage: color red|amber|yellow|reset")
        return

    choice = args[0].lower()
    mapping = {
        "red": "31",
        "amber": "33",
        "yellow": "33",
        "reset": "",
        "default": "",
    }
    code = mapping.get(choice)
    if code is None:
        print("Unknown color:", choice)
        return

    try:
        import os_core
        os_core.apply_color_pref("0")  # ensure previous styles cleared
        os_core.apply_color_pref(code)
        os_core.STATE["color_pref"] = code
        os_core.save_color_pref(code)
        print("\nColor set to", choice)
    except Exception as e:
        print("color error:", e)


def cmd_py(args):
    """Run a Python snippet in the shared MicroPython environment: py <code>."""
    if not args:
        print("Usage: py <python code>")
        return

    code = " ".join(args)
    try:
        import os_core

        ok, result = os_core.exec_python(code)
        if ok and result is not None:
            print(result)
    except Exception as e:
        print("py error:", e)


# --- Apps & scripts ---

def cmd_apps(args):
    """List available app scripts with index numbers."""
    try:
        import os_core
        scripts = os_core.list_app_scripts()
        legacy_dirs = os_core.list_apps()
    except Exception as e:
        print("Error listing apps:", e)
        return

    if scripts:
        for idx, (name, _) in enumerate(scripts, 1):
            print("{:<20} [{}]".format(name, idx))
        return

    if legacy_dirs:
        for name in legacy_dirs:
            print(name + "/")
        return

    print("No apps found in", os_core.APPS_ROOT)


def cmd_app(args):
    """Run an app script by index or name: app <index>|<name.py>."""
    if not args:
        print("Usage: app <index>|<name.py>")
        return

    try:
        import os_core
        scripts = os_core.list_app_scripts()
    except Exception as e:
        print("app error:", e)
        return

    if not scripts:
        print("No app scripts found in", os_core.APPS_ROOT)
        return

    target = args[0]
    name = None
    path = None

    if target.isdigit():
        idx = int(target) - 1
        if idx < 0 or idx >= len(scripts):
            print("Invalid app index:", target)
            return
        name, path = scripts[idx]
    else:
        desired = target if target.endswith(".py") else target + ".py"
        for n, p in scripts:
            if n == desired:
                name, path = n, p
                break
        if path is None:
            print("App not found:", desired)
            return

    os_core.run_app_script((name, path))


def cmd_edit(args):
    """Edit a file or an app by index: edit <file>|edit app <index>."""
    if not args:
        print("Usage: edit <file>|edit app <index>")
        return

    # edit app <index>
    if args[0] == "app":
        if len(args) < 2:
            print("Usage: edit app <index>")
            return
        target = args[1]
        try:
            import os_core
            scripts = os_core.list_app_scripts()
        except Exception as e:
            print("edit error:", e)
            return

        if not scripts:
            print("No app scripts found in", os_core.APPS_ROOT)
            return

        if target.isdigit():
            idx = int(target) - 1
            if idx < 0 or idx >= len(scripts):
                print("Invalid app index:", target)
                return
            _, path = scripts[idx]
        else:
            desired = target if target.endswith(".py") else target + ".py"
            path = None
            for n, p in scripts:
                if n == desired:
                    path = p
                    break
            if path is None:
                print("App not found:", desired)
                return

        _open_in_editor(path)
        return

    # edit <file>
    path = _resolve(args[0])
    _open_in_editor(path)


def cmd_run(args):
    """
    Run something.

    - If argument ends with '.py' → treat as script in CWD (or relative path),
      read its contents and exec().
    - Otherwise → treat as app name in /sd/apps/<name>/app.py.
    """
    if not args:
        print("Usage: run <script.py>|<appname>")
        return

    target = args[0]

    # Script mode
    if target.endswith(".py"):
        path = _resolve(target)
        try:
            with open(path, "r") as f:
                code = f.read()
        except Exception as e:
            print("run: cannot open script:", e)
            return

        print("Running script:", path)
        g = {"__name__": "__main__"}
        try:
            exec(code, g)
        except Exception as e:
            import sys
            sys.print_exception(e)
        return

    # App mode
    appname = target
    try:
        import os_core
        os_core.run_app(appname)
    except Exception as e:
        print("run (app) error:", e)


def cmd_exit(args):
    """Exit the OS main loop."""
    try:
        import os_core
        os_core.STATE["running"] = False
    except Exception:
        raise SystemExit


def cmd_help(args):
    """Show available commands."""
    print("Available commands:")
    for name in sorted(COMMANDS.keys()):
        print(" ", name)


# --- Command table & dispatcher ---

COMMANDS = {
    "pwd":     cmd_pwd,
    "cd":      cmd_cd,
    "ls":      cmd_ls,
    "tree":    cmd_tree,
    "cat":     cmd_cat,

    "mkdir":   cmd_mkdir,
    "rm":      cmd_rm,
    "mv":      cmd_mv,
    "cp":      cmd_cp,
    "touch":   cmd_touch,

    "clear":   cmd_clear,
    "mem":     cmd_mem,
    "version": cmd_version,
    "date":    cmd_date,
    "history": cmd_history,
    "alias":   cmd_alias,
    "ntp-sync": cmd_ntp_sync,
    "logtail": cmd_logtail,
    "plotdemo": cmd_plotdemo,
    "color":   cmd_color,
    "py":      cmd_py,

    "apps":    cmd_apps,
    "app":     cmd_app,
    "edit":    cmd_edit,
    "run":     cmd_run,
    "exit":    cmd_exit,
    "help":    cmd_help,
}


def handle_command(cmd, args):
    """
    Dispatch a command.

    Returns:
        True  if the command name is known and was called.
        False if command is unknown.
    """
    fn = COMMANDS.get(cmd)
    if fn is None:
        return False

    fn(args)
    return True
