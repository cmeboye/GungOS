#!/usr/bin/env python3
"""Capture native simulator status-state screenshots and make review sheets."""
import argparse
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def filename(level, wifi, bluetooth):
    return 'battery_%d_wifi_%s_bt_%s.png' % (
        level,
        'on' if wifi else 'off', 'on' if bluetooth else 'off')


def sheets(output):
    for source in output.glob('*.bmp'):
        with Image.open(source) as image:
            image.save(source.with_suffix('.png'))
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 12)
    except OSError:
        font = ImageFont.load_default()
    background = (24, 24, 28)
    overview = Image.new('RGB', (960, 688), background)
    draw = ImageDraw.Draw(overview)
    examples = [(15, False, False), (25, True, False),
                (50, True, True), (75, False, True),
                (100, True, True), (100, False, False)]
    for index, (level, wifi, bluetooth) in enumerate(examples):
        x, y = (index % 3) * 320, (index // 3) * 344
        label = str(level) + '% battery'
        label += ' | WiFi ' + ('on' if wifi else 'off') + ' BT ' + ('on' if bluetooth else 'off')
        draw.text((x + 6, y + 6), label, font=font, fill='white')
        with Image.open(output / filename(level, wifi, bluetooth)) as image:
            overview.paste(image, (x, y + 24))
    overview.save(output / 'overview.png')
    matrix = Image.new('RGB', (1280, 224), background)
    draw = ImageDraw.Draw(matrix)
    for column, (wifi, bluetooth) in enumerate([(False, False), (True, False), (False, True), (True, True)]):
        x = column * 320
        label = 'WiFi ' + ('connected' if wifi else 'off') + ' / BT ' + ('connected' if bluetooth else 'off')
        draw.text((x + 6, 6), label, font=font, fill='white')
        for row, level in enumerate((15, 25, 50, 75, 100)):
            y = 24 + row * 40
            draw.text((x + 6, y + 2), str(level) + '% battery', font=font, fill=(185, 185, 190))
            with Image.open(output / filename(level, wifi, bluetooth)) as image:
                matrix.paste(image.crop((0, 0, 320, 16)), (x, y + 20))
    matrix.save(output / 'all-status-states.png')
    themes = Image.new('RGB', (640, 688), background)
    draw = ImageDraw.Draw(themes)
    for index, name in enumerate(['red', 'yellow', 'green', 'purple']):
        x, y = (index % 2) * 320, (index // 2) * 344
        draw.text((x + 6, y + 6), name + ' theme', font=font, fill='white')
        with Image.open(output / ('theme_' + name + '.png')) as image:
            themes.paste(image, (x, y + 24))
    themes.save(output / 'themes.png')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--micropython', type=Path, default=ROOT / 'builds/MicroPython/desktop/micropython')
    parser.add_argument('--output', type=Path, default=ROOT / 'verification/status-bar')
    parser.add_argument('--sheets-only', action='store_true', help='Compose already captured BMP screenshots.')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not args.sheets_only:
        subprocess.run([str(args.micropython.resolve()), '-X', 'heapsize=16M',
                        str(ROOT / 'simulator/preview_status_bar.py'), str(output)], cwd=ROOT, check=True)
    sheets(output)
    print('Saved 24 native screenshot PNGs and three review sheets: ' + str(output))


if __name__ == '__main__':
    main()
