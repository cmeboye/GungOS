"""WiFi Settings - Configure WiFi settings."""
from picoware.gui.style import MENU_HELP

HELP = MENU_HELP + (
    "Network Info:",
    "Shows the saved SSID and password; ESC closes it.",
)

_settings_menu = None
_settings_menu_index = 0


def start(view_manager) -> bool:
    """Start the app and build the WiFi settings menu.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the app started.
    """
    from picoware.gui.menu import Menu

    global _settings_menu

    if _settings_menu is None:
        _settings_menu = Menu(
            view_manager.draw,
            "WiFi Settings",
            0,
            view_manager.draw.size.y,
            view_manager.foreground_color,
            view_manager.background_color,
            view_manager.selected_color,
            view_manager.foreground_color,
            2,
        )
        _settings_menu.add_item("Network Info")
        _settings_menu.add_item("Change SSID")
        _settings_menu.add_item("Change Password")
        _settings_menu.set_selected(0)
        _settings_menu.draw()

    return True


def run(view_manager) -> None:
    """Run the app and handle menu input.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from picoware.system.view import View
    from picoware.system.buttons import (
        BUTTON_ESCAPE,
        BUTTON_UP,
        BUTTON_DOWN,
        BUTTON_LEFT,
        BUTTON_CENTER,
        BUTTON_RIGHT,
    )

    global _settings_menu
    if not _settings_menu:
        return

    global _settings_menu_index

    button: int = view_manager.button

    if button in (BUTTON_UP, BUTTON_LEFT):
        _settings_menu.scroll_up()
    elif button in (BUTTON_DOWN, BUTTON_RIGHT):
        _settings_menu.scroll_down()
    elif button == BUTTON_ESCAPE:
        _settings_menu_index = 0
        view_manager.back()
    elif button == BUTTON_CENTER:
        _settings_menu_index = _settings_menu.selected_index
        if _settings_menu_index == 0:
            from picoware.applications.wifi.utils import (
                load_wifi_password,
                load_wifi_ssid,
            )

            ssid = load_wifi_ssid(view_manager)
            password = load_wifi_password(view_manager)

            view_manager.show("NETWORK INFO", ("SSID\t" + ssid, "Password\t" + password))

        elif _settings_menu_index == 1:
            from picoware.applications.wifi import ssid

            view_manager.add(
                View(
                    "wifi_ssid",
                    ssid.run,
                    ssid.start,
                    ssid.stop, getattr(ssid, "HELP", None),
                )
            )
            view_manager.switch_to("wifi_ssid")
        elif _settings_menu_index == 2:
            from picoware.applications.wifi import password

            view_manager.add(
                View(
                    "wifi_password",
                    password.run,
                    password.start,
                    password.stop, getattr(password, "HELP", None),
                )
            )
            view_manager.switch_to("wifi_password")


def stop(view_manager) -> None:
    """Stop the app and clean up.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from gc import collect

    global _settings_menu

    if _settings_menu is not None:
        del _settings_menu
        _settings_menu = None


    collect()
