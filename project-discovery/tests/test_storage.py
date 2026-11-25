"""Storage behavior only; these tests do not prove the agent asks good questions."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/storage.py'
spec = importlib.util.spec_from_file_location('discovery_storage', SCRIPT)
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.config = self.base / 'settings/location.json'
        self.root = self.base / 'Persönlich 文件'

    def test_location_is_requested_and_existing_kb_preserved(self):
        self.assertEqual(storage.status(self.config)['status'], 'needs_location')
        storage.configure(self.config, str(self.root))
        kb = self.root / 'discovery_kb.md'; kb.write_text('Keep my lesson.\n', encoding='utf-8')
        storage.configure(self.config, str(self.root))
        self.assertEqual(kb.read_text(encoding='utf-8'), 'Keep my lesson.\n')
        with self.assertRaises(ValueError): storage.configure(self.config, str(self.base / 'other'))
        self.assertEqual(storage.read_root(self.config), self.root)

    def test_cli_saves_unicode_and_refuses_overwrite(self):
        def cli(*args):
            return subprocess.run([sys.executable, str(SCRIPT), '--config', str(self.config), *map(str, args)], capture_output=True, text=True)
        self.assertEqual(cli('configure', '--root', self.root).returncode, 0)
        source = self.base / 'draft.md'; source.write_text('# Prüfung 文件\nActual answer.\n', encoding='utf-8')
        args = ('save', '--source', source, '--name', 'DISCOVERY_文件.md')
        result = cli(*args); self.assertEqual(result.returncode, 0, result.stdout)
        target = Path(json.loads(result.stdout)['report'])
        self.assertEqual(target.read_bytes(), source.read_bytes())
        self.assertEqual(cli(*args).returncode, 1)
        source.write_text('Explicit replacement.\n', encoding='utf-8')
        self.assertEqual(cli(*args, '--overwrite').returncode, 0)
        self.assertEqual(target.read_bytes(), source.read_bytes())

    def test_override_leaves_root_and_symlink_redirect_is_blocked(self):
        storage.configure(self.config, str(self.root))
        source = self.base / 'draft.md'; source.write_text('Useful draft', encoding='utf-8')
        output = self.base / 'one-run.md'
        storage.save(self.config, source, output=str(output))
        self.assertEqual(storage.read_root(self.config), self.root)
        (self.root / 'reports').rmdir()
        (self.root / 'reports').symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(ValueError): storage.save(self.config, source, name='DISCOVERY_leak.md')
        self.assertFalse((self.base / 'DISCOVERY_leak.md').exists())

    def test_only_ignored_untracked_git_destination_is_accepted(self):
        repo = self.base / 'repo'; repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        with self.assertRaises(ValueError): storage.configure(self.config, str(repo / 'shared'))
        (repo / '.gitignore').write_text('private/\n', encoding='utf-8')
        storage.configure(self.config, str(repo / 'private'))
        tracked = repo / 'private/discovery_kb.md'
        subprocess.run(['git', '-C', str(repo), 'add', '-f', str(tracked)], check=True)
        with self.assertRaises(ValueError): storage.status(self.config)

    def test_missing_root_and_empty_report_do_not_claim_success(self):
        storage.configure(self.config, str(self.root))
        source = self.base / 'empty.md'; source.write_text('  ', encoding='utf-8')
        with self.assertRaises(ValueError): storage.save(self.config, source, name='DISCOVERY_empty.md')
        self.root.rename(self.base / 'moved')
        with self.assertRaises(ValueError): storage.status(self.config)


if __name__ == '__main__':
    unittest.main()
