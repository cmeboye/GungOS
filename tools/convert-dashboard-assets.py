#!/usr/bin/env python3
"""Pack assets/gungOS_logo_large.png at native size into the compact desktop header."""
import argparse
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def compile_logo(path):
    with Image.open(path) as source:
        image = source.convert('RGB')
    if image.size != (320, 320):
        raise ValueError('Expected a 320x320 desktop canvas')
    pixels = image.load()
    points = [(x, y) for y in range(320) for x in range(320)
              if max(pixels[x, y]) > 7]
    if not points:
        raise ValueError('No logo artwork found')
    x0, y0 = min(x for x, y in points), min(y for x, y in points)
    x1, y1 = max(x for x, y in points) + 1, max(y for x, y in points) + 1
    width, height = x1 - x0, y1 - y0
    # Preserve source pixels; center in the left header cell with a 1px margin.
    target_x = 1 + (92 - width) // 2
    target_y = max(17, min(y0 - 1, 42 - height))
    if target_x < 1 or target_x + width > 91 or target_y + height > 42:
        raise ValueError('Unscaled logo must fit between x=1..90 and y=17..41')
    palette, lookup, runs = [0], {0: 0}, bytearray()
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = pixels[x, y]
            colour = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            if colour not in lookup:
                if len(palette) >= 256:
                    raise ValueError('Logo exceeds the indexed colour limit')
                lookup[colour] = len(palette)
                palette.append(colour)
            index = lookup[colour]
            if runs and runs[-1] == index and runs[-2] < 255:
                runs[-2] += 1
            else:
                runs.extend((1, index))
    text = '"""Generated from assets/gungOS_logo_large.png without resizing; black is canvas."""\n'
    text += f'X, Y, WIDTH, HEIGHT = {target_x}, {target_y}, {width}, {height}\n'
    text += f'PALETTE = {tuple(palette)!r}\nDARK = (\n'
    text += ''.join('    ' + repr(bytes(runs[i:i + 72])) + '\n' for i in range(0, len(runs), 72))
    text += ')\nLIGHT = DARK\n'
    text += '''
def decode(dark=True, background=0):
    out = bytearray(WIDTH*HEIGHT*2)
    position = 0
    for i in range(0,len(DARK),2):
        count,index = DARK[i],DARK[i+1]
        color = PALETTE[index] if index else background
        run = bytes((color & 255,color >> 8))*count
        out[position:position+len(run)] = run
        position += len(run)
    return out
'''
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check the packed logo matches the source PNG.')
    args = parser.parse_args()
    content = compile_logo(ROOT / 'assets/gungOS_logo_large.png')
    output = ROOT / 'src/MicroPython/picoware/assets/dashboard_logo.py'
    if args.check:
        if not output.exists() or output.read_text() != content:
            parser.exit(1, 'Packed logo is stale; run tools/convert-dashboard-assets.py\n')
        print('PASS: packed logo matches the native source artwork')
    else:
        output.write_text(content)
        print('Packed native-size desktop logo: ' + str(output))


if __name__ == '__main__':
    main()
