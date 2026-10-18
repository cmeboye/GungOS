"""Strict mono WAV reader and fixed-buffer music/effects playback."""
import struct
from sys import platform

RATE=22050
FRAMES=512
TARGET=1536
ROOT='picoware/apps/games/tetris_sounds/'

class Wave:
    def __init__(self,path,loop=False):
        self.file=open(path,'rb')
        self.loop,self.position,self.closed=loop,0,False
        try:
            header=self.file.read(12)
            if len(header)!=12 or header[:4]!=b'RIFF' or header[8:]!=b'WAVE':
                name=path.rsplit('/',1)[-1]
                print('[Tetris WAV] '+name+' header='+repr(header)+' position='+str(self.file.tell()))
                raise ValueError('Invalid WAV header: '+name)
            self.file.seek(0,2);length=self.file.tell();self.file.seek(12)
            valid=False
            for _ in range(64):
                chunk=self.file.read(8)
                if len(chunk)!=8:raise ValueError('WAV data chunk is missing')
                name,size=chunk[:4],struct.unpack('<I',chunk[4:])[0]
                start=self.file.tell()
                if start+size>length:raise ValueError('Truncated WAV chunk')
                if name==b'fmt ':
                    if size<16:raise ValueError('Invalid WAV format')
                    fmt,channels,rate,byte_rate,align,bits=struct.unpack('<HHIIHH',self.file.read(16))
                    valid=(fmt,channels,rate,byte_rate,align,bits)==(1,1,RATE,RATE*2,2,16)
                    if not valid:raise ValueError('WAV must be mono/22050Hz/16-bit PCM')
                elif name==b'data':
                    if not valid or not size or size%2:raise ValueError('Invalid PCM data')
                    self.start,self.frames=start,size//2
                    break
                self.file.seek(start+size+(size&1))
                if self.file.tell()>16384:raise ValueError('WAV header exceeds the small-player limit')
            else:raise ValueError('Too many WAV header chunks')
        except Exception:
            self.file.close();self.file=None;self.closed=True;raise
    def seek(self,frame):
        frame=max(0,min(self.frames,int(frame)))
        self.file.seek(self.start+frame*2);self.position=frame
    def read_into(self,buffer,zero):
        buffer[:]=zero
        written,wraps=0,0
        view=memoryview(buffer)
        while written<len(buffer):
            if self.position>=self.frames:
                if not self.loop:break
                wraps+=1
                if wraps>32:raise ValueError('Music loop is too short')
                self.seek(0)
            count=min(len(buffer)-written,(self.frames-self.position)*2)
            got=self.file.readinto(view[written:written+count])
            if not got or got!=count:raise OSError('PCM file ended unexpectedly')
            written+=got;self.position+=got//2
        return written//2
    def close(self):
        if self.file:self.file.close();self.file=None
        self.closed=True

PRIORITY={'move':1,'rotate':1,'menu':2,'hold':2,'lock':2,'line_fall':2,
          'clear':3,'tetris':4,'level':4,'game_over':5}
EFFECTS=('menu','move','rotate','clear','tetris','level','game_over','line_fall','lock')

class Playback:
    def __init__(self,enabled=True,volume=25,storage=None,music_enabled=True,effects_enabled=True):
        self.enabled,self.volume=bool(enabled),max(0,min(100,int(volume)))
        self.storage=storage
        self.music_enabled,self.effects_enabled=bool(music_enabled),bool(effects_enabled)
        self.player,self.native,self.music,self.sink=None,None,None,None
        self.assets={}
        self.voices=[None,None];self.priorities=[0,0];self.pending=[]
        self.buffers=[];self.zero=None
        self.paused=False;self.music_active=True
        self.last_event='';self.error=''
        self.blocks_written=0
    def path(self,name):
        path=ROOT+name+'.wav'
        if platform in ('darwin','linux','win32'):
            import sim_runtime
            host=sim_runtime.host_path(path)
            if sim_runtime._exists(host):return host
            return sim_runtime.app_source_path(path)
        if self.storage is None or not self.storage.mount_vfs():raise OSError('Audio requires an SD card')
        return self.storage.vfs_prefix+'/'+path
    def ensure(self):
        if self.player and (not self.music_enabled or self.music is not None) and (not self.effects_enabled or self.assets):return
        from gc import collect,mem_free
        collect()
        if mem_free()<96*1024:raise MemoryError('Not enough heap for PCM audio and the UI reserve')
        try:import picoware_pcm
        except ImportError:raise RuntimeError('Tetris audio needs the new PCM firmware')
        self.native=picoware_pcm
        if not self.buffers:
            self.buffers=[bytearray(FRAMES*2) for _ in range(4)]
            self.zero=bytes(FRAMES*2)
        if self.music_enabled and self.music is None:self.music=Wave(self.path('music'),True)
        # Validate once and retain streaming readers. Repeated keys never reopen
        # files; the two voices refer to these readers, not independent handles.
        if self.effects_enabled:
            for name in EFFECTS:
                if name not in self.assets:self.assets[name]=Wave(self.path(name))
        if self.player is None:self.player=self.native.Player(RATE)
        if platform in ('darwin','linux','win32') and self.sink is None:
            import sim_tetris_audio
            self.sink=sim_tetris_audio.Output(RATE)
        self.error=''
    def rewind_queued(self):
        if self.player:
            queued=self.player.queued()
            if self.music and self.music_active and self.music_enabled and queued:
                self.music.seek((self.music.position-queued)%self.music.frames)
            self.player.clear()
            if self.sink:self.sink.clear()
    def silence(self):
        self.rewind_queued()
        self.voices=[None,None];self.priorities=[0,0]
        self.pending=[]
    def restart(self):
        self.silence();self.paused=False;self.music_active=True;self.error=''
        if self.music:self.music.seek(0)
        if self.enabled and self.volume:
            try:
                if self.music_enabled:
                    self.ensure();self.music.seek(0)
                self.tick()
            except Exception as exc:self.fail(exc)
    def pause(self,paused=True):
        self.silence();self.paused=bool(paused)
        if not self.paused:self.tick()
    def configure(self,enabled,volume,music_enabled=None,effects_enabled=None):
        self.silence()
        self.enabled,self.volume=bool(enabled),max(0,min(100,int(volume)))
        if music_enabled is None and effects_enabled is None:
            music_enabled=effects_enabled=bool(enabled)
        if music_enabled is not None:self.music_enabled=bool(music_enabled)
        if effects_enabled is not None:self.effects_enabled=bool(effects_enabled)
        if self.enabled and self.volume:self.tick()
    def play(self,event,from_queue=False):
        self.last_event=event
        if event=='game_over':self.silence();self.music_active=False
        if not self.enabled or not self.effects_enabled or not self.volume or self.paused or event not in PRIORITY:return
        try:
            self.ensure()
            if event=='game_over':
                self.silence();self.music_active=False
            elif event=='level' and any(v and p>=3 for v,p in zip(self.voices,self.priorities)):
                if len(self.pending)<4:self.pending.append(event)
                return
            if PRIORITY[event]<3 and not from_queue and (self.pending or any(v and p>=3 for v,p in zip(self.voices,self.priorities))):return
            voice=self.assets['menu' if event=='hold' else event]
            # Retrigger an existing effect in its own slot; a reader must never
            # be advanced by both voices in the same mixing block.
            slot=next((i for i,v in enumerate(self.voices) if v is voice),None)
            if slot is None:slot=next((i for i,v in enumerate(self.voices) if v is None),None)
            if slot is None:
                slot=0 if self.priorities[0]<=self.priorities[1] else 1
                if self.priorities[slot]>PRIORITY[event]:return
            voice.seek(0)
            self.voices[slot]=voice
            self.priorities[slot]=PRIORITY[event]
            if event in ('clear','tetris') and len(self.pending)<4:self.pending.append('line_fall')
        except Exception as exc:self.fail(exc)
    def tick(self,now=None):
        if not self.enabled or not self.volume or self.paused:return
        if not self.music_enabled and not any(self.voices) and not self.pending:return
        try:
            self.ensure()
            for _ in range(4):
                if self.player.queued()>=TARGET:break
                if self.pending and not any(self.voices):
                    self.play(self.pending.pop(0),True)
                    if self.player is None:return
                if not (self.music_active and self.music_enabled) and not any(self.voices):break
                music,a,b,out=self.buffers
                music_data=None
                if self.music_active and self.music_enabled:self.music.read_into(music,self.zero);music_data=music
                fx=[None,None]
                important=any(v and p>=3 for v,p in zip(self.voices,self.priorities))
                for i,buffer in enumerate((a,b)):
                    voice=self.voices[i]
                    if voice:
                        voice.read_into(buffer,self.zero);fx[i]=buffer
                        if voice.position>=voice.frames:
                            self.voices[i]=None;self.priorities[i]=0
                self.native.mix_into(out,music_data,fx[0],fx[1],self.volume,18 if important else 40)
                if self.player.write(out)!=FRAMES:raise RuntimeError('PCM queue unexpectedly filled')
                if self.sink:self.sink.write(out)
                self.blocks_written+=1
        except Exception as exc:self.fail(exc)
    def fail(self,exc):
        if platform in ('darwin','linux','win32'):
            from sys import print_exception
            print_exception(exc)
        self.error=str(exc);self.stop();self.enabled=False
    def stop(self):
        for voice in self.assets.values():voice.close()
        self.assets={}
        self.voices=[None,None];self.priorities=[0,0];self.pending=[]
        if self.music:self.music.close();self.music=None
        if self.player:self.player.stop();self.player=None
        if self.sink:self.sink.stop();self.sink=None
        self.buffers=[];self.zero=None
