"""Real EPUB archives, bounded loading, and PicoReader simulator lifecycle."""
import os,sys,tempfile,zipfile,struct
root=os.getcwd()
for relative in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+relative)
from desktopapps.reader.epub import Book,TxtBook,open_book,plain_text,wrap,resolve,LIMIT,TEXT_LIMIT

container='<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>'
package='''<package><metadata><dc:title>Test &amp; Book</dc:title></metadata><manifest>
<item id="b" href="two.xhtml" media-type="application/xhtml+xml"/>
<item id="a" href="one%20space.xhtml" media-type="application/xhtml+xml"/>
</manifest><spine><itemref idref="a"/><itemref idref="b"/></spine></package>'''

def fixture(path,compression=zipfile.ZIP_DEFLATED,chapter=None):
    with zipfile.ZipFile(path,'w',compression) as z:
        for name,data in (('mimetype','application/epub+zip'),('META-INF/container.xml',container),
                          ('OPS/book.opf',package),('OPS/one space.xhtml',chapter or '<html><head><title>Hidden</title></head><body><h1>First</h1><p>Hello &amp; world.</p></body></html>'),
                          ('OPS/two.xhtml','<p>Second chapter</p>')):z.writestr(name,data)

with tempfile.TemporaryDirectory() as folder:
    for compression in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
        path=folder+'/book.epub';fixture(path,compression)
        book=Book(path)
        assert book.title=='Test & Book'
        assert book.chapter(0)=='First\nHello & world.'
        assert book.chapter(1)=='Second chapter'
        assert book.chapters[0]=='OPS/one space.xhtml'
        book.close();assert book.archive.file is None
    fixture(path,zipfile.ZIP_STORED)
    with zipfile.ZipFile(path) as z:offset=z.getinfo('OPS/two.xhtml').header_offset
    with open(path,'r+b') as f:
        f.seek(offset+26);nl,el=struct.unpack('<HH',f.read(4))
        f.seek(offset+30+nl+el);f.write(b'X')
    book=Book(path)
    try:book.chapter(1)
    except ValueError:pass
    else:raise AssertionError('Corrupt chapter accepted')
    book.close()
    fixture(path)
    with zipfile.ZipFile(path,'a') as z:z.writestr('META-INF/encryption.xml','<encryption/>')
    try:Book(path)
    except ValueError:pass
    else:raise AssertionError('Encrypted resources accepted')
    fixture(path,chapter='<p>'+'x'*LIMIT+'</p>')
    book=Book(path)
    try:book.chapter(0)
    except ValueError:pass
    else:raise AssertionError('Oversized chapter accepted')
    book.close()
    with open(path,'wb') as f:f.write(b'not a zip')
    try:Book(path)
    except ValueError:pass
    else:raise AssertionError('Invalid archive accepted')
assert plain_text('<p>a <em>b</em> c &#xE9; &nbsp;</p><script>bad</script><p>d</p>')=='a b c é\nd'
assert all(len(line)<=7 for line in wrap('Longwordthatislong short\nnext',7))
try:resolve('OPS/book.opf','../../escape')
except ValueError:pass
else:raise AssertionError('Traversal accepted')

with tempfile.TemporaryDirectory() as folder:
    # UTF-8 text: BOM, line-ending normalisation, bounded parts and safe splits.
    body='\ufeffOne\r\nTwo\rThree\n'+''.join('café %d\n'%i for i in range(12000))
    path=folder+'/notes.txt'
    with open(path,'w',encoding='utf-8',newline='') as f:f.write(body)
    book=TxtBook(path)
    assert book.title=='notes' and len(book.chapters)>=2
    assert ''.join(book.chapter(i) for i in range(len(book.chapters)))==body[1:].replace('\r\n','\n').replace('\r','\n')
    book.close()
    opened=open_book(path);assert isinstance(opened,TxtBook);opened.close()
    path=folder+'/wide.txt'
    with open(path,'w',encoding='utf-8') as f:f.write('a'+'é'*100000)
    book=TxtBook(path)
    assert ''.join(book.chapter(i) for i in range(len(book.chapters)))=='a'+'é'*100000
    book.close()
    path=folder+'/huge.txt'
    with open(path,'wb') as f:f.truncate(TEXT_LIMIT+1)
    try:TxtBook(path)
    except ValueError:pass
    else:raise AssertionError('Oversized text file accepted')
    path=folder+'/bad.txt'
    with open(path,'wb') as f:f.write(b'broken \xff text')
    book=TxtBook(path)
    try:book.chapter(0)
    except UnicodeError:pass
    else:raise AssertionError('Invalid UTF-8 text accepted')
    book.close()
print('PASS: stored/deflated EPUB, TXT chunking, spine order, entities, hidden text, bounds and invalid archive')

# Exercise native MicroPython decompression, drawing, and app lifecycle.
import subprocess
with tempfile.TemporaryDirectory() as folder:
    path=folder+'/book.epub'
    fixture(path,chapter='<p>'+'A sentence for paging. '*300+'</p>')
    subprocess.run([root+'/builds/MicroPython/desktop/micropython','-X','heapsize=16M',
                    root+'/simulator/test_reader_ui.py',path],check=True)
    stage=root+'/.build/sd-app-staging'
    if os.path.isdir(stage):
        subprocess.run([root+'/builds/MicroPython/desktop/micropython','-X','heapsize=16M',
                        root+'/simulator/test_reader_ui.py',path,stage],check=True)
