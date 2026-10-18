"""PCM mixing, WAV validation, music lifecycle and bounded effect sequencing."""
import os,sys,struct,json,gc
from time import ticks_ms,sleep_ms
root=os.getcwd()
for path in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+path)
import picoware_pcm as native
from engtools.system.pcm import Wave,Playback,FRAMES

def pack(values):return struct.pack('<'+'h'*len(values),*values)
def unpack(data):return struct.unpack('<'+'h'*(len(data)//2),data)
def trunc(value,denominator):return (abs(value)//denominator)*(-1 if value<0 else 1)
music=pack((32767,-32768,15000,-15000))
effect=pack((32767,-32768,-15000,15000))
out=bytearray(8)
for volume,gain in ((100,100),(25,40),(100,0),(0,100)):
    native.mix_into(out,music,effect,effect,volume,gain)
    expected=[max(-32768,min(32767,trunc((a*gain+2*b*64)*volume,10000))) for a,b in zip(unpack(music),unpack(effect))]
    assert list(unpack(out))==expected
for args in ((out,music[:2],None,None,100,40),(out,music,None,None,101,40),(bytearray(4098),None,None,None,100,40)):
    try:native.mix_into(*args)
    except ValueError:pass
    else:raise AssertionError('Invalid mixer input accepted')
p=native.Player(22050)
assert p.write(bytes(2048))==1024 and 0<=p.queued()<=1024
try:native.Player(22050)
except RuntimeError:pass
else:raise AssertionError('Two physical PCM owners accepted')
gc.collect();assert p.write(bytes(2))==1
p.stop();assert p.queued()==0
try:p.write(bytes(2))
except RuntimeError:pass
else:raise AssertionError('Stopped player accepted samples')
p=native.Player(22050);del p;gc.collect()
p=native.Player(22050);p.stop()
print('PASS: native PCM saturation/gains, buffer validation, singleton and GC cleanup')

temporary='/private/tmp/gungos-wav-fixture-'+str(ticks_ms())+'.wav'
def wav(data,channels=1,rate=22050):
    fmt=struct.pack('<HHIIHH',1,channels,rate,rate*channels*2,channels*2,16)
    junk=b'JUNK'+struct.pack('<I',1)+b'x\0'
    body=b'WAVE'+junk+b'fmt '+struct.pack('<I',16)+fmt+b'data'+struct.pack('<I',len(data))+data
    return b'RIFF'+struct.pack('<I',len(body))+body
data=pack((1,-2,3,-4))
with open(temporary,'wb') as f:f.write(wav(data))
reader=Wave(temporary,True);buf=bytearray(16);reader.read_into(buf,bytes(16))
assert unpack(buf)==(1,-2,3,-4,1,-2,3,-4)
reader.close()
for bad in (wav(data,2),wav(data,1,44100),wav(data)[:-1],b'not WAV'):
    with open(temporary,'wb') as f:f.write(bad)
    try:Wave(temporary)
    except ValueError:pass
    else:raise AssertionError('Unsupported/truncated WAV accepted')
os.remove(temporary)

import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-pcm-tests-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
vm=ViewManager()
fixture_dir=sim_runtime.sd_root+'/generated-audio'
os.mkdir(fixture_dir)
for name in ('music',)+tuple(__import__('engtools.system.pcm',None,None,('EFFECTS',)).EFFECTS):
    # A long loop and short cues exercise the player without shipped recordings.
    frames=pack((1200,-1200,600,-600))*(22050*90//4 if name=='music' else 512)
    with open(fixture_dir+'/'+name+'.wav','wb') as f:f.write(wav(frames))
del frames
gc.collect()
Playback.path=lambda self,name:fixture_dir+'/'+name+'.wav'
gc.collect();before=gc.mem_alloc()
sound=Playback(True,25,vm.storage);sound.restart()
assert sound.player and not sound.error,sound.error
assert sound.music.frames>22050*89
assert sound.blocks_written>=3 and sound.music.position<FRAMES*5
assert len(sound.buffers)==4 and all(len(buf)==1024 for buf in sound.buffers)
assert len(sound.assets)==9
gc.collect();delta=gc.mem_alloc()-before
assert delta<64*1024,delta
# The original recording starts quietly; examine a full second, not just startup.
audible=False
for _ in range(15):
    sound.player.clear();sound.tick()
    audible=audible or any(unpack(sound.buffers[3]))
assert audible
# Gameplay must use the validated readers without opening any new WAVs.
original_init=Wave.__init__
def reject_reopen(*args):raise AssertionError('Effect reopened during gameplay')
Wave.__init__=reject_reopen
try:
    readers=list(sound.assets.values())
    for cycle in range(300):
        for event in ('move','rotate','hold','lock','clear','tetris','level'):
            sound.silence();sound.play(event)
            voice=next(v for v in sound.voices if v)
            sound.play(event)
            assert sum(v is voice for v in sound.voices)==1
            sound.player.clear();sound.tick()
            assert not sound.error,sound.error
        if cycle%10==0:gc.collect()
    sound.pause(True);sound.pause(False)
    sound.configure(False,25);sound.configure(True,25)
    sound.play('game_over');sound.restart()
    assert not sound.error
    assert all(not reader.closed for reader in readers)
finally:Wave.__init__=original_init
sound.silence()
sound.play('clear');sound.play('level')
assert sound.pending==['line_fall','level']
seen=[]
for _ in range(40):
    for voice,priority in zip(sound.voices,sound.priorities):
        if voice and priority not in seen:seen.append(priority)
    sound.player.clear();sound.tick()
assert 3 in seen and 2 in seen and 4 in seen,seen
assert not any(sound.voices) and not sound.pending
sound.pause(True)
position=sound.music.position;blocks=sound.blocks_written
sound.tick();assert sound.music.position==position and sound.blocks_written==blocks
sound.pause(False);assert sound.blocks_written>blocks
sound.configure(False,25);position=sound.music.position
sound.tick();assert sound.music.position==position
sound.configure(True,25);sound.play('game_over')
assert not sound.music_active
sound.stop();assert sound.player is None and sound.music is None and not sound.buffers
assert not sound.assets and all(reader.closed for reader in readers)
# Separate channels: disabled categories need no files/readers and never advance.
music_only=Playback(True,25,vm.storage,music_enabled=True,effects_enabled=False)
music_only.restart()
assert music_only.player and music_only.music and not music_only.assets
position=music_only.music.position
music_only.play('clear')
assert not any(music_only.voices) and not music_only.pending
music_only.play('game_over')
assert not music_only.music_active and music_only.player.queued()==0
music_only.stop()
fx_only=Playback(True,25,vm.storage,music_enabled=False,effects_enabled=True)
fx_only.restart()
assert fx_only.music is None and fx_only.player is None
fx_only.play('clear');fx_only.tick()
assert fx_only.player and fx_only.music is None and fx_only.assets and not fx_only.error
fx_only.configure(True,25,music_enabled=True,effects_enabled=False)
assert fx_only.music and fx_only.music_enabled and not fx_only.effects_enabled
fx_only.restart()
position=fx_only.music.position
fx_only.configure(True,25,music_enabled=False,effects_enabled=True)
position=fx_only.music.position
fx_only.play('move');fx_only.player.clear();fx_only.tick()
assert fx_only.music.position==position and not fx_only.error
fx_only.configure(False,25,music_enabled=False,effects_enabled=False)
assert not fx_only.enabled and not any(fx_only.voices) and not fx_only.pending
fx_only.stop()
print('PASS: music-only, FX-only, live channel changes, silent game-over and disabled-channel resource isolation')
missing=Playback(True,25,vm.storage)
original_path=missing.path
missing.path=lambda name:'/private/tmp/gungos-audio-does-not-exist.wav'
missing.restart();assert missing.error and missing.player is None and not missing.enabled
missing.path=original_path
missing.configure(True,25);assert missing.player and not missing.error and missing.enabled
missing.stop()
# A corrupt later asset must close every reader opened before it, without
# claiming native output or waiting for that particular gameplay event.
with open(temporary,'wb') as f:f.write(b'broken WAV header')
bad=Playback(True,25,vm.storage);original_path=bad.path;opened=[]
bad.path=lambda name:temporary if name=='rotate' else original_path(name)
def track_open(self,*args):
    original_init(self,*args);opened.append(self)
Wave.__init__=track_open
try:bad.restart()
finally:Wave.__init__=original_init
assert bad.error.startswith('Invalid WAV header:') and not bad.enabled
assert not bad.assets and bad.music is None and bad.player is None
assert len(opened)==3 and all(reader.closed for reader in opened)
os.remove(temporary)
print('PASS: generated WAV metadata/padding/truncation, bounded playback and <64 KiB live audio allocation')
print('PASS: PCM music/effect sequence, pause/mute/resume, game over, missing assets and cleanup')
print('PASS: 4200 effect triggers without WAV reopens, retrigger isolation and cached-reader cleanup')
print('PASS: corrupt effect rejected at startup; partially opened readers released')
