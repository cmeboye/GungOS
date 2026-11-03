"""Generate original JPEG fixtures and run transport, pixel and native tests.

Requires Pillow and the built desktop MicroPython interpreter.
"""
from pathlib import Path
import subprocess
import tempfile
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='gungos-jpeg-fixtures-') as folder:
    directory=Path(folder);fixtures=[]
    for width,height in ((1,1),(17,19),(31,17),(319,241),(321,319),(601,799),(1281,961)):
        path=directory/('%dx%d.jpg'%(width,height))
        image=Image.new('RGB',(width,height))
        image.putdata([((x*7+y*3)%256,(x*11)%256,(y*13)%256)
                       for y in range(height) for x in range(width)])
        image.save(path,quality=80);fixtures.append(str(path))
    Image.new('RGB',(63,47),'orange').save(directory/'progressive.jpg',progressive=True)
    subprocess.run(['sh','src/MicroPython/jpeg/tests/run-tests.sh',*fixtures],cwd=ROOT,check=True)
    binary=str(ROOT/'builds/MicroPython/desktop/micropython')
    subprocess.run([binary,'-X','heapsize=16M','simulator/test_jpeg_streaming.py'],cwd=ROOT,check=True)
    subprocess.run([binary,'-X','heapsize=32M','simulator/test_jpeg_images.py',folder],cwd=ROOT,check=True)
print('PASS: JPEGDEC fixtures, transport/failures, GUI file/memory paths and scaling')
