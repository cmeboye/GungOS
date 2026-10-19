"""Main menu with categories and submenus side by side."""

CATEGORIES = ("Apps", "System", "Comms", "Utils")
APP_ITEMS = ("PicoDESK", "PicoLAB", "Games", "Misc")
SYSTEM_ITEMS = ("Settings", "About", "System Info", "Restart", "Shutdown")
COMMS_ITEMS = ("Bluetooth", "USB", "WiFi")
UTIL_ITEMS = ("File Manager", "PicoIDE", "Python REPL", "Serial Terminal", "SSH Terminal")
SCRIPT_ITEMS = ("Python Apps",)
SECTIONS = (APP_ITEMS, SYSTEM_ITEMS, COMMS_ITEMS, UTIL_ITEMS)

_library = None
_library_state = None

_ROUTES = {
    "Misc": ("misc", "picoware.applications.applications.misc"),
    "Games": ("games", "picoware.applications.applications.games.games"),
    "Screensavers": ("screensavers", "picoware.applications.applications.screensavers"),
    "Python Apps": ("custom", "picoware.applications.applications.custom"),
    "Settings": ("settings", "picoware.applications.settings"),
    "About": ("about", "picoware.applications.system.about"),
    "System Info": ("system_info", "picoware.applications.system.system_info"),
    "Bluetooth": ("bluetooth", "picoware.applications.bluetooth.bluetooth"),
    "USB": ("usb", "picoware.applications.usb.usb"),
    "WiFi": ("wifi", "picoware.applications.wifi.wifi"),
    "File Manager": ("file_manager", "picoware.applications.utilities.file_manager"),
    "PicoIDE": ("ide", "picoware.applications.utilities.pico_ide"),
    "Python REPL": ("repl", "picoware.applications.utilities.repl"),
    "Serial Terminal": ("serial", "picoware.applications.utilities.serial"),
    "SSH Terminal": ("ssh", "picoware.applications.utilities.ssh"),
}


def launch(view_manager, item):
    """Open an existing feature without importing the other menu features."""
    from picoware.system.view import View
    from picoware.system.features import RELEASE_APPS
    if item in RELEASE_APPS:
        try:
            module=view_manager.app_loader.load_app(item)
        except (OSError,RuntimeError,ImportError) as exc:
            view_manager.alert('Insert an SD card with the GungOS apps.\n'+str(exc))
            return
        if module is None:
            view_manager.alert('Could not load '+item+': '+str(view_manager.app_loader.error))
            return
        name='app_'+item
        if view_manager.get_view(name) is None:
            view_manager.add(View(name,module.run,module.start,module.stop))
        view_manager.switch_to(name)
        return
    if item in ("Restart", "Shutdown"):
        from picoware.applications.system import system
        system.activate(view_manager, 3 if item == "Restart" else 4,
                        _library.draw if _library else None)
        return
    route = _ROUTES.get(item)
    if route is None:
        view_manager.alert("Feature unavailable in this firmware.")
        return
    name, path = route
    if view_manager.get_view(name) is None:
        module = __import__(path, None, None, ["start"])
        view_manager.add(View(name, module.run, module.start, module.stop))
    view_manager.switch_to(name)


def start(view_manager):
    global _library
    from picoware.system.app_loader import AppLoader
    AppLoader.release(view_manager)  # unload closed SD apps
    from picoware.gui.split_menu import SplitMenu
    _library = SplitMenu(view_manager, CATEGORIES, SECTIONS)
    if _library_state is not None:
        category, indices, focus, nested, nested_index = _library_state
        _library.category = category
        _library.indices = indices[:]
        _library.focus_right = focus
        if nested:
            _library.nested_items = SCRIPT_ITEMS
            _library.nested_title = "Scripts"
            _library.nested_index = nested_index
    _library.draw()
    return True


def run(view_manager):
    global _library_state
    from picoware.system.buttons import BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT, BUTTON_CENTER, BUTTON_ESCAPE
    button = view_manager.button
    if button == BUTTON_UP:
        _library.move(-1)
    elif button == BUTTON_DOWN:
        _library.move(1)
    elif button == BUTTON_LEFT:
        _library.focus_right = False
        _library.nested_items = None
        _library.draw()
    elif button == BUTTON_RIGHT or (button == BUTTON_CENTER and not _library.focus_right):
        _library.focus_right = True
        _library.draw()
    elif button == BUTTON_ESCAPE:
        if not _library.back():
            _library_state = None
            view_manager.back()
    elif button == BUTTON_CENTER:
        item = _library.current_item
        if item == "Scripts":
            _library.open_submenu("Scripts", SCRIPT_ITEMS)
        else:
            launch(view_manager, item)


def stop(view_manager):
    global _library, _library_state
    if _library is not None:
        _library_state = (_library.category, _library.indices[:], _library.focus_right,
                          _library.nested_items is not None, _library.nested_index)
    _library = None
