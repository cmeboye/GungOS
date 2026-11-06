"""Original EPUB2/3 title fixtures and source/compiled navigation UI checks."""
from pathlib import Path
import subprocess,tempfile,zipfile,sys
ROOT=Path(__file__).resolve().parents[2]
def build(path,epub3=False):
 nav='<nav epub:type="toc"><ol><li><a href="a.xhtml#start">Start café</a><ol><li><a href="a.xhtml#sub">Subheading</a></li></ol></li><li><a href="b.xhtml">Middle</a></li><li><a href="c.xhtml">Finish</a></li></ol></nav>' if epub3 else '<ncx><navMap>'+''.join('<navPoint><navLabel><text>'+label+'</text></navLabel><content src="'+name+'.xhtml#section"/></navPoint>' for name,label in (('a','Start café'),('b','Middle'),('c','Finish')))+'</navMap></ncx>'
 if epub3:nav='<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head><body>'+nav+'</body></html>'
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('mimetype','application/epub+zip');z.writestr('META-INF/container.xml','<container><rootfile full-path="book.opf"/></container>')
  z.writestr('book.opf','<package><metadata><title>Navigation Check</title></metadata><manifest>'+''.join('<item id="'+n+'" href="'+n+'.xhtml" media-type="application/xhtml+xml"/>' for n in 'abc')+('<item id="nav" href="nav.xhtml" properties="nav" media-type="application/xhtml+xml"/>' if epub3 else '<item id="nav" href="nav.ncx" media-type="application/x-dtbncx+xml"/>')+'</manifest><spine>'+''.join('<itemref idref="'+n+'"/>' for n in 'abc')+'</spine></package>')
  z.writestr('nav.xhtml' if epub3 else 'nav.ncx',nav)
  for n in 'abc':z.writestr(n+'.xhtml','<html><body>'+''.join('<p>'+n+' passage %d: a line for testing page navigation and preserved passages.</p>'%i for i in range(100))+'</body></html>')
with tempfile.TemporaryDirectory(prefix='reader-navigation-') as tmp:
 for epub3 in (False,True):
  path=Path(tmp)/'navigation.epub';build(path,epub3)
  cmd=[str(ROOT/'builds/MicroPython/desktop/micropython'),'-X','heapsize=8M','simulator/test_reader_navigation.py',str(path)]
  subprocess.run(cmd,cwd=ROOT,check=True)
  if len(sys.argv)>1:subprocess.run(cmd+[str(Path(sys.argv[1]).resolve())],cwd=ROOT,check=True)
# Persist only our original fixture for device retesting.
output=ROOT/'.build/reader-navigation';output.mkdir(parents=True,exist_ok=True)
build(output/'PicoReader-Navigation-Check.epub',True)
print('PASS: EPUB2 NCX and EPUB3 nav chapter labels and keyboard workflows')
