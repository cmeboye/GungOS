"""BLE Beacon - Simple beacon broadcaster"""

_bluetooth = None
_broadcasting = False
_last_update = 0
_beacon_count = 0
_page = None

HELP = (
    "BLE beacon:",
    "Broadcasts as Picoware-Beacon every 100 ms.",
    "ESC\tstop broadcasting and return",
)


def start(view_manager) -> bool:
    """Start the Beacon app and begin broadcasting.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if broadcasting started, False on failure.
    """
    from picoware.system.bluetooth import Bluetooth

    global _bluetooth, _broadcasting, _beacon_count

    if _bluetooth is not None:
        _bluetooth.close()
        del _bluetooth
        _bluetooth = None

    _broadcasting = False
    _beacon_count = 0

    _bluetooth = Bluetooth(storage=view_manager.storage)

    try:
        if _bluetooth.start_peripheral(name="Picoware-Beacon", interval_us=100000):
            _broadcasting = True
        else:
            view_manager.alert("Failed to start BLE peripheral.")
            _bluetooth.close()
            return False
    except Exception as e:
        view_manager.alert("Error starting BLE peripheral:\n{}".format(e))
        _bluetooth.close()
        return False

    return True


def run(view_manager) -> None:
    """Run the app and update the display.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from picoware.system.buttons import BUTTON_ESCAPE
    from utime import ticks_ms, ticks_diff

    global _last_update, _beacon_count, _page

    if _bluetooth is not None:_bluetooth.poll()

    button: int = view_manager.button

    if button == BUTTON_ESCAPE:
        view_manager.back()
        return

    # Update display periodically
    now = ticks_ms()
    if ticks_diff(now, _last_update) < 500:
        return
    _last_update = now

    if _broadcasting:
        _beacon_count += 1

    if _page is None:
        from picoware.gui.style import Page
        _page = Page(view_manager, "Bluetooth / Beacon", ())
    lines = ["Name\tPicoware-Beacon", "MAC\t" + _bluetooth.mac_address]
    if _broadcasting:
        lines += ["Status\tBroadcasting", "Interval\t100 ms", "Updates\t%d" % _beacon_count]
    else:
        lines.append("Status\tStopped")
    conn_count = len(_bluetooth.central_connections)
    if conn_count > 0:
        lines.append("Connections\t%d" % conn_count)
    _page.update(lines)


def stop(view_manager) -> None:
    """Stop the app and stop broadcasting.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from gc import collect

    global _bluetooth, _broadcasting, _beacon_count, _last_update, _page

    _page = None
    if _bluetooth is not None:
        _bluetooth.stop_peripheral()
        _bluetooth.close()
        del _bluetooth
        _bluetooth = None

    _broadcasting = False
    _beacon_count = 0
    _last_update = 0

    collect()
