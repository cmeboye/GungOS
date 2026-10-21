"""System Menu - Central hub for system apps."""

_system = None
_system_index = 0
from picoware.gui.style import MENU_HELP as HELP

# Preserve the existing action IDs while removing rows from the visible menu.
_MENU_ACTIONS = (1, 3, 4)


def start(view_manager) -> bool:
    """Start the app and build the system menu.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the app started.
    """
    from picoware.gui.menu import Menu

    global _system
    if _system is None:
        _system = Menu(
            view_manager.draw,
            "System",
            0,
            view_manager.draw.size.y,
            view_manager.foreground_color,
            view_manager.background_color,
            view_manager.selected_color,
            view_manager.foreground_color,
            2,
        )
        _system.add_item("Info")
        _system.add_item("Restart")
        _system.add_item("Shutdown")

        _system.set_selected(
            _MENU_ACTIONS.index(_system_index) if _system_index in _MENU_ACTIONS else 0
        )

        _system.draw()
    return True


def run(view_manager) -> None:
    """Run the app and handle menu input.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from picoware.system.buttons import (
        BUTTON_ESCAPE,
        BUTTON_UP,
        BUTTON_DOWN,
        BUTTON_LEFT,
        BUTTON_CENTER,
        BUTTON_RIGHT,
    )

    global _system
    if not _system:
        return
    global _system_index

    button: int = view_manager.button

    if button in (BUTTON_UP, BUTTON_LEFT):
        _system.scroll_up()
    elif button in (BUTTON_DOWN, BUTTON_RIGHT):
        _system.scroll_down()
    elif button == BUTTON_ESCAPE:

        view_manager.back()
        _system_index = 0
    elif button == BUTTON_CENTER:
        activate(view_manager, _MENU_ACTIONS[_system.selected_index])


def activate(view_manager, index):
    """Run a system action from either menu layout."""
    global _system_index
    _system_index = index
    if _system_index in (0, 1):  # 0 was About, now part of Info
        from picoware.applications.system import system_info
        from picoware.system.view import View

        view_manager.add(
            View(
                "system_info", system_info.run, system_info.start, system_info.stop,
                system_info.HELP,
            )
        )
        view_manager.switch_to("system_info")
    elif _system_index == 2:
        from picoware.system.system import System

        system = System()
        system.bootloader_mode()
    elif _system_index == 3:
        from picoware.system.system import System

        system = System()
        system.hard_reset()
    elif _system_index == 4:
        if view_manager.choose("Shutdown?", ("No", "Yes")) == 1:
            from picoware.system.system import System

            System().shutdown_device(view_manager)
    elif _system_index == 5:
        inp = view_manager.input_manager
        inp.reset()
        view_manager.active = False

def stop(view_manager) -> None:
    """Stop the app and clean up.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from gc import collect

    global _system
    if _system:
        del _system
        _system = None
    collect()
