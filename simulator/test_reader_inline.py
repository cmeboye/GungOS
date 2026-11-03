"""Mixed page order, height budgets, font anchors and viewer passage return."""
exec(open('simulator/test_reader_math.py').read())
# Reuse the isolated native UI/storage initialized by the equation tests.
app=PicoReader();vm.add(View('inline',app.run,app.start,app.stop));vm.switch_to('inline');app.refresh()
key(k.BUTTON_CENTER);settle();assert app.session.rich
app.session.seek(0,0);settle();app.sync_page()
seen=[];steps=0;visited=set()
while not app.session.ended:
 assert app.blocks
 height=sum(app.height if b[0]=='t' else b[3] for b in app.blocks)
 assert height<=app.rows*app.height
 if app.session.current[:2] not in visited:
  visited.add(app.session.current[:2])
  for block in app.blocks:
   if block[0]=='m':seen.append(block[2])
 if steps==0:sim_runtime.lcd_screenshot('/private/tmp/gungos-reader-inline.bmp')
 key(k.BUTTON_RIGHT);settle();steps+=1
 assert steps<100
assert seen==list(range(9)),seen
# Character anchors include the old normalized math text even though it is no
# longer drawn as flattened characters. Thus stored positions remain meaningful.
from desktopapps.reader.pager import paginate
legacy=[p for p in paginate(app.book,0,app.width,app.rows) if p]
assert legacy[-1][5]==app.session.current[5],(legacy[-1][5],app.session.current[5])
# Find a page with equations and exercise the contextual F8 entry point.
app.session.seek(0,0);settle();app.sync_page()
while not any(b[0]=='m' for b in app.blocks):key(k.BUTTON_RIGHT);settle()
old=app.session.current;anchor=app.page_offset();equation=next(b for b in app.blocks if b[0]=='m')
key(k.BUTTON_F8);assert app.equations.ordinal==equation[2] and not app.equations.loading
key(vm.input_manager._key_esc);assert app.session.current is old and app.page_offset()==anchor
key(k.BUTTON_F1);app.save_position();assert app.bookmarks
key(k.BUTTON_F6)
for _ in range(100000):
 if not app.reflow:break
 key(k.BUTTON_NONE)
assert not app.reflow and not app.error,app.error
assert app.session.current[4]<=anchor<=app.session.current[5]
# Disk cache reload retains mixed payload and equation backing data.
page=app.session.current;app.session.cache.ram=[];app.session.cache.bytes=0
assert app.session.cache.get(*page[:2])==page
key(vm.input_manager._key_esc);assert app.library
key(k.BUTTON_CENTER);settle();assert app.bookmarks and app.session.rich
path=app.session.rich.path;vm.back()
try:open(path);raise AssertionError('Equation cache survived exit')
except OSError:pass
print('PASS: nine ordered equation blocks, page height, old character anchors, contextual F8, reflow/bookmarks/reopen, disk replay and cache cleanup')
