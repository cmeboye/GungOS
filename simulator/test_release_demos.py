"""Tetris rules/sound lifecycle and bounded Lorenz/native widget demos."""
import os,sys
from time import ticks_ms,ticks_add
root=os.getcwd()
for path in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen','builds/MicroPython/apps_unfrozen/games','builds/MicroPython/apps_unfrozen/misc/screensavers'):
    sys.path.insert(0,root+'/'+path)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/picoware-release-demos-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from picoware.system.settings import Settings
from picoware.system.storage import Storage
from engtools.system.sfx import Effects
import Tetris,Lorenz
Input.button=property(lambda self:self._last_button)
vm=ViewManager()
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
vm.add(View('tetris',Tetris.run,Tetris.start,Tetris.stop));vm.switch_to('tetris')
g=Tetris._game
g.bag=[]
assert sorted(g.piece() for _ in range(7))==list(range(7))
for piece in range(7):
    for rotation in range(4): assert len(set(Tetris.shape(piece,rotation)))==4
    assert Tetris.shape(piece,4)==Tetris.shape(piece)
g.current,g.x,g.y,g.rotation=2,0,4,1
assert not g.collides(g.x,g.y,g.rotation)
assert g.rotate() and not g.collides(g.x,g.y,g.rotation)
g.reset();assert g.hold() and g.hold_used and not g.hold()
g.hard_drop();assert not g.hold_used and g.score>0
g.reset()
for col in range(10):g.grid[190+col]=1 if col not in (4,5) else 0
g.current,g.x,g.y,g.rotation=1,3,18,0
g.lock();assert g.lines==1 and g.score==100 and g.sound.last_event=='clear'
g.reset()
for row in range(16,20):
    for col in range(10):g.grid[row*10+col]=1 if col!=5 else 0
g.current,g.x,g.y,g.rotation=0,3,16,1
g.lock();assert g.lines==4 and g.score==800 and g.sound.last_event=='tetris'
assert not any(g.grid)
g.reset();g.pause();old_y=g.y
g.run(k.BUTTON_NONE,ticks_add(ticks_ms(),5000));assert g.y==old_y
g.pause()
g.current,g.x,g.y,g.rotation=1,3,18,0
now=ticks_ms()
g.run(k.BUTTON_NONE,now)
assert g.lock_at==now
g.run(k.BUTTON_NONE,ticks_add(now,499));assert g.y==18
g.run(k.BUTTON_NONE,ticks_add(now,501));assert g.y==-1
g.reset();g.grid=bytearray([1]*200);g.spawn();assert g.over
g.run(k.BUTTON_CENTER);assert not g.over and not any(g.grid)
g.draw();vm.draw.screenshot('/private/tmp/picoware-tetris.bmp')
old=Storage.serialize
Storage.serialize=lambda *args,**kwargs:False
before=g.sound.enabled
try:assert not g.settings('tetris_sound',not before) and g.sound.enabled==before
finally:Storage.serialize=old
assert g.settings('tetris_sound',False)
assert Settings(vm.storage).settings['tetris_sound'] is False
g.sound.configure(True,25);g.sound.play('clear')
if g.sound.player:
    assert any(g.sound.voices)
    g.sound.tick()
else:
    # Public builds omit optional recordings; missing files must not end the game.
    assert g.sound.error and not g.sound.enabled
    g.draw();g.run(k.BUTTON_LEFT,ticks_ms());assert Tetris._game is g
g.sound.stop();assert g.sound.player is None and not any(g.sound.voices)
vm.back();assert Tetris._game is None
vm.add(View('lorenz',Lorenz.run,Lorenz.start,Lorenz.stop));vm.switch_to('lorenz')
for _ in range(100):
    Lorenz._next=0;vm._button=k.BUTTON_NONE;Lorenz.run(vm)
assert Lorenz._count==Lorenz.POINTS and len(Lorenz._trail)==Lorenz.POINTS*2
assert len(set(tuple(Lorenz._trail[i:i+2]) for i in range(0,len(Lorenz._trail),2)))>30
vm.draw.screenshot('/private/tmp/picoware-lorenz.bmp')
state=(Lorenz._x,Lorenz._y,Lorenz._z)
vm._button=k.BUTTON_SPACE;Lorenz.run(vm)
Lorenz._next=0;vm._button=k.BUTTON_NONE;Lorenz.run(vm)
assert state==(Lorenz._x,Lorenz._y,Lorenz._z)
vm.back();assert Lorenz._trail is None
print('PASS: seven-bag/SRS, hold, drops, line scoring, lock delay, pause/restart and sound cleanup')
print('PASS: explicit sound settings, bounded Lorenz trail, pause and resource release')
