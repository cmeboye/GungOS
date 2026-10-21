"""WiFi RSSI Monitor - Monitor signal strength of nearby WiFi networks in real-time"""

from utime import ticks_ms, ticks_diff
from picoware.system.colors import TFT_WHITE, TFT_RED, TFT_GREEN, TFT_YELLOW, TFT_ORANGE

_networks = {}  # ssid_str -> (bssid, channel, rssi, authmode, last_seen)
_last_update = 0
_scan_count = 0
_last_scan = None
_scan_error = ""

HELP = (
    "RSSI monitor:",
    "Networks rescan every two seconds, strongest first.",
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

    global _last_update, _networks, _scan_count, _last_scan, _scan_error

    button: int = view_manager.button

    if button == BUTTON_ESCAPE:
        view_manager.back()
        return

    if button == BUTTON_CENTER:
        # Clear network list
        _networks = {}
        _scan_count = 0

    # Update display periodically
    now = ticks_ms()
    if ticks_diff(now, _last_update) < 500:
        return
    _last_update = now

    # Perform WiFi scan
    wifi = view_manager.wifi
    if wifi is not None and (_last_scan is None or ticks_diff(now,_last_scan)>=2000):
        _last_scan=now
        try:
            _scan_error=""
            results = wifi.scan()
            for ssid, bssid, channel, rssi, authmode, hidden in results:
                try:ssid_str=ssid.decode("utf-8") if ssid else "<hidden>"
                except UnicodeError:continue
                if len(ssid_str) == 0:
                    ssid_str = "<hidden>"

                # Update or add network with timestamp
                if ssid_str in _networks or len(_networks)<64:
                    _networks[ssid_str] = (bssid, channel, rssi, authmode, now)
            _scan_count+=1
        except Exception as exc:
            _scan_error=str(exc)

    # Remove stale networks (not seen in last 10 seconds)
    stale_threshold = 10000
    _networks = {
        ssid: (bssid, channel, rssi, authmode, last_seen)
        for ssid, (bssid, channel, rssi, authmode, last_seen) in _networks.items()
        if ticks_diff(now, last_seen) < stale_threshold
    }


    from picoware.gui import style

    draw = view_manager.draw
    palette = style.system_palette(view_manager)
    draw.fill_screen(palette.BG)

    width = draw.size.x
    status_y = draw.size.y - style.FOOT_HEIGHT

    # Sort networks by RSSI (strongest first)
    sorted_networks = sorted(_networks.items(), key=lambda x: x[1][2], reverse=True)

    y = style.HEAD_HEIGHT + 8
    max_networks = max(1, (status_y - y - 3) // 16)

    if not sorted_networks:
        message = _scan_error[:36] if _scan_error else "Scanning..."
        draw.text(Vector(max(0, (width - draw.len(message)) // 2), y), message)
    else:
        for i, (ssid, (bssid, channel, rssi, authmode, last_seen)) in enumerate(
            sorted_networks[:max_networks]
        ):
            if y > status_y - 3:
                break

            # Display SSID (truncate if needed)
            display_ssid = ssid[:12]

            # Create RSSI bar visualization
            # WiFi RSSI typically ranges from -30 (very close) to -90 (far)
            bar_length = max(0, min(8, (rssi + 90) // 8))
            bar_sym = "|" * bar_length + " " * (8 - bar_length)

            # Color based on RSSI strength
            if rssi >= -50:
                color = TFT_GREEN
            elif rssi >= -60:
                color = TFT_WHITE
            elif rssi >= -70:
                color = TFT_YELLOW
            elif rssi >= -80:
                color = TFT_ORANGE
            else:
                color = TFT_RED

            if width < 180:
                color = TFT_WHITE

            rssi_text = f"{rssi}dB"
            suffix = f" {bar_sym} {rssi_text}"
            max_ssid_width = max(1, width - draw.len(suffix) - 2)
            max_ssid_chars = max(1, max_ssid_width // max(1, draw.font_size.x))
            row = f"{display_ssid[:max_ssid_chars]}{suffix}"
            draw.text(Vector(max(0, (width - draw.len(row)) // 2), y), row, color)
            y += 16

    style.chrome(draw, "WiFi / RSSI Monitor", f"Networks: {len(_networks)}", palette=palette)
    draw.swap()


def start(view_manager) -> bool:
    """Start the WiFi RSSI Monitor app.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the app started, False if WiFi is unavailable.
    """
    global _networks, _scan_count, _last_update, _last_scan, _scan_error

    if view_manager.wifi is None:
        view_manager.alert("WiFi not available")
        return False

    _networks = {}
    _scan_count = 0
    _last_scan = None
    _scan_error = ""
    _last_update = ticks_ms()

    return True


def stop(view_manager) -> None:
    """Stop the app and reset state.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from gc import collect

    global _networks, _scan_count, _last_update, _last_scan, _scan_error

    _networks = {}
    _scan_count = 0
    _last_scan = None
    _scan_error = ""
    _last_update = 0

    collect()
