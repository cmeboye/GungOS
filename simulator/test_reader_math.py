"""MathML parser/layout, lazy F8 lifecycle and original visual fixtures."""
import sys,os,gc
from time import ticks_ms
root=os.getcwd();apps=sys.argv[2] if len(sys.argv)>2 else 'builds/MicroPython/apps_unfrozen'
for path in ('src/MicroPython','simulator/hardware',apps):sys.path.insert(0,path if path.startswith('/') else root+'/'+path)
from desktopapps.reader.epub import Book,stream_tokens
from desktopapps.reader.mathml import equations,MAX_DEPTH
from desktopapps.reader.mathlayout import MathRenderer
class Font:
 def __init__(self,s):self.width=(5,7,11,14,17)[s];self.spacing=1;self.height=(8,12,16,20,24)[s]
class Recording:
 def __init__(self):self.calls=0
 def get_font(self,s):return Font(s)
 def _text(self,x,y,text,color,font):assert 0<=x<320 and 0<=y<320;self.calls+=1
 def _fill_rectangle(self,x,y,w,h,c):assert 0<=x<x+w<=320 and 0<=y<y+h<=320;self.calls+=1
 def _line(self,x,y,xx,yy,c):assert 0<=x<320 and 0<=xx<320 and 0<=y<320 and 0<=yy<320;self.calls+=1

def events(book):return [e for e in equations(book,0) if e is not None]
b=Book(sys.argv[1]);sample=events(b);assert len(sample)==9 and not any(e[2] for e in sample)
r=MathRenderer(Recording(),(8,58,312,272));boxes=[]
for index,node,error in sample:
 try:box=r.layout_math(node,2)
 except ValueError as exc:assert index==7 and 'menclose' in str(exc);continue
 boxes.append(box)
 for x,y in ((8,64),(-100,-100),(300,250)):r.paint(box,x,y)
assert r.draw.calls>100
# Real structure checks, independent of serialized calculator source.
a=sample[0][1].children[0];assert a.tag=='mrow'
assert [n.tag for n in a.children]==['msub','mo','mfrac']
assert a.children[0].children[0].children==['σ']
scripts=r.layout_math(sample[1][1].children[0].children[0],2)
assert scripts.children[1][1]==scripts.children[2][1]
assert scripts.children[1][2]<scripts.children[0][2]<scripts.children[2][2]
# Integral does not acquire the calculator editor's implicit "dx" suffix.
assert boxes[3].kind=='mathrow' and boxes[3].w>0
assert boxes[5].w>304
matrix=r.layout_math(sample[4][1],2)
assert matrix.h>2*r.metrics[2][1]
class ChunkBook:
 def __init__(self,text):self.text=text
 def stream(self,ch):
  class Stream:
   def __init__(self,t):self.data=t.encode();self.at=0;self.closed=False
   def read(self):data=self.data[self.at:self.at+1];self.at+=len(data);return data
   def close(self):self.closed=True
  self.last=Stream(self.text);return self.last
# Every tag/entity/UTF-8 sequence crosses source boundaries; empty paired tags
# must not disturb nesting or consume the next equation.
p=ChunkBook('<math><mrow><mi>σ</mi><mo>&lt;</mo><mn>2</mn></mrow></math><math><mrow/></math>')
e=events(p);assert len(e)==2 and not e[0][2] and p.last.closed
assert e[0][1].children[0].children[1].children==['<']
for text in ('<math><mrow></mi></math>','<math>'+'<mrow>'*30+'<mi>x</mi>'+'</mrow>'*30+'</math>', '<math><mi>'+'x'*4097+'</mi></math>'):
 p=ChunkBook(text+'<math><mi>z</mi></math>');e=events(p)
 assert e[0][2] and not e[-1][2]
 assert p.last.closed
p=ChunkBook('<math><mi>π</mi></math>');scan=equations(p,0);next(scan);scan.close();assert p.last.closed
# Unsupported symbols/attributes and malformed arities cannot be drawn as
# apparently valid equations. Scripts/style nodes are never executed.
for markup in ('<mfrac><mi>x</mi></mfrac>', '<mi>☃</mi>', '<mi mathvariant="bold">x</mi>',
               '<mtable><mtr><mtd rowspan="2"><mi>x</mi></mtd></mtr></mtable>'):
 event=events(ChunkBook('<math>'+markup+'</math>'))[0]
 try:r.layout_math(event[1])
 except ValueError:pass
 else:raise AssertionError('Unsupported semantics accepted')
p=ChunkBook('<script><math><mi>not-an-equation</mi></math></script><math><mi>x</mi></math>')
assert len(events(p))==1
p=ChunkBook('<math><mrow>'+'<mi>x</mi>'*769+'</mrow></math><math><mi>z</mi></math>')
e=events(p);assert e[0][2] and not e[1][2]
b.close();print('PASS: parser bounds/UTF-8/self-close/recovery, script geometry, matrix, clip bounds and unsupported rejection')

import sim_runtime
sim_runtime.configure(root,'/private/tmp/reader-math-'+str(ticks_ms()),root+'/'+apps,1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from desktopapps.reader.app import PicoReader,DIRECTORY
Input.button=property(lambda self:self._last_button)
vm=ViewManager();vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
app=PicoReader();vm.add(View('reader',app.run,app.start,app.stop));vm.switch_to('reader')
with open(sys.argv[1],'rb') as f:assert vm.storage.write(DIRECTORY+'/Equation Check.epub',f.read(),'wb')
app.refresh()
def key(button):vm.input_manager._last_button=button;vm.run()
def settle():
 for _ in range(100000):
  if app.equations:
   if not app.equations.loading:break
  elif app.session and not app.session.pending:break
  key(k.BUTTON_NONE)
 else:raise AssertionError('Reader did not settle')
key(k.BUTTON_CENTER);settle();old=app.session.current;anchor=app.page_offset();font=app.font
key(k.BUTTON_F8);assert app.equations;settle();assert app.equations.box and app.equations.ordinal==0
for i in range(9):
 if i:key(k.BUTTON_RIGHT_BRACKET);settle()
 assert app.equations.ordinal==i
 if i==7:assert 'menclose' in app.equations.error and app.equations.box is None
 else:
  assert app.equations.box and not app.equations.error,app.equations.error
  if i in (0,1,2,3,4,5,6):sim_runtime.lcd_screenshot('/private/tmp/gungos-reader-equation-%d.bmp'%i)
 if i==0:
  for _ in range(3):key(k.BUTTON_F6);assert app.equations.box and not app.equations.error
  assert app.equations.font==2
 if i==5:
  key(k.BUTTON_RIGHT);assert app.equations.x>0
  key(k.BUTTON_F9);assert app.equations.help
  key(k.BUTTON_F9);assert not app.equations.help
key(k.BUTTON_RIGHT_BRACKET);settle();assert app.equations.ended
key(k.BUTTON_LEFT_BRACKET);settle();assert app.equations.ordinal==7
key(vm.input_manager._key_esc);assert app.equations is None
assert app.session.current is old and app.page_offset()==anchor and app.font==font
key(k.BUTTON_F8);key(vm.input_manager._key_esc);assert app.equations is None
key(k.BUTTON_RIGHT);settle();assert not app.error
vm.back();assert app.book is None and app.equations is None
print('PASS: F8 scan, bracket browse, unsupported recovery, pan/help, cancellation, exact text-page return and exit cleanup')
