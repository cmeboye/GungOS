#!/usr/bin/env python3
"""Original MathML references, native UI, bytecode and bounded-core checks."""
from pathlib import Path
import importlib.util,subprocess,sys,tempfile,xml.etree.ElementTree as ET,zipfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'builds/MicroPython/apps_unfrozen'))
from desktopapps.reader.epub import Book
from desktopapps.reader.mathml import equations
spec=importlib.util.spec_from_file_location('reader_math_fixture',ROOT/'tools/build-reader-math-sample.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

def xml_signature(node):
    tag=node.tag.split('}')[-1]
    if tag in ('mi','mo','mn','mtext','ms'):return tag,''.join(node.itertext())
    return tag,[xml_signature(c) for c in node]
def reader_signature(node):
    if node.tag in ('mi','mo','mn','mtext','ms'):return node.tag,''.join(node.children)
    return node.tag,[reader_signature(c) for c in node.children]

with tempfile.TemporaryDirectory(prefix='reader-math-') as temp:
    folder=Path(temp);epub=fixture.build(folder/'original-math.epub')
    with zipfile.ZipFile(epub) as z:
        doc=ET.fromstring(z.read('equations.xhtml'))
    reference=[xml_signature(e) for e in doc.iter() if e.tag.split('}')[-1]=='math']
    book=Book(str(epub));actual=[reader_signature(e[1]) for e in equations(book,0) if e is not None];book.close()
    assert actual==reference
    native=ROOT/'builds/MicroPython/desktop/micropython';compiler=ROOT/'.build/mpy-cross/mpy-cross'
    subprocess.run([str(native),'-X','heapsize=8M','simulator/test_reader_math.py',str(epub)],cwd=ROOT,check=True)
    # A private compilation stage avoids treating an earlier release as tested.
    stage=folder/'apps';stage.mkdir()
    source=ROOT/'builds/MicroPython/apps_unfrozen'
    for src in list((source/'desktopapps').rglob('*.py'))+list((source/'engtools').rglob('*.py')):
        output=stage/src.relative_to(source).with_suffix('.mpy');output.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run([str(compiler),'-o',str(output),str(src)],check=True)
    subprocess.run([str(native),'-X','heapsize=8M','simulator/test_reader_math.py',str(epub),str(stage)],cwd=ROOT,check=True)
    probe=folder/'core.py';probe.write_text('''import sys,gc
sys.path.insert(0,sys.argv[2]);sys.path.insert(0,'src/MicroPython');sys.path.insert(0,'simulator/hardware')
from desktopapps.reader.epub import Book
from desktopapps.reader.mathml import equations
from desktopapps.reader.mathlayout import MathRenderer
class Font:
 def __init__(self,s):self.width=(5,7,11,14,17)[s];self.spacing=1;self.height=(8,12,16,20,24)[s]
class Draw:
 def get_font(self,s):return Font(s)
r=MathRenderer(Draw(),(0,0,320,320));base=None
for cycle in range(12):
 book=Book(sys.argv[1]);good=0
 for event in equations(book,0):
  if event is None:continue
  index,node,error=event
  try:
   for font in (0,1,2):box=r.layout_math(node,font)
  except ValueError:assert index==7
  else:good+=1
  box=None;node=None;gc.collect()
 assert good==8
 book.close();book=None;event=None;gc.collect()
 if cycle==2:base=gc.mem_alloc()
assert gc.mem_alloc()-base<2048
print('PASS: compiled equation parser/layout, three fonts, 12 cycles at 256 KiB core heap; excludes UI/device costs')
''')
    subprocess.run([str(native),'-X','heapsize=256K',str(probe),str(epub),str(stage)],cwd=ROOT,check=True)
print('PASS: independent XML structure reference, source/MPY equation UI and constrained heap')
