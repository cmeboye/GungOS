#!/usr/bin/env python3
"""Check the Pico 2 W UF2, clean SD allowlist, source closure and checksums."""
import argparse
import hashlib
import json
import runpy
from pathlib import Path
import struct
import wave
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION=runpy.run_path(str(ROOT/'src/MicroPython/picoware/system/features.py'))['FIRMWARE_VERSION']
FIRMWARE='GungOS-v'+VERSION+'-PicoCalc-Pico2W.uf2'

def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as reader:
        for block in iter(lambda:reader.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()

def uf2_info(path):
    data=path.read_bytes()
    assert data and len(data)%512==0,'UF2 length must be whole 512-byte blocks'
    blocks={};addresses=set();total=None;ignored=0
    for offset in range(0,len(data),512):
        start0,start1,flags,address,size,number,count,family=struct.unpack_from('<8I',data,offset)
        assert (start0,start1)==(0x0a324655,0x9e5d5157),'UF2 header magic'
        assert struct.unpack_from('<I',data,offset+508)[0]==0x0ab16f30,'UF2 end magic'
        assert 0<size<=476 and flags&0x2000,'UF2 payload/family flag'
        if family==0xe48bff57:
            assert flags==0xa000 and address==0x10ffff00 and size==256,'Unexpected absolute-address UF2 block'
            assert struct.unpack_from('<I',data,offset+32+size)[0]==0x9957e304,'Missing RP2350 ignore extension'
            ignored+=1;continue
        assert family==0xe48bff59 and flags==0x2000,'UF2 must target RP2350 ARM secure'
        assert address>=0x10000000 and address+size<=0x10000000+4194304-2048000,'UF2 overlaps flash filesystem'
        assert address%256==0 and number not in blocks and address not in addresses,'Duplicate/misaligned UF2 block'
        if total is None:total=count
        assert total==count,'Inconsistent UF2 block count'
        blocks[number]=(address,data[offset+32:offset+32+size]);addresses.add(address)
    assert total and sorted(blocks)==list(range(total)) and ignored<=1,'Incomplete UF2 sequence'
    image=b''.join(blocks[n][1] for n in range(total))
    markers=(b'GungOS',b'picoware_pcm',b'ulab')
    if VERSION=='2.2':markers+=(b'PicoDESK',b'misc/screensavers',b'picoware/gui/style.py')
    for name in markers:
        assert name in image,'Expected firmware marker is missing: '+repr(name)
    start=min(addresses);end=max(address+len(payload) for address,payload in blocks.values())
    return {'sha256':sha256(path),'uf2_bytes':len(data),'flash_start':hex(start),'flash_end':hex(end),
            'flash_image_bytes':end-start,'flash_capacity_bytes':4194304-2048000,
            'flash_filesystem_bytes':2048000,'family_id':'0xe48bff59','main_blocks':total,'ignore_blocks':ignored}

def verify_sd(root):
    apps=root/'sd-card/picoware/apps'
    source=root/'builds/MicroPython/apps_unfrozen'
    entries={'Graph.mpy','Graph3D.mpy','PicoLAB.mpy'}
    if (source/'Eggcel.py').exists(): entries.add('Eggcel.mpy')
    for name in ('Apps','PicoWord','PicoPaint','PicoDESK'):
        if (source/(name+'.py')).exists():entries.add(name+'.mpy')
    assert {p.name for p in apps.glob('*.mpy')}==entries,'Unexpected top-level app'
    assert {p.name for p in (apps/'games').glob('*.mpy')}=={'Tetris.mpy'},'Unexpected game'
    screens=apps/('misc/screensavers' if (source/'misc/screensavers').exists() else 'screensavers')
    assert {p.name for p in screens.glob('*.mpy')}=={'Calculator Widget.mpy','Lorenz.mpy'},'Unexpected screensaver'
    expected={p.relative_to(source).with_suffix('.mpy') for p in source.rglob('*.py')
              if 'tools' not in p.relative_to(source).parts}
    actual={p.relative_to(apps) for p in apps.rglob('*.mpy')}
    assert actual==expected and not list(apps.rglob('*.py')),'Compiled app package mismatch'
    assert not (apps/'engtools/tools').exists(),'Unfinished tools in release'
    settings=json.loads((root/'sd-card/picoware/settings/picoware.json').read_text())
    assert settings['wifi_ssid']==settings['wifi_password']=='','Release contains Wi-Fi credentials'
    assert not any(settings.get(key) for key in settings if 'api_key' in key or 'server_password' in key),'Release contains secrets'
    retired=runpy.run_path(str(root/'src/MicroPython/picoware/system/settings.py'))['RETIRED_SETTINGS']
    assert not any(key in settings for key in retired),'Release contains retired settings'
    assert settings['screensaver']=='Calculator Widget','Missing demonstration widget default'
    assert isinstance(settings['tetris_sound'],bool) and settings['tetris_volume']==25,'Sound defaults'
    for path in apps.rglob('*.wav'):
        with wave.open(str(path),'rb') as reader:
            assert (reader.getnchannels(),reader.getframerate(),reader.getsampwidth())==(1,22050,2),path
            assert reader.getnframes()>0,path
    assert len(list(apps.rglob('*.wav'))) in (0,10),'Optional audio must be absent or a complete ten-file set'
    with zipfile.ZipFile(root/('GungOS-v'+VERSION+'-SD.zip')) as archive:
        assert archive.testzip() is None,'Damaged SD archive'
        files={p.relative_to(root/'sd-card').as_posix():p for p in (root/'sd-card').rglob('*') if p.is_file()}
        assert set(archive.namelist())==set(files),'SD archive differs from copyable directory'
        assert all(archive.read(name)==p.read_bytes() for name,p in files.items()),'SD archive contents differ'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--write-report',action='store_true')
    args=parser.parse_args();root=args.root.resolve()
    info=uf2_info(root/'firmware'/FIRMWARE)
    verify_sd(root)
    for path in root.rglob('*'):
        if '.build' in path.relative_to(root).parts:continue
        assert not path.is_symlink(),'External link in standalone release: '+str(path)
    for name in ('vendor/micropython/ports/rp2/CMakeLists.txt','vendor/picotool/CMakeLists.txt',
                 'src/MicroPython/ulab/upstream/LICENSE','LICENSE','THIRD_PARTY_NOTICES.md'):
        assert (root/name).is_file(),name
    sums=root/'SHA256SUMS.txt'
    if sums.exists():
        for line in sums.read_text().splitlines():
            expected,name=line.split('  ',1)
            assert sha256(root/name)==expected,'Checksum differs: '+name
    if args.write_report:
        (root/'verification/package-check.json').write_text(json.dumps(info,indent=2)+'\n')
    print('PASS: RP2350 UF2, flash bounds, embedded PCM/ulab/GungOS, clean SD contents and standalone source')
    print(json.dumps(info,indent=2))

if __name__=='__main__':main()
