"""Crash summaries, multi-line alerts, idle key waits and fatal-error recovery.

Run from the repo root with builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_error_reporting.py.
"""

import os
import sys
from time import ticks_ms

root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
import sim_runtime
sd_root = '/private/tmp/gungos-error-regression-' + str(ticks_ms())
sim_runtime.configure(root, sd_root, root + '/builds/MicroPython/apps_unfrozen',
                      1, 'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent')
sim_runtime.mkdir_p(sd_root)
from picoware.system.view_manager import ViewManager
from picoware.system.view import View, CRASH_LOG_PATH
from picoware.system.input import Input
from picoware.system import buttons as k

# Idle polls (-1) come first so the wait loop must sleep and keep polling.
pending = []
def scripted_button(self):
    if self._last_button == -1 and pending:
        self._last_button = pending.pop(0)
    return self._last_button
Input.button = property(scripted_button)

vm = ViewManager()
vm._wifi = None

# The alert wait loop ignores idle polls and reports Escape as "denied".
pending[:] = [-1, -1, -1, k.BUTTON_ESCAPE]
assert vm.alert('Escape cancels') is False
pending[:] = [-1, k.BUTTON_CENTER]
assert vm.alert('Any other key confirms') is True

# Alerts honour newlines instead of joining every word onto one line.
drawn = []
original_text = vm.draw._text
vm.draw._text = lambda x, y, text, color, *rest: drawn.append((y, text))
pending[:] = [k.BUTTON_CENTER]
vm.alert('first line\nsecond line', title='Title')
vm.draw._text = original_text
rows = [text for y, text in sorted(drawn) if text not in ('Title', 'Any key continues')]
assert rows == ['first line', 'second line'], rows

# A crashing view reports the exception and its innermost file and line.
alerts = []
vm.alert = lambda message, back=False, title='Alert': alerts.append((title, message)) or True
def crash(view_manager):
    return 1 // 0
vm.add(View('home', lambda v: None, lambda v: True, lambda v: None))
vm.switch_to('home')
vm.add(View('crashy', crash, lambda v: True, lambda v: None))
vm.switch_to('crashy')
vm._button = -1
vm.run()
assert vm.current_view.name == 'home', 'A crashing view must return to the previous view'
title, message = alerts[-1]
assert title == 'App error', title
assert 'crashy failed while running.' in message, message
assert 'ZeroDivisionError' in message, message
assert 'At simulator/test_error_reporting.py, line ' in message, message
assert 'Details: ' + CRASH_LOG_PATH in message, message
saved = vm.storage.read(CRASH_LOG_PATH)
assert saved.startswith('View: crashy (running)') and 'Traceback' in saved and 'ZeroDivisionError' in saved

# Fatal errors: the traceback is saved and the user's choice is returned.
namespace = {'__name__': 'gungos_main_under_test'}
with open(root + '/src/MicroPython/main.py') as handle:
    exec(handle.read(), namespace)
report = namespace['_report_fatal']
vm.alert = lambda message, back=False, title='Alert': alerts.append((title, message)) or True
assert report(vm, ValueError('boom')) is True
title, message = alerts[-1]
assert title == 'Critical error' and 'boom' in message and 'Esc stops at the REPL' in message
assert 'ValueError: boom' in vm.storage.read(namespace['CRASH_LOG_PATH'])
vm.alert = lambda message, back=False, title='Alert': False
assert report(vm, ValueError('stay')) is False
assert report(None, ValueError('no display')) is False
print('PASS: crash summaries with file/line, saved tracebacks, multi-line alerts, idle waits and fatal restart choice')
