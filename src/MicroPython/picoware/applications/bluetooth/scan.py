"""BLE Scanner - Scan for nearby Bluetooth devices (Central mode)"""
from picoware.gui.style import MENU_HELP

HELP = MENU_HELP[:2] + (
    "ENTER\tshow the device's details",
    "ESC\treturn",
    "Scanning takes a few seconds; devices list when done.",
)

_menu = None
_bluetooth = None
_loading = None
_addresses = []
_scanned_devices = []  # List of (addr_type, addr_bytes, name, rssi)


def bluetooth_callback(event, data):
    """Handle Bluetooth scan result events.

    Args:
        event (int): Bluetooth event code.
        data (tuple): Event payload with address and RSSI.
    """
    global _scanned_devices

    if event == 5:
        from picoware.applications.bluetooth.common import add_result
        add_result(_bluetooth,_menu,_scanned_devices,_addresses,data,False)

    elif event == 6:  # _IRQ_SCAN_DONE
        pass


def start(view_manager) -> bool:
    """Start the app and begin scanning for devices.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the app started, False on failure.
    """
    from picoware.gui.loading import Loading
    from picoware.gui.menu import Menu
    from picoware.system.bluetooth import Bluetooth

    global _menu, _bluetooth, _loading, _addresses, _scanned_devices

    # Cleanup
    if _menu is not None:
        del _menu
        _menu = None
    if _bluetooth is not None:
        _bluetooth.close()
        del _bluetooth
        _bluetooth = None
    if _loading is not None:
        del _loading
        _loading = None

    _scanned_devices = []
    _addresses = []

    bg = view_manager.background_color
    fg = view_manager.foreground_color
    sel = view_manager.selected_color

    _menu = Menu(
        view_manager.draw,
        "BLE Scan",
        0,
        view_manager.draw.size.y,
        fg,
        bg,
        sel,
        fg,
        2,
    )

    _loading = Loading(
        view_manager.draw,
        fg,
        bg,
    )
    _loading.text = "Scanning..."

    _bluetooth = Bluetooth(storage=view_manager.storage)
    _bluetooth.callback = bluetooth_callback
    if not _bluetooth.scan():
        view_manager.alert(_bluetooth.error)
        _bluetooth.close()
        return False

    return True


def run(view_manager) -> None:
    """Run the app and handle scan results.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from picoware.system.buttons import (
        BUTTON_ESCAPE,
        BUTTON_UP,
        BUTTON_DOWN,
        BUTTON_LEFT,
        BUTTON_RIGHT,
        BUTTON_CENTER,
    )

    if _bluetooth is not None:_bluetooth.poll()

    button: int = view_manager.button

    if button == BUTTON_ESCAPE:
        view_manager.back()
        return

    global _loading

    # If scan is still active, show loading animation
    if _bluetooth.is_scanning:
        if _loading:
            _loading.animate()
        return

    # Scan just completed, transition to results
    if _loading is not None:
        _loading.stop()
        del _loading
        _loading = None

        if _menu.item_count == 0:
            view_manager.alert("No Bluetooth devices found.", True)
        else:
            _menu.draw()
        return

    # Handle menu navigation
    if button in (BUTTON_UP, BUTTON_LEFT):
        _menu.scroll_up()
    elif button in (BUTTON_DOWN, BUTTON_RIGHT):
        _menu.scroll_down()
    elif button == BUTTON_CENTER:
        # Show device details
        idx = _menu.selected_index
        if 0 <= idx < len(_scanned_devices):
            addr_type, addr, name, rssi = _scanned_devices[idx]
            addr_str = ":".join("{:02X}".format(b) for b in addr)

            view_manager.show("DEVICE INFO", (
                "Name\t" + (name or "Unknown"),
                "Address\t" + addr_str,
                "Type\t" + ("Public" if addr_type == 0 else "Random"),
                "RSSI\t%d dB" % rssi,
            ))


def stop(view_manager) -> None:
    """Stop the app and clean up.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from gc import collect

    global _menu, _bluetooth, _loading, _addresses, _scanned_devices

    if _bluetooth is not None:
        if _bluetooth.is_scanning:
            _bluetooth.scan_stop()
        _bluetooth.close()
        del _bluetooth
        _bluetooth = None
    if _menu is not None:
        del _menu
        _menu = None
    if _loading is not None:
        del _loading
        _loading = None

    _addresses.clear()
    _scanned_devices = []
    collect()
