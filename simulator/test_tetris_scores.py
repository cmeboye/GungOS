"""Internal-flash records survive game instances and never cross modes."""
import os, sys, json
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen', 'builds/MicroPython/apps_unfrozen/games'):
    sys.path.insert(0, root + '/' + part)
import sim_runtime
sd = '/private/tmp/gungos-tetris-scores-' + str(ticks_ms())
sim_runtime.configure(root, sd, root+'/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w', 0, True, False, False, False, '', _network_mode='offline', _audio_mode='silent', _sd_profile='clean')
from engtools.system.tetris_scores import Scores, flash_path
from engtools.system import tetris_scores as score_store
from picoware.system.view_manager import ViewManager
import Tetris

class Sound:
    def __init__(self, *args):self.error=''
    def silence(self):pass
    def restart(self):pass
    def play(self, event):pass
    def pause(self, value):pass
    def stop(self):pass

Tetris.Effects = Sound
vm = ViewManager(); vm._wifi = None
g = Tetris.Game(vm)
assert g.best == 0 and g.mode == 'Modern'
assert flash_path() == sd + '.flash/tetris_scores.json'
# Exit saves an unfinished run, including soft-drop points before a lock.
g.score = 1200; g.stop()
g = Tetris.Game(vm)
assert g.best == 1200 and g.score == 0
# Mode switch saves the outgoing score and loads the other record.
g.score = 1500
assert g.settings('tetris_mode', 'Classic')
g.reset()
assert g.best == 0 and g.score == 0
assert Scores().values == {'Modern':1500, 'Classic':0}
g.score = 300; g.end()
assert Scores().values == {'Modern':1500, 'Classic':300}
g.stop(); g = Tetris.Game(vm)
assert g.mode == 'Classic' and g.best == 300
# Restart and pause also preserve records without contaminating either mode.
g.score = 400; g.reset()
assert g.best == 400 and g.score == 0
g.score = 450; g.pause()
assert Scores().values['Classic'] == 450
assert g.settings('tetris_mode', 'Modern')
g.reset(); assert g.best == 1500

# A failed atomic replacement leaves the previous file intact, preserves the
# in-memory record, and retries successfully on the next save point.
real_os = score_store.os
calls = []
def broken_rename(source, target):
    calls.append((source, target))
    raise OSError('read-only flash')
class FailingFlash:
    rename = staticmethod(broken_rename)
    remove = staticmethod(real_os.remove)
score_store.os = FailingFlash
try:
    g.score = 2000; g.end()
    assert g.over and g.best == 2000 and 'internal flash' in g.error
    assert Scores().values == {'Modern':1500, 'Classic':450}
    g.reset()
    assert g.best == 2000 and g.error and g.score == 0
finally:
    score_store.os = real_os
assert len(calls) == 2
assert g.save_best() and not g.error
assert Scores().values == {'Modern':2000, 'Classic':450}
# Unchanged/lower scores do not touch flash at all.
class FailingFlash:
    rename = staticmethod(broken_rename)
    remove = staticmethod(real_os.remove)
score_store.os = FailingFlash
try:
    g.score = 50; g.stop()
    assert len(calls) == 2
finally:
    score_store.os = real_os

# Missing/malformed/non-integer records recover independently, not as crashes.
path = sim_runtime.flash_path('scores-test.json')
assert Scores(path).values == {'Modern':0, 'Classic':0}
for raw in ('{', '[]', '{"Modern":true,"Classic":-1}', '{"Modern":12.5,"Classic":"300"}'):
    with open(path, 'w') as handle:handle.write(raw)
    assert Scores(path).values == {'Modern':0, 'Classic':0}
with open(path, 'w') as handle:json.dump({'Modern':700, 'Classic':False}, handle)
scores = Scores(path)
assert scores.values == {'Modern':700, 'Classic':0}
scores.record('Classic', 900); assert scores.save()
assert Scores(path).values == {'Modern':700, 'Classic':900}
# A stale instance must not lower a newer record for the other mode.
a = Scores(path); b = Scores(path)
a.record('Modern', 1000); assert a.save()
b.record('Classic', 950); assert b.save()
assert Scores(path).values == {'Modern':1000, 'Classic':950}
print('Tetris persistent per-mode scores: PASS')
