"""PicoIDE must not change files on open or save source over bytecode."""
import os, sys
from time import ticks_ms

root = os.getcwd()
for relative in ('src/MicroPython', 'simulator/hardware'):
    sys.path.insert(0, root+'/'+relative)

from picoware.system.drivers.pye import Editor
from picoware.applications.utilities import pico_ide


class Terminal:
    def wr(self, text): pass


class Storage:
    def __init__(self):
        self.files = {'program.mpy': b'M\x06\x00\x1f\xff\x80',
                      'bad.txt': b'\xff\xfe', 'binary.txt': b'abc\x00def',
                      'empty.py': b'', 'source.py': b'x = 2\nprint(x)\n',
                      'unreadable.py': b'original source'}
        self.writes = []
    def exists(self, path): return path in self.files
    def read(self, path, mode='r'):
        if path == 'unreadable.py' or path not in self.files: return ''
        data = self.files[path]
        return data if mode != 'r' else data.decode('utf-8')
    def write(self, path, text, mode='w'):
        self.writes.append(path)
        self.files[path] = text.encode('utf-8')
        return True


storage = Storage()
before = dict(storage.files)
editor = Editor(4, 50, Terminal(), storage)
for name in ('program.mpy', 'PROGRAM.MPY', 'bad.txt', 'binary.txt', 'unreadable.py'):
    try: editor.get_file(name)
    except (ValueError, UnicodeError, OSError): pass
    else: raise AssertionError('Accepted bytecode/binary/unreadable file: '+name)
    assert editor.fname == '' and editor.content == ['']
assert storage.files == before and not storage.writes
for name in ('empty.py', 'new.py'):
    editor.get_file(name)
    assert editor.content == [''] and not storage.writes
assert 'new.py' not in storage.files
editor.get_file('source.py')
assert editor.content == ['x = 2', 'print(x)']
editor.content = ['x = 3', 'print(x)']
for name in ('program.mpy', 'PROGRAM.MPY'):
    try: editor.put_file(name)
    except OSError: pass
    else: raise AssertionError('Allowed text Save As over bytecode')
assert storage.files == before and not storage.writes
editor.put_file('source.py')
assert storage.files['source.py'] == b'x = 3\nprint(x)\n'

# Direct filesystem fallback also rejects compiled files before opening/writing.
path = '/private/tmp/picoide-bytecode-'+str(ticks_ms())+'.mpy'
with open(path, 'wb') as handle: handle.write(before['program.mpy'])
try:
    direct = Editor(4, 50, Terminal())
    for operation in (direct.get_file, direct.put_file):
        try: operation(path)
        except (ValueError, OSError): pass
        else: raise AssertionError('Direct file access bypassed bytecode guard')
    with open(path, 'rb') as handle: assert handle.read() == before['program.mpy']
finally: os.remove(path)


class Context:
    def __init__(self): self.alerts = []
    def alert(self, message): self.alerts.append(message)


context = Context()
for name in ('picoware/apps/PicoLAB.mpy', '/sd/picoware/apps/PicoLAB.MPY'):
    pico_ide._editor_state = pico_ide.STATE_EDITOR
    pico_ide._file_browser = object()
    assert pico_ide._start_editor(context, name, create_template=True) is False
    assert pico_ide._editor_state == pico_ide.STATE_FILE_BROWSER
    assert pico_ide._file_browser is None and '.py source' in context.alerts[-1]
print('PASS: rejected .mpy open/Save As, failed reads, binary input and read-only opening')

# Render the actual terminal editor with readable source for visual inspection.
import sim_runtime
sim_runtime.configure(root, '/private/tmp/picoide-test-'+str(ticks_ms()),
                      root+'/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w',
                      0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.drivers.vt import vt
from picoware.system.view import View
from picoware.system.drivers import pye

vm = ViewManager()
vm.add(View('parent', lambda vm:None, lambda vm:True, lambda vm:None))
vm.switch_to('parent')
sample = 'picoware/ide-example.py'
assert vm.storage.write(sample, '# PicoIDE source example\nfrom math import sin, pi\n\ndef signal(t):\n    return sin(2 * pi * t)\n\nprint(signal(0.25))\n')
original = vm.storage.read(sample, 'rb')
terminal = vt(vm)
editor = Editor(4, 50, terminal, vm.storage)
editor.get_file(sample)
editor.total_lines = len(editor.content)
terminal.start_batch()
editor.redraw(True)
editor.display_window()
terminal.end_batch()
vm.draw.screenshot('/private/tmp/picoide-source-preview.bmp')
assert vm.storage.read(sample, 'rb') == original

# Creating an app must not replace an existing unreadable file with a template.
binary = 'picoware/binary.py'
assert vm.storage.write(binary, b'\xff\xfe\x00original', 'wb')
original = vm.storage.read(binary, 'rb')
old_edit = pye.pye_edit
try:
    pye.pye_edit = lambda *args, **kwargs: None
    pico_ide._start_editor(vm, binary, create_template=True)
finally: pye.pye_edit = old_edit
assert vm.storage.read(binary, 'rb') == original
print('PASS: terminal source rendering and existing-file template protection')
