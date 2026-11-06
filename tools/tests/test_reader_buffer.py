"""Large EPUB and bounded-buffer regression, host and native MicroPython."""
from pathlib import Path
import gc,os,random,struct,subprocess,sys,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'builds/MicroPython/apps_unfrozen'))
from desktopapps.reader.epub import Book,Archive,plain_text,wrap,stream_tokens
from desktopapps.reader.pager import Session,paginate,STRIDE,RAM_BYTES,RAM_PAGES,DISK_PAGES

CONTAINER='<container><rootfile full-path="book.opf"/></container>'
PACKAGE='<package><metadata><title>Streaming test</title></metadata><manifest><item id="a" href="a.xhtml" media-type="application/xhtml+xml"/><item id="b" href="b.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="a"/><itemref idref="b"/></spine></package>'
def fixture(path,text,large=False):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for name,body in [('mimetype','application/epub+zip'),('META-INF/container.xml',CONTAINER),('book.opf',PACKAGE),('b.xhtml','<p>The end.</p>')]:z.writestr(name,body)
        with z.open('a.xhtml','w') as out:
            out.write(b'<html><head><title>Hidden</title></head><body>')
            if large:
                for i in range(24000):out.write(('<p>Paragraph %d. '%i+text+'</p>').encode())
            else:out.write(text.encode())
            out.write(b'</body></html>')
        if large:
            for i in range(1100):z.writestr('art/%04d.bin'%i,b'')
            info=zipfile.ZipInfo('art/large-unused-image.bin');info.compress_type=zipfile.ZIP_STORED
            with z.open(info,'w') as out:
                chunk=b'x'*65536
                for _ in range(530):out.write(chunk)
        z.comment=b'x'*60000

def settle(session):
    for _ in range(100000):
        session.step();assert not session.error,session.error
        if not session.pending and not session.queue:return
    raise AssertionError('Pagination did not settle')

with tempfile.TemporaryDirectory(prefix='gungos-reader-buffer-') as tmp:
    folder=Path(tmp);path=folder/'small.epub'
    text='<p>ab<em>cd</em>ef &amp; café 😀 &unknown; &#xE9;.</p><!--'+('x'*2000)+'--><p>'+('w'*1300)+' short</p>'
    fixture(path,text);book=Book(str(path))
    for width,rows in [(50,18),(38,12),(25,10),(7,3)]:
        result=[page for page in paginate(book,0,width,rows) if page]
        actual=[line for page in result for line in page[6].split('\n')]
        expected=wrap(plain_text('<html><head><title>Hidden</title></head><body>'+text+'</body></html>'),width)
        assert actual==expected,(width,actual,expected)
        offsets=[page[4] for page in result];assert offsets==sorted(offsets)
    # Every possible boundary through tags, entities, comments and UTF-8.
    class Chunks:
        def __init__(self,data,size):self.data=data;self.size=size;self.at=0
        def read(self):
            chunk=self.data[self.at:self.at+self.size];self.at+=len(chunk);return chunk
        def close(self):pass
    sample='<p>a<em>bc</em> &amp; café 😀 &#x1F600;</p><!-- hide -->'
    for size in range(1,40):
        chunks=[t for t in stream_tokens(Chunks(sample.encode(),size)) if t is not None]
        visible=''.join(t for t in chunks if isinstance(t,str))
        assert visible=='abc & café 😀 😀',(size,visible)
    book.close()
    # A real archive above 32 MiB and a chapter above the old 192 KiB ceiling.
    large=folder/'large.epub';fixture(large,'A passage for a bounded page buffer. café &amp; 😀 '*8,True)
    assert large.stat().st_size>32*1024*1024
    book=Book(str(large));assert len(book.archive.entries)>1024 and len(book.archive.entries.cache)<=16
    assert book.archive.entries['a.xhtml'][3]>8*1024*1024
    session=Session(book,50,18,str(folder/'pages.bin'));session.seek(0);settle(session)
    first=session.current;first_pages=[first]
    for i in range(180):
        for _ in range(10):session.step()
        session.turn(1);settle(session);first_pages.append(session.current)
        assert session.current[1]==i+1
        assert session.cache.bytes<=RAM_BYTES and len(session.cache.ram)<=RAM_PAGES
        assert len(session.cache.slots)<=DISK_PAGES
    assert (folder/'pages.bin').stat().st_size<=DISK_PAGES*STRIDE
    # SD cache hits survive removal of the text source; distant misses replay.
    session.stop_source();reader=book.stream
    def fail(index):raise AssertionError('Cached turn reparsed the chapter')
    book.stream=fail
    for i in range(20):session.turn(-1);settle(session)
    book.stream=reader
    session.seek(0,0,first_pages[2][4]);settle(session);assert session.current==first_pages[2]
    # Bounded fast-key queue: one outstanding request plus up to eight turns.
    for _ in range(20):session.turn(1)
    settle(session);assert session.current[1]==11,session.current[:2]
    anchor=session.current[4];old=session.current
    reflow=Session(book,25,10,str(folder/'font.bin'));reflow.seek(0,offset=anchor);settle(reflow)
    assert reflow.current[4]<=anchor<reflow.current[5]
    reflow.close();session.close();book.close();assert not (folder/'pages.bin').exists()
    # Empty chapters, partial entities and malformed/oversized markup stay bounded.
    for data in ('<p></p>','<p>tail &unfinished','<!-- unfinished','<p '+'x'*2100+'>'):
        fixture(path,data);probe=Book(str(path))
        try:
            try:result=[v for v in paginate(probe,0,50,18) if v]
            except ValueError:
                assert data.startswith('<!--') or len(data)>2048
            else:assert result and not data.startswith('<!--') and len(data)<2048
        finally:probe.close()
    fixture(path,'<p>Hello world.</p>');probe=Book(str(path));entry=probe.archive.entries['a.xhtml']
    for replacement in (entry[:2]+(entry[2]+1,)+entry[3:],entry[:3]+(entry[3]-1,)+entry[4:]):
        probe.archive.entries['a.xhtml']=replacement
        try:list(v for v in paginate(probe,0,50,18) if v)
        except ValueError:pass
        else:raise AssertionError('Inconsistent compressed/plain length accepted')
    probe.archive.entries['a.xhtml']=entry
    # No writable cache directory: RAM caps and bounded replay still work.
    ram=Session(probe,7,1,str(folder/'missing/pages.bin'));ram.seek(0);settle(ram)
    assert ram.cache.file is None;ram.turn(1);settle(ram);ram.turn(-1);settle(ram)
    assert ram.current[1]==0;ram.close();probe.close()
    # A queued cache allocation failure is caught inside the idle step.
    fixture(path,'<p>Hello world.</p>');probe=Book(str(path))
    queued=Session(probe,7,1,str(folder/'queued.bin'));queued.seek(0);settle(queued)
    getter=queued.cache.get
    def no_memory(*args):raise MemoryError('injected queued cache allocation')
    queued.cache.get=no_memory;queued.queue=1
    assert queued.step() and queued.failed and 'injected queued' in queued.error
    queued.cache.get=getter;queued.close();probe.close()
    # Corrupt text is rejected at EOF, and an error is not retried every idle tick.
    fixture(path,'<p>Hello world.</p>');book=Book(str(path));entry=book.archive.entries['a.xhtml']
    book.archive.entries['a.xhtml']=entry[:-1]+(entry[-1]^1,)
    broken=Session(book,50,18,str(folder/'broken.bin'));broken.seek(0)
    for _ in range(100):
        broken.step()
        if broken.error:break
    assert 'Damaged' in broken.error
    assert broken.source is None and all(not broken.step() for _ in range(20))
    broken.close();book.close()
    # Exercise precisely the same stream/cache logic in the native interpreter.
    native=ROOT/'builds/MicroPython/desktop/micropython'
    for heap in ('384K',):
        subprocess.run([str(native),'-X','heapsize='+heap,'simulator/test_reader_buffer.py',str(large)],cwd=ROOT,check=True)
    compiler=ROOT/'.build/mpy-cross/mpy-cross';stage=folder/'compiled/desktopapps/reader';stage.mkdir(parents=True)
    for name in ('__init__','epub','pager'):
        source=ROOT/'builds/MicroPython/apps_unfrozen/desktopapps/reader'/(name+'.py')
        subprocess.run([str(compiler),'-o',str(stage/(name+'.mpy')),str(source)],check=True)
    (stage.parent/'__init__.py').write_text('')
    subprocess.run([str(native),'-X','heapsize=160K','simulator/test_reader_buffer.py',str(large),str(folder/'compiled')],cwd=ROOT,check=True)
print('PASS: >32 MiB EPUB, >8 MiB chapter, >1024 assets; bounded RAM/SD; replay, fast turns, reflow, CRC and chunk boundaries')
