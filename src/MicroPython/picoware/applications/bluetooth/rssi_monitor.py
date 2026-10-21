"""BLE RSSI Monitor - Monitor signal strength of nearby devices in real-time"""

from utime import ticks_ms, ticks_diff

_bluetooth = None
_devices = {}  # addr_str -> (name, rssi, last_seen)
_last_update = 0
_scan_count = 0


def bluetooth_callback(event, data):
    """Handle Bluetooth scan result events.

    Args:
        event (int): Bluetooth event code.
        data (tuple): Event payload with address and RSSI.
    """
    global _devices, _scan_count

    if event == 5:  # _IRQ_SCAN_RESULT
        addr_type, addr, adv_type, rssi, adv_data = data
        addr_str = ":".join("{:02X}".format(b) for b in addr)

        name = ""
        if _bluetooth is not None:
            name = _bluetooth.decode_name(adv_data)

        # Update or add device with timestamp
        if addr_str in _devices or len(_devices)<64:
            _devices[addr_str] = (name, rssi, ticks_ms())


    elif event==6:_scan_count+=1


def start(view_manager) -> bool:
    """Start the RSSI Monitor app and begin scanning.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the app started, False on failure.
    """
    from picoware.system.bluetooth import Bluetooth

    global _bluetooth, _devices, _scan_count

    if _bluetooth is not None:
        _bluetooth.close()
        del _bluetooth
        _bluetooth = None

    _devices = {}
    _scan_count = 0

    _bluetooth = Bluetooth(storage=view_manager.storage)
    _bluetooth.callback = bluetooth_callback

    # Start continuous scanning
    if not _bluetooth.scan(duration_ms=2000):
        view_manager.alert(_bluetooth.error)
        _bluetooth.close()
        return False

    return True


HELP = (
    "RSSI monitor:",
    "Nearby devices, strongest first; unseen for 10 s drop off.",
    "ENTER\tclear the list",
    "ESC\treturn",
)


def run(view_manager) -> None:
    """Run the app and update the RSSI display.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from picoware.system.buttons import BUTTON_ESCAPE, BUTTON_CENTER
    from picoware.system.vector import Vector

    global _last_update, _devices, _scan_count

    if _bluetooth is not None:_bluetooth.poll()

    button: int = view_manager.button

    if button == BUTTON_ESCAPE:
        view_manager.back()
        return

    if button == BUTTON_CENTER:
        # Clear device list
        _devices = {}
        _scan_count = 0

    if not _bluetooth.is_scanning:_bluetooth.scan(duration_ms=2000)

    # Update display periodically
    now = ticks_ms()
    if ticks_diff(now, _last_update) < 300:
        return
    _last_update = now

    # Remove stale devices (not seen in last 10 seconds)
    stale_threshold = 10000
    _devices = {
        addr: (name, rssi, last_seen)
        for addr, (name, rssi, last_seen) in _devices.items()
        if ticks_diff(now, last_seen) < stale_threshold
    }


    from picoware.gui import style

    draw = view_manager.draw
    palette = style.system_palette(view_manager)
    draw.fill_screen(palette.BG)

    text_vec = Vector(5, 2)
    height = draw.size.y - style.FOOT_HEIGHT

    # Sort devices by RSSI (strongest first)
    sorted_devices = sorted(_devices.items(), key=lambda x: x[1][1], reverse=True)

    y = style.HEAD_HEIGHT + 8
    max_devices = (height - y - 4) // 16

    if not sorted_devices:
        text_vec.x, text_vec.y = 5, y
        draw.text(text_vec, "Scanning...")
    else:
        for i, (addr, (name, rssi, last_seen)) in enumerate(
            sorted_devices[:max_devices]
        ):
            if y > height - 20:
                break

            # Display name or shortened address
            display = name if name else addr[:11]
            display = display[:12]

            # Create RSSI bar visualization
            # RSSI typically ranges from -30 (very close) to -100 (far)
            bar_length = max(0, min(8, (rssi + 100) // 10))
            bar_sym = "|" * bar_length + " " * (8 - bar_length)

            text_vec.x, text_vec.y = 5, y
            draw.text(text_vec, f"{display[:10]}")
            text_vec.x, text_vec.y = 70, y
            draw.text(text_vec, f"{bar_sym} ")
            text_vec.x, text_vec.y = 130, y
            draw.text(text_vec, f"{rssi}dB")
            y += 16

    style.chrome(draw, "Bluetooth / RSSI Monitor", f"Devices: {len(_devices)}", palette=palette)
    draw.swap()


def stop(view_manager) -> None:
    """Stop the app and stop scanning.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from gc import collect

    global _bluetooth, _devices, _scan_count

    if _bluetooth is not None:
        if _bluetooth.is_scanning:
            _bluetooth.scan_stop()
        _bluetooth.close()
        del _bluetooth
        _bluetooth = None

    _devices = {}
    _scan_count = 0

    collect()
