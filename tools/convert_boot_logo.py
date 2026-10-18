"""Convert a 320x320 PNG to an embedded RGB332 logo with transparent RLE runs.

Run: python3 tools/convert_boot_logo.py assets/legacy/testimg.png
Requires Pillow on the build computer; the firmware needs no PNG decoder.
"""
import argparse
from pathlib import Path
from PIL import Image


def convert(source, output, text_region=(31, 64, 202, 96)):
    image = Image.open(source).convert("RGBA")
    if image.size != (320, 320):
        raise ValueError("The boot logo must be 320x320 pixels")
    bounds = image.getbbox()
    if bounds is None:
        raise ValueError("The image is entirely transparent")
    cropped = image.crop(bounds)
    pixels = []
    source_pixels = cropped.get_flattened_data() if hasattr(cropped, "get_flattened_data") else cropped.getdata()
    for index, (r, g, b, alpha) in enumerate(source_pixels):
        if alpha not in (0, 255):
            raise ValueError("Use fully opaque or transparent pixels for pixel art")
        color = (r & 0xE0) | ((g & 0xE0) >> 3) | (b >> 6)
        x = bounds[0] + index % cropped.width
        y = bounds[1] + index // cropped.width
        themed = alpha and (r, g, b) == (0, 0, 0) and text_region[0] <= x < text_region[2] and text_region[1] <= y < text_region[3]
        pixels.append((color if alpha else 0, 2 if themed else (0 if alpha else 1)))
    runs = bytearray()
    previous, count = pixels[0], 0
    for pixel in pixels:
        if pixel != previous or count == 255:
            runs.extend((count, previous[0], previous[1]))
            previous, count = pixel, 0
        count += 1
    runs.extend((count, previous[0], previous[1]))
    chunks = [bytes(runs[i:i + 48]) for i in range(0, len(runs), 48)]
    data = "\n".join("    " + repr(chunk) for chunk in chunks)
    text = ('"""Generated logo: RGB332 RLE (count, color, kind: pixel/transparent/text)."""\n'
            f"X, Y = {bounds[0]}, {bounds[1]}\n"
            f"WIDTH, HEIGHT = {cropped.width}, {cropped.height}\n"
            "DATA = (\n" + data + "\n)\n\n"
            "def decode(background=0, foreground=255):\n"
            "    result = bytearray(WIDTH * HEIGHT)\n"
            "    offset = 0\n"
            "    for i in range(0, len(DATA), 3):\n"
            "        count = DATA[i]\n"
            "        kind = DATA[i + 2]\n"
            "        color = foreground if kind == 2 else (background if kind == 1 else DATA[i + 1])\n"
            "        result[offset:offset + count] = bytes([color]) * count\n"
            "        offset += count\n"
            "    return result\n")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text)
    print(f"Logo bounds: {bounds}; embedded data: {len(runs)} bytes; decoded: {len(pixels)} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "src/MicroPython/picoware/assets/boot_logo.py")
    parser.add_argument("--text-region", nargs=4, type=int, default=(31, 64, 202, 96), metavar=("X0", "Y0", "X1", "Y1"), help="Region whose black lettering should follow the device theme")
    arguments = parser.parse_args()
    convert(arguments.source, arguments.output, arguments.text_region)
