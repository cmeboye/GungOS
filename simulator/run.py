"""MicroPython-only Picoware simulator entrypoint."""

import builtins
import gc
import os
import sys


def _dirname(path):
    """Return the directory portion of a path."""
    path = path.replace("\\", "/")
    if "/" not in path:
        return "."
    value = path.rsplit("/", 1)[0]
    return value if value else "/"


def _abspath(path):
    """Return an absolute path, resolving relative to cwd."""
    if path.startswith("/"):
        return path
    return os.getcwd() + "/" + path


THIS_DIR = _dirname(_abspath(sys.argv[0]))
ROOT = _dirname(THIS_DIR)
HARDWARE_DIR = THIS_DIR + "/hardware"
MICROPYTHON_DIR = ROOT + "/src/MicroPython"

# GungOS targets one board: the PicoCalc with a Raspberry Pi Pico 2 W.
SUPPORTED_BOARD = "picocalc-pico2w"
DISPLAY_SIZE = (320, 320)


def _insert_path(path):
    """Insert a directory into sys.path if not present."""
    if path not in sys.path:
        sys.path.insert(0, path)


def _simulator_display_size(board_name):
    """Return the PicoCalc framebuffer size."""
    return DISPLAY_SIZE


def _parse_args(argv):
    """Parse command-line arguments into an options dict."""
    opts = {
        "headless": True,
        "viewer": False,
        "frames": 0,
        "exit_after_frames": 0,
        "scale": 2,
        "sd": THIS_DIR + "/sdcard",
        "apps_source": ROOT + "/builds/MicroPython/apps_unfrozen",
        "board": "picocalc-pico2w",
        "keys": "",
        "keys_text": "",
        "open": "",
        "app": "",
        "game": "",
        "screenshot": "",
        "trace_keys": False,
        "trace_views": False,
        "trace_imports": False,
        "network": "real",
        "bluetooth": "virtual",
        "audio": "real",
        "speed": "auto",
        "fps": 0,
        "capabilities": False,
        "coverage": "",
        "script": "",
        "wait_view": "",
        "assert_text": "",
        "sim_check": False,
        "keep_interpreter": False,
        "reset_sd": False,
        "sd_profile": "dev",
        "record": "",
    }
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--headless":
            opts["headless"] = True
        elif arg == "--viewer":
            opts["viewer"] = True
            opts["headless"] = True
        elif arg == "--sdl":
            opts["headless"] = False
        elif arg == "--frames" and i + 1 < len(argv):
            i += 1
            opts["frames"] = int(argv[i])
        elif arg == "--exit-after-frames" and i + 1 < len(argv):
            i += 1
            opts["exit_after_frames"] = int(argv[i])
        elif arg == "--scale" and i + 1 < len(argv):
            i += 1
            opts["scale"] = int(argv[i])
        elif arg == "--sd" and i + 1 < len(argv):
            i += 1
            opts["sd"] = _abspath(argv[i])
        elif arg == "--apps-source" and i + 1 < len(argv):
            i += 1
            opts["apps_source"] = _abspath(argv[i])
        elif arg == "--board" and i + 1 < len(argv):
            i += 1
            if argv[i].lower().replace("_", "-") != SUPPORTED_BOARD:
                raise SystemExit("unsupported board: " + argv[i] + " (only " + SUPPORTED_BOARD + ")")
            opts["board"] = SUPPORTED_BOARD
        elif arg == "--keys" and i + 1 < len(argv):
            i += 1
            opts["keys"] = argv[i]
        elif arg == "--keys-text" and i + 1 < len(argv):
            i += 1
            opts["keys_text"] = argv[i]
        elif arg == "--open" and i + 1 < len(argv):
            i += 1
            opts["open"] = argv[i]
        elif arg == "--app" and i + 1 < len(argv):
            i += 1
            opts["app"] = argv[i]
        elif arg == "--game" and i + 1 < len(argv):
            i += 1
            opts["game"] = argv[i]
        elif arg == "--screenshot" and i + 1 < len(argv):
            i += 1
            opts["screenshot"] = argv[i]
        elif arg == "--trace-keys":
            opts["trace_keys"] = True
        elif arg == "--trace-views":
            opts["trace_views"] = True
        elif arg == "--trace-imports":
            opts["trace_imports"] = True
        elif arg == "--network" and i + 1 < len(argv):
            i += 1
            opts["network"] = argv[i]
        elif arg == "--bluetooth" and i + 1 < len(argv):
            i += 1
            opts["bluetooth"] = argv[i]
        elif arg == "--audio" and i + 1 < len(argv):
            i += 1
            opts["audio"] = argv[i]
        elif arg == "--speed" and i + 1 < len(argv):
            i += 1
            opts["speed"] = argv[i]
        elif arg == "--fps" and i + 1 < len(argv):
            i += 1
            opts["fps"] = int(argv[i])
        elif arg == "--capabilities":
            opts["capabilities"] = True
        elif arg == "--coverage" and i + 1 < len(argv):
            i += 1
            opts["coverage"] = argv[i]
        elif arg == "--script" and i + 1 < len(argv):
            i += 1
            opts["script"] = _abspath(argv[i])
        elif arg == "--wait-view" and i + 1 < len(argv):
            i += 1
            opts["wait_view"] = argv[i]
        elif arg == "--assert-text" and i + 1 < len(argv):
            i += 1
            opts["assert_text"] = argv[i]
        elif arg == "--sim-check":
            opts["sim_check"] = True
        elif arg == "--keep-interpreter":
            opts["keep_interpreter"] = True
        elif arg == "--reset-sd":
            opts["reset_sd"] = True
        elif arg == "--sd-profile" and i + 1 < len(argv):
            i += 1
            opts["sd_profile"] = argv[i]
        elif arg == "--record" and i + 1 < len(argv):
            i += 1
            opts["record"] = _abspath(argv[i])
        elif arg == "--help":
            print("usage: micropython simulator/run.py [--viewer] [--sdl] [--headless] [--frames N] [--exit-after-frames N] [--speed auto|real|pico2w|fast|unlimited] [--fps N] [--network real|offline] [--bluetooth virtual|off] [--audio real|silent] [--keys a,b] [--keys-text TEXT] [--record FILE] [--open NAME] [--app NAME] [--game NAME] [--apps-source PATH] [--reset-sd] [--sd-profile clean|dev|media|network-fixtures] [--screenshot PATH] [--coverage apps|games|all] [--script FILE] [--wait-view NAME] [--assert-text TEXT] [--capabilities] [--sim-check] [--keep-interpreter]")
            raise SystemExit
        else:
            print("Unknown argument:", arg)
            raise SystemExit
        i += 1
    return opts


def _mkdir_p(path):
    """Create a directory tree, ignoring existing directories."""
    parts = path.replace("\\", "/").split("/")
    current = "/" if path.startswith("/") else ""
    for part in parts:
        if not part:
            continue
        current = current + ("" if current.endswith("/") or not current else "/") + part
        try:
            os.mkdir(current)
        except OSError:
            pass


def _remove_tree(path):
    """Recursively delete a directory tree."""
    try:
        names = os.listdir(path)
    except OSError:
        try:
            os.remove(path)
        except OSError:
            pass
        return
    for name in names:
        child = path.rstrip("/") + "/" + name
        try:
            mode = os.stat(child)[0]
        except OSError:
            # os.stat() fails for a broken symlink.  Remove the link node so
            # --reset-sd can actually clear persistent simulator fixtures.
            try:
                os.remove(child)
            except OSError:
                pass
            continue
        if mode & 0x4000:
            _remove_tree(child)
        else:
            try:
                os.remove(child)
            except OSError:
                pass
    try:
        os.rmdir(path)
    except OSError:
        pass


def _safe_reset_sd(path):
    """Reset the SD card path, with safety guards."""
    target = _abspath(path)
    sim_default = THIS_DIR + "/sdcard"
    allowed = target == sim_default or target.startswith("/tmp/")
    if not allowed:
        print("--reset-sd refused unsafe path:", target)
        print("Use the default simulator/sdcard or a path under /tmp for destructive reset.")
        raise SystemExit(2)
    if target in ("", "/", "/tmp", THIS_DIR, ROOT):
        print("--reset-sd refused root-like path:", target)
        raise SystemExit(2)
    _remove_tree(target)
    _mkdir_p(target)


def _run_main():
    """Execute the Picoware main.py entry point."""
    fatal_errors = []

    def main_print(*args, **kwargs):
        separator = kwargs.get("sep", " ")
        message = separator.join(str(arg) for arg in args)
        if message.startswith("Error occurred:"):
            fatal_errors.append(message)
        builtins.print(*args, **kwargs)

    namespace = {
        "__name__": "__sim_picoware_main__",
        "__file__": MICROPYTHON_DIR + "/main.py",
        "print": main_print,
    }
    with open(MICROPYTHON_DIR + "/main.py", "r") as handle:
        code = handle.read()
    exec(code, namespace)
    try:
        result = namespace["main"]()
    except BaseException:
        if fatal_errors:
            raise RuntimeError(
                "Picoware main reported a fatal error: " + fatal_errors[-1]
            )
        raise
    if result is False:
        raise RuntimeError("Picoware main reported a fatal error")
    if fatal_errors:
        raise RuntimeError(
            "Picoware main reported a fatal error: " + fatal_errors[-1]
        )


def _install_view_tracking():
    """Report ViewManager transitions to the simulator harness."""
    try:
        import sim_runtime
        from picoware.system.input import Input
        from picoware.system.view_manager import ViewManager
    except Exception:
        return
    if getattr(ViewManager, "_sim_view_tracking_installed", False):
        return

    def current_name(manager):
        view = getattr(manager, "_current_view", None)
        return getattr(view, "name", "")

    def note(manager):
        try:
            name = current_name(manager)
            if name != getattr(sim_runtime, "_current_view_name", ""):
                sim_runtime.note_view(name)
        except Exception:
            pass

    def note_name(name):
        try:
            if str(name or "") != getattr(sim_runtime, "_current_view_name", ""):
                sim_runtime.note_view(name)
        except Exception:
            pass

    original_set = ViewManager.set
    original_switch_to = ViewManager.switch_to
    original_back = ViewManager.back
    original_remove = ViewManager.remove

    def tracked_set(self, *args, **kwargs):
        if args:
            note_name(args[0])
        result = original_set(self, *args, **kwargs)
        note(self)
        return result

    def tracked_switch_to(self, *args, **kwargs):
        if args:
            note_name(args[0])
        result = original_switch_to(self, *args, **kwargs)
        note(self)
        return result

    def tracked_back(self, *args, **kwargs):
        result = original_back(self, *args, **kwargs)
        note(self)
        return result

    def tracked_remove(self, *args, **kwargs):
        result = original_remove(self, *args, **kwargs)
        note(self)
        return result

    def tracked_input_button(self):
        sim_runtime.input_polled()
        return self._last_button

    ViewManager.set = tracked_set
    ViewManager.switch_to = tracked_switch_to
    ViewManager.back = tracked_back
    ViewManager.remove = tracked_remove
    Input.button = property(tracked_input_button)
    ViewManager._sim_view_tracking_installed = True


def _quote(path):
    """Shell-quote a path string."""
    return "'" + path.replace("'", "'\"'\"'") + "'"


def _interpreter_command():
    """Return the current MicroPython executable for child simulator runs."""
    executable = getattr(sys, "executable", "")
    return _quote(executable if executable else "micropython")


def _bootstrap_runtime(opts):
    """Make direct launches use the built native interpreter and a usable heap."""
    if opts["keep_interpreter"]:
        return
    executable = getattr(sys, "executable", "micropython")
    selected = executable
    if not _module_available("picoware_desktop", "native_modules"):
        build_dir = os.getenv("PICOWARE_DESKTOP_BUILD_DIR") or ROOT + "/builds/MicroPython/desktop"
        candidate = build_dir + "/micropython"
        try:
            if os.stat(candidate)[0] & 0o111:
                selected = candidate
        except OSError:
            pass
    heap = gc.mem_alloc() + gc.mem_free()
    if selected == executable and heap >= 8 * 1024 * 1024:
        return
    heap = max(heap, 16 * 1024 * 1024)
    if selected != executable:
        print("[sim] Using the built Picoware C++ interpreter")
    else:
        print("[sim] Restarting with a 16 MiB heap for simulator apps")
    sys.stdout.flush()
    command = _quote(selected) + " -X heapsize=" + str(heap)
    command += " " + " ".join(_quote(str(arg)) for arg in sys.argv)
    status = os.system(command)
    raise SystemExit((status >> 8) if (status & 255) == 0 else 128 + (status & 127))


def _module_available(name, attribute=""):
    """Return whether the selected interpreter supplies an optional module."""
    try:
        module = __import__(name)
        return not attribute or hasattr(module, attribute)
    except ImportError:
        return False


def _board_option(opts):
    """Return the selected simulator board as a quoted child-process option."""
    return " --board " + _quote(opts["board"])


def _file_exists(path):
    """Return True if the given path exists."""
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _is_newer(path, other):
    """Return True if path was modified after other."""
    try:
        return os.stat(path)[8] > os.stat(other)[8]
    except Exception:
        return True


def _json_escape(text):
    """Escape a string for inclusion in JSON."""
    text = str(text)
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "\\r")
    text = text.replace("\t", "\\t")
    return text


def _list_py_entries(path):
    """Return sorted list of .py module names in a directory."""
    try:
        files = os.listdir(path)
    except OSError:
        return []
    out = []
    for item in files:
        if item.startswith(".") or item == "__init__.py":
            continue
        if item.endswith(".py"):
            out.append(item[:-3])
    out.sort()
    return out


def _write_coverage_report(path, mode, rows):
    """Write a JSON coverage report to disk."""
    _mkdir_p(_dirname(path))
    passed = 0
    failed = 0
    skipped = 0
    with open(path, "w") as handle:
        handle.write('{"mode":"' + _json_escape(mode) + '","results":[')
        first = True
        for row in rows:
            status = row[2]
            if status == "pass":
                passed += 1
            elif status == "fail":
                failed += 1
            else:
                skipped += 1
            if not first:
                handle.write(",")
            first = False
            handle.write(
                '{"kind":"'
                + _json_escape(row[0])
                + '","name":"'
                + _json_escape(row[1])
                + '","status":"'
                + _json_escape(row[2])
                + '","reason":"'
                + _json_escape(row[3])
                + '","log":"'
                + _json_escape(row[4])
                + '"}'
            )
        handle.write('],"summary":{"pass":%d,"fail":%d,"skipped":%d}}' % (passed, failed, skipped))
    print("coverage", mode, "pass", passed, "fail", failed, "skipped", skipped)
    print("report", path)


def _run_coverage(opts):
    """Run headless coverage sweep over apps and games."""
    mode = opts["coverage"].lower()
    if mode not in ("apps", "games", "all"):
        print("--coverage expects apps, games, or all")
        raise SystemExit
    report_dir = opts["sd"] + "/sim_reports"
    _mkdir_p(report_dir)
    rows = []
    entries = []
    if mode in ("apps", "all"):
        for name in _list_py_entries(opts["apps_source"]):
            entries.append(("app", name))
    if mode in ("games", "all"):
        if _board_supports_ghouls(opts["board"]):
            entries.append(("game", "Ghouls"))
        for name in _list_py_entries(opts["apps_source"] + "/games"):
            entries.append(("game", name))
    if not entries:
        rows.append(("coverage", mode, "skipped", "no entries found", ""))
    for kind, name in entries:
        safe = (kind + "-" + name).replace("/", "_").replace(" ", "_")
        log_path = report_dir + "/" + safe + ".log"
        cmd = (
            _interpreter_command()
            + " "
            + _quote(THIS_DIR + "/run.py")
            + " --headless --frames 220 --audio silent --network offline --sd "
            + _quote(opts["sd"])
            + " --apps-source "
            + _quote(opts["apps_source"])
            + _board_option(opts)
            + (" --app " if kind == "app" else " --game ")
            + _quote(name)
            + " --wait-view "
            + _quote(("app_" if kind == "app" else "game_") + name)
            + " >"
            + _quote(log_path)
            + " 2>&1"
        )
        status = os.system(cmd)
        if status == 0:
            rows.append((kind, name, "pass", "", log_path))
            print("[coverage:pass]", kind, name)
        else:
            rows.append((kind, name, "fail", "child run exited " + str(status), log_path))
            print("[coverage:fail]", kind, name, status)
    _write_coverage_report(report_dir + "/coverage-" + mode + ".json", mode, rows)
    if any(row[2] == "fail" for row in rows):
        raise SystemExit(1)


def _build_native(target, check=False):
    """Build a native simulator helper via build.sh."""
    cmd = "sh " + _quote(THIS_DIR + "/build.sh")
    if check:
        cmd += " --check"
    cmd += " " + _quote(target)
    return os.system(cmd) == 0


def _run_sim_check(opts):
    """Run the simulator self-check suite."""
    _run_selected_profile_check(opts)
    _run_library_route_check()
    _run_stale_app_link_check(opts)
    _run_duplicate_app_link_check(opts)
    _run_ir_parity_check()
    _run_uart_parity_check()
    _run_keyboard_background_check()
    _run_lcd_parity_check()
    _run_font_parity_check()
    _run_log_storage_check(opts)
    _run_audio_shutdown_check()
    _run_fatal_exit_check(opts)
    print("[sim-check:pass]")


def _run_selected_profile_check(opts):
    """Check the retained firmware without expecting excluded native modules."""
    tests = (
        "test_dashboard.py",
        "test_statistics.py",
        "test_calculator.py",
        "test_calculator_modes.py",
        "test_release_demos.py",
        "test_tetris_audio.py",
        "test_ulab.py",
        "test_trimmed_firmware.py", "test_menu.py", "test_home_visual.py",
        "test_preferences.py", "test_wifi_setup.py",
        "test_connectivity.py", "test_connectivity_ui.py", "test_service_independence.py",
        "test_shared_plots.py", "test_graph.py", "test_graph3d.py",
        "test_graph3d_implicit.py", "test_choice_dialogs.py", "test_error_reporting.py", "test_secrets.py",
    )
    for name in tests:
        command = _interpreter_command() + " -X heapsize=16M " + _quote(THIS_DIR + "/" + name)
        status = os.system(command)
        if status:
            raise RuntimeError("Selected firmware regression failed: " + name)
    print("[sim-check:pass] Python/engineering firmware")


def _run_ir_parity_check():
    """Exercise the simulator's real IR timer waveform and PicoCalc pins."""
    import sim_runtime
    from picoware.system.infrared import (
        InfraredTransmitter,
        Signal,
        _default_rx_pin,
        _default_tx_pin,
    )

    tx_pin = _default_tx_pin()
    if getattr(tx_pin, "id", None) != 28:
        raise RuntimeError("simulator PicoCalc IR TX pin mismatch")
    signal = Signal(
        {
            "name": "simulator",
            "type": "raw",
            "frequency": "38000",
            "duty_cycle": "0.33",
            "data": "9000 4500 560 560",
        }
    )
    sim_runtime.clear_ir_waveform()
    InfraredTransmitter(tx_pin).send(signal)
    waveform = sim_runtime.get_ir_waveform()
    if len(waveform) < 4:
        raise RuntimeError("simulator IR waveform is incomplete")
    first = waveform[0]
    if (
        first["duration_us"] != 9000
        or not first["mark"]
        or first["frequency"] != 38000
    ):
        raise RuntimeError("simulator IR waveform does not match raw signal")
    try:
        _default_rx_pin()
    except ValueError:
        pass
    else:
        raise RuntimeError("PicoCalc must not report an infrared receiver")
    print("[sim-check:ok] infrared timer waveform and PicoCalc pins")


def _run_library_route_check():
    """Keep simulator --open routes synchronized with the Library menu."""
    import sim_runtime

    from picoware.applications import library
    sim_runtime.sync_menu_routes()
    for index, category in enumerate(library.CATEGORIES):
        if sim_runtime.LIBRARY_ITEMS.get(category.lower()) != index:
            raise RuntimeError("Simulator sidebar route mismatch: " + category)
        routes = sim_runtime._MENU_ITEMS[category.lower()]
        for item_index, label in enumerate(library.SECTIONS[index]):
            if routes.get(label.lower()) != item_index:
                raise RuntimeError("Simulator submenu route mismatch: " + label)
    for index, label in enumerate(library.SCRIPT_ITEMS):
        if sim_runtime.SCRIPT_ITEMS.get(label.lower()) != index:
            raise RuntimeError("Simulator script route mismatch: " + label)
    print("[sim-check:ok] Two-panel menu routes synchronized")


def _run_stale_app_link_check(opts):
    """Verify persistent SD cleanup removes only broken managed links."""
    import sim_runtime

    probe = opts["sd"] + "/sim-stale-link-check"
    broken = probe + "/RemovedApp.py"
    local = probe + "/LocalApp.py"
    _mkdir_p(probe)
    with open(local, "w") as handle:
        handle.write("# user-installed simulator app\n")
    status = os.system(
        "ln -sf "
        + _quote(ROOT + "/builds/MicroPython/apps_unfrozen/RemovedApp.py")
        + " "
        + _quote(broken)
    )
    if status != 0 or "RemovedApp.py" not in os.listdir(probe):
        _remove_tree(probe)
        raise RuntimeError("simulator stale-link fixture setup failed")
    sim_runtime._prune_stale_links(probe)
    entries = os.listdir(probe)
    if "RemovedApp.py" in entries:
        _remove_tree(probe)
        raise RuntimeError("simulator stale app link was not removed")
    if "LocalApp.py" not in entries:
        _remove_tree(probe)
        raise RuntimeError("simulator stale-link cleanup removed a local app")
    _remove_tree(probe)
    print("[sim-check:ok] stale app links pruned, local apps preserved")


def _run_duplicate_app_link_check(opts):
    """Remove managed .mpy duplicates while preserving regular SD files."""
    import sd_mp
    import sim_runtime

    probe = opts["sd"] + "/sim-duplicate-link-check"
    source_py = probe + "/source-py"
    source_mpy = probe + "/source-mpy"
    destination = probe + "/apps"
    _mkdir_p(source_py)
    _mkdir_p(source_mpy)
    _mkdir_p(destination)
    with open(source_py + "/ManagedApp.py", "w") as handle:
        handle.write("# managed source app\n")
    with open(source_py + "/CaseApp.py", "w") as handle:
        handle.write("# canonical case app\n")
    with open(source_py + "/caseApp.py", "w") as handle:
        handle.write("# duplicate case app\n")
    with open(source_mpy + "/ManagedApp.mpy", "w") as handle:
        handle.write("managed compiled app\n")
    with open(source_mpy + "/LocalApp.mpy", "w") as handle:
        handle.write("compiled source placeholder\n")
    with open(destination + "/LocalApp.py", "w") as handle:
        handle.write("# local source app\n")
    with open(destination + "/LocalApp.mpy", "w") as handle:
        handle.write("local compiled app\n")

    # A case-insensitive host filesystem (default macOS APFS) cannot hold both
    # spellings, so only the FAT directory-view half of this check applies.
    case_sensitive_host = sorted(
        name for name in os.listdir(source_py) if name.lower() == "caseapp.py"
    ) == ["CaseApp.py", "caseApp.py"]
    if case_sensitive_host:
        status = os.system(
            "ln -sf "
            + _quote(source_py + "/caseApp.py")
            + " "
            + _quote(destination + "/caseApp.py")
        )
        if status != 0:
            _remove_tree(probe)
            raise RuntimeError("simulator case-duplicate fixture setup failed")
    sim_runtime._link_app_files_into(source_py, destination)
    if case_sensitive_host:
        case_entries = [name for name in os.listdir(destination)
                        if name.lower() == "caseapp.py"]
        if case_entries != ["CaseApp.py"]:
            _remove_tree(probe)
            raise RuntimeError("simulator case-insensitive app duplicate was not removed")
    merged_names = []
    seen_names = {}
    sd_mp._append_unique_names(
        merged_names, seen_names, ["caseApp.py", "CaseApp.py"]
    )
    if merged_names != ["CaseApp.py"]:
        _remove_tree(probe)
        raise RuntimeError("simulator FAT directory view exposed case duplicates")
    status = os.system(
        "ln -sf "
        + _quote(source_mpy + "/ManagedApp.mpy")
        + " "
        + _quote(destination + "/ManagedApp.mpy")
    )
    if status != 0:
        _remove_tree(probe)
        raise RuntimeError("simulator duplicate-link fixture setup failed")
    sim_runtime._link_app_files_into(
        source_mpy, destination, skip_if_py_exists=True
    )
    entries = os.listdir(destination)
    if "ManagedApp.mpy" in entries:
        _remove_tree(probe)
        raise RuntimeError("simulator managed .mpy duplicate was not removed")
    try:
        with open(destination + "/LocalApp.mpy", "r") as handle:
            local_contents = handle.read()
    except OSError:
        local_contents = ""
    if local_contents != "local compiled app\n":
        _remove_tree(probe)
        raise RuntimeError("simulator duplicate cleanup removed a local .mpy app")
    _remove_tree(probe)
    print("[sim-check:ok] duplicate managed apps pruned, local .mpy preserved")


def _run_keyboard_background_check():
    """Exercise the PicoCalc background-poll callback contract."""
    import picoware_keyboard
    import sim_runtime

    received = []

    def on_key(_):
        received.append(picoware_keyboard.get_key_nonblocking())

    sim_runtime._keys = []
    picoware_keyboard.init()
    picoware_keyboard.set_key_available_callback(on_key)
    picoware_keyboard.set_background_poll(True)
    sim_runtime.push_key(ord("a"))
    sim_runtime.push_key(ord("b"))
    sim_runtime.input_polled()
    if received != [ord("a")]:
        raise RuntimeError("simulator background keyboard dispatched wrong first key")
    sim_runtime.input_polled()
    if received != [ord("a"), ord("b")]:
        raise RuntimeError("simulator background keyboard did not dispatch queued keys")

    picoware_keyboard.set_background_poll(False)
    sim_runtime.push_key(ord("c"))
    sim_runtime.input_polled()
    if received != [ord("a"), ord("b")]:
        raise RuntimeError("simulator background keyboard ignored disabled state")
    if sim_runtime.pop_key() != ord("c"):
        raise RuntimeError("simulator disabled background keyboard consumed a key")
    picoware_keyboard.deinit()
    print("[sim-check:ok] picocalc background keyboard callbacks")


def _run_lcd_parity_check():
    """Verify LCD APIs added by the current Picoware runtime."""
    import lcd

    display = lcd.LCD()
    display.set_brightness(37)
    if display._brightness != 37:
        raise RuntimeError("simulator LCD brightness state mismatch")
    display.set_rgb_led(17, 34, 51)
    if display._rgb_led != (17, 34, 51):
        raise RuntimeError("simulator LCD RGB LED state mismatch")

    display._clear(0)
    display._bytearray(0, 0, 2, 1, bytearray((0x00, 0xFF)), True)
    if display._get_pixel(0, 0) != 0xFFFF or display._get_pixel(1, 0) != 0x0000:
        raise RuntimeError("simulator LCD bytearray inversion mismatch")

    display._clear(0x001F)
    display._fill_triangle_alpha(1, 1, 5, 1, 1, 5, 0xF800, 128)
    blended = display._get_pixel(2, 2)
    if blended in (0x001F, 0xF800):
        raise RuntimeError("simulator LCD alpha triangle mismatch")

    display._clear(0)
    display._polygon(((1, 1), (5, 1), (5, 5), (1, 5)), 0xFFFF)
    if display._get_pixel(1, 1) != 0xFFFF or display._get_pixel(3, 3) != 0:
        raise RuntimeError("simulator LCD polygon outline mismatch")
    display._fill_polygon(((1, 1), (5, 1), (5, 5), (1, 5)), 0x07E0)
    if display._get_pixel(3, 3) != 0x07E0:
        raise RuntimeError("simulator LCD polygon fill mismatch")
    _run_polygon_parity_check(display)
    print("[sim-check:ok] lcd brightness RGB LED bytearray inversion alpha triangle polygon")


def _run_polygon_parity_check(display):
    square = ((1, 1), (9, 1), (9, 9), (1, 9))
    concave = ((1, 1), (9, 1), (9, 9), (7, 9), (7, 3), (3, 3), (3, 9), (1, 9))
    for points in (concave, tuple(reversed(concave))):
        display._clear(0)
        display._fill_polygon(points, 0xFFFF)
        for y in range(1, 9):
            for x in range(1, 10):
                expected = 0xFFFF if y < 3 or x <= 3 or x >= 7 else 0
                if display._get_pixel(x, y) != expected:
                    raise RuntimeError("simulator concave polygon coverage mismatch")

    # Every covered pixel must be blended once, including the former fan seam.
    for alpha, expected in ((0, 0), (128, 0x7BEF), (255, 0xFFFF)):
        display._clear(0)
        display._fill_polygon_alpha(square, 0xFFFF, alpha)
        for y in range(1, 9):
            for x in range(1, 10):
                if display._get_pixel(x, y) != expected:
                    raise RuntimeError("simulator polygon alpha coverage mismatch")
        if display._get_pixel(5, 9) != 0:
            raise RuntimeError("simulator polygon bottom edge must be excluded")

    display._clear(0)
    display._fill_polygon(((display.width - 2, 1), (display.width + 5, 1),
                           (display.width + 5, 4), (display.width - 2, 4)), 0xFFFF)
    if display._get_pixel(display.width - 1, 2) != 0xFFFF or display._get_pixel(0, 2):
        raise RuntimeError("simulator polygon clipping mismatch")

    display._clear(0)
    for points in ((), ((2, 2),), ((2, 2), (5, 5))):
        display._fill_polygon(points, 0xFFFF)
    display._polygon(((2, 2),), 0xFFFF)
    if any(display._buffer):
        raise RuntimeError("simulator degenerate polygon mismatch")

    try:
        for scale_position in (False, True):
            display.set_scaling(2, 2, scale_position)
            # Firmware applies mean scale in both modes, plus position scale.
            corner = 8 if scale_position else 4
            points = ((2, 2), (5, 2), (5, 5), (2, 5))
            for method in (display._polygon, display._fill_polygon):
                display._clear(0)
                method(points, 0xFFFF)
                if display._get_pixel(corner, corner) != 0xFFFF or display._get_pixel(2, 2):
                    raise RuntimeError("simulator polygon scaling mismatch")
    finally:
        display.set_scaling(1, 1, False)


def _run_uart_parity_check():
    """Verify the PicoCalc default UART pins."""
    from picoware.system.uart import UART

    port = UART()
    try:
        if (port._uart_id, port.tx_pin, port.rx_pin) != (0, 0, 1):
            raise RuntimeError("simulator PicoCalc UART defaults mismatch")
    finally:
        del port
        gc.collect()
    print("[sim-check:ok] PicoCalc UART defaults")


def _run_font_parity_check():
    """Verify the PicoCalc default font and the corrected Font16 spacing."""
    import lcd
    from font import FontSize

    if lcd.LCD.FONT_DEFAULT != 0:
        raise RuntimeError("simulator PicoCalc default font mismatch")
    if FontSize(2).spacing != 1:
        raise RuntimeError("simulator Font16 spacing mismatch")
    print("[sim-check:ok] PicoCalc default font and Font16 spacing")


def _run_log_storage_check(opts):
    """Verify storage-mode logs persist under the selected simulated SD root."""
    import log
    import sim_runtime

    original_sd_root = sim_runtime.sd_root
    relative_path = "sim_reports/log-parity.txt"
    try:
        sim_runtime.sd_root = opts["sd"]
        logger = log.Log(log.Log.LOG_MODE_STORAGE, relative_path, True)
        if logger.log("stored", log.Log.LOG_TYPE_INFO) is not True:
            raise RuntimeError("simulator storage log write failed")

        path = sim_runtime.host_path(relative_path)
        try:
            with open(path, "r") as handle:
                contents = handle.read()
        except OSError:
            contents = ""
        if contents != "[INFO]stored\n":
            raise RuntimeError("simulator storage log contents mismatch")
        if logger.logs != ["[INFO]stored"]:
            raise RuntimeError("simulator in-memory log contents mismatch")

        if logger.reset() is not True or logger.logs:
            raise RuntimeError("simulator storage log reset failed")
        with open(path, "r") as handle:
            if handle.read():
                raise RuntimeError("simulator storage log file was not reset")
    finally:
        sim_runtime.sd_root = original_sd_root
    print("[sim-check:ok] storage log persistence reset")


def _run_audio_shutdown_check():
    """Verify shutdown signals every active simulator audio helper."""
    import sim_runtime

    probe_root = "/tmp/picoware-sim-audio-shutdown-check"
    filenames = (
        "sim_audio.status",
        "sim_audio.cmd",
        "sim_audio_mix_1.status",
        "sim_audio_mix_1.cmd",
        "unrelated.status",
    )
    original_sd_root = sim_runtime.sd_root
    _mkdir_p(probe_root)
    try:
        for name in filenames:
            try:
                os.remove(probe_root + "/" + name)
            except OSError:
                pass
        with open(probe_root + "/sim_audio.status", "w") as handle:
            handle.write("playing=1\n")
        with open(probe_root + "/sim_audio_mix_1.status", "w") as handle:
            handle.write("playing=1\n")
        with open(probe_root + "/unrelated.status", "w") as handle:
            handle.write("playing=1\n")

        sim_runtime.sd_root = probe_root
        if sim_runtime.shutdown_audio_sidecars(0):
            raise RuntimeError("simulator audio shutdown ignored active helpers")
        for name in ("sim_audio.cmd", "sim_audio_mix_1.cmd"):
            with open(probe_root + "/" + name, "r") as handle:
                if handle.read() != "stop\n":
                    raise RuntimeError("simulator audio shutdown command mismatch")
        if sim_runtime._exists(probe_root + "/unrelated.cmd"):
            raise RuntimeError("simulator audio shutdown signaled an unrelated helper")
    finally:
        sim_runtime.sd_root = original_sd_root
        for name in filenames + ("unrelated.cmd",):
            try:
                os.remove(probe_root + "/" + name)
            except OSError:
                pass
        try:
            os.rmdir(probe_root)
        except OSError:
            pass
    print("[sim-check:ok] audio sidecar shutdown")


def _run_fatal_exit_check(opts):
    """Prove a main.py-caught assertion still makes the child exit nonzero."""
    probe_sd = "/tmp/picoware-sim-fatal-probe-sd"
    probe_log = "/tmp/picoware-sim-fatal-probe.log"
    missing_text = "__PICOWARE_SIM_EXPECTED_MISSING_TEXT__"
    cmd = (
        _interpreter_command()
        + " "
        + _quote(THIS_DIR + "/run.py")
        + " --headless --frames 1 --assert-text "
        + _quote(missing_text)
        + " --audio silent --network offline --reset-sd --sd "
        + _quote(probe_sd)
        + " --apps-source "
        + _quote(opts["apps_source"])
        + " >"
        + _quote(probe_log)
        + " 2>&1"
    )
    status = os.system(cmd)
    try:
        with open(probe_log, "r") as handle:
            output = handle.read()
    except OSError:
        output = ""
    if status == 0:
        raise RuntimeError("simulator fatal-error probe unexpectedly exited zero")
    if "assert-text not seen: " + missing_text not in output:
        raise RuntimeError("simulator fatal-error probe missed assertion evidence")
    if "Picoware main reported a fatal error" not in output:
        raise RuntimeError("simulator fatal-error probe missed propagated failure")
    print("[sim-check:ok] fatal main errors exit nonzero")


def _write_error_file(path, exc):
    """Write exception details to an error log file."""
    if not path:
        return
    try:
        import sys as _sys

        with open(path, "w") as handle:
            handle.write("Picoware simulator exception\n")
            try:
                import sim_runtime

                handle.write("View: " + str(getattr(sim_runtime, "_current_view_name", "")) + "\n")
            except Exception:
                pass
            handle.write("\n")
            try:
                _sys.print_exception(exc, handle)
            except Exception:
                handle.write(str(exc))
                handle.write("\n")
    except OSError:
        pass


def _wait_for_viewer_close(frame):
    """Block until the viewer quit signal appears."""
    quit_path = frame + ".quit"
    while True:
        try:
            os.stat(quit_path)
            return
        except OSError:
            pass
        time_sleep(0.1)


def _relaunch_self(reset_sd=False):
    """Restart the simulator process via micropython."""
    args = []
    for arg in sys.argv:
        args.append(_quote(str(arg)))
    if reset_sd and "--reset-sd" not in sys.argv:
        args.append("--reset-sd")
    cmd = _interpreter_command() + " " + " ".join(args) + " >/tmp/picoware-sim-restart.log 2>&1 &"
    os.system(cmd)


def time_sleep(seconds):
    """Sleep for the given number of seconds."""
    try:
        import time

        time.sleep(seconds)
    except Exception:
        pass


def _start_viewer(opts):
    """Build and launch the native SDL viewer, returning frame/key paths."""
    frame = opts["sd"] + "/sim_frame.rgb565"
    keys = opts["sd"] + "/sim_keys.txt"
    binary = THIS_DIR + "/viewer/sdl_fb_viewer"

    if not _build_native("viewer"):
        print("Could not build SDL viewer. Run: sh simulator/build.sh viewer")
        raise SystemExit

    try:
        os.remove(keys)
    except OSError:
        pass
    try:
        os.remove(frame + ".stop")
    except OSError:
        pass
    try:
        os.remove(frame + ".quit")
    except OSError:
        pass
    try:
        os.remove(frame + ".error")
    except OSError:
        pass
    try:
        os.remove(frame + ".status")
    except OSError:
        pass
    try:
        os.remove(frame + ".control")
    except OSError:
        pass
    try:
        os.remove(frame + ".log")
    except OSError:
        pass

    board_name = str(opts["board"]).lower().replace("_", "-")
    width, height = _simulator_display_size(board_name)
    cmd = (
        _quote(binary)
        + " "
        + _quote(frame)
        + " "
        + _quote(keys)
        + " "
        + str(opts["scale"])
        + " "
        + str(width)
        + " "
        + str(height)
        + " >/tmp/picoware-sim-viewer.log 2>&1 &"
    )
    os.system(cmd)
    return frame, keys


def main():
    """Picoware simulator entry point."""
    opts = _parse_args(sys.argv)
    _bootstrap_runtime(opts)
    _insert_path(ROOT)
    _insert_path(MICROPYTHON_DIR)
    _insert_path(HARDWARE_DIR)

    import sim_usocket
    import sim_tls

    sys.modules["usocket"] = sim_usocket
    sys.modules["socket"] = sim_usocket
    sys.modules["tls"] = sim_tls
    sys.modules["ssl"] = sim_tls
    if opts["reset_sd"]:
        _safe_reset_sd(opts["sd"])
    _mkdir_p(opts["sd"])

    if opts["sim_check"]:
        _run_sim_check(opts)
        return

    if opts["coverage"]:
        _run_coverage(opts)
        return

    viewer_frame = ""
    viewer_keys = ""
    if opts["viewer"]:
        viewer_frame, viewer_keys = _start_viewer(opts)

    import sim_runtime

    frame_limit = opts["exit_after_frames"]
    if not frame_limit and opts["headless"] and not opts["viewer"]:
        frame_limit = opts["frames"]

    sim_runtime.configure(
        ROOT,
        opts["sd"],
        opts["apps_source"],
        opts["scale"],
        opts["board"],
        frame_limit,
        opts["headless"],
        opts["trace_keys"],
        opts["trace_views"],
        opts["trace_imports"],
        opts["screenshot"],
        opts["viewer"],
        viewer_frame,
        viewer_keys,
        opts["network"],
        opts["bluetooth"],
        opts["audio"],
        opts["speed"],
        opts["fps"],
        opts["sd_profile"],
        opts["record"],
    )
    sim_runtime.set_script_expectations(opts["wait_view"], opts["assert_text"])
    if opts["capabilities"]:
        sim_runtime.print_capabilities()
        return
    _install_view_tracking()
    try:
        if opts["open"]:
            sim_runtime.request_open(opts["open"])
        if opts["app"]:
            sim_runtime.request_app(opts["app"])
        if opts["game"]:
            sim_runtime.request_game(opts["game"])

        delayed_input = bool(opts["open"] or opts["app"] or opts["game"])
        delayed_loops = 180 if opts["app"] or opts["game"] else 120
        if opts["keys_text"]:
            if delayed_input:
                sim_runtime.schedule_text(delayed_loops, opts["keys_text"])
            else:
                sim_runtime.enqueue_text(opts["keys_text"])
        if opts["keys"]:
            if delayed_input:
                sim_runtime.schedule_key_names(delayed_loops + 1, opts["keys"])
            else:
                sim_runtime.enqueue_key_names(opts["keys"])
        if opts["script"]:
            sim_runtime.run_script_file(opts["script"])
    except sim_runtime.LaunchTargetError as e:
        print("[sim:launch:fail]", e)
        raise SystemExit(2)

    restart_requested = False
    restart_reset_sd = False
    try:
        _run_main()
    except sim_runtime.StopSimulation:
        pass
    except sim_runtime.RestartSimulation as r:
        restart_requested = True
        restart_reset_sd = bool(getattr(r, "reset", False))
    except Exception as e:
        try:
            sys.print_exception(e)
        except Exception:
            print("Unhandled simulator exception:", e)
        if opts["viewer"] and viewer_frame:
            _write_error_file(viewer_frame + ".error", e)
            _wait_for_viewer_close(viewer_frame)
        else:
            _write_error_file(opts["sd"] + "/sim_error.txt", e)
        raise SystemExit(1)
    finally:
        try:
            sim_runtime.shutdown_audio_sidecars()
        except Exception:
            pass
        try:
            sim_runtime.finish_recording()
        except Exception:
            pass
        if opts["viewer"] and viewer_frame:
            try:
                with open(viewer_frame + ".stop", "w") as handle:
                    handle.write("stop\n")
            except OSError:
                pass
        gc.collect()
    if restart_requested:
        _relaunch_self(restart_reset_sd)


main()
