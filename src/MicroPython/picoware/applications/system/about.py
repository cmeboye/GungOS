"""GungOS version, features and upstream attribution."""
from picoware.system.features import FIRMWARE_NAME,FIRMWARE_VERSION

ABOUT_TEXT = (
    FIRMWARE_NAME+' v'+FIRMWARE_VERSION+"\n\n"
    "Lightweight PicoCalc firmware supporting an engineering toolbox.\n\n"
    "Scientific calculator\n"
    "Calculate, Statistics, Solver, Complex, Base-N and Matrix. Structured mathematical input and variables.\n\n"
    "Graph and Graph3D\n"
    "2D and 3D plotting, general expressions, navigation and adjustable views.\n\n"
    "PicoLAB engineering toolbox\n"
    "Shared numerical routines powered by ulab.\n\n"
    "PicoCalc desktop\n"
    "Category navigation, system information, themes and a configurable widget.\n\n"
    "SD files and Wi-Fi connectivity.\n\n"
    "Tetris and the Lorenz attractor demonstration.\n\n"
    "Based on the open-source project Picoware by jblanked.\n\n"
    "GungOS by Cem Gungor\n"
    "License: GNU GPL v3.\n"
    "Includes third-party components under their respective licenses."
)

_about = None


def start(view_manager) -> bool:
    """Start the app and show the about text.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the app started.
    """
    from picoware.gui.textbox import TextBox

    global _about
    if _about is None:
        _about = TextBox(
            view_manager.draw,
            0,
            view_manager.draw.size.y,
            view_manager.foreground_color,
            view_manager.background_color,
        )
        _about.set_text(ABOUT_TEXT)
        _about._set_cursor(0)
    return True


def run(view_manager) -> None:
    """Run the app and handle scrolling input.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from picoware.system.buttons import (
        BUTTON_ESCAPE,
        BUTTON_UP,
        BUTTON_DOWN,
        BUTTON_LEFT,
        BUTTON_ESCAPE,
        BUTTON_I,
    )

    if not _about:
        return

    button: int = view_manager.button

    if button == BUTTON_ESCAPE:
        view_manager.back()
    elif button == BUTTON_DOWN:
        _about.scroll_down()
    elif button == BUTTON_UP:
        _about.scroll_up()


def stop(view_manager) -> None:
    """Stop the app and clean up.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from gc import collect

    global _about
    if _about:
        del _about
        _about = None
    collect()
