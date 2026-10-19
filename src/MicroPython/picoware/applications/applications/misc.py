"""Miscellaneous SD utilities and demonstrations."""
_menu=None
_selected=0


def start(vm):
    global _menu
    from picoware.system.app_loader import AppLoader
    AppLoader.release(vm)  # unload closed SD apps
    from picoware.gui.menu import Menu
    _menu=Menu(vm.draw,'Misc',0,vm.draw.size.y,vm.foreground_color,
               vm.background_color,vm.selected_color)
    _menu.add_item('Screensavers')
    _menu.add_item('EngTool render benchmark')
    _menu.set_selected(_selected);_menu.draw();return True


def run(vm):
    from picoware.system import buttons as k
    if vm.button==k.BUTTON_ESCAPE:vm.back()
    elif vm.button in (k.BUTTON_UP,k.BUTTON_LEFT):_menu.scroll_up()
    elif vm.button in (k.BUTTON_DOWN,k.BUTTON_RIGHT):_menu.scroll_down()
    elif vm.button==k.BUTTON_CENTER:
        if _menu.current_item=='EngTool render benchmark':_open_sd_app(vm,'Benchmark','misc')
        else:
            from picoware.applications.library import launch
            launch(vm,_menu.current_item)


def _open_sd_app(vm,name,folder):
    """Open an SD app from picoware/apps/<folder>, keeping it out of the UF2."""
    from picoware.system.view import View
    try:module=vm.app_loader.load_app(name,folder)
    except (OSError,RuntimeError,ImportError) as exc:
        vm.alert('Insert an SD card with the GungOS apps.\n'+str(exc));return
    if module is None:
        vm.alert('Could not load '+name+': '+str(vm.app_loader.error));return
    view='app_'+folder+'_'+name
    if vm.get_view(view) is None:vm.add(View(view,module.run,module.start,module.stop))
    vm.switch_to(view)


def stop(vm):
    global _menu,_selected
    if _menu is not None:_selected=_menu.selected_index
    _menu=None
