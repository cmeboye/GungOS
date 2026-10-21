"""Select a desktop widget from the SD screensavers directory."""
from picoware.gui.style import MENU_HELP as HELP
_items=[]
_selected=0
_error=''

def start(vm):
    global _items,_selected,_error
    from picoware.system.settings import Settings
    from picoware.system.features import SCREENSAVER_DIRECTORIES
    _items=['None']+sorted(set(name for directory in SCREENSAVER_DIRECTORIES
                                for name in vm.app_loader.list_available_apps(directory)))
    saved=Settings(vm.storage).screensaver
    _selected=_items.index(saved) if saved in _items else 0
    _error=''
    draw(vm)
    return True

def draw(vm):
    from picoware.gui import style
    rows=[(name,'') for name in _items]
    style.menu(vm.draw,rows,_selected,'Settings / Screensaver / widget','GungOS',
               _error,palette=style.system_palette(vm),error=bool(_error))


def run(vm):
    global _selected,_error
    from picoware.system import buttons as k
    if vm.button == k.BUTTON_ESCAPE: vm.back(); return
    if vm.button in (k.BUTTON_UP,k.BUTTON_DOWN):
        _selected=(_selected+(-1 if vm.button==k.BUTTON_UP else 1))%len(_items)
        draw(vm)
    elif vm.button==k.BUTTON_CENTER:
        from picoware.system.settings import Settings
        name='' if _selected==0 else _items[_selected]
        if not Settings(vm.storage).update({'screensaver':name}):
            _error='Could not save selection. Check the SD card.'
            draw(vm)
        else: vm.back()

def stop(vm):
    global _items
    _items=[]
