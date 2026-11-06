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
    # Validate external data before copying firmware or replacing the SD tree.
    subprocess.run(['python3',str(ROOT/'tools/check-build-inputs.py')],check=True)
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
    for name in ('settings','wifi','engineering'):(card/'picoware'/name).mkdir()
    # Full SD releases carry their optional-app data, never a personal SD tree.
    if (ROOT/'builds/MicroPython/apps_unfrozen/PicoDict.py').exists():
        data_package=ROOT/'builds/MicroPython/PicoDict-data.zip'
        expected={'picoware/dictionary/'+name for name in ('en-it.pdict','it-en.pdict','NOTICE.txt','manifest.json')}
        with zipfile.ZipFile(data_package) as package:
            assert set(package.namelist())==expected,'Unexpected dictionary data archive contents'
            for name in sorted(expected):package.extract(name,card)
    if (ROOT/'builds/MicroPython/apps_unfrozen/PicoReader.py').exists():
        samples_spec=importlib.util.spec_from_file_location('reader_samples',ROOT/'tools/build-reader-samples.py')
        samples=importlib.util.module_from_spec(samples_spec);samples_spec.loader.exec_module(samples)
        samples.generate(card/'picoware/documents/picoreader')
    for source,target in (('LICENSE','LICENSE.txt'),('THIRD_PARTY_NOTICES.md','THIRD_PARTY_NOTICES.md'),
                          ('assets/fonts/spleen/LICENSE','Spleen-LICENSE.txt')):
        shutil.copy2(ROOT/source,card/target)
    defaults={'screen_brightness':100,'theme_color':31,'background_color':0,
              'text_on_dark':65535,'text_on_light':0,'debug':False,
              'gmt_offset':0,'onscreen_keyboard':False,
              'screensaver':'Calculator Widget','wifi_ssid':'',
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
    try:
        build_info['source_revision']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
        build_info['source_dirty']=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True))
    except (OSError,subprocess.CalledProcessError):
        build_info['source_revision']='source archive (Git metadata unavailable)'
    report=ROOT/'verification/simulator-tests.json'
    if report.exists():
        data=json.loads(report.read_text())
        assert data['version']==verify.VERSION,'Simulator report belongs to another release'
        suites=data['tests']
        assert suites and all(s['exit_code']==0 for s in suites),'Simulator regression failure'
        build_info['validation']['simulator_suites_passed']=len(suites)
    compiled_report=ROOT/'verification/compiled-sd-tests.json'
    if compiled_report.exists():
        data=json.loads(compiled_report.read_text())
        assert data['version']==verify.VERSION,'Compiled SD report belongs to another release'
        suites=data['tests']
        assert suites and all(s['exit_code']==0 for s in suites),'Compiled SD regression failure'
        build_info['validation']['compiled_sd_suites_passed']=len(suites)
    (ROOT/'verification/build-info.json').write_text(json.dumps(build_info,indent=2)+'\n')
    (ROOT/'verification/package-check.json').write_text(json.dumps(image,indent=2)+'\n')
    # The manifest describes this release, not earlier UF2s/reports in a checkout.
    reports=('build-info.json','package-check.json','simulator-tests.json','compiled-sd-tests.json',
             'firmware.elf','firmware.elf.map','frozen_content.c','mpversion.h')
    paths=[firmware]+[ROOT/'verification'/name for name in reports if (ROOT/'verification'/name).is_file()]
    paths+=list(p for p in card.rglob('*') if p.is_file() and p.name!='.DS_Store')
    paths=sorted(paths)
    (ROOT/'SHA256SUMS.txt').write_text(''.join(verify.sha256(p)+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in paths))
    print('GungOS release ready:',ROOT)
    print('UF2:',firmware)
    print('SHA256:',image['sha256'])

if __name__=='__main__':main()
