"""Audible PCM preview; silent/headless tests create no sidecar."""
import os,struct
from time import ticks_ms,ticks_diff,sleep_ms
import sim_runtime

class Output:
    def __init__(self,rate):
        self.file=None;self.base='';self.frames=0
        try:self.start(rate)
        except Exception:
            self.stop();raise
    def start(self,rate):
        if sim_runtime.audio_mode!='real' or (sim_runtime.headless and not sim_runtime.viewer):return
        if not sim_runtime.build_native('tetris-audio'):raise RuntimeError('Could not build Tetris audio preview')
        binary=sim_runtime.native_helper_path('audio/tetris_pcm_player','tetris-audio')
        self.base=sim_runtime.sd_root+'/sim_audio_mix_tetris_'+str(ticks_ms())
        fifo=self.base+'.fifo'
        quote=sim_runtime._quote
        if os.system('mkfifo '+quote(fifo)):raise OSError('Could not create the audio pipe')
        command=quote(binary)+' '+quote(fifo)+' '+quote(self.base)+' '+str(rate)+' >'+quote(self.base+'.log')+' 2>&1 &'
        if os.system(command):raise OSError('Could not start the audio preview')
        deadline=ticks_ms()
        while ticks_diff(ticks_ms(),deadline)<5000:
            try:
                with open(self.base+'.status') as status:state=status.read()
                if 'state=error' in state:raise RuntimeError('Desktop audio device could not open; see '+self.base+'.log')
                if 'state=playing' in state:break
            except OSError:pass
            sleep_ms(10)
        else:
            with open(self.base+'.cmd','w') as f:f.write('stop\n')
            raise RuntimeError('Desktop audio startup timed out')
        self.file=open(fifo,'wb')
    def write(self,buffer):
        self.frames+=len(buffer)//2
        if self.file:
            self.file.write(struct.pack('<I',len(buffer)));self.file.write(buffer)
    def clear(self):
        if self.file:self.file.write(b'\0\0\0\0')
    def stop(self):
        if self.file:
            try:self.file.write(b'\xff\xff\xff\xff')
            except OSError:pass
            self.file.close();self.file=None
        if self.base:
            with open(self.base+'.cmd','w') as f:f.write('stop\n')
            try:os.remove(self.base+'.fifo')
            except OSError:pass
