"""Startup caches the extensible built-ins, and nothing shadows them.

Importing an "extensible" built-in such as array searches every sys.path
directory first; on the device that is SD card access, about 70 ms per
import. main._cache_builtins() looks each up once and stores it in
sys.modules. That is only correct while no file of the same name exists in
GungOS or its SD apps, which this test also checks.

Run with the desktop MicroPython build, from the project root.
"""
import os, sys
root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
import main

for name in main._CACHED_BUILTINS:
    sys.modules.pop(name, None)
main._cache_builtins()
cached = [name for name in main._CACHED_BUILTINS if name in sys.modules]
assert 'array' in cached and 'time' in cached and 'json' in cached, cached
for name in cached:
    assert not hasattr(sys.modules[name], '__file__'), name + ' was cached from a file'
from array import array
assert array('f', [1.5])[0] == 1.5
print('PASS: %d built-ins cached at startup (%s)' % (len(cached), ' '.join(cached)))


def top_level_modules(directory):
    """Module names importable from directory itself (not inside packages)."""
    names = []
    try:
        entries = os.listdir(directory)
    except OSError:
        return names
    for entry in entries:
        base, dot, ext = entry.rpartition('.')
        if dot and ext in ('py', 'mpy'):
            names.append(base)
        elif not dot:
            names.append(entry)  # a package directory
    return names


apps = root + '/builds/MicroPython/apps_unfrozen'
directories = [root + '/src/MicroPython', apps]
for entry in os.listdir(apps):  # app_loader adds each app folder to sys.path
    if '.' not in entry:
        directories.append(apps + '/' + entry)
for directory in directories:
    clash = sorted(set(top_level_modules(directory)) & set(main._CACHED_BUILTINS))
    assert not clash, '%s would be replaced by the cached built-in: %s' % (directory, clash)
print('PASS: no GungOS or SD-app module shadows a cached built-in (%d directories)' % len(directories))
