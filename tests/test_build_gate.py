"""Independent QA, planning, delivery structure and build-report gates."""
import json
import copy
import subprocess
import sys
import tempfile
import hashlib
import base64
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'litflux'
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_graph import build
from compile_review import (ACCEPTANCE_CHECKS, planning_errors, prepare, qa_gate_errors,
                            review_structure_errors, split_warning_policy, warning_summary)
from test_business_dag import fixture
from quality_audit import QA_CHECKS, STORY_FIELDS, entry_manifest

EVIDENCE_DIRECTORY = tempfile.TemporaryDirectory(prefix='litflux-test-evidence-')


def attach_receipts(graph, review, source_root=None):
    """Declared test data for gate tests; never described as actual browser/QA work."""
    root = Path(EVIDENCE_DIRECTORY.name) / str(len(list(Path(EVIDENCE_DIRECTORY.name).iterdir())))
    root.mkdir()
    try:
        draft = prepare(copy.deepcopy(graph), review, source_root=source_root, delivery=False)
        revision = draft['qualityRevision']
        manifest = entry_manifest(draft['graph'])
    except ValueError:
        revision, manifest = 'invalid-negative-test-input', {'scopes': [], 'calls': [], 'readings': []}
    evidence = root / 'declared-evidence.md'
    evidence.write_text('A declared regression receipt, not real QA or browser acceptance. app.py:1\n', encoding='utf-8')
    ref = {'path': evidence.name, 'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}
    screenshot = root / 'declared-screenshot.png'
    screenshot.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZ1kAAAAASUVORK5CYII='))
    image_ref = {'path': screenshot.name, 'sha256': hashlib.sha256(screenshot.read_bytes()).hexdigest()}
    write_json(root / 'qa.json', {'revision': revision, 'agent': review['qa']['agent'],
        'phases': ['independent', 'compare'], 'checks': {key: {'status': 'passed',
        'capability': 'image' if key == 'visuals' else 'source', 'evidence': [ref, image_ref] if key == 'visuals' else [ref]} for key in QA_CHECKS}})
    write_json(root / 'entries.json', {'revision': revision, 'engine': 'browser', 'status': 'passed',
        'scopes': [{**item, 'status': 'passed'} for item in manifest['scopes']],
        'calls': [{**item, 'status': 'passed', 'mode': item['expected'], 'target': 'business-node.' + item['businessNode'],
                   'interaction': {'entered': True, 'returned': True, 'target': 'business-node.' + item['businessNode']}} for item in manifest['calls']], 'failures': []})
    # Gate fixtures declare protocol records; they are never actual UI/QA runs.
    from graphlib import TopologicalSorter
    receipt_path = root / 'entries.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    guide_nodes = draft['graph']['presentation']['businessDAG']['nodes'] if manifest.get('guides') else []
    receipt['guides'] = []
    for item in manifest.get('guides', []):
        definition = item['definition']
        target = next(('business-node.' + node['id'] for node in guide_nodes
                       if node['scope'] == definition or 'business-node.' + node['id'] == definition), definition)
        receipt['guides'].append({**item, 'status': 'passed', 'enabled': bool(definition),
            'mode': 'graph', 'target': target, 'entered': bool(definition), 'returned': True,
            'reason': '' if definition else 'No modeled definition for this source-only symbol.'})
    receipt['readings'] = []
    for item in manifest['readings']:
        predecessors = {key: set() for key in item['expectedDecisions'] + item['expectedActiveCalls']}
        for pair in item['expectedOrder']:
            predecessors[pair['after']].add(pair['before'])
        order = list(TopologicalSorter(predecessors).static_order())
        receipt['readings'].append({**item, 'status': 'passed', 'order': order, 'complete': True,
            'iterationComplete': True, 'blocked': [], 'invalid': [], 'executed': [],
            'interaction': {'started': True, 'advanced': len(order), 'selected': order}})
    write_json(receipt_path, receipt)
    review['qa'].update({'checklistFile': str(root / 'qa.json'), 'entryAuditFile': str(root / 'entries.json')})
    return review


def qa(**overrides):
    record = {'delegated': True, 'independent': True, 'agent': 'independent-qa',
              'phases': ['independent', 'compare'],
              'evidence': 'Read app.py:1, the model and the rendered page independently.'}
    record.update(overrides)
    return record


def acceptance(**overrides):
    record = {'checks': {
        'boundaryAndMeaning': {'status': 'passed', 'evidence': 'app.py:1 establishes the main workflow boundary.'},
        'depthAndSource': {'status': 'passed', 'evidence': 'planning breadth=project depth=key-paths; app.py:1 checked.'},
        'branchesAndNavigation': {'status': 'passed', 'evidence': 'app.py:1 and #litflux-canvas-app branches/navigation checked.'},
        'componentProviders': {'status': 'not-applicable', 'evidence': 'app.py:1 has no invocation component provider.'},
    }, 'issues': []}
    record.update(overrides)
    return record


def planning():
    return {'breadth': 'project', 'depth': 'key-paths', 'confirmedByUser': True,
            'delegated': False, 'notes': 'User confirmed the default depth.'}


def full_review(spec, language='en'):
    for node in spec['nodes']:
        for plan in (node.get('views') or {}).values():
            plan['story'] = {key: 'The declared request is prepared and answered through the fixture boundary.'
                             for key in STORY_FIELDS}
    review = {
        'language': language, 'authoringLanguage': language, 'author': 'author-agent',
        'planning': planning(),
        'sourceScope': {'include': ['app.py'], 'exclude': [], 'files': {
            'app.py': {'role': 'primary', 'owner': 'author-agent', 'reason': 'The complete declared fixture.'}}},
        'workflows': [{'id': 'main', 'root': 'service', 'label': 'Answer requests',
                       'description': 'Prepare and process a request.'}],
        'entrypoints': {'main': {'kind': 'command', 'trigger': 'run the fixture command',
                                 'reason': 'The fixture declares one external command.',
                                 'source': {'path': 'app.py', 'startLine': 1, 'endLine': 1}}},
        'reading': {'sources': {'app.py': {'startLine': 1, 'endLine': 1, 'reader': 'author-agent'}}},
        'delivery': {'scope': 'project', 'inventoryReviewed': True, 'description': 'Explain the fixture request workflow.',
                     'goals': [{'id': 'main', 'label': 'Answer a request', 'workflow': 'main', 'status': 'covered',
                                'source': {'path': 'app.py', 'startLine': 1, 'endLine': 1}}]},
        'businessDAG': spec,
        'qa': qa(), 'acceptance': acceptance(),
    }
    graph, _ = fixture()
    review['summary'] = {'description': 'Prepare a declared request and produce its reply.',
        'goal': 'Answer fixture requests.', 'features': ['Request processing'],
        'highlights': ['A shared engine context'], 'stack': ['Declared model'],
        'goalSource': {'path': 'app.py', 'startLine': 1, 'endLine': 1}}
    review['files'] = {'app.py': {'description': 'Declares request preparation and reply processing.'}}
    review['directories'] = {'.': {'description': 'The declared fixture source.'}}
    review['symbols'] = {op['definition']: {'kind': 'function', 'definition': op['id'],
        'label': 'Process the request' if op['id'] == 'service' else 'Prepare request' if op['id'] == 'prepare' else 'Produce reply',
        'description': 'A declared part of the request-to-reply path.', 'source': op['source'], 'confidence': 'high'}
        for op in [graph['operations'][0], *graph['operations'][0]['expansion']['operations']]}
    review['guide'] = {'runtimeStory': 'Prepare a request and use the shared engine to produce a reply.',
        'mechanisms': [], 'focus': []}
    review['semanticInventory'] = {node['id']: {'role': 'utility', 'reason': 'The complete declared fixture boundary.',
        'complexity': 'simple', 'sourceCalls': [], 'delegates': [], 'noProjectCalls': True, 'implementationSets': [],
        'control': {'branches': [], 'loops': [], 'exceptions': [], 'awaits': []}} for node in spec['nodes']}
    return attach_receipts(graph, review)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


class GateTests(unittest.TestCase):
    def test_qa_requires_author_independence_and_anchored_evidence(self):
        graph, spec = fixture()
        review = full_review(spec)
        self.assertEqual([], qa_gate_errors(review, graph))
        self.assertTrue(any('author' in error for error in qa_gate_errors({**review, 'author': ''}, graph)))
        self.assertTrue(any('independent' in error for error in qa_gate_errors(
            {**review, 'qa': qa(agent='author-agent')}, graph)))
        self.assertTrue(any('anchor' in error for error in qa_gate_errors(
            {**review, 'qa': qa(evidence='looks good')}, graph)))
        self.assertTrue(any('anchor' in error for error in qa_gate_errors(
            {**review, 'acceptance': acceptance(checks={
                **acceptance()['checks'],
                'boundaryAndMeaning': {'status': 'passed', 'evidence': 'looks good'}})}, graph)))

    def test_all_four_acceptance_checks_are_required(self):
        graph, spec = fixture()
        review = full_review(spec)
        broken = acceptance()
        broken['checks']['branchesAndNavigation'] = {'status': 'failed',
                                                      'evidence': 'app.py:1 and #litflux-canvas-app'}
        self.assertTrue(any('branchesAndNavigation' in error for error in qa_gate_errors(
            {**review, 'acceptance': broken}, graph)))
        missing = acceptance()
        missing['checks'].pop('depthAndSource')
        self.assertTrue(any('depthAndSource' in error for error in qa_gate_errors(
            {**review, 'acceptance': missing}, graph)))

    def test_issues_need_severity_and_only_blockers_fail(self):
        graph, spec = fixture()
        review = full_review(spec)
        self.assertTrue(any('issues[0]' in error for error in qa_gate_errors(
            {**review, 'acceptance': acceptance(issues=[{'id': 'p1'}])}, graph)))
        self.assertEqual([], qa_gate_errors(
            {**review, 'acceptance': acceptance(issues=[{'severity': 'minor', 'note': 'display only'}])}, graph))
        self.assertTrue(any('blocker' in error for error in qa_gate_errors(
            {**review, 'acceptance': acceptance(issues=[{'severity': 'blocker'}])}, graph)))

    def test_planning_is_required(self):
        self.assertTrue(planning_errors({}))
        self.assertEqual([], planning_errors({'planning': planning()}))
        self.assertTrue(planning_errors({'planning': {'breadth': 'project', 'depth': 'key-paths'}}))

    def test_review_structure_requires_scope_entrypoints_reading_and_dag(self):
        graph, spec = fixture()
        review = full_review(spec)
        errors = review_structure_errors(review, graph)
        self.assertEqual([], errors)
        self.assertTrue(any('sourceScope' in error for error in review_structure_errors(
            {**review, 'sourceScope': None}, graph)))
        self.assertTrue(any('entrypoints' in error for error in review_structure_errors(
            {**review, 'entrypoints': {}}, graph)))
        self.assertTrue(any('reading' in error for error in review_structure_errors(
            {**review, 'reading': {}}, graph)))
        self.assertTrue(any('businessDAG' in error for error in review_structure_errors(
            {**review, 'businessDAG': None}, graph)))

    def test_warning_policy_keeps_errors_and_acknowledges_warnings(self):
        warnings, hints, acknowledged = split_warning_policy(
            [{'kind': 'primaryMissing', 'severity': 'warning', 'scope': 'internal.a'},
             {'kind': 'budgetUnderuse', 'severity': 'hint', 'scope': 'internal.a'},
             {'kind': 'broken', 'severity': 'error', 'scope': 'internal.a'}],
            {'acknowledge': [{'kind': 'primaryMissing', 'scope': 'internal.a', 'reason': 'reviewed', 'evidence': 'app.py:1'},
                             {'kind': 'budgetUnderuse', 'scope': 'internal.a', 'reason': 'reviewed', 'evidence': 'app.py:1'}]})
        self.assertEqual(['broken'], [item['kind'] for item in warnings])
        self.assertEqual([], hints)
        self.assertEqual({'primaryMissing', 'budgetUnderuse'},
                         {item['kind'] for item in acknowledged})
        summary = warning_summary(warnings, hints, acknowledged)
        self.assertEqual(3, sum(summary['byKind'].values()))


class BuildTests(unittest.TestCase):
    def test_empty_or_non_object_reviews_cannot_bypass_delivery_gates(self):
        for review in ({}, None, [], 'not a review'):
            with self.subTest(review=review):
                graph, _ = fixture()
                with self.assertRaisesRegex(ValueError, 'non-empty review'):
                    prepare(graph, review)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph, _ = fixture()
            write_json(root / 'model.json', graph)
            write_json(root / 'review.json', {})
            with self.assertRaisesRegex(ValueError, 'non-empty review'):
                build(root / 'model.json', root / 'out', root / 'review.json')
            self.assertFalse((root / 'out').exists())
            result = subprocess.run(
                [sys.executable, '-B', str(SKILL / 'scripts/render_graph.py'),
                 str(root / 'model.json'), str(root / 'preview.html'),
                 '--review', str(root / 'review.json')], capture_output=True)
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((root / 'preview.html').exists())

    def test_build_checks_language_declarations_and_authored_prose(self):
        graph, spec = fixture()
        review = full_review(spec)
        review['language'] = 'zh'
        with self.assertRaisesRegex(ValueError, 'Language route conflicts'):
            prepare(graph, review, language='en')
        for origin in ('review', 'model'):
            graph, spec = fixture()
            review = full_review(spec)
            if origin == 'review':
                spec['nodes'][0]['description'] = '中文业务说明'
            else:
                graph['operations'][0]['description'] = '中文业务说明'
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, 'English review contains Chinese prose'):
                prepare(graph, review, language='en')
        graph, spec = fixture()
        graph['operations'][0]['sourceCode'] = '# 原始源码'
        self.assertTrue(prepare(graph, full_review(spec), language='en')['valid'])

    def test_endpoint_ranges_are_checked_against_source_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app.py').write_text('pass\n', encoding='utf-8')
            for path, line in (('app.py', 999), ('missing.py', 1), ('../outside.py', 1)):
                graph, spec = fixture()
                source = {'path': path, 'startLine': line, 'endLine': line, 'url': None}
                graph['operations'][0]['expansion']['operations'][0]['source'] = source
                spec['nodes'][1]['sourceRanges'] = [source]
                with self.subTest(path=path, line=line), self.assertRaisesRegex(ValueError, 'Source endpoint validation failed'):
                    prepare(graph, full_review(spec), source_root=root)
            graph, spec = fixture()
            review = full_review(spec)
            attach_receipts(graph, review, root)
            self.assertTrue(prepare(graph, review, source_root=root)['valid'])

    def test_delivery_needs_real_source_reading_and_answered_clarifications(self):
        graph, spec = fixture()
        review = full_review(spec)
        for reading in ({'instructions': ['SKILL.md']}, {'sources': ['app.py']},
                        {'sources': {'app.py': {}}}):
            with self.subTest(reading=reading), self.assertRaisesRegex(ValueError, 'reading.sources'):
                prepare(copy.deepcopy(graph), {**review, 'reading': reading})
        review['clarifications'] = [{'id': 'scope', 'question': 'Which scope?', 'status': 'answered'}]
        with self.assertRaisesRegex(ValueError, 'non-empty answer'):
            prepare(copy.deepcopy(graph), review)
        review['clarifications'][0]['answer'] = 'The whole project.'
        attach_receipts(graph, review)
        self.assertTrue(prepare(copy.deepcopy(graph), review)['valid'])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app.py').write_text('pass\n', encoding='utf-8')
            review['reading']['sources']['app.py']['endLine'] = 999
            with self.assertRaisesRegex(ValueError, 'reading.sources'):
                prepare(copy.deepcopy(graph), review, source_root=root)

    def test_qa_depth_evidence_must_match_planning(self):
        graph, spec = fixture()
        review = full_review(spec)
        for text in ('breadth=selected depth=overview; app.py:1',
                     '广度和深度已确认；app.py:1',
                     'breadth=project1 depth=key-paths_extra; app.py:1',
                     'breadth=project depth=key-paths breadth=selected; app.py:1'):
            review['acceptance']['checks']['depthAndSource']['evidence'] = text
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'match review.planning'):
                prepare(copy.deepcopy(graph), review)
        review['acceptance']['checks']['depthAndSource']['evidence'] = '广度：project 深度：key-paths； app.py:1'
        self.assertEqual([], qa_gate_errors(review, graph))

    def test_unresolved_simple_endpoint_is_reported_for_qa(self):
        graph, spec = fixture()
        spec['nodes'][1]['stop']['review']['sourceCalls'] = [{
            'call': 'engine.process', 'line': 1, 'receiverType': 'Engine',
            'resolution': 'unknown', 'disposition': 'unknown',
            'reason': 'The concrete injected implementation is unknown.'}]
        review = full_review(spec)
        review['semanticInventory']['prep']['sourceCalls'] = spec['nodes'][1]['stop']['review']['sourceCalls']
        with self.assertRaisesRegex(ValueError, 'simple eligibility failed'):
            prepare(graph, review)

    def build_fixture(self, root, review_overrides=None, check_only=False):
        graph, spec = fixture()
        model = root / 'model.json'
        review = full_review(spec)
        review.update(review_overrides or {})
        review_path = root / 'review.json'
        write_json(model, graph)
        write_json(review_path, review)
        return build(model, root / 'out', review_path, check_only=check_only)

    def test_build_writes_outputs_and_names_business_views(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.build_fixture(root)
            self.assertTrue(report['valid'])
            self.assertEqual('review', report['businessViews']['source'])
            self.assertTrue(report['businessViews']['compiled'])
            self.assertEqual('independent-qa', report['qa']['agent'])
            for name in ('litflux.graph.json', 'litflux.coverage.md', 'litflux.build-report.json'):
                self.assertTrue((root / 'out' / name).is_file())

    def test_check_only_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.build_fixture(root, check_only=True)
            self.assertTrue(report['valid'])
            self.assertFalse((root / 'out').exists())

    def test_schema_02_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph, spec = fixture()
            graph['schemaVersion'] = '0.2'
            model = root / 'model.json'
            write_json(model, graph)
            review_path = root / 'review.json'
            write_json(review_path, full_review(spec))
            with self.assertRaisesRegex(ValueError, "schemaVersion"):
                build(model, root / 'out', review_path)

    def test_missing_planning_or_structure_blocks_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'Review gates failed'):
                self.build_fixture(root, {'planning': None})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'Review gates failed'):
                self.build_fixture(root, {'entrypoints': {}})

    def test_cli_check_only_reports_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph, spec = fixture()
            model = root / 'model.json'
            review_path = root / 'review.json'
            write_json(model, graph)
            write_json(review_path, full_review(spec))
            result = subprocess.run(
                [sys.executable, '-B', str(SKILL / 'scripts' / 'build_graph.py'), str(model),
                 '--review', str(review_path), '--check-only'], cwd=root, capture_output=True,
                text=True, encoding='utf-8')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((root / '.litflux').exists())
            self.assertTrue(json.loads(result.stdout)['valid'])

    def test_render_with_review_runs_the_same_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph, spec = fixture()
            model = root / 'model.json'
            review_path = root / 'review.json'
            write_json(model, graph)
            write_json(review_path, full_review(spec))
            output = root / 'preview.html'
            result = subprocess.run(
                [sys.executable, '-B', str(SKILL / 'scripts' / 'render_graph.py'), str(model),
                 str(output), '--review', str(review_path), '--language', 'en'],
                cwd=root, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(output.is_file())

    def test_business_dag_check_avoids_normal_whole_definition_noise(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph, spec = fixture()
            model = root / 'model.json'
            review_path = root / 'review.json'
            write_json(model, graph)
            write_json(review_path, full_review(spec))
            result = subprocess.run(
                [sys.executable, '-B', str(SKILL / 'scripts' / 'business_dag.py'), 'check',
                 str(model), '--review', str(review_path)],
                cwd=root, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            kinds = {warning['kind'] for warning in payload['warnings']}
            self.assertNotIn('sourceRangeStartsAtFileHead', kinds)
            self.assertNotIn('sourceRangeCoversWholeScope', kinds)

    def test_build_requires_a_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph, _ = fixture()
            model = root / 'model.json'
            write_json(model, graph)
            with self.assertRaisesRegex(ValueError, 'review JSON is required'):
                build(model, root / 'out')

    def test_internal_entrypoint_is_only_for_selected_scope(self):
        graph, spec = fixture()
        review = full_review(spec)
        review['entrypoints']['main']['kind'] = 'internal'
        self.assertTrue(any('internal' in error for error in review_structure_errors(review, graph)))
        review['delivery']['scope'] = 'selected-workflows'
        self.assertFalse(any('internal' in error for error in review_structure_errors(review, graph)))

    def test_clarifications_must_be_typed(self):
        graph, spec = fixture()
        review = full_review(spec)
        for value in (None, 'open', ['open question'], [{'status': 'Open'}]):
            self.assertTrue(any('clarifications' in error for error in review_structure_errors(
                {**review, 'clarifications': value}, graph)), value)

    def test_malformed_goals_and_entry_bindings_raise_value_errors(self):
        graph, spec = fixture()
        review = full_review(spec)
        with self.assertRaises(ValueError):
            prepare(graph, {**review, 'delivery': {**review['delivery'], 'goals': 'main'}})
        with self.assertRaises(ValueError):
            prepare(graph, {**review, 'entryBindings': []})

    def test_fake_anchors_are_rejected(self):
        graph, spec = fixture()
        review = full_review(spec)
        review['qa']['evidence'] = 'checked in v1.2:3'
        self.assertTrue(any('anchor' in error for error in qa_gate_errors(review, graph)))
        review = full_review(spec)
        review['acceptance']['checks']['boundaryAndMeaning']['evidence'] = 'see http://x.com:80'
        self.assertTrue(any('anchor' in error for error in qa_gate_errors(review, graph)))
        review = full_review(spec)
        review['acceptance']['checks']['branchesAndNavigation']['evidence'] = 'app.py:1 litflux.'
        self.assertTrue(any('page anchor' in error for error in qa_gate_errors(review, graph)))
        review = full_review(spec)
        review['acceptance']['checks']['depthAndSource']['evidence'] = 'app.py:1 planning'
        self.assertTrue(any('breadth/depth' in error for error in qa_gate_errors(review, graph)))


if __name__ == '__main__':
    unittest.main()
