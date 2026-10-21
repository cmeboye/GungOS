"""BLE Advertise - Broadcast as a peripheral and accept connections"""

from micropython import const

_bluetooth = None
_advertising = False
_connections = []
_received_data = []
_last_update = 0

STATE_IDLE = const(0)
STATE_ADVERTISING = const(1)
STATE_CONNECTED = const(2)

_state = STATE_IDLE
_page = None

HELP = (
    "BLE advertise:",
    "Broadcasts as Picoware and accepts connections.",
    "ENTER\tsend a test message when connected",
    "ESC\tstop advertising and return",
)


def bluetooth_callback(event, data):
    """Handle Bluetooth connection and disconnection events.

    Args:
        event (int): Bluetooth event code.
        data (tuple): Event payload with connection handle and address.
    """
    global _connections, _state

    if event == 1:  # _IRQ_CENTRAL_CONNECT
        conn_handle, addr_type, addr = data
        addr_str = ":".join("{:02X}".format(b) for b in addr)
        _connections.append((conn_handle, addr_str))
        _state = STATE_CONNECTED

    elif event == 2:  # _IRQ_CENTRAL_DISCONNECT
        conn_handle, addr_type, addr = data
        _connections = [(h, a) for h, a in _connections if h != conn_handle]
        if len(_connections) == 0:
            _state = STATE_ADVERTISING


def on_data_received(data):
    """Store data received from the connected central.

    Args:
        data (bytes): Raw data received over BLE.
    """
    global _received_data
    try:
        text = data.decode("utf-8")
    except Exception:
        text = str(data)
    _received_data.append(text)
    # Keep only last 5 messages
    if len(_received_data) > 5:
        _received_data = _received_data[-5:]


def start(view_manager) -> bool:
    """Start the app and advertise this device for connections.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if advertising started, False on failure.
    """
    from picoware.system.bluetooth import Bluetooth

    global _bluetooth, _advertising, _connections, _received_data, _state

    if _bluetooth is not None:
        _bluetooth.close()
        del _bluetooth
        _bluetooth = None

    _advertising = False
    _connections = []
    _received_data = []
    _state = STATE_IDLE

    _bluetooth = Bluetooth(storage=view_manager.storage)
    _bluetooth.callback = bluetooth_callback
    _bluetooth.on_write(on_data_received)

    try:
        if _bluetooth.start_peripheral(name="Picoware"):
            _advertising = True
            _state = STATE_ADVERTISING
        else:
            view_manager.alert("Failed to start advertising")
            _bluetooth.close()
            return False
    except Exception as e:
        view_manager.alert(f"Error: {str(e)}")
        _bluetooth.close()
        return False

    return True


def run(view_manager) -> None:
    """Run the app and update the display.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from picoware.system.buttons import BUTTON_ESCAPE, BUTTON_CENTER
    from utime import ticks_ms, ticks_diff

    global _last_update

    if _bluetooth is not None:_bluetooth.poll()

    button: int = view_manager.button

    if button == BUTTON_ESCAPE:
        view_manager.back()
        return

    # Send test data when center pressed
    if button == BUTTON_CENTER and _state == STATE_CONNECTED:
        _bluetooth.send("Hello from Picoware!")

    # Update display periodically
    now = ticks_ms()
    if ticks_diff(now, _last_update) < 200:
        return
    _last_update = now

    global _page
    if _page is None:
        from picoware.gui.style import Page
        _page = Page(view_manager, "Bluetooth / Advertise", ())
    status = {STATE_ADVERTISING: "Broadcasting...", STATE_CONNECTED: "Connected"}.get(_state, "Idle")
    lines = ["Name\tPicoware", "MAC\t" + _bluetooth.mac_address,
             "Status\t" + status, "Connections\t%d" % len(_connections)]
    lines.extend("Device\t" + addr[:17] for handle, addr in _connections[:2])
    if _received_data:
        lines.append("Last received:")
        lines.extend(_received_data[-2:])
    _page.update(lines)


def stop(view_manager) -> None:
    """Stop the app and clean up the BLE connection.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from gc import collect

    global _bluetooth, _advertising, _connections, _received_data, _state, _page

    _page = None
    if _bluetooth is not None:
        _bluetooth.stop_peripheral()
        for conn_handle, _ in _connections:
            try:
                _bluetooth.disconnect(conn_handle)
            except Exception:
                pass
        _bluetooth.close()
        del _bluetooth
        _bluetooth = None

    _advertising = False
    _connections = []
    _received_data = []
    _state = STATE_IDLE
    collect()
