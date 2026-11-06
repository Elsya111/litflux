"""The runtime and documentation use the LitFlux names, not the old brand."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'litflux'
SKIP = {'.git', 'history', 'test-results', 'dist', '.zcode', '__pycache__', 'node_modules'}
SUFFIXES = {'.py', '.html', '.css', '.md', '.json', '.js'}


def current_files():
    own = Path(__file__).resolve()
    for path in ROOT.rglob('*'):
        if any(part in SKIP for part in path.parts) or path.resolve() == own:
            continue
        if path.is_file() and path.suffix in SUFFIXES:
            yield path


class NamingTests(unittest.TestCase):
    def test_old_runtime_identifiers_are_gone(self):
        for path in current_files():
            text = path.read_text(encoding='utf-8', errors='ignore')
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn('#superflow-canvas-app', text)
                self.assertNotIn('id="superflow-canvas-app"', text)
                self.assertNotIn('__SUPERFLOW_', text)
                self.assertNotIn('_superflowCompression', text)
                self.assertNotIn('root.superflow', text)

    def test_viewer_has_one_legacy_storage_read_only(self):
        text = (SKILL / 'assets' / 'viewer.html').read_text(encoding='utf-8')
        self.assertNotIn('superflow', text.lower())
        self.assertIn('id="litflux-canvas-app"', text)

    def test_css_uses_the_litflux_canvas_id(self):
        text = (SKILL / 'assets' / 'interface.css').read_text(encoding='utf-8')
        self.assertIn('#litflux-canvas-app', text)
        self.assertNotIn('#superflow-canvas-app', text)


if __name__ == '__main__':
    unittest.main()
