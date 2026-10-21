"""USB Media Keys - Emulate USB media keys."""

_usb = None
_initialized = False
_key_map = None

HELP = (
    "Media keys:",
    "UP / DOWN\tvolume up / down",
    "LEFT/RIGHT\tprevious / next track",
    "ENTER\tplay or pause",
    "0\tmute",
    "ESC\tstop and return",
)


def start(view_manager) -> bool:
    """Start the app and map buttons to media keys.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the app started.
    """
    from picoware.system.usb import USBMedia
    from picoware.system.buttons import (
        BUTTON_UP,
        BUTTON_DOWN,
        BUTTON_LEFT,
        BUTTON_RIGHT,
        BUTTON_CENTER,
        BUTTON_0,
    )

    view_manager.alert(
        "USB Media Keys is about to start. Connect the USB cable, then press any key."
    )
    global _usb, _initialized, _key_map
    _usb = USBMedia(manufacturer="MicroPython", product="Pico Media", serial="000002")
    from picoware.gui.style import Page
    Page(view_manager, "USB / Media Keys", HELP[1:-1]).draw()
    _key_map = {
        BUTTON_CENTER: USBMedia.USAGE_PLAY_PAUSE,
        BUTTON_UP: USBMedia.USAGE_VOL_UP,
        BUTTON_DOWN: USBMedia.USAGE_VOL_DOWN,
        BUTTON_LEFT: USBMedia.USAGE_PREV_TRACK,
        BUTTON_RIGHT: USBMedia.USAGE_NEXT_TRACK,
        BUTTON_0: USBMedia.USAGE_MUTE,
    }

    return True


def run(view_manager) -> None:
    """Run the app and send media key presses.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from picoware.system.buttons import BUTTON_ESCAPE

    global _initialized

    button = view_manager.button

    if button == BUTTON_ESCAPE:
        view_manager.back()
        return

    if not _usb:
        return

    if not _initialized:
        _usb.init()
        _initialized = True

    if button in _key_map:
        _usb.press(_key_map[button])


def stop(view_manager) -> None:
    """Stop the app and clean up.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from gc import collect

    global _usb, _initialized, _key_map
    if _usb is not None:
        del _usb
        _usb = None
    _initialized = False
    _key_map = None

    collect()
