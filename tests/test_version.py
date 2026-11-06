"""Version references stay in sync with the plugin manifest."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'litflux'


class VersionTests(unittest.TestCase):
    def test_all_release_references_match_the_manifest(self):
        version = json.loads((ROOT / 'plugin.json').read_text(encoding='utf-8'))['version']
        self.assertRegex(version, r'^\d+\.\d+\.\d+$')
        self.assertIn('v' + version, (SKILL / 'SKILL.md').read_text(encoding='utf-8'))
        self.assertIn('v' + version, (SKILL / 'instructions' / 'zh.md').read_text(encoding='utf-8'))
        self.assertIn('v' + version, (ROOT / 'SPEC.md').read_text(encoding='utf-8').splitlines()[0])
        for name in ('README.md', 'README.zh-CN.md'):
            text = (ROOT / name).read_text(encoding='utf-8')
            self.assertIn('dist/litflux-' + version + '.zip', text)
        self.assertIn('## ' + version, (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
