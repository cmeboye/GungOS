"""Native streaming regression; run through tools/tests/test_reader_buffer.py."""
import sys,os,gc,io
from time import ticks_ms,ticks_diff
root=os.getcwd();sys.path.insert(0,sys.argv[2] if len(sys.argv)>2 else root+'/builds/MicroPython/apps_unfrozen')
from desktopapps.reader.epub import Book,EntryStream
from desktopapps.reader.pager import Session,RAM_BYTES,RAM_PAGES,DISK_PAGES,STRIDE
import pngdec
assert hasattr(pngdec,'BoundedReader')
class Short(io.IOBase):
    def __init__(self):self.left=2048
    def readinto(self,b):
        n=min(7,len(b),self.left);b[:n]=b'x'*n;self.left-=n;return n
r=pngdec.BoundedReader(Short(),1700);buffer=bytearray(513)
assert r.readinto(buffer)==513 and r.remaining()==1187
assert r.readinto(buffer)==513 and r.readinto(buffer)==513 and r.readinto(buffer)==161
assert r.remaining()==0 and r.readinto(buffer)==0
r.close()
try:r.readinto(buffer);assert False
except OSError:pass
try:pngdec.BoundedReader(io.BytesIO(b'x'),10).readinto(buffer);assert False
except OSError:pass
buffer=None;r=None;gc.collect()
book=Book(sys.argv[1]);cache='/private/tmp/reader-native-%d.bin'%ticks_ms()
# The SD-only compatibility path remains usable on older firmware.
sys.modules['pngdec']=io
try:
    stream=book.stream(0);assert stream.read() and stream.read();stream.close();stream=None
finally:sys.modules['pngdec']=pngdec
gc.collect()
session=Session(book,50,18,cache);session.seek(0)
def settle():
    for _ in range(100000):
        session.step();assert not session.error,session.error
        if not session.pending and not session.queue:return
    raise AssertionError('Native reader did not settle')
settle();base=[];slowest=0
for i in range(320):
    for _ in range(10):session.step()
    begin=ticks_ms();session.turn(1);settle();slowest=max(slowest,ticks_diff(ticks_ms(),begin))
    assert session.current[1]==i+1
    assert session.cache.bytes<=RAM_BYTES and len(session.cache.ram)<=RAM_PAGES
    if i%20==0:gc.collect();base.append(gc.mem_alloc())
assert max(base[5:])-min(base[5:])<8192,base
assert os.stat(cache)[6]<=DISK_PAGES*STRIDE
for i in range(75):session.turn(-1);settle();assert session.current[1]==319-i
anchor=session.current[4];session.seek(0,offset=anchor);settle();assert session.current[4]==anchor
session.close();book.close();gc.collect()
print('PASS: native 320 forward / 75 back, cache payload',RAM_BYTES,'heap plateau',min(base[5:]),max(base[5:]),'cached flip ms max',slowest,'compiled',len(sys.argv)>2)
