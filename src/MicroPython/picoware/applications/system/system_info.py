"""Info - firmware version, device resources and credits on one page."""
from picoware.gui.style import PAGE_HELP as HELP

ABOUT = (
    "Lightweight PicoCalc firmware supporting an engineering toolbox.",
    "",
    "Scientific calculator:",
    "Calculate, Statistics, Solver, Complex, Base-N and Matrix. Structured mathematical input and variables.",
    "Graph and Graph3D:",
    "2D and 3D plotting, general expressions, navigation and adjustable views.",
    "PicoLAB engineering toolbox:",
    "Shared numerical routines powered by ulab.",
    "PicoCalc desktop:",
    "Category navigation, system information, themes and a configurable widget.",
    "Also included:",
    "SD files and Wi-Fi connectivity.",
    "Tetris and the Lorenz attractor demonstration.",
    "Credits:",
    "Based on the open-source project Picoware by jblanked.",
    "GungOS by Cem Gungor",
    "License: GNU GPL v3.",
    "Includes third-party components under their respective licenses.",
)

_page = None


def _lines(view_manager) -> list:
    from picoware.system.features import FIRMWARE_NAME, FIRMWARE_VERSION
    from picoware.system.resource_info import snapshot, lines

    result = [FIRMWARE_NAME + " v" + FIRMWARE_VERSION + ":"]
    result.extend(ABOUT[:2])
    result.append("Device:")
    try:
        result.append("Battery: %d%%" % view_manager.battery.percentage)
    except (OSError, ValueError, TypeError):
        pass
    result.extend(lines(snapshot(view_manager)))
    result.append("")
    result.extend(ABOUT[2:])
    return result


def start(view_manager) -> bool:
    """Show the version, resources and credits."""
    from picoware.gui.style import Page

    global _page
    _page = Page(view_manager, "System / Info", _lines(view_manager))
    _page.draw()
    return True


def run(view_manager) -> None:
    """Scroll the page; ESC returns."""
    from picoware.system.buttons import BUTTON_ESCAPE

    button = view_manager.button
    if button == BUTTON_ESCAPE:
        view_manager.back()
    elif button != -1:
        _page.key(button)


def stop(view_manager) -> None:
    """Release the page."""
    global _page
    _page = None
