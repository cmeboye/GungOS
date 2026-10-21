"""USB Numpad - Emulate a USB numeric keypad."""

_usb = None
_initialized = False
_key_map = None

HELP = (
    "Numpad:",
    "0-9\tnumpad digits",
    "UP / DOWN\t+ / -",
    "LEFT/RIGHT\t* / /",
    "ENTER\tnumpad Enter",
    "ESC\tstop and return",
)


def start(view_manager) -> bool:
    """Start the app and map buttons to numpad keys.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the app started.
    """
    from picoware.system.usb import USBKeyboard
    from picoware.system.buttons import (
        BUTTON_UP,
        BUTTON_DOWN,
        BUTTON_LEFT,
        BUTTON_RIGHT,
        BUTTON_CENTER,
        BUTTON_0,
        BUTTON_1,
        BUTTON_2,
        BUTTON_3,
        BUTTON_4,
        BUTTON_5,
        BUTTON_6,
        BUTTON_7,
        BUTTON_8,
        BUTTON_9,
    )

    view_manager.alert(
        "USB Numpad is about to start. Connect the USB cable, then press any key."
    )
    global _usb, _initialized, _key_map
    _usb = USBKeyboard(
        manufacturer="MicroPython", product="Picoware Numpad", serial="000003"
    )
    from picoware.gui.style import Page
    Page(view_manager, "USB / Numpad", HELP[1:-1]).draw()
    _key_map = {
        BUTTON_0: 0x62,
        BUTTON_1: 0x59,
        BUTTON_2: 0x5A,
        BUTTON_3: 0x5B,
        BUTTON_4: 0x5C,
        BUTTON_5: 0x5D,
        BUTTON_6: 0x5E,
        BUTTON_7: 0x5F,
        BUTTON_8: 0x60,
        BUTTON_9: 0x61,
        BUTTON_UP: 0x57,
        BUTTON_DOWN: 0x56,
        BUTTON_LEFT: 0x55,
        BUTTON_RIGHT: 0x54,
        BUTTON_CENTER: 0x58,
    }
    return True


def run(view_manager) -> None:
    """Run the app and send numpad key presses.

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

    if button != -1:
        if button in _key_map:
            _usb.press(0, _key_map[button])


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
