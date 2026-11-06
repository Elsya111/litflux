"""Final-audit failures remain reproducible at their real entry points."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/litflux'
sys.path[:0] = [str(SKILL / 'scripts'), str(ROOT / 'tests')]
import build_graph
from business_views import normalize_component_invocations
from compile_review import prepare, review_structure_errors, has_component_providers
from render_graph import render
from route_language import authoring_language
from quality_audit import STORY_FIELDS
from test_business_dag import fixture, simple_stop, source_ranges
from test_build_gate import full_review, attach_receipts, write_json


class FinalAuditRegressionTests(unittest.TestCase):
    def source_case(self, directory):
        graph, spec = fixture()
        graph['project']['sourceKind'] = 'code'
        spec['nodes'][2].update(sourceRanges=source_ranges(), stop=simple_stop())
        source = directory / 'source'
        source.mkdir()
        (source / 'app.py').write_text('def fixture(): return "before"\n', encoding='utf-8')
        review = full_review(spec)
        attach_receipts(graph, review, source_root=source)
        return graph, review, source

    def test_raw_cli_does_not_inherit_accepted_or_stale_receipts(self):
        graph, _ = fixture()
        graph['project']['sourceKind'] = 'code'
        graph['presentation'].update(deliveryStatus='accepted', qualityRevision='stale-quality',
                                     engineRevision='stale-engine', prepared=True,
                                     sourceFingerprint={'mode': 'files', 'files': {}})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / 'model.json', graph)
            result = subprocess.run([sys.executable, str(SKILL / 'scripts/render_graph.py'),
                                     str(root / 'model.json'), str(root / 'preview.html'), '--language', 'en'],
                                    capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            text = (root / 'preview.html').read_text(encoding='utf-8')
            self.assertIn('"deliveryStatus":"draft"', text)
            self.assertNotIn('"qualityRevision":"stale-quality"', text)
            self.assertNotIn('"engineRevision":"stale-engine"', text)
            self.assertNotIn('"sourceFingerprint":', text)

    def test_prepared_delivery_preserves_current_acceptance_and_source_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            graph, review, source = self.source_case(Path(directory))
            compiled = prepare(graph, review, source_root=source)['graph']
            html, _ = render(compiled, source, language='en', prepared=True)
            self.assertIn('"deliveryStatus":"accepted"', html)
            self.assertEqual(compiled['presentation']['sourceFingerprint']['files']['app.py'],
                             compiled['sourceFiles']['app.py']['sha256'])

    def test_final_build_rejects_source_changed_after_its_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph, review, source = self.source_case(root)
            write_json(root / 'model.json', graph)
            write_json(root / 'review.json', review)
            original = build_graph.render

            def change_before_embedding(*args, **kwargs):
                (source / 'app.py').write_text('def fixture(): return "after"\n', encoding='utf-8')
                return original(*args, **kwargs)

            with patch.object(build_graph, 'render', side_effect=change_before_embedding):
                with self.assertRaisesRegex(ValueError, 'Source changed after evidence verification'):
                    build_graph.build(root / 'model.json', root / 'output', root / 'review.json', source)
            self.assertFalse((root / 'output').exists())

    def test_source_edit_during_embedding_is_rejected_before_returning_html(self):
        with tempfile.TemporaryDirectory() as directory:
            graph, review, source = self.source_case(Path(directory))
            compiled = prepare(graph, review, source_root=source)['graph']
            original = Path.read_bytes
            reads = 0

            def edit_after_read(path):
                nonlocal reads
                data = original(path)
                if path == source / 'app.py':
                    reads += 1
                    if reads == 2:
                        path.write_text('def fixture(): return "changed during export"\n', encoding='utf-8')
                return data

            with patch.object(Path, 'read_bytes', edit_after_read):
                with self.assertRaisesRegex(ValueError, 'Source changed after evidence verification'):
                    render(compiled, source, prepared=True)
            self.assertEqual(compiled['presentation']['sourceFingerprint']['files']['app.py'],
                             compiled['sourceFiles']['app.py']['sha256'])

    def test_prepared_render_rejects_changed_engine_and_missing_source_root(self):
        with tempfile.TemporaryDirectory() as directory:
            graph, review, source = self.source_case(Path(directory))
            compiled = prepare(graph, review, source_root=source)['graph']
            with patch('quality_audit.engine_revision', return_value='different-engine'):
                with self.assertRaisesRegex(ValueError, 'engine changed'):
                    render(copy.deepcopy(compiled), source, prepared=True)
            with self.assertRaisesRegex(ValueError, 'same --source-root'):
                render(compiled, prepared=True)

    def test_each_reading_range_requires_an_actual_reader(self):
        graph, spec = fixture()
        review = full_review(spec)
        for reader in (None, '', '  ', 42):
            review['reading']['sources']['app.py']['reader'] = reader
            with self.subTest(reader=reader):
                self.assertTrue(any('.reader' in error for error in review_structure_errors(review, graph)))

    def test_multiple_real_readers_are_preserved(self):
        graph, spec = fixture()
        review = full_review(spec)
        review['reading']['sources']['app.py'] = [
            {'startLine': 1, 'endLine': 1, 'reader': 'reader-a'},
            {'startLine': 2, 'endLine': 2, 'reader': 'reader-b'}]
        attach_receipts(graph, review)
        self.assertEqual('accepted', prepare(graph, review)['deliveryStatus'])
        self.assertEqual(['reader-a', 'reader-b'], [r['reader'] for r in review['reading']['sources']['app.py']])

    def test_receiver_evidence_cannot_waive_component_acceptance(self):
        graph, spec = fixture()
        call = graph['operations'][0]['expansion']['operations'][1]
        call['methodCall'] = {'receivers': ['engine']}
        call['inputs'][1]['relation'] = 'dependency'
        self.assertTrue(has_component_providers(graph))
        review = full_review(spec)
        with self.assertRaisesRegex(ValueError, 'componentProviders.*passed'):
            prepare(graph, review)
        self.assertEqual('invocation', call['inputs'][1]['relation'])

    def test_receiver_provider_is_required_in_view_and_story(self):
        graph, spec = fixture()
        graph['components'][0]['presentation'] = {'importance': 'main'}
        graph['operations'][0]['expansion']['operations'][1]['methodCall'] = {'receivers': ['engine']}
        for plan in spec['nodes'][0]['views'].values():
            plan['concepts'] = [c for c in plan['concepts'] if c['members'] != ['engine']]
        review = full_review(spec)
        review['acceptance']['checks']['componentProviders'] = {'status': 'passed', 'evidence': 'app.py:1 provides the engine.'}
        draft = prepare(graph, review, delivery=False)
        self.assertEqual(['engine'], draft['semanticAudit']['views']['entry']['components']['expected'])
        self.assertTrue(any('direct resource/provider' in error for error in draft['semanticAudit']['errors']))

    def test_data_receivers_stay_data_and_invalid_receiver_ids_fail(self):
        graph, _ = fixture()
        call = graph['operations'][0]['expansion']['operations'][1]
        call['methodCall'] = {'receivers': ['terms']}
        normalize_component_invocations(graph)
        self.assertNotEqual('invocation', call['inputs'][0].get('relation'))
        self.assertFalse(has_component_providers(graph))
        call['methodCall']['receivers'] = ['missing-input']
        with self.assertRaisesRegex(ValueError, 'methodCall.receivers'):
            normalize_component_invocations(graph)

    def test_english_story_fields_and_na_reasons_are_checked(self):
        for field in STORY_FIELDS:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'story.' + field):
                authoring_language({'language': 'en', 'story': {field: '\u4e2d\u6587\u4e1a\u52a1\u8bf4\u660e'}})
        with self.assertRaisesRegex(ValueError, 'reason'):
            authoring_language({'language': 'en', 'story': {'branches': {'status': 'not-applicable', 'reason': '\u4e2d\u6587'}}})
        self.assertEqual('en', authoring_language({'language': 'en', 'inputs': ['\u539f\u59cb\u6807\u8bc6\u7b26'],
            'story': {'branches': {'status': 'not-applicable', 'reason': 'No branches.', 'evidence': ['\u6e90\u7801.py:1']}}}))

    def test_source_budget_keeps_both_branches_and_their_ports(self):
        template = (SKILL / 'assets/viewer.html').read_text(encoding='utf-8')
        start = template.index('  function budgetView(')
        function = template[start:template.index('\n  function ', start + 3)]
        script = '''const scope=null,dependencies=new Map(),decisionSpecs=()=>[],decisionApplies=()=>true;
const splitBoundaryOutputs=x=>x,sharedReturnView=x=>x,compactCore=x=>x;
const ops=['yes','no'].map(id=>({id,inputs:[{entity:'request'}],outcomes:[{outputs:[{entity:id+'-reply'}]}]}));
const model={operations:ops},visible={ops,entities:['request','yes-reply','no-reply'].map(id=>({id})),boundary:new Map([['request','input']]),portVisible:()=>true};
''' + function + '''
const value=budgetView(visible,'root');if(value.ops.length!==2||value.entities.length!==3||!value.portVisible({entity:'no-reply'}))throw Error('Source projection discarded an unselected branch');
'''
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == '__main__':
    unittest.main()
