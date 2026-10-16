"""Miscellaneous SD utilities and demonstrations."""
_menu=None
_selected=0


def start(vm):
    global _menu
    from picoware.gui.menu import Menu
    _menu=Menu(vm.draw,'Misc',0,vm.draw.size.y,vm.foreground_color,
               vm.background_color,vm.selected_color)
    _menu.add_item('Screensavers')
    _menu.set_selected(_selected);_menu.draw();return True


def run(vm):
    from picoware.system import buttons as k
    if vm.button==k.BUTTON_ESCAPE:vm.back()
    elif vm.button in (k.BUTTON_UP,k.BUTTON_LEFT):_menu.scroll_up()
    elif vm.button in (k.BUTTON_DOWN,k.BUTTON_RIGHT):_menu.scroll_down()
    elif vm.button==k.BUTTON_CENTER:
        from picoware.applications.library import launch
        launch(vm,_menu.current_item)


def stop(vm):
    global _menu,_selected
    if _menu is not None:_selected=_menu.selected_index
    _menu=None
