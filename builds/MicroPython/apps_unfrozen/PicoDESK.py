"""PicoDESK: independent productivity applications."""
HELP=('PicoDESK:','UP/DOWN\tchoose an app','ENTER\topen it','ESC\treturn')
_owner=None


def start(vm):
    global _owner
    from desktopapps.launcher import Launcher
    if _owner is None:_owner=Launcher()
    return _owner.start(vm)


def run(vm):
    if _owner is not None:_owner.run(vm)


def stop(vm):
    global _owner
    if _owner is not None:
        _owner.stop(vm)
        if not _owner.suspended:_owner=None
