"""Project decomposition and execution calls have different, testable identities."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/litflux/scripts'))
from business_views import compile_views, apply_workflows, dag_budget_warnings
from business_dag import compile_dag, inspect_dag


def operation(key, inputs, outputs, children=None):
    return {'id': key, 'name': key, 'definition': 'example.' + key, 'signature': key + '()',
            'phase': 'main', 'trigger': 'all', 'operationKind': 'source-function',
            'inputs': [{'port': 'p' + str(i), 'entity': v, 'role': 'argument', 'required': True} for i, v in enumerate(inputs)],
            'outcomes': [{'id': 'ok', 'condition': 'success', 'outputs': [{'port': 'p' + str(i), 'entity': v, 'role': 'return'} for i, v in enumerate(outputs)]}],
            'effects': [], 'evidence': ['example'], 'source': {'path': 'app.py', 'startLine': 1, 'endLine': 1, 'url': None},
            'expansion': {'operations': children, 'bindings': []} if children else None}


def source_ranges():
    return [{'path': 'app.py', 'startLine': 1, 'endLine': 1}]


def simple_stop(detail='A direct declared source endpoint.'):
    return {'reason': 'simple', 'detail': detail,
            'review': {'sourceRangesChecked': True,
                       'reason': 'Read the direct fixture implementation and its source.',
                       'delegates': [], 'sourceCalls': [], 'noProjectCalls': True}}


def fixture():
    graph = {'schemaVersion': '0.3', 'project': {'name': 'DAG fixture', 'scope': 'A declared fixture.', 'sourceKind': 'declaration', 'coverage': [{'entry': 'Process a request', 'kind': 'business', 'status': 'covered', 'operations': ['service'], 'reason': None}]},
             'evidence': [{'id': 'example', 'kind': 'declaration', 'ref': None, 'note': 'A regression example, not target project source.'}],
             'phases': [{'id': 'main', 'label': 'Process', 'requires': [], 'completion': None, 'evidence': ['example']}], 'unknowns': [],
             'entities': [{'id': v, 'name': v, 'kind': 'value', 'scope': 'service', 'type': 'str', 'evidence': ['example']} for v in ('request', 'terms', 'reply')],
             'components': [{'id': v, 'name': v, 'kind': 'component', 'scope': 'project', 'type': 'Engine', 'evidence': ['example']} for v in ('engine',)], 'resources': [],
             'operations': [operation('service', ['request', 'engine'], ['reply'], [
                 operation('prepare', ['request'], ['terms']), operation('execute', ['terms', 'engine'], ['reply'])])],
             'presentation': {'workflows': [{'id': 'main', 'root': 'service', 'label': 'Reply', 'description': 'Prepare and process a request.'}]}}
    graph['operations'][0]['expansion']['bindings'] = [
        {'outer': 'in/p0', 'operation': 'prepare', 'inner': 'in/p0'},
        {'outer': 'in/p1', 'operation': 'execute', 'inner': 'in/p1'},
        {'outer': 'out/ok/p0', 'operation': 'execute', 'inner': 'out/ok/p0'}]
    view = {'description': 'Prepare content and use the engine to answer.', 'steps': [
        {'operation': 'prepare', 'node': 'prep', 'bindings': {}, 'label': 'Prepare content', 'description': 'Extract the content needed by the engine.'},
        {'operation': 'execute', 'node': 'run', 'bindings': {'backend': 'engine'}, 'label': 'Produce reply', 'description': 'Use the engine to turn prepared content into a reply.'}],
        'concepts': [{'members': [v], 'label': label, 'description': 'The role of ' + label, 'meaning': 'One source identity.'}
                     for v, label in [('request', 'User request'), ('terms', 'Prepared content'), ('reply', 'Final reply'), ('engine', 'Processing engine')]]}
    spec = {'roots': {'main': 'entry'}, 'nodes': [
        {'id': 'entry', 'scope': 'service', 'label': 'Answer requests', 'description': view['description'], 'bindings': {'backend': 'engine'}, 'views': {'0': view}},
        {'id': 'prep', 'scope': 'prepare', 'label': 'Prepare content', 'description': 'Extract request content.', 'bindings': {}, 'sourceRanges': source_ranges(), 'stop': simple_stop('This direct content extraction is clear from its source.')},
        {'id': 'run', 'scope': 'execute', 'label': 'Produce reply', 'description': 'Use the bound engine.', 'bindings': {'backend': 'engine'}, 'stop': {'reason': 'external', 'detail': 'The actual engine implementation is external to this fixture.'}}]}
    return graph, spec


class UnderstandingDAGTests(unittest.TestCase):
    def test_global_function_graph_can_exceed_canvas_budget(self):
        graph, _ = fixture()
        bodies=[]
        nodes=[]
        for index in range(60):
            call=operation('call'+str(index),['request'],['reply'])
            if index<59:call['implementation']='body'+str(index+1)
            body=operation('body'+str(index),['request'],['reply'],[call] if index<59 else None)
            if body['expansion']:
                body['expansion']['bindings']=[{'outer':'in/p0','operation':call['id'],'inner':'in/p0'},
                    {'outer':'out/ok/p0','operation':call['id'],'inner':'out/ok/p0'}]
            node={'id':body['id'],'scope':body['id'],'bindings':{},'label':'Apply the transformation','description':'A declared transformation in this large graph fixture.'}
            if index<59:
                node['views']={'0':{'description':'Apply the next transformation.',
                    'steps':[{'operation':call['id'],'node':'body'+str(index+1),'bindings':{},'label':'Apply transformation','description':'Continue the declared transformation.'}],
                    'concepts':[{'members':[v],'label':'Incoming content' if v=='request' else 'Result content','description':'A declared input or result.','meaning':'One declared fixture identity.'} for v in ('request','reply')]}}
            else:
                node['sourceRanges']=source_ranges();node['stop']=simple_stop()
            bodies.append(body);nodes.append(node)
        graph['operations'],graph['definitions']=bodies[:1],bodies[1:]
        graph['presentation']['workflows'][0]['root']='body0'
        compiled=compile_dag(graph,{'roots':{'main':'body0'},'nodes':nodes})
        self.assertEqual(60,len(compiled['nodes']))
        self.assertEqual(59,len(compiled['edges']))

    def test_group_cannot_jump_to_an_unrelated_implementation_using_enter(self):
        graph, spec = fixture()
        graph['definitions'] = [operation('unrelated', ['request'], ['reply'])]
        entry = spec['nodes'][0]
        entry['views']['0']['steps'] = [{
            'members': ['prepare', 'execute'], 'node': 'unrelated', 'bindings': {},
            'enter': 'unrelated', 'label': 'Produce a reply', 'description': 'Grouped request processing.'}]
        entry['views']['0']['concepts'] = [c for c in entry['views']['0']['concepts'] if c['members'] != ['terms']]
        spec['nodes'] = [entry, {'id': 'unrelated', 'scope': 'unrelated', 'bindings': {},
                                'label': 'Another implementation', 'description': 'Unrelated original source.',
                                'sourceRanges': source_ranges(), 'stop': simple_stop()}]
        with self.assertRaisesRegex(ValueError, 'source-backed composition'):
            compile_dag(graph, spec)

    def test_implementation_choice_must_belong_to_current_source_region(self):
        graph, spec = fixture()
        graph['definitions'] = [operation('foreign-call', ['request'], ['reply'])]
        graph['presentation']['dispatch'] = {'foreign-call': {'candidates': [{'id': 'prepare'}]}}
        spec['nodes'][0]['implementationChoices'] = {'foreign-call': 'prepare'}
        with self.assertRaisesRegex(ValueError, 'current source region'):
            compile_dag(graph, spec)

    def test_composition_cannot_claim_component_constructed_only_in_a_sibling(self):
        graph, spec = fixture()
        graph['components'].append({**graph['components'][0], 'id': 'other-engine'})
        children = graph['operations'][0]['expansion']['operations']
        children[0]['outcomes'][0]['outputs'].append({'port': 'other', 'entity': 'other-engine', 'role': 'reference'})
        children[1]['expansion'] = {'operations': [operation('inner-call', ['terms', 'engine'], ['reply'])], 'bindings': []}
        spec['nodes'][0]['views']['0']['steps'][1].update(node='region', bindings={})
        region_view = copy.deepcopy(spec['nodes'][0]['views']['0'])
        region_view['steps'] = [{'operation': 'inner-call', 'node': 'inner', 'bindings': {'backend': 'other-engine'},
                                 'label': 'Use processing engine', 'description': 'Run the actual processing call.'}]
        region_view['concepts'] = [c for c in region_view['concepts'] if c['members'] != ['request']]
        spec['nodes'] = spec['nodes'][:2] + [
            {'id': 'region', 'scope': 'service', 'members': ['execute'], 'bindings': {},
             'label': 'Process content', 'description': 'The processing source region.', 'views': {'0': region_view}},
            {'id': 'inner', 'scope': 'inner-call', 'bindings': {'backend': 'other-engine'},
             'label': 'Run processing', 'description': 'A source call in this region.',
             'sourceRanges': source_ranges(), 'stop': simple_stop()}]
        with self.assertRaisesRegex(ValueError, 'actual call input, inherited context or source construction'):
            compile_dag(graph, spec)

    def test_inspection_reports_disconnected_frontier_without_compiling_or_mutating(self):
        graph, spec = fixture()
        spec['nodes'][0]['views']['0']['concepts'] = [
            c for c in spec['nodes'][0]['views']['0']['concepts'] if c['members'] != ['terms']]
        before = copy.deepcopy((graph, spec))
        with self.assertRaisesRegex(ValueError, '真实端到端去向'):
            compile_dag(graph, spec)
        report = inspect_dag(graph, spec, ['entry'], 'zh')
        node = report['nodes'][0]
        self.assertEqual(['reply'], node['sourceBoundary']['outputs'])
        self.assertEqual(['terms'], node['tasks'][0]['stages'][0]['outputs'])
        self.assertIn('step-without-endpoint', {i['kind'] for i in node['tasks'][0]['issues']})
        self.assertFalse(report['applicationExecuted'])
        self.assertEqual(before, (graph, spec))

    def test_inspection_keeps_contexts_separate_and_reports_source_stops(self):
        graph, spec = fixture()
        second = {**copy.deepcopy(spec['nodes'][0]), 'id': 'other-context',
                  'bindings': {'backend': {'unknown': 'A separate invocation context'}}}
        spec['nodes'].append(second)
        report = inspect_dag(graph, spec, ['entry', 'other-context', 'prep'])
        self.assertEqual(['entry', 'prep', 'other-context'], [n['id'] for n in report['nodes']])
        self.assertNotEqual(report['nodes'][0]['bindings'], report['nodes'][2]['bindings'])
        self.assertEqual('simple', report['nodes'][1]['stop']['reason'])
        with self.assertRaisesRegex(ValueError, 'Unknown business nodes'):
            inspect_dag(graph, spec, ['not-in-the-review'])

    def test_inspection_uses_exact_composition_boundary_and_continues_past_bad_nodes(self):
        graph, spec = fixture()
        region = copy.deepcopy(spec['nodes'][0])
        region.update(id='region', members=['execute'])
        region['views']['0']['steps'] = [region['views']['0']['steps'][1]]
        region['views']['0']['concepts'] = [c for c in region['views']['0']['concepts'] if c['members'] != ['request']]
        spec['nodes'].extend([region, {**region, 'id': 'bad-region', 'members': ['invented']}])
        report = inspect_dag(graph, spec, ['region', 'bad-region'])
        self.assertEqual(['engine', 'terms'], report['nodes'][0]['sourceBoundary']['inputs'])
        self.assertEqual(['reply'], report['nodes'][0]['sourceBoundary']['outputs'])
        self.assertEqual([], report['nodes'][0]['tasks'][0]['issues'])
        self.assertIn('error', report['nodes'][1])

    def test_inspection_reports_missing_scope_without_suppressing_other_nodes(self):
        graph, spec = fixture()
        spec['nodes'][0].pop('scope')
        report = inspect_dag(graph, spec)
        self.assertIn('source operation', report['nodes'][0]['error'])
        self.assertEqual('simple', report['nodes'][1]['stop']['reason'])
        spec['nodes'].append({'scope': 'service'})
        with self.assertRaisesRegex(ValueError, 'nonempty ID'):
            inspect_dag(graph, spec)

    def exposure_fixture(self):
        graph, spec = fixture()
        handler = operation('event-handler', ['request', 'engine'], ['reply'])
        graph.setdefault('definitions', []).append(handler)
        spec['nodes'][0]['exposes'] = [{'node': 'event', 'via': ['prepare'], 'bindings': {'backend': 'engine'},
                                      'trigger': 'A request arrives after setup',
                                      'description': 'Registration makes the handler available without running it.'}]
        spec['nodes'].append({'id': 'event', 'scope': 'event-handler', 'label': 'Handle a request',
                              'description': 'Run only when the registered event occurs.', 'bindings': {'backend': 'engine'},
                              'sourceRanges': source_ranges(), 'stop': simple_stop('This declared fixture has a direct source endpoint.')})
        return graph, spec

    def test_exposure_connects_real_handler_without_faking_an_execution_step(self):
        graph, spec = self.exposure_fixture()
        compiled = compile_dag(graph, spec)
        self.assertEqual(2, len(compiled['nodes'][0]['views']['0']['steps']))
        edges = compiled['exposures']
        self.assertEqual([('entry', 'event')], [(e['from'], e['to']) for e in edges])
        self.assertEqual(['prepare'], edges[0]['members'])
        self.assertEqual('A request arrives after setup', edges[0]['trigger'])
        self.assertTrue(all(e['kind']=='decomposes' for e in compiled['edges']))
        self.assertEqual(compiled, compile_dag(graph, compiled))

    def test_exposure_must_cite_registration_inside_its_owner(self):
        graph, spec = self.exposure_fixture()
        spec['nodes'][0]['exposes'][0]['via'] = ['event-handler']
        with self.assertRaisesRegex(ValueError, 'real registration source'):
            compile_dag(graph, spec)

    def test_exposure_preserves_component_context_without_becoming_decomposition(self):
        graph, spec = self.exposure_fixture()
        exposure = spec['nodes'][0]['exposes'][0]
        exposure['bindings'] = {}
        with self.assertRaisesRegex(ValueError, 'bindings differ'):
            compile_dag(graph, spec)
        exposure['bindings'] = spec['nodes'][0]['bindings']
        exposure['node'] = 'entry'
        spec['nodes'].pop()
        compiled=compile_dag(graph, spec)
        self.assertFalse(any(e['from']==e['to'] for e in compiled['edges']))
        self.assertEqual('entry', compiled['exposures'][0]['to'])

    def test_lifecycle_binding_uses_separate_located_construction_evidence(self):
        graph, spec = self.exposure_fixture()
        graph['components'].append({**graph['components'][0], 'id': 'late-engine'})
        graph['definitions'].append(operation('startup-factory', [], ['late-engine']))
        exposure = spec['nodes'][0]['exposes'][0]
        exposure['bindings'] = spec['nodes'][-1]['bindings'] = {'backend': 'late-engine'}
        with self.assertRaisesRegex(ValueError, 'actual call input, inherited context or source construction'):
            compile_dag(graph, spec)
        exposure['bindingSources'] = ['startup-factory']
        compiled = compile_dag(graph, spec)
        self.assertEqual(['startup-factory'], compiled['exposures'][-1]['bindingSources'])

    def test_all_tiers_keep_the_same_invocations_and_entry_targets(self):
        graph, spec = fixture()
        compiled = compile_dag(graph, spec)
        self.assertEqual(3, len(compiled['nodes']))
        self.assertEqual([('entry', 'prep'), ('entry', 'run')], [(e['from'], e['to']) for e in compiled['edges']])
        views = compiled['nodes'][0]['views']
        self.assertEqual(views['0']['steps'], views['100']['steps'])
        self.assertNotIn('50', spec['nodes'][0]['views'])  # source review remains intact

    def test_tier_specific_helper_call_or_group_change_is_rejected(self):
        graph, spec = fixture()
        views = spec['nodes'][0]['views']
        views['100'] = copy.deepcopy(views['0'])
        views['100']['steps'][0]['enter'] = 'execute'
        with self.assertRaisesRegex(ValueError, '三档业务分组成员'):
            compile_dag(graph, spec)
        views['100']['steps'].pop()
        with self.assertRaisesRegex(ValueError, '三档业务分组成员'):
            compile_dag(graph, spec)

    def test_data_cannot_be_declared_a_component_binding(self):
        graph, spec = fixture()
        spec['nodes'][0]['bindings']['backend'] = 'request'
        with self.assertRaisesRegex(ValueError, 'actual components'):
            compile_dag(graph, spec)

    def test_different_incoming_components_cannot_share_a_node(self):
        graph, spec = fixture()
        graph['components'].append({**graph['components'][0], 'id': 'other'})
        spec['nodes'][0]['views']['0']['steps'][1]['bindings']['backend'] = 'other'
        with self.assertRaisesRegex(ValueError, 'bindings differ'):
            compile_dag(graph, spec)

    def test_matching_metadata_cannot_invent_a_component_origin(self):
        graph, spec = fixture()
        graph['components'].append({**graph['components'][0], 'id': 'other'})
        spec['nodes'][0]['views']['0']['steps'][1]['bindings']['backend'] = 'other'
        spec['nodes'][2]['bindings']['backend'] = 'other'
        with self.assertRaisesRegex(ValueError, 'actual call input, inherited context or source construction'):
            compile_dag(graph, spec)

    def test_same_component_can_share_without_merging_invocation_positions(self):
        graph, spec = fixture()
        second = operation('second', ['terms', 'engine'], ['reply'], [operation('call2', ['terms', 'engine'], ['reply'])])
        second['expansion']['operations'][0]['implementation'] = 'execute'
        graph['operations'].append(second)
        graph['presentation']['workflows'].append({'id': 'other', 'root': 'second', 'label': 'Another entry', 'description': 'Another entry delegates to the same bound engine.'})
        view = copy.deepcopy(spec['nodes'][0]['views']['0'])
        view['steps'] = [{**view['steps'][1], 'operation': 'call2'}]
        view['concepts'] = [c for c in view['concepts'] if c['members'] != ['request']]
        spec['nodes'].append({'id': 'second', 'scope': 'second', 'label': 'Another entry', 'description': 'Another route into the same implementation.', 'bindings': {'backend': 'engine'}, 'views': {'0': view}})
        spec['roots']['other'] = 'second'
        compiled = compile_dag(graph, spec)
        self.assertEqual(2, len([e for e in compiled['edges'] if e['to'] == 'run']))
        self.assertEqual(1, len([n for n in compiled['nodes'] if n['id'] == 'run']))
        # Ordinary arguments belong to each call, not to the understanding node's identity.
        self.assertNotIn('request', compiled['nodes'][2]['identity'])

    def test_real_recursion_is_not_an_understanding_cycle(self):
        graph, spec = fixture()
        call = graph['operations'][0]['expansion']['operations'][1]
        call['implementation'] = 'service'
        step = spec['nodes'][0]['views']['0']['steps'][1]
        step['node'] = 'entry'
        spec['nodes'].pop()
        with self.assertRaisesRegex(ValueError, 'acyclic'):
            compile_dag(graph, spec)

    def test_unreachable_or_missing_direct_successor_is_rejected(self):
        graph, spec = fixture()
        spec['nodes'][0]['views']['0']['steps'][0]['node'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'Unknown direct successor'):
            compile_dag(graph, spec)


    def test_simple_leaf_requires_explicit_ranges_and_accepts_soft_review(self):
        graph, spec = fixture()
        prep = next(node for node in spec['nodes'] if node['id'] == 'prep')
        prep.pop('sourceRanges')
        with self.assertRaisesRegex(ValueError, 'sourceRanges'):
            compile_dag(graph, spec)
        prep['sourceRanges'] = source_ranges()
        prep['stop'].pop('review')
        warnings = []
        self.assertTrue(compile_dag(graph, spec, warnings=warnings))
        self.assertIn('sourceEvidenceMissing', {w['kind'] for w in warnings})
        prep['stop']['review'] = {'sourceRangesChecked': True, 'reason': 'Read directly.',
                                  'delegates': [], 'sourceCalls': {}}
        with self.assertRaisesRegex(ValueError, 'sourceCalls'):
            compile_dag(graph, spec)

    def test_source_calls_and_delegates_are_validated_semantically(self):
        graph, spec = fixture()
        prep = next(node for node in spec['nodes'] if node['id'] == 'prep')
        review = prep['stop']['review']
        review['sourceCalls'] = [{'call': 'call', 'line': 1, 'receiverType': 'T',
                                  'resolution': 'resolved', 'implementation': 'execute',
                                  'disposition': 'decomposed', 'childNode': 'missing',
                                  'reason': 'A real delegate.'}]
        with self.assertRaisesRegex(ValueError, 'childNode'):
            compile_dag(graph, spec)
        review['sourceCalls'][0]['childNode'] = 'prep'
        with self.assertRaisesRegex(ValueError, 'childNode'):
            compile_dag(graph, spec)
        review['sourceCalls'][0].update(childNode='run', disposition='simple')
        review['sourceCalls'][0]['line'] = 99
        with self.assertRaisesRegex(ValueError, 'sourceRanges'):
            compile_dag(graph, spec)
        review['sourceCalls'][0]['line'] = 1
        review['delegates'] = [{'call': 'delegate', 'implementation': 'execute',
                                'disposition': 'simple', 'reason': 'A direct delegate.'}]
        self.assertTrue(compile_dag(graph, spec))

    def test_omitted_leaf_requires_source_and_reopen(self):
        graph, spec = fixture()
        prep = next(node for node in spec['nodes'] if node['id'] == 'prep')
        prep['stop'] = {'reason': 'omitted', 'detail': 'Known implementation outside this review.',
                        'review': {'sourceRangesChecked': True, 'reason': 'The user scoped it out.',
                                   'reopen': 'Reopen when the selected scope includes it.'}}
        self.assertTrue(compile_dag(graph, spec))
        prep['stop']['review'].pop('reopen')
        warnings = []
        self.assertTrue(compile_dag(graph, spec, warnings=warnings))
        self.assertIn('reopenMissing', {w['kind'] for w in warnings})

    def test_simple_leaf_needs_no_project_calls_when_source_calls_empty(self):
        graph, spec = fixture()
        prep = next(node for node in spec['nodes'] if node['id'] == 'prep')
        review = prep['stop']['review']
        review['sourceCalls'] = []
        review.pop('noProjectCalls', None)
        warnings = []
        self.assertTrue(compile_dag(graph, spec, warnings=warnings))
        self.assertIn('noProjectCallsMissing', {w['kind'] for w in warnings})
        review['noProjectCalls'] = True
        self.assertTrue(compile_dag(graph, spec))

    def test_simple_delegate_needs_a_real_implementation(self):
        graph, spec = fixture()
        prep = next(node for node in spec['nodes'] if node['id'] == 'prep')
        prep['stop']['review']['delegates'] = [
            {'call': 'delegate', 'implementation': 'missing', 'disposition': 'simple', 'reason': 'A delegate.'}]
        with self.assertRaisesRegex(ValueError, 'existing model operation/definition ID'):
            compile_dag(graph, spec)

    def test_simple_leaf_cannot_use_composition_to_hide_multiple_stages(self):
        graph, spec = fixture()
        prep = next(node for node in spec['nodes'] if node['id'] == 'prep')
        prep['stop']['review']['composition'] = 'Two stages were combined.'
        warnings = []
        self.assertTrue(compile_dag(graph, spec, warnings=warnings))
        self.assertIn('compositionNeedsReview', {w['kind'] for w in warnings})

    def test_overlapping_simple_source_ranges_are_reported(self):
        graph, spec = fixture()
        run = next(node for node in spec['nodes'] if node['id'] == 'run')
        run['sourceRanges'] = source_ranges()
        run['stop'] = simple_stop('A direct endpoint.')
        warnings = []
        compile_dag(graph, spec, warnings=warnings)
        self.assertIn('sourceRangeOverlap', {warning['kind'] for warning in warnings})

    def test_primary_from_is_preserved_in_all_tiers(self):
        graph, spec = fixture()
        spec['nodes'][0]['views']['0']['steps'][1]['primaryFrom'] = 'terms'
        compiled = compile_dag(graph, spec)
        for tier in ('0', '50', '100'):
            self.assertEqual('terms', compiled['nodes'][0]['views'][tier]['steps'][1]['primaryFrom'])

    def test_workflow_root_cannot_declare_members(self):
        graph, spec = fixture()
        spec['nodes'][0]['members'] = ['prepare', 'execute']
        with self.assertRaisesRegex(ValueError, 'workflow root cannot declare members'):
            compile_dag(graph, spec)

    def test_understanding_step_cannot_mix_operation_and_members(self):
        graph, spec = fixture()
        spec['nodes'][0]['views']['0']['steps'][0]['members'] = ['prepare']
        with self.assertRaisesRegex(ValueError, 'operation 或 members 之一'):
            compile_dag(graph, spec)

    def test_composition_source_range_cannot_use_the_parent_whole_range(self):
        graph, spec = fixture()
        children = graph['operations'][0]['expansion']['operations']
        graph['operations'][0]['source'] = {'path': 'app.py', 'startLine': 1, 'endLine': 20, 'url': None}
        children[0]['source'] = {'path': 'app.py', 'startLine': 5, 'endLine': 10, 'url': None}
        next(node for node in spec['nodes'] if node['id'] == 'prep')['sourceRanges'] = [
            {'path': 'app.py', 'startLine': 5, 'endLine': 10}]
        entry = spec['nodes'][0]
        entry_view = entry['views']['0']
        entry_view['steps'][0] = {'members': ['prepare'], 'node': 'region', 'bindings': {},
                                  'label': 'Prepare content', 'description': 'Extract the content.'}
        region_view = {'description': 'Prepare content.',
                       'steps': [{'operation': 'prepare', 'node': 'prep', 'bindings': {},
                                  'label': 'Prepare content', 'description': 'Extract the content.'}],
                       'concepts': [c for c in entry_view['concepts'] if c['members'] in (['request'], ['terms'])]}
        region = {'id': 'region', 'scope': 'service', 'members': ['prepare'], 'bindings': {},
                  'label': 'Prepare content', 'description': 'The prepare source region.',
                  'views': {'0': region_view},
                  'sourceRanges': [{'path': 'app.py', 'startLine': 1, 'endLine': 20}]}
        spec['nodes'].append(region)
        with self.assertRaisesRegex(ValueError, 'scope/member source'):
            compile_dag(graph, spec)
        region['sourceRanges'] = [{'path': 'app.py', 'startLine': 5, 'endLine': 10}]
        compiled = compile_dag(graph, spec)
        self.assertIn('region', {node['id'] for node in compiled['nodes']})

    def test_numbered_business_node_label_is_rejected(self):
        graph, spec = fixture()
        spec['nodes'][0]['label'] = '结果1'
        with self.assertRaisesRegex(ValueError, 'numbered/generic'):
            compile_dag(graph, spec)


if __name__ == '__main__':
    unittest.main()
