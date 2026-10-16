"""Apps - Compact entry point for application categories."""
_applications = None
_applications_index = 0


def start(vm):
    global _applications
    from picoware.gui.menu import Menu
    from picoware.applications.library import APP_ITEMS
    _applications = Menu(vm.draw, "Apps", 0, vm.draw.size.y, vm.foreground_color,
                         vm.background_color, vm.selected_color, vm.foreground_color, 2)
    for item in APP_ITEMS:
        _applications.add_item(item)
    _applications.set_selected(_applications_index)
    _applications.draw()
    return True


def run(vm):
    global _applications_index
    from picoware.system.buttons import BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT, BUTTON_CENTER, BUTTON_ESCAPE
    from picoware.applications.library import launch
    button = vm.button
    if button in (BUTTON_UP, BUTTON_LEFT): _applications.scroll_up()
    elif button in (BUTTON_DOWN, BUTTON_RIGHT): _applications.scroll_down()
    elif button == BUTTON_ESCAPE: vm.back()
    elif button == BUTTON_CENTER:
        _applications_index = _applications.selected_index
        if _applications.current_item == "Scripts":
            from picoware.applications.applications import scripts
            from picoware.system.view import View
            if vm.get_view("scripts") is None:
                vm.add(View("scripts", scripts.run, scripts.start, scripts.stop))
            vm.switch_to("scripts")
        else:
            launch(vm, _applications.current_item)


def stop(vm):
    global _applications
    _applications = None
