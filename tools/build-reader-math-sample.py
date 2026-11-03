#!/usr/bin/env python3
"""Generate an original equation fixture, containing no textbook content."""
from pathlib import Path
import zipfile,argparse

EQUATIONS=[
('Axial stress: fraction and subscript','<mrow><msub><mi>σ</mi><mi>x</mi></msub><mo>=</mo><mfrac><mi>F</mi><mi>A</mi></mfrac></mrow>'),
('Combined scripts and square root','<mrow><msubsup><mi>x</mi><mi>i</mi><mn>2</mn></msubsup><mo>+</mo><msqrt><mrow><msup><mi>a</mi><mn>2</mn></msup><mo>+</mo><msup><mi>b</mi><mn>2</mn></msup></mrow></msqrt></mrow>'),
('Summation limits and overbar','<mrow><mover accent="true"><mi>x</mi><mo>¯</mo></mover><mo>=</mo><mfrac><mn>1</mn><mi>n</mi></mfrac><munderover><mo>∑</mo><mrow><mi>i</mi><mo>=</mo><mn>1</mn></mrow><mi>n</mi></munderover><msub><mi>x</mi><mi>i</mi></msub></mrow>'),
('Integral: no implied extra differential','<mrow><mi>I</mi><mo>=</mo><munderover><mo>∫</mo><mn>0</mn><mi>L</mi></munderover><mfrac><mrow><mi>F</mi><mi>x</mi></mrow><mrow><mi>E</mi><mi>A</mi></mrow></mfrac><mi>d</mi><mi>x</mi></mrow>'),
('Bracketed matrix and Greek symbols','<mrow><mfenced open="[" close="]"><mtable><mtr><mtd><mi>α</mi></mtd><mtd><mi>β</mi></mtd></mtr><mtr><mtd><mi>γ</mi></mtd><mtd><mi>δ</mi></mtd></mtr></mtable></mfenced><mo>=</mo><mfenced><mtable><mtr><mtd><mn>1</mn></mtd><mtd><mn>2</mn></mtd></mtr><mtr><mtd><mn>3</mn></mtd><mtd><mn>4</mn></mtd></mtr></mtable></mfenced></mrow>'),
('Wide equation: use arrow keys','<mrow><mi>Q</mi><mo>=</mo>'+''.join(('<mo>+</mo>' if i else '')+'<mfrac><mrow><msub><mi>F</mi><mn>%d</mn></msub><msup><mi>L</mi><mn>2</mn></msup></mrow><mrow><mi>E</mi><msub><mi>I</mi><mn>%d</mn></msub></mrow></mfrac>'%(i,i) for i in range(1,8))+'</mrow>'),
('Nth root and mathematical symbols','<mrow><mi>r</mi><mo>=</mo><mroot><mi>V</mi><mn>3</mn></mroot><mo>;</mo><mi>θ</mi><mo>≤</mo><mi>π</mi><mo>;</mo><mi>ρ</mi><mo>≠</mo><mn>0</mn><mo>;</mo><mi>∂</mi><mi>u</mi></mrow>'),
('Unsupported content must remain explicit','<menclose notation="circle"><mi>x</mi></menclose>'),
('Supported equation after unsupported one','<mrow><mi>a</mi><mo>+</mo><mi>b</mi><mo>=</mo><mi>c</mi></mrow>'),
]

def build(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    body='<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>PicoReader Equation Check</h1><p>Original test equations. Press F8, then brackets to browse; arrows pan.</p>'
    for label,math in EQUATIONS:body+='<p>'+label+'</p><math xmlns="http://www.w3.org/1998/Math/MathML" display="block">'+math+'</math>'
    body+='</body></html>'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('mimetype','application/epub+zip',compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml','<container><rootfile full-path="book.opf"/></container>')
        z.writestr('book.opf','<package><metadata><title>PicoReader Equation Check</title></metadata><manifest><item id="a" href="equations.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="a"/></spine></package>')
        z.writestr('equations.xhtml',body)
    return path

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args();print(build(args.output))
