#!/usr/bin/env python3
"""Create original dummy EPUBs for PicoReader's simulator and local SD trees."""
from pathlib import Path
from html import escape
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def write_book(path,title,chapters):
    path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('mimetype','application/epub+zip',compress_type=zipfile.ZIP_STORED)
        archive.writestr('META-INF/container.xml',
            '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="EPUB/book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        manifest=[];spine=[];nav=[]
        for i,(heading,paragraphs) in enumerate(chapters,1):
            filename=f'chapter{i}.xhtml'
            manifest.append(f'<item id="c{i}" href="{filename}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="c{i}"/>')
            nav.append(f'<li><a href="{filename}">{escape(heading)}</a></li>')
            archive.writestr('EPUB/'+filename,
                '<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml">'
                f'<head><title>{escape(heading)}</title></head><body><h1>{escape(heading)}</h1>'+
                ''.join('<p>'+escape(p)+'</p>' for p in paragraphs)+'</body></html>')
        archive.writestr('EPUB/nav.xhtml',
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
            '<head><title>Contents</title></head><body><nav epub:type="toc"><ol>'+''.join(nav)+'</ol></nav></body></html>')
        archive.writestr('EPUB/book.opf',
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f'<dc:identifier id="book-id">urn:picoreader:sample:{escape(path.stem)}</dc:identifier>'
            f'<dc:title>{escape(title)}</dc:title><dc:language>en</dc:language>'
            '<meta property="dcterms:modified">2026-10-25T00:00:00Z</meta></metadata><manifest>'+''.join(manifest)+
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
            '</manifest><spine>'+''.join(spine)+'</spine></package>')


def generate(destination):
    """Write only the original release samples to the chosen library folder."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    books=[('Getting Started.epub','Getting Started with PicoReader',[
        ('Your pocket library',[
            'This is an original dummy document for trying PicoReader. The default reading text uses the extra-small system font.',
            'Press Right or Down to turn forward. Press Left or Up to turn back. Enter also turns forward.',
            'F3 and F4 change chapters. F1 adds or removes a bookmark; F5 lists bookmarks. F6 chooses the reading font.',
            'Escape returns to the library. F2 refreshes the list of books. F9 opens help.']),
        ('Adding your books',[
            'Copy EPUB or UTF-8 TXT documents into picoware/documents/picoreader on your SD card, then refresh the library.',
            'This version reads text and paragraph breaks. Images, complex styling, and protected books are outside this first version.',
            'Your position, bookmarks and font are saved on the SD card.',
            'These sample documents are generated locally and contain no third-party book text.'])]),
        ('The Lantern Walk.epub','The Lantern Walk',[
            (heading,[f'{i}. '+paragraph for i in range(1,13)]) for heading,paragraph in (
                ('The harbour','Mira arrived at the quiet harbour with a small lantern and a folded map. The boats moved gently against their ropes. Beyond the last house, a path climbed toward the old signal tower. She waited for the evening bell, then began her walk.'),
                ('The hillside','The path crossed a garden where rosemary grew between pale stones. Mira stopped to look back at the harbour. Every window below had become a little square of light. She marked the turn on her map and followed the wall toward the hilltop.'),
                ('The signal tower','At the tower, Mira placed the lantern on the broad stone ledge. Its light reached the bend in the path. A friend answered from the harbour with a second lantern. The walk was complete, and the two lights stayed visible until the stars appeared.'))]),
        ('Field Notes.epub','Field Notes: A Dummy Notebook',[
            ('Morning observations',[
                'Observation %02d: The air is cool, the sky is clear, and a narrow band of sunlight reaches the desk. A small computer rests beside a notebook. This repeated observation supplies enough text to test several page turns.'%i for i in range(1,19)]),
            ('Words and punctuation',[
                'English: A quiet room, a good book, and a cup of tea.',
                'Italian: Una piccola biblioteca, una città tranquilla, un caffè sul tavolo.',
                'Characters: café, perché, più, già. Symbols: & < > "quotes" and apostrophes.',
                'Long words wrap too: abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.',
                'Numbers: 0 1 2 3 4 5 6 7 8 9. Punctuation: commas, colons: semicolons; parentheses (like these).']),
            ('A short final chapter',['This chapter deliberately fits on one page. Turn back to test the transition to the last page of the previous chapter.'])])]
    texts=[('Pocket Notes.txt',[
        'This is an original UTF-8 text sample for PicoReader.',
        'Text files have no chapters, so the reader splits one into bounded parts, preferably at a line break. Page turning, bookmarks, the font choice and the saved position work as they do for EPUB.',
        'Accents: café, perché, più, già. Punctuation: commas, colons: semicolons; parentheses (like these).',
        'A plain text file can also hold a few short lines:',
        'One: lanterns on the harbour wall.',
        'Two: a map folded along its creases.',
        'Three: the quiet path home.'])]
    for filename,title,chapters in books:write_book(destination/filename,title,chapters)
    for filename,paragraphs in texts:
        (destination/filename).write_text(filename[:-4]+'\n\n'+'\n\n'.join(paragraphs)+'\n',encoding='utf-8')
    print(f'Created {len(books)} sample EPUBs and {len(texts)} TXT book in {destination}')


def main():
    for tree in ('simulator/sdcard','sd-card','SD contents'):
        generate(ROOT/tree/'picoware/documents/picoreader')


if __name__=='__main__':main()
