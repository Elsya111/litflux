"""HTML output names stay readable and valid on Windows."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'litflux'
sys.path.insert(0, str(SKILL / 'scripts'))
from render_graph import html_filename, safe_project_name


class OutputNamingTests(unittest.TestCase):
    def test_cli_json_is_readable_with_a_non_utf8_stdout_encoding(self):
        model = Path(__file__).resolve().parent / 'fixtures' / 'dataflow-example.json'
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, '-B', str(SKILL / 'scripts/render_graph.py'), str(model)],
                cwd=directory, capture_output=True,
                env={**os.environ, 'PYTHONIOENCODING': 'cp936'})
            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout.decode('utf-8'))
            self.assertTrue(Path(report['output']).is_file())
            self.assertIn('真实数据依赖示例', report['output'])

    def test_readable_names_keep_chinese_and_spaces(self):
        self.assertEqual('litflux_问答 服务.html', html_filename('问答 服务'))

    def test_windows_invalid_characters_are_replaced(self):
        name = safe_project_name('a<>:"/\\|?*b')
        self.assertNotRegex(name, r'[<>:"/\\|?*\x00-\x1f]')
        self.assertTrue(name.startswith('a'))
        self.assertTrue(name.endswith('b'))
        control = safe_project_name('a\x01b')
        self.assertNotIn('\x01', control)
        self.assertEqual('a_b', control)

    def test_empty_and_trailing_characters_fall_back(self):
        self.assertEqual('litflux_project.html', html_filename(''))
        self.assertEqual('litflux_project.html', html_filename('.'))
        self.assertEqual('litflux_project.html', html_filename('..'))
        self.assertEqual('litflux_name.html', html_filename('name. '))

    def test_reserved_device_names_are_prefixed(self):
        self.assertEqual('_CON', safe_project_name('CON'))
        self.assertEqual('_COM1.txt', safe_project_name('COM1.txt'))
        self.assertEqual('_lpt9', safe_project_name('lpt9'))

    def test_long_names_are_bounded(self):
        name = html_filename('x' * 200)
        self.assertLessEqual(len(name), len('litflux_') + 80 + len('.html'))
        self.assertTrue(name.endswith('.html'))

    def test_render_defaults_to_the_named_litflux_output(self):
        model = Path(__file__).resolve().parent / 'fixtures' / 'dataflow-example.json'
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, '-B', str(SKILL / 'scripts' / 'render_graph.py'), str(model)],
                capture_output=True, text=True, encoding='utf-8', cwd=directory)
            self.assertEqual(0, result.returncode, result.stderr)
            output = Path(directory) / '.litflux' / 'output' / 'litflux_真实数据依赖示例.html'
            self.assertTrue(output.is_file())
            self.assertEqual(str(output.resolve()), json.loads(result.stdout)['output'])

    def test_explicit_render_path_wins(self):
        model = Path(__file__).resolve().parent / 'fixtures' / 'dataflow-example.json'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'custom.html'
            result = subprocess.run(
                [sys.executable, '-B', str(SKILL / 'scripts' / 'render_graph.py'),
                 str(model), str(output)],
                capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(output.is_file())
            self.assertFalse((Path(directory) / 'litflux_真实数据依赖示例.html').exists())
            self.assertEqual(str(output.resolve()), json.loads(result.stdout)['output'])


if __name__ == '__main__':
    unittest.main()
