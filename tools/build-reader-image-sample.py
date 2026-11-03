#!/usr/bin/env python3
"""Build an original illustrated EPUB for PicoReader device testing (Pillow)."""
import argparse,io,zipfile
from pathlib import Path
from PIL import Image,ImageDraw

def generate(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    chart=Image.new('RGB',(640,480),'white');d=ImageDraw.Draw(chart)
    d.rectangle((40,40,600,440),outline='black',width=3)
    for i,colour in enumerate(('#df4539','#248a65','#356fd0','#c18b20')):
        x=90+i*130;d.rectangle((x,400-60*(i+1),x+70,400),fill=colour)
    d.text((60,55),'Original PicoReader test illustration',fill='black')
    alpha=Image.new('RGBA',(301,201),(0,0,0,0));d=ImageDraw.Draw(alpha)
    for i in range(5):
        d.ellipse((10+i*47,20,100+i*47,170),fill=(30,80+i*30,220-i*35,50+i*45))
    images=[('RGB chart','chart.png',chart),('JPEG chart','chart.jpg',chart),
            ('Grayscale chart','gray.png',chart.convert('L')),
            ('Palette chart','palette.png',chart.quantize(colors=16)),
            ('Transparency','alpha.png',alpha)]
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('mimetype','application/epub+zip',compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml','<container><rootfile full-path="OPS/book.opf"/></container>')
        manifest=[];spine=[]
        for i,(title,name,image) in enumerate(images):
            data=io.BytesIO();image.save(data,format='JPEG' if name.endswith('.jpg') else 'PNG')
            z.writestr('OPS/art/'+name,data.getvalue(),compress_type=zipfile.ZIP_STORED if i==3 else zipfile.ZIP_DEFLATED)
            manifest.append('<item id="c%d" href="c%d.xhtml" media-type="application/xhtml+xml"/>'%(i,i))
            manifest.append('<item id="i%d" href="art/%s" media-type="image/%s"/>'%(i,name,'jpeg' if name.endswith('.jpg') else 'png'))
            spine.append('<itemref idref="c%d"/>'%i)
            text='<html xmlns="http://www.w3.org/1999/xhtml"><head><title>'+title+'</title></head><body><h1>'+title+'</h1>'
            text+='<p>Press F7, then Enter to view this illustration. Esc returns to the list; Esc again restores this page. F4 opens the next chapter.</p>'
            text+='<img src="art/'+name+'" alt="'+title+'"/>'
            text+=''.join('<p>Reading-position check %d. Turn a page before opening the image, then check that the same passage returns.</p>'%n for n in range(25))
            z.writestr('OPS/c%d.xhtml'%i,text+'</body></html>')
        z.writestr('OPS/book.opf','<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>PicoReader Image Check</dc:title><dc:language>en</dc:language><dc:identifier id="id">gungos-original-image-check-1</dc:identifier></metadata><manifest>'+''.join(manifest)+'</manifest><spine>'+''.join(spine)+'</spine></package>')
    return path
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    print(generate(parser.parse_args().output))
