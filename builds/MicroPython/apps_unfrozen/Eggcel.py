"""Eggcel standalone entry; also available through PicoDESK."""
_owner = None


def start(vm):
    global _owner
    from desktopapps.eggcel.app import Spreadsheet
    if _owner is None: _owner = Spreadsheet()
    return _owner.start(vm)


def run(vm):
    if _owner is not None:
        _owner.run(vm)


def stop(vm):
    global _owner
    if _owner is not None:
        _owner.stop(vm)
        if not _owner.suspended: _owner = None
