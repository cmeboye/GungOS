"""Read-only MathML coverage probe: BOOK.epub [compiled-apps-directory].

Run with desktop MicroPython. Layout acceptance is not a visual-correctness or
physical-device qualification claim. This tool never modifies the supplied EPUB.
"""
import sys,gc
sys.path.insert(0,'src/MicroPython');sys.path.insert(0,'simulator/hardware');sys.path.insert(0,sys.argv[2] if len(sys.argv)>2 else 'builds/MicroPython/apps_unfrozen')
from desktopapps.reader.epub import Book
from desktopapps.reader.mathml import equations
from desktopapps.reader.mathlayout import MathRenderer
class Font:
 def __init__(self,s):self.width=(5,7,11,14,17)[s];self.spacing=1;self.height=(8,12,16,20,24)[s]
class Draw:
 def get_font(self,s):return Font(s)
r=MathRenderer(Draw(),(0,0,320,320));b=Book(sys.argv[1]);good=0;bad={}
for ch in range(len(b.chapters)):
 for event in equations(b,ch):
  if event is None:continue
  n,node,error=event
  try:
   if error:raise ValueError(error)
   box=r.layout_math(node,2)
   assert box.w>=0 and box.h>0
   good+=1
  except (ValueError,MemoryError) as exc:
   error=str(exc);bad[error]=bad.get(error,0)+1
  box=None;node=None;gc.collect()
b.close();print('LAYOUT ACCEPTED',good,'UNSUPPORTED',bad)
