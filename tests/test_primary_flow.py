"""The solid forest follows the author's primary predecessor, then importance."""
import subprocess
import unittest
from pathlib import Path

TEMPLATE = (Path(__file__).resolve().parents[1] / 'skills/litflux/assets/viewer.html').read_text(encoding='utf8')


def function(name):
    start = TEMPLATE.index('  function ' + name + '(')
    return TEMPLATE[start:TEMPLATE.index('\n  function ', start + 3)]


FLOOR = next(line for line in TEMPLATE.splitlines() if line.startswith('  const importanceFloor='))


class PrimaryFlowTests(unittest.TestCase):
    def run_js(self, script):
        helpers = 'const components=new Map();\n' + function('componentLink') + function('branchEmphasis')
        result = subprocess.run(['node', '-e', helpers + script], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_importance_chooses_the_solid_predecessor(self):
        self.run_js(FLOOR + '''
const entities=new Map([
  ['main',{id:'main',presentation:{importance:'main'}}],
  ['support',{id:'support',presentation:{importance:'supporting'}}]]);
const operations=new Map(),decisions=new Map(),label=item=>item?.id||item?.name||'';
''' + function('forestProjection') + '''
const links=[{id:'a',from:'support',to:'target'},{id:'z',from:'main',to:'target'}];
forestProjection(links);
if(links[1].deferred||!links[0].deferred)throw Error('importance did not choose the main predecessor');
if(links[0].deferredReason!=='主前驱：main')throw Error('missing predecessor reason');
''')

    def test_declared_primary_wins_over_importance(self):
        self.run_js(FLOOR + '''
const entities=new Map([
  ['main',{id:'main',presentation:{importance:'main'}}],
  ['support',{id:'support',presentation:{importance:'supporting'}}]]);
const operations=new Map(),decisions=new Map(),label=item=>item?.id||item?.name||'';
''' + function('forestProjection') + '''
const links=[{id:'a',from:'support',to:'target',primary:true},{id:'z',from:'main',to:'target'}];
forestProjection(links);
if(links[0].deferred||!links[1].deferred)throw Error('declared primary was overridden');
''')

    def test_solid_forest_rejects_multiple_or_cyclic_predecessors(self):
        self.run_js(function('assertSolidForest') + '''
let failed=false;
try{assertSolidForest([{id:'1',from:'a',to:'t'},{id:'2',from:'b',to:'t'}]);}catch(error){failed=/多条主前驱/.test(error.message);}
if(!failed)throw Error('multiple solid predecessors accepted');
failed=false;
try{assertSolidForest([{id:'1',from:'a',to:'b'},{id:'2',from:'b',to:'a'}]);}catch(error){failed=/实线环/.test(error.message);}
if(!failed)throw Error('solid cycle accepted');
''')

    def test_control_edges_have_a_dedicated_forest_exception(self):
        self.run_js(function('assertSolidForest') + '''
for(const links of [
 [{id:'branch',from:'gate',to:'join',decisionControl:true},{id:'value',from:'result',to:'join'}],
 [{id:'predicate',from:'value',to:'gate',decisionControl:true},{id:'branch',from:'gate',to:'value',decisionControl:true}]
]){
 let failed=false;try{assertSolidForest(links);}catch(error){failed=/实线森林约束失败/.test(error.message);}
 if(failed)throw Error('Dedicated decision relations were incorrectly classified as ordinary solid edges');
}
''')

    def test_each_branch_choice_selects_an_active_merge_predecessor(self):
        self.run_js(FLOOR + '''
const entities=new Map(),operations=new Map(),decisions=new Map([['gate',{}]]),label=item=>item?.id||'';
''' + function('forestProjection') + function('assertSolidForest') + '''
for(const side of ['yes','no']){
 const links=[{id:'operand',from:'criterion',to:'gate',decisionControl:true},
  {id:'yes',from:'gate',to:'join',decisionControl:true,branchDecision:'gate',branchSide:'yes',branchLabel:'Yes'},
  {id:'no',from:'gate',to:'generate',decisionControl:true,branchDecision:'gate',branchSide:'no',branchLabel:'No'},
  {id:'return',from:'generate',to:'answer'},
  {id:'merge',from:'answer',to:'join',primary:true}];
 const visible={branchChoices:new Map([['gate',side]]),branchRegions:[
  {decision:'gate',side:'yes',members:['join'],merge:'join'},
  {decision:'gate',side:'no',members:['generate'],merge:'join'}]};
 forestProjection(links,visible);assertSolidForest(links);
 const incoming=links.filter(l=>l.to==='join'&&!l.deferred&&!l.decisionControl);
 if(incoming.length!==1||incoming[0].id!=='merge')throw Error('Merge retained an inactive or multiple solid predecessors for '+side);
}
''')

    def test_nested_branch_combinations_keep_all_visible_solid_edges_a_forest(self):
        self.run_js(FLOOR + '''
const entities=new Map(),operations=new Map(),decisions=new Map([['outer',{}],['inner',{}]]),label=()=>'';
''' + function('forestProjection') + function('assertSolidForest') + '''
for(const outer of ['yes','no'])for(const inner of ['yes','no']){
 const links=[{id:'pred-a',from:'a',to:'outer',decisionControl:true},
  {id:'pred-b',from:'b',to:'outer',decisionControl:true},
  {id:'outer-yes',from:'outer',to:'inner',decisionControl:true,branchDecision:'outer',branchSide:'yes'},
  {id:'outer-no',from:'outer',to:'other',decisionControl:true,branchDecision:'outer',branchSide:'no'},
  {id:'inner-yes',from:'inner',to:'left',decisionControl:true,branchDecision:'inner',branchSide:'yes'},
  {id:'inner-no',from:'inner',to:'right',decisionControl:true,branchDecision:'inner',branchSide:'no'},
  {id:'left-join',from:'left',to:'join'},{id:'right-join',from:'right',to:'join'},
  {id:'other-join',from:'other',to:'join'},
  {id:'order',from:'a',to:'join',decisionControl:true,executionControl:true,forcedDeferred:true,deferred:true}];
 const visible={branchChoices:new Map([['outer',outer],['inner',inner]]),branchRegions:[
  {decision:'outer',side:'yes',members:['inner'],merge:'join'},
  {decision:'outer',side:'no',members:['other'],merge:'join'},
  {decision:'inner',side:'yes',members:['left'],merge:'join'},
  {decision:'inner',side:'no',members:['right'],merge:'join'}]};
 forestProjection(links,visible);assertSolidForest(links);
 const indegree=new Map();for(const link of links.filter(l=>!l.deferred&&!l.decisionControl)){indegree.set(link.to,(indegree.get(link.to)||0)+1);}
 if([...indegree.values()].some(count=>count>1))throw Error('A visible decision edge escaped forest classification');
 if(!links.find(l=>l.id==='order').deferred)throw Error('Explicit source ordering was promoted to a solid predecessor');
 const merge=links.find(l=>l.to==='join'&&!l.deferred&&!l.decisionControl);
 if(merge.id!==(outer==='no'?'other-join':inner==='yes'?'left-join':'right-join'))throw Error('Nested choice lost its active merge predecessor');
}
''')

    def test_component_input_never_competes_for_the_primary_predecessor(self):
        self.run_js(FLOOR + '''
const entities=new Map([['query',{id:'query',presentation:{importance:'supporting'}}]]);
const operations=new Map(),decisions=new Map(),label=item=>item?.id||'';
components.set('engine',{});
''' + function('forestProjection') + function('assertSolidForest') + '''
const capability={id:'capability',from:'engine',to:'search',entity:'engine',direction:'input',capabilityProvider:true,primary:true,deferred:true,deferredReason:'old primary'};
const data={id:'query',from:'query',to:'search'};
forestProjection([capability,data]);
if(!data.primary||data.deferred||capability.primary||capability.deferred||capability.deferredReason)throw Error('Capability still competed for the solid predecessor');
assertSolidForest([capability,data,{id:'other',from:'other-component',to:'search',componentOperation:true,direction:'input',capabilityProvider:true}]);
''')

    def test_component_inputs_are_excluded_from_deferred_consumption(self):
        self.run_js('''
const operations=new Map([['first',{}],['later',{}]]),decisions=new Map(),label=()=>'';
components.set('engine',{});
''' + function('executionProjection') + '''
const first={id:'first-provider',from:'engine',to:'first',entity:'engine',direction:'input',capabilityProvider:true};
const later={id:'later-provider',from:'engine',to:'later',entity:'engine',direction:'input',capabilityProvider:true,forcedDeferred:true,primary:true,deferredReason:'old reason'};
executionProjection([first,later,{id:'result',from:'first',to:'later'}]);
if(first.deferred||later.deferred||later.primary||later.deferredReason)throw Error('Component input acquired execution-order classification');
''')

    def test_reading_does_not_traverse_component_inputs_but_checks_availability(self):
        self.run_js('''
components.set('engine',{});
const scope='test',decisions=new Map();
const nodes=[{id:'engine',kind:'component',provided:true,guards:[],sourceDecisions:[],prerequisites:[]},
 {id:'query',kind:'data',provided:true,guards:[],sourceDecisions:[],prerequisites:[]},
 {id:'search',kind:'operation',guards:[],sourceDecisions:[],prerequisites:[
  {value:'query',alternatives:[{from:'query',link:'input'}]},
  {value:'engine',alternatives:[{from:'engine',link:'provider'}]}]}];
const provider={id:'provider',from:'engine',to:'search',entity:'engine',direction:'input',capabilityProvider:true};
const plan={nodes,links:[provider,{id:'input',from:'query',to:'search'}],requirements:[],foldedDecisions:[],scope:'test'};
const readingPlan=()=>plan;
''' + function('walkExecution') + '''
let result=walkExecution();
if(result.order.includes('engine')||result.events.some(e=>e.type==='execute'&&e.kind==='component'))throw Error('Component availability became an execution step');
if(!result.complete||!result.order.includes('search'))throw Error('An available component blocked its consumer');
if(result.events.some(e=>e.type==='backtrack'&&e.to==='engine'&&e.node==='search'))throw Error('Reading followed a component input');
nodes[0].provided=false;
nodes[0].prerequisites=[{value:'unavailable',alternatives:[{from:'missing',link:'unknown'}]}];
result=walkExecution();
if(result.order.includes('search')||!result.blocked.some(n=>n.node==='search'&&n.waitingFor.some(w=>w.value==='engine')))throw Error('Excluding capability traversal waived real availability');
''')

    def test_branch_control_keeps_cross_frame_arguments_and_real_return_in_reading(self):
        self.run_js('''
const scope='branch',decisions=new Map([['gate',{}]]);
const branchOptions=()=>[{id:'yes',targets:['run']},{id:'no',targets:['refuse']}];
const need=from=>({value:from,alternatives:[{from,link:from}]}),n=(id,kind,prerequisites=[],guards=[])=>({id,kind,prerequisites,guards,provided:false,sourceDecisions:[]});
const nodes=[{...n('request','data'),provided:true},{...n('evidence','data'),provided:true},{...n('config','resource'),provided:true},
 {...n('gate','decision',[need('request')]),sourceDecisions:['gate']},
 n('run','operation',[need('request'),need('evidence'),need('config')],[{decision:'gate',side:'yes'}]),
 n('refuse','operation',[need('request')],[{decision:'gate',side:'no'}]),n('answer','data',[need('run')]),n('refused','data',[need('refuse')]),
 n('merge','operation',[{value:'selected',alternatives:[{from:'answer'},{from:'refused'}]}]),n('result','data',[need('merge')])];
const links=[{id:'criterion',from:'request',to:'gate',decisionControl:true},
 {id:'yes',from:'gate',to:'run',decisionControl:true},{id:'no',from:'gate',to:'refuse',decisionControl:true},
 {id:'request-run',from:'request',to:'run'},{id:'evidence-run',from:'evidence',to:'run',deferred:true},
 {id:'config-run',from:'config',to:'run',resourceOperation:true,deferred:true},{id:'request-refuse',from:'request',to:'refuse',deferred:true},
 {id:'answer',from:'run',to:'answer'},{id:'refused',from:'refuse',to:'refused'},
 {id:'merge-answer',from:'answer',to:'merge'},{id:'merge-refused',from:'refused',to:'merge',deferred:true},{id:'return',from:'merge',to:'result'}];
const plan={scope,nodes,links,requirements:[],foldedDecisions:[]},readingPlan=()=>plan;
''' + function('walkExecution') + '''
for(const side of ['yes','no']){
 const r=walkExecution({gate:side});if(!r.complete||r.blocked.length)throw Error('Selected data path did not complete');
 const selected=side==='yes'?'run':'refuse',other=side==='yes'?'refuse':'run';
 if(r.order.indexOf('gate')>=r.order.indexOf(selected)||!r.order.includes('gate'))throw Error('Decision was skipped or evaluated too late');
 if(r.order.includes(other)||r.order.at(-1)!=='result')throw Error('Control replaced the actual selected result');
 if(side==='yes'&&(r.order.indexOf('evidence')>=r.order.indexOf('run')||!r.events.some(e=>e.type==='available'&&e.node==='config')))throw Error('Cross-frame arguments or resource availability lost');
}
nodes.find(n=>n.id==='evidence').provided=false;
const blocked=walkExecution({gate:'yes'});
if(blocked.order.includes('run')||blocked.order.includes('result')||!blocked.blocked.some(n=>n.node==='run'))throw Error('A selected branch waived its missing dashed argument');
''')


if __name__ == '__main__':
    unittest.main()
