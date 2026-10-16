#!/usr/bin/env python3
"""Pack the supplied 320px desktop logo art into a small RGB565 RLE asset."""
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[1]
images = [Image.open(root/'assets'/name).convert('RGB') for name in ('main_darkmode.png','main_lightmode.png')]
assert all(image.size == (320,320) for image in images)
# The artwork is in the upper-left region. Ignore one-bit export noise and
# stray canvas pixels outside it rather than retaining a 320x320 framebuffer.
points = [(x,y) for image in images for y in range(18,92) for x in range(148)
          if max(image.getpixel((x,y))) > 7]
x0,y0 = min(x for x,y in points),min(y for x,y in points)
x1,y1 = max(x for x,y in points)+1,max(y for x,y in points)+1
palette = [0]
streams = []
for image in images:
    indices = []
    for y in range(y0,y1):
        for x in range(x0,x1):
            r,g,b = image.getpixel((x,y))
            color = ((r>>3)<<11)|((g>>2)<<5)|(b>>3)
            if color == 0: indices.append(0); continue
            if color not in palette[1:]: palette.append(color)
            indices.append(palette.index(color,1))
    assert len(palette) < 256
    runs = bytearray()
    for index in indices:
        if runs and runs[-1] == index and runs[-2] < 255: runs[-2] += 1
        else: runs.extend((1,index))
    streams.append(bytes(runs))
output = root/'src/MicroPython/picoware/assets/dashboard_logo.py'
text = '"""Generated from main_darkmode.png/main_lightmode.png; black is canvas."""\n'
text += f'X, Y, WIDTH, HEIGHT = {x0}, {y0}, {x1-x0}, {y1-y0}\nPALETTE = {tuple(palette)!r}\n'
for name,data in zip(('DARK','LIGHT'),streams):
    text += name+' = (\n'+''.join('    '+repr(data[i:i+72])+'\n' for i in range(0,len(data),72))+')\n'
text += '''
def decode(dark=True, background=0):
    data = DARK if dark else LIGHT
    out = bytearray(WIDTH*HEIGHT*2)
    position = 0
    for i in range(0,len(data),2):
        count,index = data[i],data[i+1]
        color = PALETTE[index] if index else background
        run = bytes((color & 255,color >> 8))*count
        out[position:position+len(run)] = run
        position += len(run)
    return out
'''
output.write_text(text)
print(f'Packed {x1-x0}x{y1-y0} art; {sum(len(s) for s in streams)} bytes RLE; {len(palette)} palette entries.')
