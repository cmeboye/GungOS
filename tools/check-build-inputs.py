#!/usr/bin/env python3
"""Validate external package inputs before a build changes generated outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    if not (root / 'builds/MicroPython/apps_unfrozen/PicoDict.py').is_file():
        return
    archive = root / 'builds/MicroPython/PicoDict-data.zip'
    if not archive.is_file():
        raise ValueError('Missing builds/MicroPython/PicoDict-data.zip. Follow '
                         'guides/PicoDict.md and run tools/build-dictionary.py '
                         'with the two WikDict SQLite inputs before the full build. '
                         'For a firmware-only build, set GUNGOS_SKIP_PACKAGE=1.')
    prefix = 'picoware/dictionary/'
    expected = {prefix + name for name in ('en-it.pdict', 'it-en.pdict', 'NOTICE.txt', 'manifest.json')}
    try:
        with zipfile.ZipFile(archive) as package:
            names = package.namelist()
            if len(names) != len(expected) or set(names) != expected:
                raise ValueError('Dictionary archive must contain exactly the four documented data/notice files')
            manifest = json.loads(package.read(prefix + 'manifest.json'))
            if manifest['format'] != 1 or manifest['license'] != 'CC-BY-SA-4.0':
                raise ValueError('Dictionary format or license metadata is invalid')
            notice = package.read(prefix + 'NOTICE.txt').decode('utf-8')
            if 'CC' not in notice and 'Creative Commons' not in notice:
                raise ValueError('Dictionary attribution is missing')
            for direction in ('en-it', 'it-en'):
                data = package.read(prefix + direction + '.pdict')
                entry = manifest['dictionaries'][direction]
                count = entry['entries']
                if (len(data) < 12 or data[:8] != b'PDICT01\0' or
                        count <= 0 or struct.unpack_from('<I', data, 8)[0] != count or
                        len(data) != 12 + count * 128):
                    raise ValueError('Dictionary header/record count mismatch: ' + direction)
                if hashlib.sha256(data).hexdigest() != entry['data_sha256']:
                    raise ValueError('Dictionary checksum mismatch: ' + direction)
    except (OSError, KeyError, TypeError, zipfile.BadZipFile, UnicodeError) as exc:
        raise ValueError('Invalid PicoDict data package: ' + str(exc)) from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        check(args.root.resolve())
    except ValueError as exc:
        parser.exit(1, str(exc) + '\n')
    print('PASS: external package inputs')


if __name__ == '__main__':
    main()
