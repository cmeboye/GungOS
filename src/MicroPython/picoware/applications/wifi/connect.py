"""WiFi Connect - Connect to a WiFi network."""

from utime import ticks_ms, ticks_diff

HELP = (
    "Wi-Fi connect:",
    "RIGHT\tconnect to the saved network",
    "LEFT / DOWN\tconnect as well",
    "UP\tdisconnect",
    "ESC\treturn",
)

_connect = None
_status_message: str = ""
_connection_start_time = 0
_ssid = ""
_password = ""


def __connect_callback(state: int, error: str) -> None:
    """Callback for Wi-Fi connection status updates.

    Args:
        state (int): The Wi-Fi connection state.
        error (str): The connection error message.
    """
    from picoware.system.wifi import (
        WIFI_STATE_CONNECTED,
        WIFI_STATE_TIMEOUT,
        WIFI_STATE_ISSUE,
    )

    global _status_message
    if state == WIFI_STATE_CONNECTED:
        _status_message = "Connected successfully!"
    elif state == WIFI_STATE_ISSUE:
        _status_message = error or "Connection issue"
    elif state == WIFI_STATE_TIMEOUT:
        _status_message = "Connection timeout"


def _get_status_lines(view_manager) -> list:
    """Build the connection status lines.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        list: The lines to display.
    """
    global _status_message

    wifi = view_manager.wifi
    lines = ["Network\t" + _ssid, "MAC address\t" + wifi.mac_address]

    if wifi.is_connected():
        _status_message = "Connected successfully!"
        lines.append("IP address\t" + wifi.device_ip)
        lines.append("Status\t" + _status_message)

    else:
        from picoware.system.wifi import (
            WIFI_STATE_IDLE,
            WIFI_STATE_CONNECTING,
            WIFI_STATE_CONNECTED,
            WIFI_STATE_TIMEOUT,
        )

        state = wifi.status()
        if wifi.last_error:
            _status_message=wifi.last_error
        lines.append("Status\t" + _status_message)
        if wifi.last_error:
            lines.append("Reason\t" + wifi.last_error)

        if state == WIFI_STATE_IDLE:
            lines.append("Ready to connect.")
        elif state == WIFI_STATE_CONNECTING:
            elapsed = max(0,ticks_diff(ticks_ms(),wifi.connection_start_time)) // 1000 if wifi.connection_start_time is not None else 0
            lines.append(f"Connecting... ({elapsed}s)")
        elif state == WIFI_STATE_CONNECTED:
            lines.append("Connected!")
        elif state == WIFI_STATE_TIMEOUT:
            lines.append("Connection timeout")

    return lines


def start(view_manager) -> bool:
    """Start the app and load the saved WiFi credentials.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the app started, False if no credentials are saved.
    """
    from picoware.applications.wifi.utils import load_wifi_password, load_wifi_ssid

    global _connect, _ssid, _password

    _ssid = load_wifi_ssid(view_manager)
    _password = load_wifi_password(view_manager)

    if not _ssid:
        view_manager.alert(
            "No saved WiFi credentials found.\nPlease set up WiFi in the Settings app.",
        )
        return False

    if _connect is None:
        from picoware.gui.style import Page

        global _connection_start_time
        global _status_message

        _connect = Page(view_manager, "WiFi / Connect", ())

        # Reset state
        _connection_start_time = 0
        _status_message = (
            "Connected" if view_manager.wifi.is_connected() else "Disconnected"
        )
        _connect.update(_get_status_lines(view_manager))

    return True


def start_connection(view_manager) -> bool:
    """Start connecting and immediately update the status screen."""
    global _status_message, _connection_start_time

    if _connect is None:
        return False
    wifi = view_manager.wifi
    wifi.reset()
    _status_message = "Starting connection..."
    wifi.callback_connect = __connect_callback
    started = wifi.connect_async(_ssid, _password, sta_mode=True)
    if started:
        _connection_start_time = ticks_ms()
    else:
        _status_message = wifi.error or "Failed to start connection"
    if _connect is not None:
        _connect.update(_get_status_lines(view_manager))
    return started


def run(view_manager) -> None:
    """Run the app and handle connection input.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from picoware.system.buttons import (
        BUTTON_ESCAPE,
        BUTTON_LEFT,
        BUTTON_UP,
        BUTTON_RIGHT,
        BUTTON_DOWN,
    )

    global _connect
    if _connect is None:
        return

    global _status_message
    global _connection_start_time

    button: int = view_manager.button
    wifi = view_manager.wifi

    if button == BUTTON_ESCAPE:
        view_manager.back()
        return

    if button == BUTTON_UP:
        wifi.disconnect()
        _status_message = "Disconnected"
    elif button in (BUTTON_UP, BUTTON_LEFT, BUTTON_RIGHT, BUTTON_DOWN):
        start_connection(view_manager)

    _connect.update(_get_status_lines(view_manager))


def stop(view_manager) -> None:
    """Stop the app and clean up.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from gc import collect

    view_manager.wifi.callback_connect=None

    global _connect
    if _connect:
        del _connect
        _connect = None

    global _status_message
    global _connection_start_time
    global _ssid
    global _password

    _status_message = ""
    _connection_start_time = 0
    _ssid = ""
    _password = ""

    collect()
