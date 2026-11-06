"""Regressions observed during the independent 6.1 Sol usage trial."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'skills/litflux/scripts'), str(ROOT / 'tests')]
from business_views import branch_packing_warnings, primary_audit, walk
from compile_review import has_source_anchor, prepare
from quality_audit import audit, entry_manifest, guide_manifest, receipt_errors
from test_business_dag import fixture, operation
from test_build_gate import attach_receipts, full_review

VIEWER = (ROOT / 'skills/litflux/assets/viewer.html').read_text(encoding='utf-8')


def function(name):
    start = VIEWER.index('  function ' + name + '(')
    return VIEWER[start:VIEWER.index('\n  function ', start + 3)]


class TrialRegressions(unittest.TestCase):
    def js(self, script):
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout

    def test_chinese_source_citations_still_exclude_urls(self):
        for citation in ('app.py:1，service.py:2；', 'app.py:1、service.py:2',
                         '源码：app.py:1。', '（app.py:1）', 'app.py:1; service.py:2'):
            with self.subTest(citation=citation):
                self.assertTrue(has_source_anchor(citation))
        for citation in ('https://example.com/app.py:1。', 'file:///app.py:1', 'app.py', 'app.py:x'):
            self.assertFalse(has_source_anchor(citation))

    def test_decision_is_neither_a_primary_candidate_nor_an_ordinary_parent(self):
        graph, spec = fixture()
        graph['presentation']['decisions'] = [{'id': 'gate', 'owner': 'service',
            'inputs': ['terms'], 'yes': ['execute'], 'no': ['execute']}]
        plan = copy.deepcopy(spec['nodes'][0]['views']['0'])
        operations = {op['id']: op for op in walk(graph['operations'])}
        self.assertEqual([], primary_audit(graph, 'service', graph['operations'][0], operations, plan, []))
        plan['steps'][1]['primaryFrom'] = 'gate'
        with self.assertRaisesRegex(ValueError, 'primaryFrom'):
            primary_audit(graph, 'service', graph['operations'][0], operations, plan, [])

    def test_branch_packing_does_not_repack_an_inherited_whole_region(self):
        plan = {'steps': [{'operation': value} for value in 'abcd'], 'concepts': []}
        graph = {'presentation': {'decisions': [{'id': 'gate', 'owner': 'body',
            'yes': list('abcd'), 'no': ['reject']}], 'businessDAG': {'nodes': [
                {'id': 'root', 'scope': 'body', 'views': {'100': copy.deepcopy(plan)}},
                {'id': 'packed', 'scope': 'body', 'members': list('abcd'), 'views': {'100': plan}},
                {'id': 'other', 'scope': 'other-body', 'views': {'100': plan}}]}}}
        warnings = branch_packing_warnings(graph)
        self.assertEqual(['root'], [item['scope'] for item in warnings])
        self.assertEqual(4, warnings[0]['exclusiveSteps'])

    def test_simple_counts_external_apis_separately_and_reports_actual_triggers(self):
        graph, spec = fixture()
        review = full_review(spec)
        prepared = prepare(copy.deepcopy(graph), review, delivery=False)['graph']
        prepared['definitions'] = [operation('external.a', [], []), operation('external.b', [], [])]
        for op in prepared['definitions']:
            op['operationKind'] = 'external'
        record = review['semanticInventory']['prep']
        record['sourceCalls'] = [{'call': name, 'line': 1, 'receiverType': 'External API',
            'resolution': 'resolved', 'implementation': name, 'disposition': 'external',
            'reason': 'Known external API boundary; no claim about library internals.'}
            for name in ('external.a', 'external.b')]
        record['control']['awaits'] = [{'source': {'path': 'app.py', 'startLine': 1, 'endLine': 1},
            'call': 'external.a', 'reason': 'Await the adapter result.'}]
        result = audit(prepared, review)
        detail = next(item for item in result['simpleStops'] if item['node'] == 'prep')
        self.assertEqual((0, 2, []), (detail['projectCalls'], detail['externalCalls'], detail['triggers']))
        for op in prepared['definitions']:
            op['operationKind'] = 'source-function'
        result = audit(prepared, review)
        self.assertTrue(any('projectCalls=2' in error for error in result['errors']))
        for call in record['sourceCalls']:
            call['disposition'] = 'simple'
        result = audit(prepared, review)
        error = next(error for error in result['errors'] if 'simple eligibility failed' in error)
        self.assertIn('triggers=multi-stage', error)
        self.assertIn('projectCalls=2', error)
        self.assertIn('externalCalls=0', error)
        record['sourceCalls'][0]['implementation'] = ['malformed-id']
        result = audit(prepared, review)
        self.assertTrue(any('implementation' in error for error in result['errors']))

    def test_source_can_open_from_an_overview_without_a_canvas(self):
        self.js('''
const item={id:'helper'},operations=new Map([['helper',item]]),sourceIndex={has:()=>true};
let view=null,navigationRestoring=false,sourceSelection=null,selected=null,opened=0,saved=0;
const workflowId='main',checkpointNavigation=()=>{},sourceCalls=()=>[],implementationTarget=id=>id;
const openWorkflow=()=>{if(!navigationRestoring)throw Error('Intermediate workflow entered navigation history');view={};opened++;return true;};
const showPage=()=>{},renderSource=()=>{if(!view)throw Error('Source opened without a canvas context');};
const drawNavigation=()=>{},drawTree=()=>{},showDetails=()=>{},openReader=()=>{},$=()=>({focus(){}});
const save=()=>{if(navigationRestoring)throw Error('Source destination did not finish its transaction');saved++;};
''' + function('openSource') + '''
if(!openSource('helper')||opened!==1||saved!==1||sourceSelection.target!=='helper'||navigationRestoring)throw Error('Initial source navigation failed');
''')

    def test_auditor_rejects_failed_guide_return_and_role_restore(self):
        factory = (ROOT / 'skills/litflux/assets/entry-audit.js').read_text(encoding='utf-8')
        self.js('const create=' + factory + ''';
const views=Object.fromEntries([0,50,100].map(tier=>[tier,{steps:[],concepts:[]}]));
const base={dag:{roots:{main:'entry'},nodes:[{id:'entry',views}]},snapshot:()=>({}),restore:()=>true,openScope:()=>({})};
let result=create({...base,guides:()=>[{context:'guide:test',definition:'body'}],
 probeGuide:()=>({enabled:true,entered:true,returned:false})}).auditEntries();
if(result.status!=='failed'||result.guides[0].status!=='failed')throw Error('Guide without return was accepted');
result=create({...base,roleFailures:()=>[{id:'date',expected:'data',actual:'resource'}]}).auditEntries();
if(result.status!=='failed'||!result.failures.some(item=>item.kind==='roleRestoreMismatch'))throw Error('Role pollution was accepted');
result=create({...base,guides:()=>[{context:'guide:external',definition:'external'}],
 probeGuide:()=>({enabled:false,boundary:true,reason:'Actual external implementation is unavailable.'})}).auditEntries();
if(result.status!=='passed')throw Error('A genuine explicit external boundary was rejected');
''')

    def test_projected_role_replaces_old_resource_and_component_maps(self):
        self.js('''
const entities=new Map(),components=new Map([['provider',{}]]),resources=new Map([['store',{}]]),dependencies=new Map();
''' + function('registerProjectedEntity') + '''
const id='@interface:child:4',value={id,kind:'value',type:'datetime'};
registerProjectedEntity(id,{id,kind:'database'},'store');
if(!resources.has(id)||!dependencies.has(id))throw Error('Resource role was lost');
registerProjectedEntity(id,value,'date');
if(resources.has(id)||components.has(id)||dependencies.has(id)||entities.get(id)!==value)throw Error('Old resource role survived data');
registerProjectedEntity(id,{id,kind:'component'},'provider');
if(!components.has(id)||resources.has(id))throw Error('Component role is inconsistent');
registerProjectedEntity(id,value,'date');
if(components.has(id)||dependencies.has(id))throw Error('Old component role survived data');
''')

    def test_provider_does_not_follow_descendant_calls_into_a_parent(self):
        self.js('''
const components=new Map([['db',{}]]),entities=new Map(),businessNodes=new Map();
const direct={id:'execute',name:'Execute',inputs:[{entity:'db',relation:'invocation'}]};
const operations=new Map([['execute',direct]]),sourceCalls=()=>[direct],implementationTarget=id=>id,label=op=>op.name;
''' + function('providedFunctions') + '''
const port={entity:'db',relation:'dependency'},parent={id:'parent',inputs:[port]};
if(providedFunctions(parent,port).length)throw Error('Child execute became a parent provider');
if(providedFunctions({...parent,sourceMembers:['execute','commit']},port).length)throw Error('Group became a direct method');
if(providedFunctions(direct,{entity:'db'}).length!==1)throw Error('Actual method provider was lost');
if(providedFunctions({...parent,sourceMembers:['execute']},port).length!==1)throw Error('One exact represented call lost its provider');
''')

    def test_entry_preview_restores_all_entity_role_maps_even_when_it_fails(self):
        self.js('''
const model={presentation:{}},sourceIndex={has:()=>false},businessNodes=new Map();
const operations=new Map([['child',{id:'child',expansion:{operations:[{}]}}]]);
const original={id:'@interface:child:4',kind:'value',type:'datetime'};
const entities=new Map([[original.id,original]]),components=new Map(),resources=new Map(),dependencies=new Map();
const implementationTarget=id=>id,businessCalls=()=>[],dispatchFor=()=>null,boundaryContract=()=>[],branchStamp=()=>'',updateProfile=()=>{},entryPreviewCache=new Map();
let scope='parent',invocationContext=[],history=[],granularity=50,view={},fail=false;
const compute=()=>{const wrong={id:original.id,kind:'database'};entities.set(original.id,wrong);resources.set(original.id,wrong);dependencies.set(original.id,wrong);if(fail)throw Error('projection failed');return{ops:[{}],decisions:[]};};
''' + function('entryPlan') + function('entryAvailabilityCore') + function('entryAvailability') + '''
for(const failed of [false,true]){fail=failed;entryPreviewCache.clear();entryAvailability('child');
 if(entities.get(original.id)!==original||resources.has(original.id)||components.has(original.id)||dependencies.has(original.id))throw Error('Preview polluted active roles');
 if(scope!=='parent'||history.length||granularity!==50)throw Error('Preview changed navigation');}
''')

    def test_guide_uses_reachable_business_context_before_raw_scope(self):
        self.js('''
const workflowId='active',invocationContext=['second'];
const businessNodes=new Map([['first',{id:'first',scope:'service'}],['second',{id:'second',scope:'service'}]]);
const operations=new Map([['service',{}],['helper',{}]]),businessId=id=>'business-node.'+id;
const functionRoute=id=>({workflow:id==='second'?'active':'other',edges:[{members:[id]}]});
''' + function('guideDestination') + '''
if(guideDestination('service').target!=='business-node.second')throw Error('Guide used a raw scope or wrong binding context');
if(guideDestination('business-node.first').node!=='first')throw Error('Explicit business context was changed');
if(guideDestination('helper').target!=='helper')throw Error('Source-only helper disappeared');
if(guideDestination('missing').target!==null)throw Error('Invented guide target');
''')

    def test_guide_manifest_matches_viewer_and_missing_actions_block_receipts(self):
        graph, spec = fixture()
        review = full_review(spec)
        prepared = prepare(copy.deepcopy(graph), review, delivery=False)
        compiled = prepared['graph']
        expected = guide_manifest(compiled)
        self.assertTrue(expected)
        output = self.js('const model=' + json.dumps({'projectOverview': compiled['projectOverview']}) + ';\n'
                         + function('guideRecords')
                         + '\nconsole.log(JSON.stringify(guideRecords().map(({record,...rest})=>rest)));')
        self.assertEqual(expected, json.loads(output))
        path = Path(review['qa']['entryAuditFile'])
        receipt = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(expected), len(receipt['guides']))
        original = copy.deepcopy(receipt)
        external = next(item for item in receipt['guides'] if item['definition'] == 'execute')
        external.update(enabled=False, mode='boundary', entered=False,
                        reason='The declared external implementation is unavailable.')
        path.write_text(json.dumps(receipt), encoding='utf-8')
        self.assertEqual([], receipt_errors(compiled, review, prepared['qualityRevision'], fields=('entryAuditFile',)))
        viewed = next(item for item in receipt['guides'] if item['definition'] == 'service')
        viewed.update(enabled=False, boundary=True, entered=False, reason='A claimed boundary cannot hide a view.')
        path.write_text(json.dumps(receipt), encoding='utf-8')
        self.assertTrue(any('actual enter/return' in error for error in receipt_errors(
            compiled, review, prepared['qualityRevision'], fields=('entryAuditFile',))))
        receipt = original
        receipt.pop('guides')
        path.write_text(json.dumps(receipt), encoding='utf-8')
        self.assertTrue(any('project guide actions' in error for error in receipt_errors(
            compiled, review, prepared['qualityRevision'], fields=('entryAuditFile',))))


if __name__ == '__main__':
    unittest.main()
