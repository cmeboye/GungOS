"""System Menu - Central hub for system apps."""

_system = None
_system_index = 0


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
        _system.add_item("About")
        _system.add_item("System Info")
        _system.add_item("Bootloader")
        _system.add_item("Restart")
        _system.add_item("Shutdown")
        _system.add_item("Stop")

        _system.set_selected(_system_index)

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
        activate(view_manager, _system.selected_index)


def activate(view_manager, index, redraw=None):
    """Run a system action from either menu layout."""
    global _system_index
    from picoware.system.buttons import BUTTON_LEFT, BUTTON_UP, BUTTON_RIGHT, BUTTON_DOWN, BUTTON_CENTER, BUTTON_ESCAPE
    _system_index = index
    if _system_index == 0:
        from picoware.applications.system import about
        from picoware.system.view import View

        view_manager.add(View("about", about.run, about.start, about.stop))
        view_manager.switch_to("about")
    elif _system_index == 1:
        from picoware.applications.system import system_info
        from picoware.system.view import View

        view_manager.add(
            View(
                "system_info", system_info.run, system_info.start, system_info.stop
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
        from picoware.gui.choice import Choice
        from picoware.system.vector import Vector

        choice = Choice(
            view_manager.draw,
            Vector(0, 0),
            view_manager.draw.size,
            "Shutdown?",
            ["No", "Yes"],
            0,
            view_manager.foreground_color,
            view_manager.background_color,
        )
        choice.draw()
        choice.open()
        inp = view_manager.input_manager
        inp.reset()
        from time import sleep_ms

        while True:
            _button = inp.button
            if _button == -1:
                sleep_ms(10)  # wait without spinning the CPU
                continue
            if _button in (BUTTON_LEFT, BUTTON_UP):
                inp.reset()
                choice.scroll_up()
            elif _button in (BUTTON_RIGHT, BUTTON_DOWN):
                inp.reset()
                choice.scroll_down()
            elif _button == BUTTON_CENTER:
                inp.reset()
                if choice.is_open():
                    choice.close()

                if choice.state == 1:
                    del choice
                    choice = None
                    from picoware.system.system import System

                    system = System()
                    system.shutdown_device(view_manager)
                    return
                view_manager.draw.clear()
                redraw() if redraw is not None else _system.draw()
                del choice
                choice = None
                break
            elif _button == BUTTON_ESCAPE:
                del choice
                choice = None
                inp.reset()
                view_manager.draw.clear()
                redraw() if redraw is not None else _system.draw()
                break
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
