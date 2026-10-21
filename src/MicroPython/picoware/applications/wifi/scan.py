"""WiFi Scanner - Scan for nearby WiFi networks."""
from picoware.gui.style import MENU_HELP

HELP = MENU_HELP + (
    "Scan:",
    "Choose a network to save it, then type its password.",
)

from picoware.system.buttons import (
    BUTTON_ESCAPE,
    BUTTON_UP,
    BUTTON_DOWN,
    BUTTON_LEFT,
    BUTTON_RIGHT,
    BUTTON_CENTER,
)

_scan = None
_scan_ssids = []


def __save_ssid(view_manager) -> bool:
    """Save the selected SSID.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the SSID was saved, False otherwise.
    """
    global _scan

    if _scan is None:
        return False

    ssid_name = _scan_ssids[_scan.selected_index] if _scan_ssids else ''
    if not ssid_name:return False

    from picoware.applications.wifi.utils import save_wifi_ssid

    if not save_wifi_ssid(view_manager.storage, ssid_name):
        # try one last time
        return save_wifi_ssid(view_manager.storage, ssid_name)
    return True


def __should_save_choice(view_manager) -> bool:
    """Choose whether to save the selected SSID.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the user chose to save, False otherwise.
    """
    name = _scan.current_item.rsplit(" (", 1)[0]
    return view_manager.choose(f"Save '{name}'?", ("No", "Yes")) == 1


def __switch_to_password_view(view_manager) -> None:
    """Switch to the password view.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from picoware.applications.wifi import password
    from picoware.system.view import View

    view_manager.add(
        View(
            "wifi_password",
            password.run,
            password.start,
            password.stop, getattr(password, "HELP", None),
        )
    )
    view_manager.switch_to("wifi_password")


def start(view_manager) -> bool:
    """Start the app and scan for networks.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the app started, False if WiFi is unavailable.
    """
    from picoware.gui.menu import Menu

    global _scan, _scan_ssids

    if _scan is None:
        _scan_ssids=[]
        wifi = view_manager.wifi

        if wifi is None:
            return False

        try:results=wifi.scan()
        except Exception as exc:
            view_manager.alert('Wi-Fi scan failed: '+str(exc))
            return False

        _scan = Menu(
            view_manager.draw,
            "Scan",
            0,
            view_manager.draw.size.y,
            view_manager.foreground_color,
            view_manager.background_color,
            view_manager.selected_color,
            view_manager.foreground_color,
            2,
        )

        ssids: list[str] = []

        for ssid, bssid, channel, rssi, authmode, hidden in results:
            if len(_scan_ssids)>=64:break
            try:_ssid=ssid.decode("utf-8")
            except UnicodeError:continue
            actual_ssid=_ssid
            if len(_ssid) == 0:
                _ssid = "<hidden>"
            if _ssid not in ssids:
                ssids.append(_ssid)
                _scan_ssids.append(actual_ssid)
                _scan.add_item(f"{_ssid} ({rssi}dB)")

        _scan.set_selected(0)

        _scan.draw()
    return True


def run(view_manager) -> None:
    """Run the app and handle menu input.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    if not _scan:
        return

    button: int = view_manager.button

    if button in (BUTTON_UP, BUTTON_LEFT):
        _scan.scroll_up()
    elif button in (BUTTON_DOWN, BUTTON_RIGHT):
        _scan.scroll_down()
    elif button == BUTTON_ESCAPE:
        view_manager.back()
    elif button == BUTTON_CENTER:
        if not _scan_ssids:
            view_manager.alert("No networks found. Scan again or enter an SSID in Settings.")
            return
        if not _scan_ssids[_scan.selected_index]:
            view_manager.alert('Enter a hidden network name in Wi-Fi Settings.')
            return
        if __should_save_choice(view_manager):
            if not __save_ssid(view_manager):
                view_manager.alert("Failed to save SSID!", True)
                return
            __switch_to_password_view(view_manager)


def stop(view_manager) -> None:
    """Stop the app and clean up.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from gc import collect

    global _scan, _scan_ssids
    if _scan:
        del _scan
        _scan = None
    _scan_ssids = []
    collect()
