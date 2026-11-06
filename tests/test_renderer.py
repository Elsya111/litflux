"""Rendering stays offline, safe for arbitrary source text, and validates first."""

import json
import base64
import gzip
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'litflux'
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_graph import render
from validate_graph import validate
from test_business_dag import fixture


class RendererTests(unittest.TestCase):
    def test_understanding_revision_includes_authored_views_and_is_stable(self):
        from test_business_dag import fixture
        graph, spec = fixture()
        graph['presentation']['businessDAG'] = spec
        render(graph)
        previous = graph['presentation']['businessRevision']
        self.assertEqual(64, len(previous))
        render(graph)
        self.assertEqual(previous, graph['presentation']['businessRevision'])
        node = graph['presentation']['businessDAG']['nodes'][0]
        old_identity = node['identity']
        node['views']['100']['concepts'][0]['description'] = 'Revised explanation with the same source identities.'
        render(graph)
        self.assertEqual(old_identity, graph['presentation']['businessDAG']['nodes'][0]['identity'])
        self.assertNotEqual(previous, graph['presentation']['businessRevision'])

    def model(self):
        return fixture()[0]

    def test_offline_and_script_text(self):
        graph = self.model()
        graph['project']['name'] = '</script><script>throw "injected"</script>'
        html, result = render(graph)
        self.assertTrue(result['valid'])
        self.assertNotIn('<script src=', html)
        self.assertNotIn('__LITFLUX_GRAPH__', html)
        self.assertNotIn('__DAGRE_SCRIPT__', html)
        self.assertIn((SKILL / 'LICENSE').read_text(encoding='utf-8'), html)
        self.assertIn((SKILL / 'assets/DAGRE-LICENSE.txt').read_text(encoding='utf-8'), html)
        self.assertIn('\\u003c/script\\u003e', html)
        self.assertNotIn('<script>throw "injected"', html)

    def test_reject_invalid_model(self):
        graph = self.model()
        graph['operations'][0]['inputs'][0]['entity'] = 'missing'
        with self.assertRaises(ValueError):
            render(graph)

    def test_template_tokens_in_model_and_source_remain_literal(self):
        tokens = re.findall(r'__[A-Z_]+__', (SKILL / 'assets/viewer.html').read_text(encoding='utf-8'))
        graph = self.model()
        graph['unknowns'] = tokens
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = '\n'.join(tokens) + '\n'
            (root / 'app.py').write_text(code, encoding='utf-8')
            graph['operations'][0]['source']['endLine'] = len(tokens)
            page, _ = render(graph, root)
        payload = json.loads(re.search(r'class="sf-model">(.*?)</script>', page, re.S)[1])
        self.assertEqual(tokens, payload['unknowns'])
        self.assertEqual(code.rstrip('\n'), payload['sourceFiles']['app.py']['ranges'][0]['code'])

    def test_function_export_does_not_include_uncited_lines_or_old_full_file_cache(self):
        graph = self.model()
        for operation in [graph['operations'][0], *graph['operations'][0]['expansion']['operations']]:
            operation['source'].update(startLine=2, endLine=2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app.py').write_text('UNSELECTED_MARKER\nselected()\nANOTHER_UNSELECTED_LINE\n', encoding='utf-8')
            page, _ = render(graph, root, source_excerpts='functions')
        self.assertNotIn('UNSELECTED_MARKER', page)
        self.assertNotIn('ANOTHER_UNSELECTED_LINE', page)
        self.assertEqual([{'startLine': 2, 'endLine': 2, 'code': 'selected()'}], graph['sourceFiles']['app.py']['ranges'])
        graph['sourceFiles']['app.py'] = {'code': 'UNSELECTED_MARKER\nselected()\n'}
        page, _ = render(graph, source_excerpts='functions')
        self.assertNotIn('UNSELECTED_MARKER', page)



    def test_large_model_preserved_by_compression(self):
        graph = self.model()
        graph['unknowns'] = ['A repeated source note. ' * 12000]
        html, _ = render(graph)
        payload = json.loads(re.search(r'class="sf-model">(.*?)</script>', html, re.S)[1])
        self.assertEqual(payload['_litfluxCompression'], 'gzip')
        restored = json.loads(gzip.decompress(base64.b64decode(payload['data'])))
        self.assertEqual(restored, graph)

    def test_event_legend_and_entry_badge_use_an_envelope_not_lightning(self):
        graph = json.loads((SKILL / 'references' / 'event-example.json').read_text(encoding='utf-8'))
        html, _ = render(graph)
        self.assertNotIn('⚡', html)
        self.assertIn('sf-legend-event', html)
        self.assertIn('sf-event-trigger', html)
        self.assertIn('sf-tab-event', html)

    def test_source_excerpt_and_directory_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'repo'
            root.mkdir()
            (root / 'app.js').write_text('one\ntwo\nthree\n', encoding='utf-8')
            (root.parent / 'private.js').write_text('DO NOT INCLUDE', encoding='utf-8')
            graph = self.model()
            op = graph['operations'][0]
            op['source'] = {'path': 'app.js', 'startLine': 2, 'endLine': 3, 'url': None}
            render(graph, root)
            self.assertEqual(op['sourceCode'], 'two\nthree')
            graph = self.model()
            graph['operations'][0]['source'] = {'path': '../private.js', 'startLine': 1, 'endLine': 1, 'url': None}
            html, _ = render(graph, root)
            self.assertNotIn('DO NOT INCLUDE', html)

    def test_conversation_locale_has_no_manual_switch_and_is_not_restored_from_ui_storage(self):
        graph = self.model()
        graph.setdefault('presentation', {})['language'] = 'zh'
        page, _ = render(graph)
        self.assertIn("language:\"zh\"", page)
        self.assertNotIn('data-language-choice="', page)
        self.assertNotIn('saved?.language', page)
        english, _ = render(graph, language='en')
        self.assertIn('language:"en"', english)
        with self.assertRaises(ValueError):
            render(graph, language='invalid')

    def test_source_and_stop_metadata(self):
        graph = self.model()
        op = graph['operations'][0]['expansion']['operations'][0]
        op['stop'] = {'reason': 'simple', 'detail': 'Direct primitive operation.'}
        self.assertTrue(validate(graph)['valid'])
        op['stop']['reason'] = 'complex-but-skipped'
        self.assertFalse(validate(graph)['valid'])
        op['stop']['reason'] = 'simple'
        op['source'] = {'path': 'app.js', 'startLine': 5, 'endLine': 2, 'url': None}
        self.assertFalse(validate(graph)['valid'])

    def test_omitted_stop_needs_a_real_source_location(self):
        graph = self.model()
        op = graph['operations'][0]['expansion']['operations'][0]
        op['stop'] = {'reason': 'omitted', 'detail': 'Known implementation outside this review.',
                      'review': {'reason': 'The selected scope excludes it.', 'reopen': 'Reopen when the scope changes.'}}
        op['source'] = {'path': 'app.js', 'startLine': 1, 'endLine': 1, 'url': None}
        self.assertTrue(validate(graph)['valid'])
        op['stop'].pop('review')
        self.assertTrue(validate(graph)['valid'])
        op.pop('source')
        self.assertFalse(validate(graph)['valid'])

    def test_source_panel_shows_all_stop_reasons_and_completion(self):
        template = (SKILL / 'assets' / 'viewer.html').read_text(encoding='utf-8')
        self.assertIn('stop?.detail', template)
        self.assertIn('op.controlCompletion', template)

    def test_function_graph_layout_and_shared_styles_are_embedded(self):
        html, _ = render(self.model())
        self.assertNotIn('__LITFLUX_FUNCTION_GRAPH_LAYOUT__', html)
        self.assertIn('LitFluxFunctionLayout', html)
        self.assertIn('sf-recursion-shared', html)
        self.assertIn('sf-recursion-remote', html)

    def test_inference_and_explanation_contracts(self):
        graph = self.model()
        entity = graph['entities'][0]
        entity.update(typeOrigin='inferred', typeConfidence='high', typeReason='Object construction at source line 4.',
                      typeEvidence=[graph['evidence'][0]['id']])
        op = graph['operations'][0]
        op['explanation'] = {'purpose': 'Prepare the application.', 'steps': ['Read configuration.'],
                             'result': 'Initialized resources.', 'caveats': []}
        op['signatureInference'] = {'text': '(config: Config) => App', 'reason': 'Constructor and returns.', 'confidence': 'medium'}
        self.assertTrue(validate(graph)['valid'])
        entity['typeEvidence'] = ['missing']
        self.assertFalse(validate(graph)['valid'])
        entity['typeEvidence'] = [graph['evidence'][0]['id']]
        op['explanation']['steps'] = 'not an array'
        self.assertFalse(validate(graph)['valid'])


if __name__ == '__main__':
    unittest.main()
