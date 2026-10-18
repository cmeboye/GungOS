"""Host-only regression checks for accidentally tracked private/generated files."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('public_repo', ROOT / 'tools/check-public-repo.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class PublicRepoChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='gungos-public-check-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in ('LICENSE', 'CREDITS.md', 'THIRD_PARTY_NOTICES.md',
                     'vendor/revisions.json', 'vendor/micropython/LICENSE',
                     'src/MicroPython/ulab/upstream/LICENSE'):
            self.write(name, 'Synthetic source/license fixture\n')
        self.write('.gitignore', 'local-backup/\nreleases/\nsd-card/*\n!sd-card/README.md\n'
                   'simulator/sdcard.*/\n.DS_Store\n.env.*\n!.env.example\n')
        subprocess.run(['git', 'init', '--quiet', str(self.root)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def force_track(self, name):
        subprocess.run(['git', '-C', str(self.root), 'add', '-f', '--', name], check=True)

    def test_clean_source_and_public_templates(self):
        self.write('sd-card/README.md', 'Generated outputs go here.\n')
        self.write('.env.example', '# Configure your environment locally.\n')
        self.assertEqual(checker.audit(self.root)['issues'], [])

    def test_ignored_private_files_are_not_candidates(self):
        for name in ('local-backup/note.txt', 'releases/v1.2/note.txt',
                     'simulator/sdcard.flash/note.txt', 'nested/.DS_Store'):
            self.write(name, 'Synthetic private fixture\n')
        self.assertEqual(checker.audit(self.root)['issues'], [])

    def test_forced_private_files_are_rejected(self):
        paths = ('local-backup/note.txt', 'releases/v1.2/note.txt',
                 'simulator/sdcard.flash/note.txt', 'nested/.DS_Store',
                 'sd-card/picoware/settings/picoware.json')
        for name in paths:
            self.write(name, '{}\n')
            self.force_track(name)
        issues = checker.audit(self.root)['issues']
        for name in paths:
            self.assertTrue(any(i['file'] == name and 'private/generated' in i['reason']
                                for i in issues), name)

    def test_missing_tracked_file_is_reported(self):
        self.write('source.py', '# fixture\n')
        self.force_track('source.py')
        (self.root / 'source.py').unlink()
        issues = checker.audit(self.root)['issues']
        self.assertTrue(any(i['file'] == 'source.py' and 'missing' in i['reason'] for i in issues))

    def test_credentials_are_reported_without_their_values(self):
        token = 'ghp_' + 'a' * 36
        value = 'synthetic-' + 'credential'
        self.write('settings.json', json.dumps(dict([('api_' + 'key', value), ('token', token)])))
        issues = checker.audit(self.root)['issues']
        self.assertTrue(any('service token' in i['reason'] for i in issues))
        self.assertTrue(any('literal credential' in i['reason'] for i in issues))
        report = json.dumps(issues)
        self.assertNotIn(token, report)
        self.assertNotIn(value, report)

    def test_upstream_key_fixtures_stay_allowlisted(self):
        self.write('vendor/micropython/lib/mbedtls/tests/fixture.pem',
                   '-----BEGIN ' + 'PRIVATE KEY-----\npublic synthetic fixture\n')
        result = checker.audit(self.root)
        self.assertEqual(result['issues'], [])
        self.assertEqual(len(result['known_public_test_fixtures']), 1)


if __name__ == '__main__':
    unittest.main()
