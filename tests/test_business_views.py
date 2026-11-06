"""Business layering must not succeed by hiding a bag behind a pretty title."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/litflux/scripts'))
from business_views import (apply_entry_bindings as apply_views, apply_workflows, branch_packing_warnings, call_site_port_audit,
                            compile_views, prepare, inspect_views, delivery_audit,
                            omitted_data_issues, importance_hint, primary_audit)
def short_label(value):
    return value['name']



def operation(id, inputs, outputs, children=None):
    value = {'id': id, 'name': id, 'inputs': [{'entity': v, 'port': str(i)} for i, v in enumerate(inputs)],
             'outcomes': [{'id': 'ok', 'outputs': [{'entity': v, 'port': str(i)} for i, v in enumerate(outputs)]}]}
    if children:
        value['expansion'] = {'operations': children}
    return value


class BusinessViewTests(unittest.TestCase):
    def setUp(self):
        self.graph = {'operations': [operation('service', ['request', 'provider'], ['reply'], [
            operation('prepare', ['request'], ['terms']), operation('execute', ['terms', 'provider'], ['reply'])])],
            'entities': [{'id': v, 'name': v} for v in ('request', 'terms', 'reply')],
            'resources': [], 'components': [{'id': 'provider', 'name': 'provider'}]}
        self.view = {'description': '整理请求后调用处理组件，把回复交回调用者。', 'steps': [
            {'operation': 'prepare', 'label': '整理请求', 'description': '提取后续处理需要的内容。'},
            {'operation': 'execute', 'label': '处理请求', 'description': '调用组件处理内容并形成回复。'}],
            'concepts': [{'members': [id], 'label': label, 'description': label + '的来源与用途。', 'meaning': '指明这一个业务数据的意义。'}
                         for id, label in [('request', '原始请求'), ('terms', '待处理内容'), ('reply', '业务回复'), ('provider', '处理组件')]]}

    def compile(self):
        return compile_views(self.graph, {'service': {'0': self.view}})

    def test_local_sample_cannot_complete_a_larger_declared_delivery(self):
        self.graph['presentation'] = {'workflows': [{'id':'answer', 'root':'service'}]}
        review = {'delivery': {'scope':'project', 'description':'Explain the application lifecycle.', 'goals':[
            {'id':'answer', 'label':'Answer a request', 'workflow':'answer', 'source':{'path':'README.md','startLine':1,'endLine':2}},
            {'id':'import', 'label':'Import source documents', 'workflow':'import', 'source':{'path':'README.md','startLine':3,'endLine':4}}]}}
        result = delivery_audit(self.graph, review)
        self.assertFalse(result['complete'])
        self.assertIn('import', {m['goal'] for m in result['missing']})

    def test_unplanned_draft_is_not_a_complete_project_delivery(self):
        self.assertFalse(delivery_audit(self.graph, {})['complete'])

    def test_completed_delivery_links_goals_to_real_workflows(self):
        self.graph['presentation'] = {'workflows': [{'id':'answer', 'root':'service'}]}
        review = {'delivery': {'scope':'selected-workflows', 'description':'Explain the requested answering workflow.',
            'goals':[{'id':'answer','label':'Answer a request','workflow':'answer',
                      'source':{'path':'README.md','startLine':1,'endLine':2}}]}}
        self.assertTrue(delivery_audit(self.graph, review)['complete'])

    def test_source_facts_and_ports_stay_unchanged(self):
        original = copy.deepcopy(self.graph)
        compiled = compile_views(self.graph, {'service': {'0': self.view}})
        self.assertEqual({'0', '50', '100'}, set(compiled['service']))
        self.assertEqual(original, self.graph)

    def test_a_real_library_definition_can_be_a_workflow_reading_root(self):
        self.graph['definitions'] = self.graph['operations']
        self.graph['operations'] = []
        result = apply_workflows(self.graph, {'workflows': [
            {'id': 'main', 'root': 'service', 'label': '处理业务请求', 'description': '从实际业务函数的边界阅读主要处理。'}]})
        self.assertTrue(result['reviewed'])
        self.assertEqual('service', self.graph['presentation']['workflows'][0]['root'])
        self.assertIn('service', self.compile())

    def test_invalid_members_identify_missing_and_foreign_ids_not_a_bad_root(self):
        self.view['steps'][0].pop('operation')
        self.view['steps'][0]['members'] = ['invented', 'service']
        with self.assertRaisesRegex(ValueError, '整理请求.*模型中不存在：invented.*不在当前子域：service'):
            self.compile()

    def test_step_cannot_mix_single_call_and_group_members(self):
        self.view['steps'][0]['members'] = ['prepare']
        with self.assertRaisesRegex(ValueError, 'operation 或 members'):
            self.compile()

    def test_missing_tiers_reuse_a_complete_small_review_without_mutation(self):
        result = self.compile()['service']
        self.assertEqual({'0', '50', '100'}, set(result))
        self.assertEqual(result['0']['steps'], result['100']['steps'])
        self.assertLess(len(result['0']['concepts']), len(result['100']['concepts']))
        result['0']['steps'][0]['label'] = 'Edited separately'
        self.assertNotEqual(result['0'], result['100'])

    def test_entry_cannot_redirect_to_current_scope(self):
        self.view['steps'][0]['enter'] = 'service'
        with self.assertRaisesRegex(ValueError, '不能指回当前图'):
            self.compile()

    def test_source_endpoint_requires_source_location_and_accepts_soft_review(self):
        step = self.view['steps'][0]
        step['stop'] = {'reason':'simple','detail':'The existing explanation covers this direct transformation.'}
        with self.assertRaisesRegex(ValueError, '定位实际源成员'):
            self.compile()
        self.graph['operations'][0]['expansion']['operations'][0]['source'] = {'path':'app.py','startLine':1,'endLine':2}
        warnings = []
        compiled = compile_views(self.graph, {'service': {'0': self.view}}, warnings=warnings)
        self.assertEqual(step['stop'], compiled['service']['0']['steps'][0]['stop'])
        self.assertIn('sourceEvidenceMissing', {w['kind'] for w in warnings})
        step['stop']['review'] = {'sourceRangesChecked': True, 'reason': 'Read the direct source.',
                                  'delegates': [], 'sourceCalls': [], 'noProjectCalls': True}
        step['enter'] = 'execute'
        with self.assertRaisesRegex(ValueError, '不能同时指定子流程'):
            self.compile()

    def test_inline_simple_source_calls_are_semantically_validated(self):
        prepare = self.graph['operations'][0]['expansion']['operations'][0]
        prepare['source'] = {'path': 'app.py', 'startLine': 1, 'endLine': 1}
        self.view['steps'][0]['stop'] = {'reason': 'simple', 'detail': 'A direct source endpoint.',
                                         'review': {'sourceRangesChecked': True, 'reason': 'Read directly.',
                                                    'delegates': [], 'sourceCalls': [
                                                        {'call': 'self.worker.run', 'line': 1,
                                                         'receiverType': 'Worker', 'resolution': 'resolved',
                                                         'implementation': 'missing', 'disposition': 'simple',
                                                         'reason': 'The delegate is direct.'}]}}
        with self.assertRaisesRegex(ValueError, 'implementation'):
            self.compile()
        self.view['steps'][0]['stop']['review']['sourceCalls'][0]['implementation'] = 'execute'
        self.assertTrue(self.compile())

    def test_recursive_child_automatically_keeps_parent_component_boundary(self):
        inner = copy.deepcopy(self.view)
        inner['concepts'] = [c for c in inner['concepts'] if c['members'] != ['provider']]
        parent = {'description': '完成一次业务请求。', 'steps': [
            {'members': ['prepare', 'execute'], 'label': '制作业务回复', 'description': '先整理，再调用组件。',
             'flow': {str(t): copy.deepcopy(inner) for t in (0, 50, 100)}}],
            'concepts': [copy.deepcopy(c) for c in self.view['concepts'] if c['members'] != ['terms']]}
        result = compile_views(self.graph, {'service': {'0': parent}})['service']['0']['steps'][0]['flow']
        for plan in result.values():
            self.assertTrue(any(c['members'] == ['provider'] for c in plan['concepts']))
            self.assertTrue(any(c['members'] == ['provider'] for c in plan['interface']))

    def test_effect_binding_requires_a_real_source_effect_port(self):
        self.graph['resources'] = [{'id':'outer','name':'published version'},{'id':'inner','name':'repository'}]
        self.graph['operations'][0]['expansion']['operations'][1]['accesses'] = [{'resource':'inner','mode':'write'}]
        self.graph['operations'][0]['expansion']['operations'][1]['source'] = {'path':'service.py','startLine':10,'endLine':10}
        rule = {'outer':'outer','inner':'inner','operation':'execute','direction':'output','label':'publish version',
                'meaning':'A version is stored in the repository; distinct resources.', 'source':{'path':'service.py','startLine':10,'endLine':10}}
        apply_views(self.graph, {'entryBindings':{'service':[rule]}})
        self.assertEqual(rule, self.graph['presentation']['entryBindings']['service'][0])
        rule['inner'] = 'not-an-effect'
        with self.assertRaisesRegex(ValueError, '真实资源作用端口'):
            apply_views(self.graph, {'entryBindings':{'service':[rule]}})

    def test_delegated_effect_follows_real_calls_to_the_actual_writer(self):
        caller = operation('invoke', ['request'], ['reply']);caller['implementation'] = 'service'
        delegate = operation('delegate', ['request'], ['reply']);delegate['implementation'] = 'worker'
        delegate['source'] = {'path':'service.py','startLine':10,'endLine':10}
        writer = operation('writer', ['request'], ['reply']);writer['accesses'] = [{'resource':'inner','mode':'write'}]
        body = operation('service', ['request'], ['reply'], [delegate])
        worker = operation('worker', ['request'], ['reply'], [writer])
        self.graph.update(operations=[caller], definitions=[body,worker], resources=[{'id':'outer','name':'Storage'},{'id':'inner','name':'Session'}])
        rule = {'outer':'outer','inner':'inner','direction':'output','operation':'delegate','via':['delegate','writer'],
                'label':'Save through the worker','meaning':'A real delegated persistence call.', 'source':delegate['source']}
        apply_views(self.graph, {'entryBindings':{'invoke':[rule]}})
        self.assertEqual(rule, self.graph['presentation']['entryBindings']['invoke'][0])
        rule['via'] = ['delegate','invoke']
        with self.assertRaisesRegex(ValueError, '真实调用或构造注入依据'):
            apply_views(self.graph, {'entryBindings':{'invoke':[rule]}})

    def test_aggregate_can_contain_a_source_validated_three_tier_flow(self):
        inner = copy.deepcopy(self.view)
        aggregate = {'description': '进入后查看清理与处理之间的真实数据传递。', 'steps': [
            {'members': ['prepare', 'execute'], 'label': '制作业务回复', 'description': '先整理请求，再处理请求。',
             'flow': {str(t): copy.deepcopy(inner) for t in (0, 50, 100)}}],
            'concepts': [copy.deepcopy(c) for c in self.view['concepts'] if c['members'] != ['terms']]}
        original = copy.deepcopy(self.graph)
        result = compile_views(self.graph, {'service': {'0': aggregate}})
        self.assertEqual(['prepare', 'execute'], [s['operation'] for s in result['service']['0']['steps'][0]['flow']['0']['steps']])
        self.assertEqual(original, self.graph)
        aggregate['steps'][0]['flow']['0']['steps'][1]['operation'] = 'service'
        with self.assertRaisesRegex(ValueError, '当前源码中的真实业务'):
            compile_views(self.graph, {'service': {'0': aggregate}})

    def test_nested_flow_cannot_skip_tiers_or_fabricate_a_loop_context(self):
        aggregate = copy.deepcopy(self.view)
        aggregate['steps'][0]['members'] = ['prepare']
        aggregate['steps'][0].pop('operation')
        aggregate['steps'][0]['flow'] = {'0': copy.deepcopy(self.view)}
        with self.assertRaisesRegex(ValueError, '三档'):
            compile_views(self.graph, {'service': {'0': aggregate}})
        self.view['iteration'] = 'prepare'
        with self.assertRaisesRegex(ValueError, '真实迭代入口'):
            self.compile()

    def test_beginner_introduction_is_review_data_not_new_source_nodes(self):
        intro = {'purpose': '解释为谁解决什么问题。', 'terms': [{'term': '业务概念', 'meaning': '在本项目中的具体内容。'}],
                 'example': '用一个具体输入解释变化。', 'usage': '说明哪个后续处理使用结果。'}
        self.view['introduction'] = intro
        original = copy.deepcopy(self.graph)
        result = self.compile()['service']['0']
        self.assertEqual(intro, result['introduction'])
        self.assertEqual(original, self.graph)
        self.view['introduction']['terms'][0].pop('meaning')
        with self.assertRaisesRegex(ValueError, '术语须给出'):
            self.compile()

    def test_anonymous_count_bag_is_rejected(self):
        self.view['concepts'][0]['label'] = '输入数据 · 10 项'
        with self.assertRaisesRegex(ValueError, '禁止按端口/数量'):
            self.compile()

    def test_phase_number_is_not_a_business_action(self):
        self.view['steps'][0]['label'] = '环节 1'
        with self.assertRaisesRegex(ValueError, '禁止编号/项数打包'):
            self.compile()

    def test_a_pretty_label_cannot_combine_different_stage_results(self):
        self.view['concepts'] = [c for c in self.view['concepts'] if c['members'] not in (['terms'], ['reply'])]
        self.view['concepts'].append({'members': ['terms', 'reply'], 'label': '业务材料', 'description': '不恰当地合并。', 'meaning': '声称相近仍需核验来源。'})
        with self.assertRaisesRegex(ValueError, '不同时点的生产结果'):
            self.compile()

    def test_data_and_capability_are_not_one_payload(self):
        self.view['concepts'] = [{'members': ['request', 'provider'], 'label': '请求环境', 'description': '不恰当地合并。', 'meaning': '同方向不代表相同角色。'}]
        with self.assertRaisesRegex(ValueError, '不同类别'):
            self.compile()

    def test_budget_counts_every_role_not_only_processes(self):
        self.view['concepts'] *= 10
        with self.assertRaisesRegex(ValueError, '实际节点预算'):
            self.compile()

    def test_source_variable_can_be_a_detail_reference(self):
        self.view['concepts'][0]['label'] = 'request'
        self.assertTrue(self.compile())

    def test_shared_single_resource_is_not_false_multiple_generation(self):
        self.graph['resources'] = [{'id': 'db', 'name': 'db'}]
        for o in self.graph['operations'][0]['expansion']['operations']:
            o['accesses'] = [{'resource': 'db', 'mode': 'read', 'port': 'read'}]
        self.view['concepts'].append({'members': ['db'], 'label': '业务数据库', 'description': '供多个步骤读取。', 'meaning': '一个真实载体反复使用。'})
        self.assertTrue(self.compile())

    def test_a_hidden_unpack_must_not_disconnect_the_business_stage(self):
        children = self.graph['operations'][0]['expansion']['operations']
        children[0] = operation('prepare', ['request'], ['response'])
        children.insert(1, operation('unpack', ['response'], ['terms']))
        self.graph['entities'].append({'id': 'response', 'name': 'response'})
        self.view['steps'][0].pop('operation')
        self.view['steps'][0]['members'] = ['prepare', 'unpack']
        terms = self.view['concepts'][1]
        terms['members'] = ['response']
        with self.assertRaisesRegex(ValueError, '真实端到端去向.*整理请求'):
            self.compile()
        # The response and its actual unpacked parts describe the same stage,
        # rather than adding a fabricated edge from the opaque tuple.
        terms['members'].append('terms')
        original = copy.deepcopy(self.graph)
        self.assertTrue(self.compile())
        self.assertEqual(original, self.graph)

    def test_an_unused_local_result_is_not_a_business_endpoint(self):
        self.graph['entities'].append({'id': 'diagnostic', 'name': 'diagnostic'})
        final = self.graph['operations'][0]['expansion']['operations'][1]
        final['outcomes'][0]['outputs'].append({'entity': 'diagnostic', 'port': 'extra'})
        self.view['concepts'].append({'members': ['diagnostic'], 'label': '内部诊断', 'description': '仅作局部诊断。', 'meaning': '没有外部去向。'})
        with self.assertRaisesRegex(ValueError, '真实端到端去向.*内部诊断'):
            self.compile()

    def test_a_real_write_is_a_valid_endpoint_without_a_return(self):
        self.graph['resources'] = [{'id': 'report', 'name': 'report'}]
        final = self.graph['operations'][0]['expansion']['operations'][1]
        final['outcomes'][0]['outputs'] = []
        final['accesses'] = [{'resource': 'report', 'mode': 'write', 'port': 'save'}]
        self.graph['operations'][0]['outcomes'][0]['outputs'] = []
        self.view['concepts'] = [c for c in self.view['concepts'] if c['members'] != ['reply']]
        self.view['concepts'].append({'members': ['report'], 'label': '业务报告文件', 'description': '保存处理结果。', 'meaning': '一个真实持久化载体。'})
        self.assertTrue(self.compile())
        final['accesses'][0]['mode'] = 'read'
        with self.assertRaisesRegex(ValueError, '真实端到端去向'):
            self.compile()

    def test_source_order_cannot_hide_a_missing_data_result(self):
        self.graph['presentation'] = {'executionRequirements': [{'before': 'prepare', 'after': 'execute'}]}
        self.view['concepts'] = [c for c in self.view['concepts'] if c['members'] != ['terms']]
        with self.assertRaisesRegex(ValueError, '真实端到端去向.*整理请求'):
            self.compile()

    def test_a_void_validation_can_continue_in_cited_source_order(self):
        children = self.graph['operations'][0]['expansion']['operations']
        children[0]['outcomes'][0]['outputs'] = []
        children[1]['inputs'][0]['entity'] = 'request'
        self.graph['presentation'] = {'executionRequirements': [{'before': 'prepare', 'after': 'execute'}]}
        self.view['concepts'] = [c for c in self.view['concepts'] if c['members'] != ['terms']]
        self.assertTrue(self.compile())

    def test_a_value_used_only_by_a_real_decision_is_a_consumed_result(self):
        children = self.graph['operations'][0]['expansion']['operations']
        children[1]['inputs'][0]['entity'] = 'request'
        children.append(operation('refuse', ['request'], ['refusal']))
        self.graph['operations'][0]['outcomes'].append({'id': 'fallback', 'outputs': [{'port': 'reply', 'entity': 'refusal'}]})
        self.graph['entities'].append({'id': 'refusal', 'name': 'Refusal message'})
        self.view['steps'].append({'operation': 'refuse', 'label': '说明无法作答', 'description': '根据真实检查结果拒答。'})
        self.view['concepts'].append({'members': ['refusal'], 'label': '拒答内容', 'description': '检查未通过时返回的原因。', 'meaning': '一个实际返回值。'})
        self.graph['presentation'] = {'decisions': [{'id': 'enough', 'owner': 'service',
            'question': '检查结果是否通过？', 'condition': 'terms.is_sufficient', 'inputs': ['terms'],
            'yes': ['execute'], 'no': ['refuse']}]}
        self.assertTrue(self.compile())
        self.view['concepts'] = [item for item in self.view['concepts'] if 'terms' not in item['members']]
        with self.assertRaisesRegex(ValueError, '真实端到端去向'):
            self.compile()

    def test_zero_argument_creation_needs_no_invented_input(self):
        self.graph['operations'][0]['expansion']['operations'][0]['inputs'] = []
        self.view['concepts'] = [c for c in self.view['concepts'] if c['members'] != ['request']]
        self.assertTrue(self.compile())

    def test_an_omitted_source_cannot_become_an_independent_start(self):
        children = self.graph['operations'][0]['expansion']['operations']
        children.insert(0, operation('hidden', ['request'], ['derived']))
        children[1]['inputs'][0]['entity'] = 'derived'
        self.graph['entities'].append({'id': 'derived', 'name': 'derived'})
        self.view['concepts'][0]['members'] = ['derived']
        with self.assertRaisesRegex(ValueError, '真实端到端去向.*原始请求'):
            self.compile()

    def test_unused_visible_concepts_are_rejected(self):
        self.graph['entities'].append({'id': 'unused', 'name': 'unused'})
        self.graph['operations'][0]['inputs'].append({'entity': 'unused', 'port': 'unused'})
        self.view['concepts'].append({'members': ['unused'], 'label': '无用材料', 'description': '实际没有参与处理。', 'meaning': '不应占据主要流程。'})
        with self.assertRaisesRegex(ValueError, '真实端到端去向.*无用材料'):
            self.compile()

    def test_prepare_exposes_actual_source_ports_without_inventing_entities(self):
        self.graph['definitions'] = []
        task = prepare(self.graph, ['service'])['tasks'][0]
        self.assertEqual(['prepare', 'execute'], [o['id'] for o in task['sourceOperations']])
        self.assertEqual({'request', 'provider', 'terms', 'reply'}, {e['id'] for e in task['sourceValues']})
        self.assertEqual(self.graph['operations'][0]['expansion']['operations'][0]['inputs'], task['sourceOperations'][0]['inputs'])

    def test_inspect_finds_missing_concepts_without_choosing_or_mutating_them(self):
        original = copy.deepcopy(self.graph)
        view = copy.deepcopy(self.view)
        view['concepts'] = []
        report = inspect_views(self.graph, {'service': {'0': view}}, ['service'])
        task = report['tasks'][0]
        ports = {v['id']: v for v in task['sourceValues']}
        self.assertEqual([0], ports['terms']['producerSteps'])
        self.assertEqual([1], ports['terms']['consumerSteps'])
        self.assertTrue(ports['reply']['publicOutput'])
        self.assertEqual('components', ports['provider']['nodeRole'])
        self.assertEqual([], ports['terms']['selectedConcepts'])
        self.assertEqual({'整理请求', '处理请求'}, {i['label'] for i in task['issues']})
        self.assertEqual(original, self.graph)
        self.assertFalse(report['applicationExecuted'])

    def test_inspect_excludes_stage_internal_values_and_preserves_effect_roles(self):
        self.graph['resources'] = [{'id': 'store', 'name': '持久化仓库'}]
        children = self.graph['operations'][0]['expansion']['operations']
        children[1]['accesses'] = [{'resource': 'store', 'mode': 'write', 'label': '保存'}]
        view = {'description': '处理并保存', 'steps': [
            {'members': ['prepare', 'execute'], 'label': '处理并保存', 'description': '按真实顺序处理。'}],
            'concepts': []}
        task = inspect_views(self.graph, {'service': {'0': view}})['tasks'][0]
        ports = {v['id']: v for v in task['sourceValues']}
        self.assertNotIn('terms', ports)
        self.assertEqual('resources', ports['store']['nodeRole'])
        self.assertEqual('write', ports['store']['accessSteps'][0]['mode'])
        self.assertEqual([], ports['store']['producerSteps'])
        self.assertEqual(['reply'], task['stages'][0]['outputs'])

    def test_inspect_tracks_selected_meaning_and_rejects_unknown_scope(self):
        plans = {'service': {'50': self.view}}
        task = inspect_views(self.graph, plans)['tasks'][0]
        self.assertEqual([], task['issues'])
        self.assertEqual(['待处理内容'], next(v for v in task['sourceValues'] if v['id'] == 'terms')['selectedConcepts'])
        with self.assertRaisesRegex(ValueError, '未知已审阅业务作用域'):
            inspect_views(self.graph, plans, ['missing'])

    def test_call_site_extra_ports_are_reported(self):
        call = {'id': 'call', 'operationKind': 'source-implementation',
                'inputs': [{'port': 'q', 'entity': 'query', 'argument': 'query'},
                           {'port': 'decision', 'entity': 'decision', 'argument': 'decision'}],
                'outcomes': [{'id': 'ok', 'outputs': [{'port': 'a', 'entity': 'answer'}]}]}
        body = {'id': 'body',
                'inputs': [{'port': 'q', 'entity': 'q'}],
                'outcomes': [{'id': 'ok', 'outputs': [{'port': 'a', 'entity': 'answer'}]}]}
        graph = {'operations': [call, body], 'entities': [], 'resources': [], 'components': [],
                 'presentation': {'businessDAG': {'nodes': [{'id': 'target', 'scope': 'body', 'views': {'100': {
                                      'description': '说明本层。',
                                      'steps': [{'operation': 'call', 'node': 'target', 'label': '调用处理',
                                                 'description': '调用目标业务。'}],
                                      'concepts': []}}}]}}}
        warnings = call_site_port_audit(graph)
        self.assertEqual(['callSiteUnmapped'], [warning['kind'] for warning in warnings])
        self.assertIn('decision', warnings[0]['ports'])

    def test_branch_with_many_exclusive_steps_is_reported(self):
        graph = {'presentation': {
            'decisions': [{'id': 'flag', 'owner': 'service', 'branches': [
                {'id': 'yes', 'members': ['a', 'b', 'c', 'd'], 'targets': ['a']},
                {'id': 'no', 'members': ['e'], 'targets': ['e']}]}],
            'businessDAG': {'nodes': [{'id': 'service', 'scope': 'service', 'views': {'100': {
                'steps': [{'operation': value, 'label': value, 'description': value} for value in 'abcd'],
                'concepts': []}}}]}}}
        warnings = branch_packing_warnings(graph)
        self.assertEqual(['branchNotPacked'], [warning['kind'] for warning in warnings])
        self.assertEqual('yes', warnings[0]['branch'])

    def test_a_source_identifier_does_not_imply_one_projects_vocabulary(self):
        for name in ('row', 'source', 'runtime', 'normalized', 'query'):
            self.assertEqual(name, short_label({'name': name, 'type': 'str'}))

    def test_hidden_data_needs_specific_resource_action_or_boundary(self):
        read = {'id': 'read', 'name': 'read',
                'inputs': [{'port': 'db', 'entity': 'db', 'role': 'capture', 'label': '被读取'}],
                'outcomes': [{'id': 'ok', 'outputs': [{'port': 'out', 'entity': 'payload', 'role': 'return'}]}]}
        save = {'id': 'save', 'name': 'save',
                'inputs': [{'port': 'payload', 'entity': 'payload', 'role': 'argument', 'required': True}],
                'outcomes': [{'id': 'ok', 'outputs': [{'port': 'done', 'entity': 'done', 'role': 'return'}]}]}
        graph = {'operations': [read, save],
                 'entities': [{'id': 'payload', 'name': 'payload',
                               'presentation': {'hidden': True, 'reason': 'obvious'},
                               'lineage': ['db']}, {'id': 'done', 'name': 'done'}],
                 'resources': [{'id': 'db', 'name': 'db'}], 'components': []}
        operations = {'read': read, 'save': save}
        generic = omitted_data_issues(graph, operations, save, [read, save], {})
        self.assertIn('omitted-data-generic-label', {issue['kind'] for issue in generic})
        boundary = omitted_data_issues(graph, operations, read, [read, save], {})
        self.assertIn('omitted-data-boundary', {issue['kind'] for issue in boundary})

    def test_importance_hint_orders_boundary_resource_and_intermediate_values(self):
        graph = {'entities': [{'id': value, 'name': value} for value in ('request', 'terms', 'reply')],
                 'resources': [], 'components': [{'id': 'provider', 'name': 'provider'}]}
        source_ops = self.graph['operations'][0]['expansion']['operations']
        self.assertEqual(0, importance_hint(graph, 'reply', source_ops, {'reply'}, set())[0])
        self.assertEqual(1, importance_hint(graph, 'provider', source_ops, {'reply'}, set())[0])
        self.assertEqual(2, importance_hint(graph, 'terms', source_ops, {'reply'}, set())[0])

    def test_detail_view_is_copied_to_all_tiers_and_gets_importance(self):
        result = self.compile()['service']
        self.assertEqual({'0', '50', '100'}, set(result))
        self.assertEqual(result['0']['steps'], result['100']['steps'])
        self.assertEqual(result['50']['steps'], result['100']['steps'])
        self.assertNotIn('terms', {m for c in result['0']['concepts'] for m in c['members']})
        self.assertIn('terms', {m for c in result['50']['concepts'] for m in c['members']})
        self.assertEqual(['prepare', 'execute'], [step['operation'] for step in result['100']['steps']])
        self.assertTrue(all('importance' in concept and 'minGranularity' in concept
                            for concept in result['100']['concepts']))

    def test_importance_conflicts_with_min_granularity(self):
        self.view['concepts'][0].update(importance='main', minGranularity=100)
        with self.assertRaisesRegex(ValueError, '冲突'):
            self.compile()

    def test_processing_step_cannot_be_hidden_by_importance(self):
        self.view['steps'][0]['importance'] = 'auxiliary'
        with self.assertRaisesRegex(ValueError, '不能设置 importance'):
            self.compile()

    def test_two_steps_cannot_produce_the_same_data_identity(self):
        execute = self.graph['operations'][0]['expansion']['operations'][1]
        execute['outcomes'][0]['outputs'].append({'entity': 'terms', 'port': 'p2'})
        with self.assertRaisesRegex(ValueError, '同一数据实体被多个步骤生产'):
            self.compile()

    def test_multiproducer_is_rejected_even_when_not_selected_as_a_concept(self):
        execute = self.graph['operations'][0]['expansion']['operations'][1]
        execute['outcomes'][0]['outputs'].append({'entity': 'terms', 'port': 'p2'})
        self.view['concepts'] = [c for c in self.view['concepts'] if c['members'] != ['terms']]
        with self.assertRaisesRegex(ValueError, '同一数据实体被多个步骤生产'):
            self.compile()

    def test_detail_decision_budget_is_five(self):
        self.graph.setdefault('presentation', {})['decisions'] = [
            {'id': 'decision.' + str(i), 'owner': 'service'} for i in range(6)]
        with self.assertRaisesRegex(ValueError, '判断超过 5 个'):
            self.compile()

    def test_applicable_decision_ceiling_covers_non_owner_decisions(self):
        self.graph.setdefault('presentation', {})['decisions'] = [
            {'id': 'decision.' + str(i), 'owner': 'other', 'predicateOperation': 'prepare', 'inputs': []}
            for i in range(6)]
        with self.assertRaisesRegex(ValueError, '可适用判断超过 5'):
            self.compile()

    def test_primary_from_must_be_a_real_direct_predecessor(self):
        self.view['steps'][1]['primaryFrom'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'primaryFrom'):
            self.compile()
        self.view['steps'][1]['primaryFrom'] = 'terms'
        compiled = self.compile()['service']
        self.assertEqual('terms', compiled['100']['steps'][1]['primaryFrom'])

    def test_concept_primary_from_must_name_a_producer(self):
        self.view['concepts'][1]['primaryFrom'] = 'execute'
        with self.assertRaisesRegex(ValueError, 'primaryFrom'):
            self.compile()
        self.view['concepts'][1]['primaryFrom'] = 'prepare'
        self.assertTrue(self.compile())

    def test_external_input_does_not_create_primary_missing(self):
        warnings = []
        compile_views(self.graph, {'service': {'100': self.view}}, warnings=warnings)
        self.assertNotIn('primaryMissing', {warning['kind'] for warning in warnings})

    def test_primary_missing_and_less_important_require_two_distinct_steps(self):
        operations = {'a': operation('a', ['seed'], ['x']),
                      'b': operation('b', ['seed'], ['y']),
                      'c': operation('c', ['x', 'y'], ['z'])}
        plan = {'steps': [{'operation': 'a'}, {'operation': 'b'}, {'operation': 'c'}],
                'concepts': []}
        warnings = []
        primary_audit({'presentation': {}}, 'service', None, operations, plan, warnings)
        self.assertIn('primaryMissing', {warning['kind'] for warning in warnings})
        plan['concepts'] = [{'members': ['x'], 'importance': 'auxiliary'},
                            {'members': ['y'], 'importance': 'main'}]
        plan['steps'][2]['primaryFrom'] = 'x'
        warnings = []
        primary_audit({'presentation': {}}, 'service', None, operations, plan, warnings)
        self.assertIn('primaryLessImportant', {warning['kind'] for warning in warnings})

    def test_inline_omitted_stop_needs_reopen(self):
        prepare = self.graph['operations'][0]['expansion']['operations'][0]
        prepare['source'] = {'path': 'app.py', 'startLine': 1, 'endLine': 1}
        self.view['steps'][0]['stop'] = {'reason': 'omitted', 'detail': 'Known but outside this review.',
                                         'review': {'sourceRangesChecked': True,
                                                    'reason': 'The selected scope excludes it.',
                                                    'reopen': 'Reopen when the scope changes.'}}
        self.assertTrue(self.compile())
        self.view['steps'][0]['stop']['review'].pop('reopen')
        warnings = []
        compile_views(self.graph, {'service': {'0': self.view}}, warnings=warnings)
        self.assertIn('reopenMissing', {w['kind'] for w in warnings})

    def test_inline_external_unavailable_and_recursion_stops_are_allowed(self):
        prepare = self.graph['operations'][0]['expansion']['operations'][0]
        prepare['source'] = {'path': 'app.py', 'startLine': 1, 'endLine': 1}
        for reason in ('external', 'unavailable', 'recursion'):
            self.view['steps'][0]['stop'] = {'reason': reason, 'detail': 'A concrete boundary.'}
            self.assertTrue(self.compile(), reason)

    def test_inline_simple_stop_needs_no_project_calls_when_empty(self):
        prepare = self.graph['operations'][0]['expansion']['operations'][0]
        prepare['source'] = {'path': 'app.py', 'startLine': 1, 'endLine': 1}
        self.view['steps'][0]['stop'] = {'reason': 'simple', 'detail': 'A direct source endpoint.',
                                         'review': {'sourceRangesChecked': True, 'reason': 'Read directly.',
                                                    'delegates': [], 'sourceCalls': []}}
        warnings = []
        compile_views(self.graph, {'service': {'0': self.view}}, warnings=warnings)
        self.assertIn('noProjectCallsMissing', {w['kind'] for w in warnings})
        self.view['steps'][0]['stop']['review']['noProjectCalls'] = True
        self.assertTrue(self.compile())

    def test_numbered_or_generic_concept_labels_are_rejected(self):
        for label in ('结果1', '结果 2', '步骤3', 'result1', '中间值', '数据'):
            self.view['concepts'][0]['label'] = label
            with self.assertRaisesRegex(ValueError, '禁止按端口/数量/编号'):
                self.compile()

    def test_duplicate_concept_labels_are_rejected(self):
        self.view['concepts'][1]['label'] = self.view['concepts'][0]['label']
        with self.assertRaisesRegex(ValueError, '名称重复'):
            self.compile()

    def test_primary_from_can_target_an_external_boundary_input(self):
        operations = {'service': operation('service', ['seed'], ['result'])}
        plan = {'steps': [{'operation': 'service', 'primaryFrom': 'seed'}], 'concepts': []}
        warnings = []
        primary_audit({'presentation': {}}, 'service', operations['service'], operations, plan, warnings)
        self.assertNotIn('primaryMissing', {warning['kind'] for warning in warnings})
        self.assertNotIn('primaryLessImportant', {warning['kind'] for warning in warnings})

    def test_source_call_may_live_in_the_owner_source_outside_a_narrow_range(self):
        operations = {'impl': {}}
        review = {'sourceCalls': [{'call': 'impl.run', 'line': 5, 'receiverType': 'Runner',
                                   'resolution': 'resolved', 'implementation': 'impl',
                                   'disposition': 'simple', 'reason': 'Direct call.'}]}
        from business_views import validate_source_review
        validate_source_review('leaf', review, operations,
                               source_ranges=[{'path': 'app.py', 'startLine': 1, 'endLine': 2}],
                               evidence_ranges=[{'path': 'app.py', 'startLine': 1, 'endLine': 10}],
                               reason='simple')
        with self.assertRaisesRegex(ValueError, 'owner source'):
            validate_source_review('leaf', review, operations,
                                   source_ranges=[{'path': 'app.py', 'startLine': 1, 'endLine': 2}],
                                   evidence_ranges=[{'path': 'app.py', 'startLine': 1, 'endLine': 4}],
                                   reason='simple')

    def test_primary_from_cannot_point_at_a_later_producer(self):
        operations = {'a': operation('a', ['reply'], ['x']),
                      'b': operation('b', ['seed'], ['reply'])}
        plan = {'steps': [{'operation': 'a', 'primaryFrom': 'reply'}, {'operation': 'b'}], 'concepts': []}
        warnings = []
        with self.assertRaisesRegex(ValueError, '后续步骤生产'):
            primary_audit({'presentation': {}}, 'service', None, operations, plan, warnings)


if __name__ == '__main__':
    unittest.main()
