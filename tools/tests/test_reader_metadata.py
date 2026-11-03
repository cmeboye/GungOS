"""Stream large original EPUB manifests; validate bounded spine and integrity."""
from pathlib import Path
import subprocess,sys,tempfile,zipfile,struct
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'builds/MicroPython/apps_unfrozen'))
from desktopapps.reader.epub import Book,Archive

def fixture(path,package,compression=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(path,'w',compression) as z:
        for name,data in [('mimetype','application/epub+zip'),('META-INF/container.xml','<container><rootfile full-path="OPS/book.opf"/></container>'),('OPS/book.opf',package),('OPS/a.xhtml','<p>First café.</p>'),('OPS/b.xhtml','<p>Second.</p>')]:z.writestr(name,data)

with tempfile.TemporaryDirectory(prefix='reader-metadata-') as temp:
    folder=Path(temp);path=folder/'metadata.epub'
    unused=''.join('<item id="image%d" href="images/%d.jpg" media-type="image/jpeg"/>'%(i,i) for i in range(1800))
    package='<package><metadata><title>Large &amp; café</title></metadata><manifest>'+unused+'<item id="b" href="b.xhtml" media-type="application/xhtml+xml"/><item id="a" href="a.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="a"/><itemref idref="b"/><itemref idref="a" linear="no"/></spine></package>'
    assert len(package.encode())>100000
    read=Archive.read
    def bounded(self,name,limit=192*1024):
        assert name=='mimetype', 'Metadata must use streaming reads'
        return read(self,name,limit)
    Archive.read=bounded
    for compression in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
        fixture(path,package,compression)
        book=Book(str(path));assert list(book.chapters)==['OPS/a.xhtml','OPS/b.xhtml'];assert book.title=='Large & café';book.close()
    Archive.read=read
    # Native and compiled loader checks include the large manifest itself.
    native=ROOT/'builds/MicroPython/desktop/micropython'
    compiler=ROOT/'.build/mpy-cross/mpy-cross'
    if native.exists():
        probe=folder/'probe.py'
        probe.write_text("import sys,gc\nsys.path.insert(0,sys.argv[2])\nfrom desktopapps.reader.epub import Book\ngc.collect();base=gc.mem_alloc()\nfor _ in range(5):\n b=Book(sys.argv[1]);assert list(b.chapters)==['OPS/a.xhtml','OPS/b.xhtml'];assert b.title=='Large & café';b.close();b=None;gc.collect()\nassert gc.mem_alloc()-base<2048\nprint('PASS: large manifest, constrained heap, repeated cleanup')\n")
        for compiled in (False,True):
            source=ROOT/'builds/MicroPython/apps_unfrozen'
            if compiled:
                source=folder/'compiled';target=source/'desktopapps/reader';target.mkdir(parents=True)
                for rel in ('desktopapps/__init__.py','desktopapps/reader/__init__.py','desktopapps/reader/epub.py'):
                    output=source/Path(rel).with_suffix('.mpy')
                    subprocess.run([str(compiler),'-o',str(output),str(ROOT/'builds/MicroPython/apps_unfrozen'/rel)],check=True)
            subprocess.run([str(native),'-X','heapsize='+('160K' if compiled else '256K'),str(probe),str(path),str(source)],cwd=ROOT,check=True)
    for bad,message in [(package.replace('idref="a"','idref="missing"'),'Broken EPUB reading order'),(package.replace('<item id="b"','<item id="a"'),'Duplicate EPUB manifest ID'),('<package><spine>'+'<itemref idref="a"/>'*513+'</spine></package>','index budget'),('<package>'+(' '* (2*1024*1024))+'</package>','EPUB metadata too large: OPS/book.opf')]:
        fixture(path,bad)
        try:Book(str(path))
        except ValueError as exc:assert message in str(exc),str(exc)
        else:raise AssertionError('Invalid metadata accepted: '+message)
    fixture(path,package,zipfile.ZIP_STORED)
    with zipfile.ZipFile(path) as z:info=z.getinfo('OPS/book.opf')
    with path.open('r+b') as f:
        f.seek(info.header_offset+26);nl,el=struct.unpack('<HH',f.read(4));f.seek(info.header_offset+30+nl+el+100);f.write(b'!')
    try:Book(str(path))
    except ValueError as exc:assert 'Damaged EPUB text' in str(exc),str(exc)
    else:raise AssertionError('Metadata CRC error ignored')
print('PASS: metadata streaming, order, limits, duplicate IDs and CRC')
