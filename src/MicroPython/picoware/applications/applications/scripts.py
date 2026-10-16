"""Scripts - Python apps and the C, JavaScript, and MMBasic interpreters."""
_menu = None
_index = 0


def start(vm):
    global _menu
    from picoware.gui.menu import Menu
    from picoware.applications.library import SCRIPT_ITEMS
    _menu = Menu(vm.draw, "Scripts", 0, vm.draw.size.y, vm.foreground_color,
                 vm.background_color, vm.selected_color, vm.foreground_color, 2)
    for item in SCRIPT_ITEMS: _menu.add_item(item)
    _menu.set_selected(_index)
    _menu.draw()
    return True


def run(vm):
    global _index
    from picoware.system.buttons import BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT, BUTTON_CENTER, BUTTON_ESCAPE
    from picoware.applications.library import launch
    button = vm.button
    if button in (BUTTON_UP, BUTTON_LEFT): _menu.scroll_up()
    elif button in (BUTTON_DOWN, BUTTON_RIGHT): _menu.scroll_down()
    elif button == BUTTON_ESCAPE: vm.back()
    elif button == BUTTON_CENTER:
        _index = _menu.selected_index
        launch(vm, _menu.current_item)


def stop(vm):
    global _menu
    _menu = None
