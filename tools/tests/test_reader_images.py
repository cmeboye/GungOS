"""Build original illustrated EPUB fixtures and exercise the native reader."""
from pathlib import Path
import io,subprocess,tempfile,zipfile
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='gungos-reader-images-') as tmp:
    folder=Path(tmp);epub=folder/'images.epub'
    image=Image.new('RGBA',(101,73),(220,40,30,0));draw=ImageDraw.Draw(image)
    draw.rectangle((5,5,95,67),fill=(30,150,210,128));draw.text((12,30),'PicoCalc',fill=(0,0,0,255))
    png=io.BytesIO();image.save(png,format='PNG')
    photo=io.BytesIO();image.convert('RGB').resize((641,481)).save(photo,format='JPEG')
    with zipfile.ZipFile(epub,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('mimetype','application/epub+zip')
        z.writestr('META-INF/container.xml','<container><rootfile full-path="OPS/book.opf"/></container>')
        z.writestr('OPS/book.opf','<package><metadata><title>Images test</title></metadata><manifest><item id="c" href="chapter.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="c"/></spine></package>')
        html='<html><body>'+''.join('<p>Paragraph %d. This is a long chapter for checking the reading position after opening images.</p>'%i for i in range(80))
        html+='<img src="art/alpha.png" alt="Transparent PNG"/><img src="art/photo.jpg" alt="JPEG photo"/><image xlink:href="art/stored.png"/><img src="art/vector.svg"/><img src="art/alpha.png"/><img src="https://example.org/no.png"/></body></html>'
        z.writestr('OPS/chapter.xhtml',html);z.writestr('OPS/art/alpha.png',png.getvalue())
        z.writestr('OPS/art/photo.jpg',photo.getvalue());z.writestr('OPS/art/stored.png',png.getvalue(),compress_type=zipfile.ZIP_STORED)
        z.writestr('OPS/art/vector.svg','<svg/>')
        # Force the ZIP comment scan across blocks without a 64 KiB allocation.
        z.comment=b'x'*60000
    subprocess.run([str(ROOT/'builds/MicroPython/desktop/micropython'),'-X','heapsize=8M','simulator/test_reader_images.py',str(epub)],cwd=ROOT,check=True)
    staging=ROOT/'.build/reader-buffer-2026-11-03/sd-app-staging'
    if staging.is_dir():
        subprocess.run([str(ROOT/'builds/MicroPython/desktop/micropython'),'-X','heapsize=8M','simulator/test_reader_images.py',str(epub),str(staging.relative_to(ROOT))],cwd=ROOT,check=True)
print('PASS: original illustrated EPUB integration')
