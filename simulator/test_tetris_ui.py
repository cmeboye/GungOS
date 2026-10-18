"""Tetris mode/settings/help interactions, piece counts and bounded tile rendering."""
import os,sys
from time import ticks_ms,ticks_add,ticks_diff
root=os.getcwd()
for part in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen','builds/MicroPython/apps_unfrozen/games'):
    sys.path.insert(0,root+'/'+part)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-tetris-ui-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.settings import Settings
from picoware.system import buttons as k
from engtools.system.tetris_tiles import PALETTES,STYLES,PIXEL
import Tetris
class Sound:
    def __init__(self,enabled,volume,storage,music,fx):
        self.enabled,self.volume,self.music_enabled,self.effects_enabled=enabled,volume,music,fx
        self.paused=False;self.error='';self.last_event=''
    def silence(self):pass
    def restart(self):self.paused=False
    def pause(self,value):self.paused=value
    def play(self,event):self.last_event=event
    def tick(self,now=None):pass
    def configure(self,enabled,volume,music,fx):
        self.enabled,self.volume,self.music_enabled,self.effects_enabled=enabled,volume,music,fx
    def stop(self):self.enabled=False
Tetris.Effects=Sound
vm=ViewManager();vm._wifi=None
g=Tetris.Game(vm)
assert g.mode=='Modern' and g.next_count==3 and sum(g.counts)==1
assert g.hold() and sum(g.counts)==2
assert not g.hold() and sum(g.counts)==2
g.hard_drop();before=sum(g.counts)
assert g.hold() and sum(g.counts)==before
assert sum(g.counts)>=2

# Help suspends gravity, keeps state, scrolls and resumes the remaining delay.
g.reset();now=ticks_ms();g.drop_at=ticks_add(now,700)
old_drop=g.drop_at;old_y=g.y
before=(bytes(g.grid),tuple(g.counts),g.score)
g.run(k.BUTTON_F9,now);assert g.page=='help' and g.sound.paused
g.run(k.BUTTON_RIGHT,ticks_add(now,20000));assert g.help_first>0 and g.y==old_y
g.run(k.BUTTON_END,ticks_add(now,25000));assert g.help_first==len(g.help_lines())-g.help_capacity()
g.run(k.BUTTON_HOME,ticks_add(now,30000));assert g.help_first==0
g.run(k.BUTTON_F9,ticks_add(now,60000))
assert g.page=='game' and not g.sound.paused and ticks_diff(g.drop_at,old_drop)==60000
assert (bytes(g.grid),tuple(g.counts),g.score)==before
g.run(k.BUTTON_NONE,ticks_add(now,60001));assert g.y==old_y

# Nested help returns to the selected Settings row; saving is transactional.
g.run(k.BUTTON_F2,ticks_add(now,60002));g.settings_row=2
g.run(k.BUTTON_F9,ticks_add(now,60003));g.run(k.BUTTON_ESCAPE,ticks_add(now,60004))
assert g.page=='settings' and g.settings_row==2 and g.sound.paused
old_update=Settings.update
before_fx=g.fx_enabled
Settings.update=lambda *args:False
try:
    g.run(k.BUTTON_CENTER,ticks_add(now,60005))
    assert g.fx_enabled==before_fx and g.error
finally:Settings.update=old_update
g.run(k.BUTTON_CENTER,ticks_add(now,60006));assert g.fx_enabled!=before_fx
assert g.music_enabled and not g.fx_enabled
assert Settings(vm.storage).settings['tetris_music'] and not Settings(vm.storage).settings['tetris_sfx']

# Mode changes need confirmation. Cancel and failed saves keep the board.
g.settings_row=0;board=bytes(g.grid);counts=tuple(g.counts)
g.run(k.BUTTON_CENTER,ticks_add(now,60007));assert g.page=='restart' and g.confirm_row==1
g.run(k.BUTTON_ESCAPE,ticks_add(now,60008))
assert g.page=='settings' and g.mode=='Modern' and bytes(g.grid)==board
g.run(k.BUTTON_CENTER,ticks_add(now,60009));g.run(k.BUTTON_UP,ticks_add(now,60010))
Settings.update=lambda *args:False
try:
    g.run(k.BUTTON_CENTER,ticks_add(now,60011))
    assert g.mode=='Modern' and g.page=='restart' and tuple(g.counts)==counts
finally:Settings.update=old_update
g.run(k.BUTTON_CENTER,ticks_add(now,60012))
assert g.mode=='Classic' and g.page=='game' and g.next_count==1
assert sum(g.counts)==1 and not any(g.grid) and not g.hold() and g.held is None
assert Settings(vm.storage).settings['tetris_mode']=='Classic'
g.hard_drop();assert sum(g.counts)==2

# Restart cancellation from play must restore audio and the remaining timer.
now=ticks_ms();g.drop_at=ticks_add(now,800);old_drop=g.drop_at
g.run(k.BUTTON_F5,now);assert g.page=='restart' and g.sound.paused
g.run(k.BUTTON_ESCAPE,ticks_add(now,5000))
assert g.page=='game' and g.menu_started is None and not g.sound.paused
assert ticks_diff(g.drop_at,old_drop)==5000

# Opening a modal during a lock delay must not consume that delay.
g.reset();now=ticks_ms();g.current,g.rotation,g.x,g.y=1,0,3,18;g.lock_at=now
g.run(k.BUTTON_F2,ticks_add(now,200));g.run(k.BUTTON_ESCAPE,ticks_add(now,8000))
assert ticks_diff(g.lock_at,now)==7800
g.run(k.BUTTON_NONE,ticks_add(now,8299));assert g.y==18
g.run(k.BUTTON_NONE,ticks_add(now,8301));assert g.y==-1

g.reset();g.pause();now=ticks_ms()
g.run(k.BUTTON_F9,now);g.run(k.BUTTON_ESCAPE,ticks_add(now,2000))
assert g.paused and g.sound.paused
g.pause()

# Draw representative boards with all pieces and levels; palette changes do
# not change the board. Tile cache is bounded to current-level sizes.
preview='/private/tmp/gungos-tetris-previews';sim_runtime.mkdir_p(preview)
for piece,rows in enumerate(PIXEL):assert len(rows)==8 and all(len(row)==8 for row in rows)
for level,style in ((1,'Pixel'),(2,'Pixel'),(4,'Bevel'),(8,'Solid'),(11,'Pixel')):
    g.level=level;g.block_style=style
    g.grid=bytearray(200)
    for y in range(15,20):
        for x in range(10):
            if (x+y)%5:g.grid[y*10+x]=(x+y)%7+1
    before=bytes(g.grid);g.draw();assert bytes(g.grid)==before
    assert len(g.blocks.cache)<=21 and sum(len(data) for data in g.blocks.cache.values())<=4096
    assert g.blocks.colors==tuple(PALETTES[(level-1)%10][i] for i in (0,2,1,0,1,2,0))
    sim_runtime.lcd_screenshot(preview+'/level-'+str(level)+'-'+style+'.bmp')
for mode in Tetris.MODES:
    g.mode=mode;g.reset();g.draw();sim_runtime.lcd_screenshot(preview+'/'+mode+'.bmp')
g.run(k.BUTTON_F2);sim_runtime.lcd_screenshot(preview+'/settings.bmp')
g.run(k.BUTTON_F9);sim_runtime.lcd_screenshot(preview+'/help.bmp')
g.stop();fresh=Tetris.Game(vm)
assert fresh.mode=='Classic' and fresh.music_enabled and not fresh.fx_enabled
fresh.stop()
print('PASS: Modern/Classic hold/preview rules, piece accounting, restart confirmation and persistence')
print('PASS: scrollable contextual help, gravity/lock timer suspension, paused-state restoration and failed-save recovery')
print('PASS: original block assets, level palettes, render cache <=4 KiB and all three styles; screenshots:',preview)
