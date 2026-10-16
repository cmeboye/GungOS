CRASH_LOG_PATH = "picoware/last_crash.txt"


def _report_fatal(vm, error) -> bool:
    """Log a fatal error and ask whether to restart.

    Args:
        vm (ViewManager): The view manager, or None if it failed to start.
        error (Exception): The unhandled exception.

    Returns:
        bool: True if the user chose to restart.
    """
    import io
    import sys

    buf = io.StringIO()
    sys.print_exception(error, buf)
    trace = buf.getvalue()
    print(trace)
    if vm is None:
        # Without a display or keyboard there is nobody to ask; stay at the REPL.
        return False
    saved = False
    try:
        saved = vm.storage.write(CRASH_LOG_PATH, "GungOS stopped\n" + trace)
    except Exception:
        saved = False
    message = f"GungOS stopped:\n{error}"
    if saved:
        message += f"\nDetails: {CRASH_LOG_PATH}"
    message += "\nAny key restarts. Esc stops at the REPL."
    try:
        return vm.alert(message, False, "Critical error")
    except Exception:
        return False


def main():
    """Main function to run the application"""
    from gc import collect, threshold, mem_free, mem_alloc

    # Initial cleanup
    collect()
    threshold(mem_free() // 4 + mem_alloc())

    from picoware.system.view_manager import ViewManager
    from picoware.system.view import View
    from picoware.applications import desktop

    # Initialize the view manager
    vm: ViewManager = None
    restart = False
    try:
        vm: ViewManager = ViewManager()

        # Add views to the view manager
        vm.add(View("desktop_view", desktop.run, desktop.start, desktop.stop))

        # Switch views
        vm.switch_to("desktop_view")

        # Main loop
        while vm.run():
            pass

    except Exception as e:
        print(f"Error occurred: {e}")
        restart = _report_fatal(vm, e)
    finally:
        del vm
        vm = None
        # Final cleanup
        collect()
        threshold(mem_free() // 4 + mem_alloc())

    from sys import platform
    if restart and platform == "rp2":
        # Re-runs main.py from a clean interpreter state.
        from machine import soft_reset
        soft_reset()

# run the main function
if __name__ == "__main__":
    main()
