"""Native MicroPython heap regression for the shipped PicoReader sample books.

Run with host Python. Compiles the loader so results reflect deployed .mpy code,
then loads chapters repeatedly under bounded native MicroPython heaps. This is
not a measurement of the physical PicoCalc's available heap or SD latency.
"""
from pathlib import Path
import importlib.util
import os
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
compiler=os.getenv('MPY_CROSS')
if not compiler:
    compiler=next((str(ROOT/p) for p in ('.build/mpy-cross/mpy-cross',) if (ROOT/p).is_file()),None)
if not compiler:raise SystemExit('Set MPY_CROSS to the matching MicroPython bytecode compiler')
spec=importlib.util.spec_from_file_location('reader_samples',ROOT/'tools/build-reader-samples.py')
samples=importlib.util.module_from_spec(spec);spec.loader.exec_module(samples)
with tempfile.TemporaryDirectory(prefix='picoreader-memory-') as folder:
    directory=Path(folder);samples.generate(directory/'books')
    subprocess.run([compiler,'-o',str(directory/'reader_low.mpy'),
                    str(ROOT/'builds/MicroPython/apps_unfrozen/desktopapps/reader/epub.py')],check=True)
    probe=directory/'probe.py'
    probe.write_text('''import sys,gc
sys.path.insert(0,sys.argv[1])
from reader_low import open_book,wrap,decode_entities
folder=sys.argv[1]+'/books/'
names=('The Lantern Walk.epub',) if sys.argv[2]=='lantern' else ('Getting Started.epub','The Lantern Walk.epub','Field Notes.epub','Pocket Notes.txt')
for name in names:
    book=open_book(folder+name);lines=[];retained=[]
    for cycle in range(20):
        width=50 if sys.argv[2]=='lantern' else (50,38,25)[cycle%3]
        for chapter in range(len(book.chapters)):
            # Release the previous whole-chapter result before the next read.
            lines=[];gc.collect()
            lines=wrap(book.chapter(chapter),width)
            assert lines and all(len(line)<=width for line in lines)
            gc.collect()
        retained.append(gc.mem_alloc())
    assert max(retained[6:])-min(retained[6:])<4096,(name,retained)
    book.close();lines=[];book=None;gc.collect()
    print('PASS: bounded native heap, 20 chapter/font cycles:',name)
assert decode_entities('a &amp; b &#233; &#xE9; &unknown;')=='a & b é é &unknown;'
''')
    binary=ROOT/'builds/MicroPython/desktop/micropython'
    for heap,mode in (('128K','lantern'),('256K','all')):
        subprocess.run([str(binary),'-X','heapsize='+heap,str(probe),str(directory),mode],cwd=ROOT,check=True)
print('PASS: compiled reader samples at constrained heaps; full UI/device overhead is separate')
