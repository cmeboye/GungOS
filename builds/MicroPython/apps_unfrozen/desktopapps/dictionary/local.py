"""Bounded random-access dictionary; no dictionary-sized heap allocation."""
import struct

MAGIC=b'PDICT01\x00'
HEADER=12
FIELD=64
RECORD=128
DIRECTORY='picoware/dictionary'


def normalize(word):
    word=word.strip().lower().replace('\u2019', "'")
    for upper,lower in zip('ÀÁÂÄÃÅÆÇÈÉÊËÌÍÎÏÑÒÓÔÖÕØÙÚÛÜÝŸŒ','àáâäãåæçèéêëìíîïñòóôöõøùúûüýÿœ'):
        word=word.replace(upper,lower)
    return word


def single_word(word):
    letters='abcdefghijklmnopqrstuvwxyzàáâäãåæçèéêëìíîïñòóôöõøùúûüýÿœ'
    return bool(word) and any(c.lower() in letters for c in word) and all(
        c.lower() in letters or c in "'-" for c in word)


class Dictionary:
    def __init__(self,storage):
        self.storage=storage

    def lookup(self,word,direction='en-it'):
        if direction not in ('en-it','it-en'):raise ValueError('Invalid language direction')
        key=normalize(word)
        if not single_word(key):raise ValueError('Enter one word')
        encoded=key.encode('utf-8')
        if len(encoded)>=FIELD:raise ValueError('Word too long')
        path=DIRECTORY+'/'+direction+'.pdict'
        header=self.storage.read(path,'rb',0,HEADER)
        if not header:raise OSError('Install dictionary data on SD')
        if len(header)!=HEADER or header[:8]!=MAGIC:raise OSError('Invalid dictionary data')
        count=struct.unpack('<I',header[8:])[0]
        if not count or count>1000000 or self.storage.size(path)!=HEADER+count*RECORD:
            raise OSError('Incomplete dictionary data')
        low,high=0,count
        while low<high:
            mid=(low+high)//2
            row=self.storage.read(path,'rb',HEADER+mid*RECORD,RECORD)
            if len(row)!=RECORD:raise OSError('Cannot read dictionary')
            candidate=row[:FIELD].split(b'\x00',1)[0]
            if candidate<encoded:low=mid+1
            elif candidate>encoded:high=mid
            else:
                try:return row[FIELD:].split(b'\x00',1)[0].decode('utf-8')
                except UnicodeError:raise OSError('Invalid dictionary text')
        return None
