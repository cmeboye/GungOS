"""Missing or damaged dictionary inputs must fail before replacing SD output."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('inputs', ROOT / 'tools/check-build-inputs.py')
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)


class BuildInputs(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='gungos-build-inputs-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        source = self.root / 'builds/MicroPython/apps_unfrozen/PicoDict.py'
        source.parent.mkdir(parents=True)
        source.write_text('# fixture\n')

    def package(self, extra=False, bad_hash=False):
        data = b'PDICT01\0' + struct.pack('<I', 1) + b'\0' * 128
        entry = {'entries': 1, 'data_sha256': 'invalid' if bad_hash else hashlib.sha256(data).hexdigest()}
        manifest = {'format': 1, 'license': 'CC-BY-SA-4.0', 'dictionaries': dict.fromkeys(('en-it', 'it-en'), entry)}
        archive = self.root / 'builds/MicroPython/PicoDict-data.zip'
        with zipfile.ZipFile(archive, 'w') as package:
            for direction in ('en-it', 'it-en'):
                package.writestr('picoware/dictionary/' + direction + '.pdict', data)
            package.writestr('picoware/dictionary/manifest.json', json.dumps(manifest))
            package.writestr('picoware/dictionary/NOTICE.txt', 'CC BY-SA 4.0 synthetic fixture')
            if extra:
                package.writestr('../unexpected', 'fixture')

    def test_missing_data_has_actionable_instructions(self):
        with self.assertRaisesRegex(ValueError, 'tools/build-dictionary.py'):
            inputs.check(self.root)

    def test_valid_archive(self):
        self.package()
        inputs.check(self.root)

    def test_unexpected_archive_paths_are_rejected(self):
        self.package(extra=True)
        with self.assertRaisesRegex(ValueError, 'exactly the four'):
            inputs.check(self.root)

    def test_changed_data_is_rejected(self):
        self.package(bad_hash=True)
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            inputs.check(self.root)

    def test_finalizer_preserves_outputs_when_inputs_are_missing(self):
        tools = self.root / 'tools'
        tools.mkdir()
        for name in ('check-build-inputs.py', 'finalize-gungos-release.py'):
            shutil.copy2(ROOT / 'tools' / name, tools / name)
        sentinel = self.root / 'sd-card/retain.txt'
        sentinel.parent.mkdir()
        sentinel.write_text('existing generated output')
        result = subprocess.run(['python3', str(tools / 'finalize-gungos-release.py'),
                                 '--build-dir', str(self.root / 'not-built')], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Missing builds/MicroPython/PicoDict-data.zip', result.stderr)
        self.assertEqual(sentinel.read_text(), 'existing generated output')


if __name__ == '__main__':
    unittest.main()
