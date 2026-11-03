"""JPEG input protocol, allocation paths, EOF, failure and cleanup regression tests."""
import os,sys,io
root=os.getcwd()
for part in ('src/MicroPython','simulator/hardware'):
    sys.path.insert(0,root+'/'+part)
from picoware.gui.jpeg import JPEG
import picoware.gui.jpeg as module


def header(width=31,height=17,size=10000):
    # SOI and a valid baseline SOF marker; the transport mock owns the scan data.
    first=bytes((255,216,255,192,0,11,8,height>>8,height&255,width>>8,width&255,1,1,17,0))
    return first+bytes((i%251 for i in range(size-len(first))))


class Reader:
    def __init__(self,data,chunk=99999):self.data=data;self.pos=0;self.chunk=chunk;self.seeks=0;self.reads=0
    def seek(self,pos):self.pos=pos;self.seeks+=1
    def readinto(self,buf):
        count=min(len(buf),self.chunk,len(self.data)-self.pos)
        buf[:count]=self.data[self.pos:self.pos+count];self.pos+=count;self.reads+=1
        return count


class Transport(JPEG):
    def __init__(self,data,success=True):
        super().__init__(buffer_size=2048)
        self.data=data;self.success=success;self.started=0;self.stopped=0;self.ranges=[];self.next=0
        self.native_headers=0;self.direct=None
    def getinfo(self,buf):self.native_headers+=1;return self._dimensions(buf)
    def decode_opt(self,data,offset,clip,option):
        self.direct=(data,offset,clip,option);return (self.success,31,17)
    def decode_split(self,size,buf,offset,clip,option):
        self.started+=1;self.size=size;self.next=len(buf);self.ranges=[]
        assert bytes(buf)==self.data[:len(buf)]
        return (True,31,17,False)
    def decode_split_buffer(self,index,pos,buf):
        assert 0<=index<2 and pos<len(self.data) and 0<len(buf)<=len(self.data)-pos
        assert bytes(buf)==self.data[pos:pos+len(buf)],(pos,len(buf))
        self.ranges.append((pos,pos+len(buf)));return True
    def decode_split_wait(self):
        while True:
            found=next((high for low,high in self.ranges if low<=self.next<high),None)
            if found is None:break
            self.next=found
        if self.next>=self.size:return (1,1 if self.success else 0,0,0)
        return (0,self.next,min(2048,self.size-self.next),0)
    def decode_core_wait(self,timeout=0):self.stopped+=1;return (False,0,0,0)


for size in (15,257,2048,2049,4095,4096,4097,10000):
    data=header(size=size);jpeg=Transport(data);reader=Reader(data,137)
    assert jpeg._decode_split(reader,len(data),0,0)
    assert reader.seeks==1,(size,reader.seeks)
    assert reader.pos==len(data) and not jpeg._decoder_running
    assert jpeg.native_headers==0 and jpeg.started==1
    jpeg.close();jpeg.close()
for invalid in ((1,8192),(3,8192),(2,1024)):
    try:JPEG(buffer_num=invalid[0],buffer_size=invalid[1])
    except ValueError:pass
    else:raise AssertionError('Invalid stream buffer configuration')
# Native failure must not be reported as a successful header initialization.
jpeg=Transport(header(),False)
assert not jpeg._decode_split(Reader(jpeg.data),len(jpeg.data),0,0)
assert jpeg.last_error and not jpeg._decoder_running
# Buffer callers borrow input and avoid all split buffers / BytesIO copies.
data=header(size=1000);jpeg=Transport(data)
assert jpeg.draw_buffer(0,0,data) and jpeg.direct[0] is data
assert jpeg._filebuffer is None and jpeg.started==0
jpeg.close();assert not jpeg.draw_buffer(0,0,data)
# Reusing a decoder resets stale offsets and last-block lengths.
jpeg=Transport(header(size=10000))
assert jpeg._decode_split(Reader(jpeg.data),len(jpeg.data),0,0)
jpeg.data=header(size=2051)
assert jpeg._decode_split(Reader(jpeg.data,31),len(jpeg.data),0,0)
assert jpeg._buffers_len[1]==3
# A broken read must leave the worker marked active until cancellation.
jpeg=Transport(header())
try:jpeg._decode_split(Reader(jpeg.data[:2200]),len(jpeg.data),0,0)
except OSError:pass
else:raise AssertionError('Truncated input accepted')
assert jpeg._decoder_running
jpeg._cleanup();assert jpeg.stopped==1 and not jpeg._decoder_running
# An exception returning the native launch tuple also needs cancellation.
class LaunchFailure(Transport):
    def decode_split(self,*args):raise MemoryError('launch result tuple')
jpeg=LaunchFailure(header());
try:jpeg._decode_split(Reader(jpeg.data),len(jpeg.data),0,0)
except MemoryError:pass
jpeg._cleanup();assert jpeg.stopped==1
# Older firmware keeps the bounded header probe to avoid a core-0 input wait.
module.jpegdec.SPLIT_PREFIX_SAFE=False
jpeg=Transport(header());assert jpeg._decode_split(Reader(jpeg.data),len(jpeg.data),0,0)
assert jpeg.native_headers==1
module.jpegdec.SPLIT_PREFIX_SAFE=True
# Bounded inactivity timeout instead of an infinite hot polling loop.
class Stalled(Transport):
    def decode_split_wait(self):return (0,-1,0,0)
clock=[0]
def tick():clock[0]+=20000;return clock[0]
old_tick,old_sleep=module.ticks_ms,module.sleep_ms
module.ticks_ms=tick;module.sleep_ms=lambda n:None
jpeg=Stalled(header())
try:
    try:jpeg._decode_split(Reader(jpeg.data),len(jpeg.data),0,0)
    except OSError as exc:assert 'stalled' in str(exc)
    else:raise AssertionError('Stalled decoder did not time out')
finally:
    jpeg._cleanup();module.ticks_ms=old_tick;module.sleep_ms=old_sleep
assert jpeg.stopped==1
jpeg=Transport(header())
assert jpeg._get_scale(321,321)==(0.5,(79,79))
assert jpeg._get_scale(2560,2560)==(0.125,(0,0))
try:jpeg._get_scale(2561,2560)
except ValueError:pass
else:raise AssertionError('Oversized image silently cropped')
for data in (b'',b'not jpeg',bytes((255,216,255,192,0,1)),header()[:10]):
    assert not jpeg.draw_buffer(0,0,data)
assert JPEG._dimensions(header(321,319))==(True,321,319)
progressive=bytearray(header());progressive[3]=194
assert not JPEG._dimensions(progressive)[0]
# Small file path takes the borrowed-buffer route, including uppercase suffixes.
path='/private/tmp/gungos-jpeg-small.JPEG'
with open(path,'wb') as f:f.write(header(size=1000))
jpeg=Transport(header(size=1000));assert jpeg.draw(0,0,path) and jpeg._filebuffer is None
os.remove(path)
print('PASS: JPEG direct input, bounded streaming, short reads/EOF, reuse, launch/failure cleanup, header/scale and timeout')
