#!/usr/bin/env python3
"""Create copyable clean SD contents and record a completed native build."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir',type=Path,required=True)
    args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('release_verify',ROOT/'tools/verify-gungos-release.py')
    verify=importlib.util.module_from_spec(spec);spec.loader.exec_module(verify)
    firmware=ROOT/'firmware'/verify.FIRMWARE
    shutil.copy2(args.build_dir/'firmware.uf2',firmware)
    for name in ('firmware.elf','firmware.elf.map','frozen_content.c','genhdr/mpversion.h'):
        source=args.build_dir/name
        if source.exists():shutil.copy2(source,ROOT/'verification'/source.name)
    image=verify.uf2_info(firmware)
    card=ROOT/'sd-card'
    readme=(card/'README.md').read_bytes() if (card/'README.md').exists() else None
    if card.exists():shutil.rmtree(card)
    (card/'picoware').mkdir(parents=True)
    if readme is not None:(card/'README.md').write_bytes(readme)
    with zipfile.ZipFile(ROOT/'builds/MicroPython/engineering-preview.zip') as package:
        for name in package.namelist():
            if name.startswith('picoware/apps/'):
                assert '..' not in Path(name).parts
                package.extract(name,card)
    for name in ('settings','wifi','keyboard','engineering'):(card/'picoware'/name).mkdir()
    defaults={'dark_mode':True,'screen_brightness':100,'theme_color':31,'debug':False,
              'exit_button':77,'gmt_offset':0,'onscreen_keyboard':False,'lvgl_mode':False,
              'usb_stream':False,'screensaver':'Calculator Widget','wifi_ssid':'','wifi_password':'',
              'tetris_sound':bool(list(card.rglob('*.wav'))),'tetris_volume':25}
    (card/'picoware/settings/picoware.json').write_text(json.dumps(defaults,indent=2)+'\n')
    with zipfile.ZipFile(ROOT/('GungOS-v'+verify.VERSION+'-SD.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(card.rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(card).as_posix())
    verify.verify_sd(ROOT)
    build_info={'name':'GungOS','version':verify.VERSION,'board':'PicoCalc Raspberry Pi Pico 2 W',
                'micropython':json.loads((ROOT/'vendor/revisions.json').read_text()),
                'firmware':image,'source_date_epoch':os.getenv('SOURCE_DATE_EPOCH'),
                'gcc':subprocess.check_output(['arm-none-eabi-gcc','--version'],text=True).splitlines()[0],
                'cmake':subprocess.check_output(['cmake','--version'],text=True).splitlines()[0],
                'float_bits':32,'compiled_app_modules':len(list((card/'picoware/apps').rglob('*.mpy'))),'audio_assets':len(list(card.rglob('*.wav'))),
                'validation':{'native_build':'passed','package_checks':'passed',
                              'physical_pico_calc':'pending user flash and device checks'}}
    report=ROOT/'verification/simulator-tests.json'
    if report.exists():
        suites=json.loads(report.read_text())['tests']
        assert suites and all(s['exit_code']==0 for s in suites),'Simulator regression failure'
        build_info['validation']['simulator_suites_passed']=len(suites)
    compiled_report=ROOT/'verification/compiled-sd-tests.json'
    if compiled_report.exists():
        suites=json.loads(compiled_report.read_text())['tests']
        assert suites and all(s['exit_code']==0 for s in suites),'Compiled SD regression failure'
        build_info['validation']['compiled_sd_suites_passed']=len(suites)
    (ROOT/'verification/build-info.json').write_text(json.dumps(build_info,indent=2)+'\n')
    (ROOT/'verification/package-check.json').write_text(json.dumps(image,indent=2)+'\n')
    package_roots=('firmware','sd-card','verification')
    paths=sorted(p for name in package_roots for p in (ROOT/name).rglob('*') if p.is_file() and '.build' not in p.relative_to(ROOT).parts
                 and p.name not in ('SHA256SUMS.txt','.DS_Store') and '__pycache__' not in p.parts)
    (ROOT/'SHA256SUMS.txt').write_text(''.join(verify.sha256(p)+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in paths))
    print('GungOS release ready:',ROOT)
    print('UF2:',firmware)
    print('SHA256:',image['sha256'])

if __name__=='__main__':main()
