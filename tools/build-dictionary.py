#!/usr/bin/env python3
"""Convert supplied WikDict SQLite sources into bounded offline SD records."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'builds/MicroPython/apps_unfrozen'))
from desktopapps.dictionary.local import MAGIC,FIELD,normalize,single_word

NOTICE='''PicoDict dictionary data
Source: WikDict by Karl Bartel, https://www.wikdict.com/
Data from Wiktionary contributors via DBnary (https://kaiko.getalp.org/).
License: Creative Commons Attribution-ShareAlike 4.0
https://creativecommons.org/licenses/by-sa/4.0/
Changes: lowercased keys; curly apostrophes normalized; single-word entries
and translations retained; one source-ordered translation selected per key;
converted to fixed-width UTF-8 records. Translation ordering is not a guarantee
of the most common sense. No conjugation or grammatical inference is included.
The adapted dictionary data remains available under CC BY-SA 4.0.
'''


def convert(source,target):
    entries={}
    with sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True) as db:
        for head,translations,score in db.execute(
                'SELECT written_rep,trans_list,max_score FROM simple_translation ORDER BY written_rep'):
            key=normalize(head)
            if not single_word(key) or len(key.encode('utf-8'))>=FIELD:continue
            for translation in translations.split(' | '):
                translation=translation.strip()
                if single_word(translation) and len(translation.encode('utf-8'))<FIELD:
                    # Prefer the higher-scored source row for case-normalized collisions.
                    rank=float(score or 0)
                    if key not in entries or rank>entries[key][0]:entries[key]=(rank,translation)
                    break
    if not entries:raise ValueError('No usable entries in '+str(source))
    with target.open('wb') as out:
        out.write(MAGIC+struct.pack('<I',len(entries)))
        for key in sorted(entries,key=lambda s:s.encode('utf-8')):
            out.write(key.encode('utf-8').ljust(FIELD,b'\x00'))
            out.write(entries[key][1].encode('utf-8').ljust(FIELD,b'\x00'))
    return {'entries':len(entries),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'data_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--en-it',required=True,type=Path)
    parser.add_argument('--it-en',required=True,type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'sd-card/picoware/dictionary')
    parser.add_argument('--zip',type=Path,default=ROOT/'builds/MicroPython/PicoDict-data.zip')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    manifest={'format':1,'license':'CC-BY-SA-4.0','source':'https://www.wikdict.com/page/download','dictionaries':{}}
    for direction,source in (('en-it',args.en_it),('it-en',args.it_en)):
        manifest['dictionaries'][direction]=convert(source,args.output/(direction+'.pdict'))
    (args.output/'NOTICE.txt').write_text(NOTICE)
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    args.zip.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.zip,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in ('en-it.pdict','it-en.pdict','NOTICE.txt','manifest.json'):
            archive.write(args.output/name,'picoware/dictionary/'+name)
    print(json.dumps(manifest,indent=2))
    print('SD data:',args.output)
    print('Install archive:',args.zip)

if __name__=='__main__':main()
