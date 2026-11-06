"""Author diagnostics preserve source coordinates and actual selection semantics."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'skills/litflux/scripts')]
from authoring_check import check_authoring, field_errors
from business_views import normalize_decisions, validate_source_review
from compile_review import prepare
from quality_audit import entry_receipt_status, default_binding_errors
from test_business_dag import fixture
from test_build_gate import full_review
from test_redesign_contracts import provider_fixture


class AuthoringWorkflowTests(unittest.TestCase):
    def test_complete_declared_examples_compile_without_fake_acceptance(self):
        path=Path(__file__).resolve().parents[1]/'skills/litflux/examples/authoring-cases.json'
        cases=json.loads(path.read_text(encoding='utf8'))['cases']
        for name,case in cases.items():
            with self.subTest(case=name):
                self.assertNotIn('qa',case['review'])
                result=prepare(copy.deepcopy(case['model']),copy.deepcopy(case['review']),delivery=False)
                self.assertEqual([],result['semanticAudit']['errors'])
        shared=prepare(copy.deepcopy(cases['shared-with-views']['model']),copy.deepcopy(cases['shared-with-views']['review']),delivery=False)['graph']['presentation']['businessDAG']
        self.assertEqual(2,len([e for e in shared['edges'] if e['to']=='shared']))
        self.assertTrue(next(n for n in shared['nodes'] if n['id']=='shared')['views'])

    def test_media_dispatch_cannot_drop_a_provider_or_fake_a_fixed_default(self):
        case=json.loads((Path(__file__).resolve().parents[1]/'skills/litflux/examples/authoring-cases.json').read_text(encoding='utf8'))['cases']['input-dispatch']
        graph,review=copy.deepcopy(case['model']),copy.deepcopy(case['review'])
        review['semanticInventory']['entry']['implementationSets'][0]['cases'].pop()
        result=prepare(graph,review,delivery=False)
        self.assertTrue(any('cases must cover exactly' in e for e in result['semanticAudit']['errors']))
        for bad in [None,'a case',[{'call':[]}]]:
            graph,review=copy.deepcopy(case['model']),copy.deepcopy(case['review'])
            review['semanticInventory']['entry']['implementationSets'][0]['cases']=bad
            result=prepare(graph,review,delivery=False)
            self.assertTrue(result['semanticAudit']['errors'])
    def test_resolution_evidence_does_not_relocate_the_invocation(self):
        graph, _ = fixture()
        operations = {op['id']: op for op in graph['operations'][0]['expansion']['operations']}
        record = {'sourceCalls': [{'call': 'worker.run', 'line': 12, 'receiverType': 'Worker',
            'implementation': 'execute', 'resolution': 'resolved', 'disposition': 'simple',
            'reason': 'Direct conversion.', 'evidence': {'path': 'assembly.py', 'startLine': 30, 'endLine': 34}}]}
        validate_source_review('worker', record, operations,
            source_ranges=[{'path': 'caller.py', 'startLine': 10, 'endLine': 20}])
        record['sourceCalls'][0]['callSource'] = {'path': 'wrong.py', 'startLine': 12, 'endLine': 12}
        with self.assertRaisesRegex(ValueError, 'sourceCalls line'):
            validate_source_review('worker', record, operations, source_ranges=[{'path': 'caller.py', 'startLine': 10, 'endLine': 20}])

    def test_misplaced_author_fields_are_aggregated_and_never_ignored(self):
        graph, spec = fixture(); review = full_review(spec)
        review['presentation'] = {'decisions': []}; review['symbls'] = {}
        graph['operations'][0]['expansion']['unusedInputs'] = []
        errors = field_errors(graph, review)
        self.assertEqual(3, len(errors))
        self.assertTrue(any(e['path'] == 'review.presentation' for e in errors))
        with self.assertRaisesRegex(ValueError, 'review.presentation'):
            prepare(graph, review, delivery=False)

    def test_preflight_lists_independent_view_errors_and_budgets_without_mutation(self):
        graph, spec = fixture(); review = full_review(spec)
        review['businessDAG']['nodes'][0]['views']['0']['steps'][0]['label'] = ''
        other = copy.deepcopy(review['businessDAG']['nodes'][0]); other['id'] = 'another'
        other['views']['0']['steps'][1]['description'] = ''
        review['businessDAG']['nodes'].append(other)
        before = copy.deepcopy([graph, review]); result = check_authoring(graph, review)
        self.assertEqual(before, [graph, review])
        self.assertEqual(2, len([e for e in result['errors'] if e['code'] == 'view.contract']))
        self.assertEqual(2, len(result['budgets'])); self.assertEqual('draft', result['deliveryStatus'])
        self.assertEqual(5, result['budgets'][0]['decisionRemaining'])
        self.assertEqual(['engine', 'reply', 'request'], result['budgets'][0]['boundaryIds'])

    def test_preflight_diagnoses_malformed_scope_without_scanning_or_crashing(self):
        graph, spec = fixture(); review = full_review(spec)
        review['sourceScope'] = {'include': [None], 'files': []}
        result = check_authoring(graph, review, source_root=Path(__file__).parent)
        self.assertFalse(result['valid'])
        self.assertEqual([], result['sourceInventory'])
        self.assertTrue(any(e['path'] == 'review.sourceScope.include' for e in result['errors']))

    def test_branch_authoring_derives_only_unambiguous_compatibility_fields(self):
        graph = {'presentation': {'decisions': [{'id': 'gate', 'criterionInputs': ['config'],
            'carriedInputs': ['payload'], 'branches': [{'id': 'pdf', 'targets': ['parse.pdf'], 'members': ['parse.pdf']},
            {'id': 'text', 'targets': ['parse.text'], 'members': ['parse.text']}]}]}}
        normalize_decisions(graph); gate = graph['presentation']['decisions'][0]
        self.assertEqual(['config', 'payload'], gate['inputs'])
        self.assertEqual(['parse.pdf'], gate['yes']); self.assertEqual(['parse.text'], gate['no'])
        gate['yes'] = ['parse.text']
        with self.assertRaisesRegex(ValueError, 'yes: conflicts with branches targets'):
            normalize_decisions(graph)

    def test_draft_reports_current_stale_missing_and_failed_browser_evidence(self):
        graph, spec = fixture(); review = full_review(spec); draft = prepare(graph, review, delivery=False)
        current = entry_receipt_status(draft['graph'], review, draft['qualityRevision'])
        self.assertEqual('passed', current['status']); self.assertFalse(current['executedByBuild'])
        self.assertEqual('stale', entry_receipt_status(draft['graph'], review, 'new-revision')['status'])
        review['qa']['entryAuditFile'] = 'missing.json'
        with tempfile.TemporaryDirectory() as directory:
            missing = entry_receipt_status(draft['graph'], review, draft['qualityRevision'], directory)
            self.assertEqual('missing', missing['status']); self.assertIn(directory, missing['resolvedPath'])

    def test_runtime_unknown_selection_requires_an_unknown_boundary(self):
        graph, review, _ = provider_fixture(); graph['presentation']['defaultBindings'] = []
        review['semanticInventory'] = {'entry': {'implementationSets': [{'call': 'execute',
            'mode': 'runtime-unknown', 'candidates': ['local.run', 'remote.run'],
            'reason': 'Receiver is supplied by an external host.',
            'evidence': [{'path': 'app.py', 'startLine': 1, 'endLine': 1}]}]}}
        self.assertEqual([], default_binding_errors(graph, review))
        review['businessDAG']['nodes'][2]['stop']['reason'] = 'simple'
        self.assertTrue(any('unknown runtime receiver' in e for e in default_binding_errors(graph, review)))


if __name__ == '__main__':
    unittest.main()
