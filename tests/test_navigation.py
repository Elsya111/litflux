"""The entry guard and ancestor navigation share the real viewer projection."""
from pathlib import Path
import subprocess
import unittest

TEMPLATE = (Path(__file__).resolve().parents[1] / 'skills/litflux/assets/viewer.html').read_text(encoding='utf8')


def function(name):
    start = TEMPLATE.index('  function ' + name + '(')
    return TEMPLATE[start:TEMPLATE.index('\n  function ', start + 3)]


class NavigationTests(unittest.TestCase):
    def test_reload_preserves_a_source_only_workflow_scope(self):
        self.run_js('''
const businessSpec=null,VIEW_VERSION=33,model={project:{name:'fixture'}},sourceIndex={has:o=>o?.id==='leaf'};
const operations=new Map([['leaf',{id:'leaf',expansion:null}]]),components=new Map(),entities=new Map(),decisions=new Map();
const branchChoices=new Map(),implementationChoices=new Map(),workflows=[{id:'main'}],snapGrain=n=>n,validCamera=()=>true;
let granularity=100,currentPage,workflowId,selected,scope,sourceSelection,history,invocationContext,density,camera;
''' + function('restore') + '''
const state={viewVersion:33,project:'fixture',page:'flow',workflow:'main',scope:'leaf',selected:'leaf',
 sourceSelection:{id:'leaf',target:'leaf'},invocationContext:['leaf'],history:[]};
if(!restore(state)||scope!=='leaf'||invocationContext[0]!=='leaf'||!sourceSelection)throw Error('Source workflow state was discarded');
restore({...state,sourceSelection:null});if(scope!==null)throw Error('An inactive non-graph scope was restored');
''')

    def test_exception_decision_needs_no_fabricated_criterion_data(self):
        self.run_js('''
const model={presentation:{executionOrders:{}}},scope='root',profile={decisionBudget:5};
const operations=new Map(),sourceProducers=new Map(),dependencies=new Map(),decisions=new Map();
const spec={id:'exception',kind:'exception',inputs:[],criterionInputs:[],condition:'raises',question:'Did processing raise?',yes:['recover'],no:['continue'],merge:'continue',evidence:['code']};
const decisionSpecs=()=>[spec],decisionApplies=()=>true,decisionVisible=()=>true;
const branchOptions=d=>[{id:'yes',targets:d.yes,members:d.yes},{id:'no',targets:d.no,members:d.no}];
const chosenBranch=d=>({id:'yes'}),sharedBranchNodes=()=>new Set(),reachable=()=>false;
const visible={ops:[{id:'recover'},{id:'continue'}],entities:[],representatives:new Map(),boundary:new Map()};
''' + function('decisionProjection') + '''
const geometry=[],logical=[],result=decisionProjection(visible,geometry,logical);
if(result.decisions.length!==1||result.foldedDecisions.length)throw Error('A valid exception decision was folded');
if(result.decisions[0].controlKind!=='exception')throw Error('Renderer kind overwrote the semantic decision kind');
if(logical.filter(edge=>edge.role==='branch'&&edge.to.startsWith('@branch:')).length!==2)throw Error('Exception alternatives were lost');
if(logical.some(edge=>edge.role==='predicate'))throw Error('Exception invented a criterion input');
spec.kind='guard';decisions.clear();
if(decisionProjection(visible,[],[]).decisions.length)throw Error('An ordinary guard accepted missing criterion data');
''')

    def test_long_decision_text_fits_the_cut_corner_node_without_losing_content(self):
        self.run_js(function('decisionLabelLayout') + r"""
for(const question of ['选定证据为空或完整性判定为 none_supported 时，是否直接拒答？','Does an exceptionally_long_source_identifier change the selected result?']){
 const measure=text=>[...text].length*8,layout=decisionLabelLayout(question,measure,'异常');
 if(layout.lines.join('').replace(/\s/g,'')!==question.replace(/\s/g,''))throw Error('Decision text was truncated');
 if(layout.width<220||layout.width>376||layout.height<64||layout.width<layout.height)throw Error('Decision lost its horizontal cut-corner proportions');
 layout.lines.forEach(line=>{if(measure(line)>layout.width-76)throw Error('Text crosses its column beside the branch symbol');});
 if(28+layout.lines.length*20+24>layout.height)throw Error('Question and semantic badge overlap');
}
""")

    def test_decision_wire_anchors_follow_the_actual_octagonal_outline(self):
        self.run_js(function('decisionOutline') + function('decisionBoundary') + r"""
const n={x:100,y:200,w:280,h:68},outline=decisionOutline(n.w,n.h);
if(outline.length!==8)throw Error('Decision is not a four-corner-cut rectangle');
for(const [dx,dy]of [[1,0],[-1,0],[0,1],[0,-1]])for(const offset of [-24,0,24]){
 const p=decisionBoundary(n,dx,dy,offset),x=p.x-n.x+n.w/2,y=p.y-n.y+n.h/2;
 const onEdge=outline.some((a,i)=>{const b=outline[(i+1)%outline.length],cross=(b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0]);return Math.abs(cross)<.001&&x>=Math.min(a[0],b[0])-.001&&x<=Math.max(a[0],b[0])+.001&&y>=Math.min(a[1],b[1])-.001&&y<=Math.max(a[1],b[1])+.001;});
 if(!onEdge)throw Error('Wire anchor misses the cut-corner outline');
}
""")

    def test_branch_choice_dims_exclusive_nodes_without_starting_reading(self):
        self.run_js(r"""
let reading=null,stamp='yes',walks=0;
const branchStamp=()=>stamp,walkExecution=()=>{walks++;return{inactive:[stamp==='yes'?'no-only':'yes-only'],choices:{gate:stamp}}};
const make=()=>({flags:{},dataset:{},classList:{toggle(name,value){this.owner.flags[name]=!!value}}});
const elements=new Map(['yes-only','no-only','merge'].map(id=>{const e=make();e.classList.owner=e;return[id,e]}));
const path=make();path.classList.owner=path;
const paths=new Map([['branch',path]]),view={links:[{id:'branch',from:'no-only',to:'merge',branchDecision:'gate',branchSide:'no'}]};
""" + function('branchEmphasis') + function('paintReading') + r"""
paintReading();paintReading();
if(!elements.get('no-only').flags['sf-branch-inactive']||elements.get('merge').flags['sf-branch-inactive']||walks!==1)throw Error('Branch preview lost exclusive/shared distinction or caching');
stamp='no';paintReading();
if(!elements.get('yes-only').flags['sf-branch-inactive']||elements.get('no-only').flags['sf-branch-inactive']||path.flags['sf-branch-inactive'])throw Error('New branch was not reflected immediately');
""")

    def test_branch_emphasis_reaches_downstream_steps_and_preserves_shared_merge(self):
        self.run_js(r"""
const view={branchRegions:[{decision:'gate',side:'yes',members:['merge'],merge:'merge'},
 {decision:'gate',side:'no',members:['compress'],merge:'merge'}],links:[
 {from:'compress',to:'fragments'},{from:'fragments',to:'generate',deferred:true},
 {from:'generate',to:'answer'},{from:'answer',to:'merge'},{from:'merge',to:'result'},
 {from:'answer',to:'database',resourceOperation:true},{from:'answer',to:'before',feedback:true}]};
""" + function('branchEmphasis') + r"""
let off=branchEmphasis({inactive:['merge','result'],choices:{gate:'yes'}});
if(!['compress','fragments','generate','answer'].every(id=>off.has(id))||['merge','result','database','before'].some(id=>off.has(id)))throw Error('Exclusive branch stopped at its first node or crossed its merge');
off=branchEmphasis({inactive:['compress'],choices:{gate:'no'}});
if(off.size)throw Error('Selected branch or common merge remained dim');
""")

    def test_component_input_style_does_not_depend_on_execution_order(self):
        self.run_js("const components=new Map([['provider',{}]]);" + function('componentLink') + """
if(!componentLink({entity:'provider',direction:'input',deferred:true,capabilityProvider:true}))throw Error('Deferred capability lost its independent relation');
if(componentLink({entity:'provider',direction:'input'})||componentLink({entity:'provider',direction:'output'})||componentLink({entity:'provider',direction:'input',feedback:true}))throw Error('Component actions or feedback were relabelled as capability input');
""")

    def test_full_graph_route_prefers_current_origin_and_keeps_exposure_edges(self):
        self.run_js('''
const workflows=[{id:'one'},{id:'two'}],workflowId='two',invocationContext=['second-call'];
const businessNodes=new Map(['a','b','shared','event'].map(id=>[id,{}]));
const businessSpec={roots:{one:'a',two:'b'},edges:[
 {from:'a',to:'shared',members:['first-call'],kind:'decomposes'},
 {from:'b',to:'shared',members:['second-call'],kind:'decomposes'}],
 exposures:[{from:'shared',to:'event',members:['register'],kind:'exposes'}]};
''' + function('functionRoute') + '''
const route=functionRoute('event');
if(route.workflow!=='two'||route.edges.length!==2||route.edges[1].kind!=='exposes')throw Error('Wrong source context for shared node');
if(functionRoute('missing')!==null)throw Error('Unknown node received an invented route');
''')

    def test_component_provider_requires_actual_receiver_or_invocation_evidence(self):
        self.run_js('''
const components=new Map([['engine',{}]]),entities=new Map(),sourceCalls=()=>[],label=op=>op.name,implementationTarget=id=>'actual.'+id;
const call={id:'search',name:'Search evidence',inputs:[{entity:'engine',relation:'invocation'},{entity:'query'}]},dependency={id:'construct',name:'Construct handler',inputs:[{entity:'engine',relation:'dependency'}]};
''' + function('providedFunctions') + '''
const result=providedFunctions(call,{entity:'engine'});
if(result.length!==1||result[0].implementation!=='actual.search')throw Error('Provider lost its selected implementation');
if(providedFunctions(call,{entity:'query'}).length)throw Error('Data was treated as a function provider');
if(providedFunctions(dependency,{entity:'engine'}).length)throw Error('Passing a component became a false method call');
''')

    def test_full_graph_prefers_the_targets_own_external_trigger_entry(self):
        self.run_js('''
const workflows=[{id:'setup'},{id:'http'}],workflowId='setup',invocationContext=[];
const businessNodes=new Map(['app','handler','parse'].map(id=>[id,{}]));
const businessSpec={roots:{setup:'app',http:'handler'},edges:[{from:'handler',to:'parse',kind:'decomposes',members:['parse-call']}],exposures:[{from:'app',to:'handler',kind:'exposes',members:['register']}]};
''' + function('functionRoute') + '''
const route=functionRoute('handler');
if(route.workflow!=='http'||route.edges.length)throw Error('HTTP trigger was routed through app initialization');
if(functionRoute('parse').workflow!=='http')throw Error('A handler child was routed through registration instead of its external entrance');
''')

    def test_full_graph_jump_selects_hidden_branch_from_complete_model(self):
        self.run_js('''
const businessNodes=new Map([['entry',{scope:'body'}]]),branchChoices=new Map(),branchKey=d=>d.id;
const model={presentation:{decisions:[{id:'hidden',owner:'body',branches:[
 {id:'yes',members:['yes-call']},{id:'no',members:['no-call']}]},
 {id:'shared',owner:'body',branches:[{id:'yes',members:['common']},{id:'no',members:['common']}]}]}};
const branchOptions=d=>d.branches;
''' + function('selectFunctionBranches') + '''
selectFunctionBranches({from:'entry'},new Set(['no-call','common']));
if(branchChoices.get('hidden')!=='no')throw Error('Jump ignored a decision hidden by the current tier');
if(branchChoices.has('shared'))throw Error('Jump arbitrarily switched a common successor branch');
''')

    def test_history_stamp_changes_when_a_review_changes_without_new_source_ids(self):
        stamp = next(line for line in TEMPLATE.splitlines() if line.startswith('  const businessStamp='))
        self.run_js('''
function stampFor(model){const businessSpec=model.presentation.businessDAG;
''' + stamp + '''
return businessStamp;}
const a={presentation:{businessDAG:{nodes:[{id:'same',identity:'same',views:{0:{description:'Old'}}}],edges:[]}}};
const b=structuredClone(a);b.presentation.businessDAG.nodes[0].views[0].description='New';
if(stampFor(a)===stampFor(b))throw Error('Changed authored views retain stale navigation state');
a.presentation.businessRevision='compact-model-digest';
if(stampFor(a)!=='compact-model-digest')throw Error('The compact renderer revision was ignored');
''')

    def run_js(self, script):
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_exposed_handler_has_event_inputs_instead_of_factory_call_arguments(self):
        self.run_js('''
const operations=new Map([['handler',{id:'handler',businessStep:true,internalFlow:{0:{}},expansion:{operations:[{}]}}]]);
const model={presentation:{}},sourceIndex={has:()=>false},implementationTarget=id=>id;
let scope='factory',invocationContext=[],history=[],granularity=50,view={};
const entities=new Map(),components=new Map(),resources=new Map(),dependencies=new Map(),branchStamp=()=>'',updateProfile=()=>{},entryPreviewCache=new Map();
const boundaryContract=()=>{throw Error('An event handler is not invoked by factory arguments');};
const compute=()=>({ops:[{}],decisions:[]});
''' + function('entryPlan') + function('entryAvailabilityCore') + function('entryAvailability') + '''
const result=entryAvailability('handler',new Set(),true);
if(!result.enabled||result.mode!=='graph')throw Error('Registered capability cannot be explored');
if(scope!=='factory'||granularity!==50||history.length)throw Error('Capability preview changed navigation');
''')

    def test_capability_navigation_is_limited_to_current_exposures(self):
        self.run_js('''
const operations=new Map([['root',{businessId:'factory'}]]),businessNodes=new Map([['factory',{exposes:[{node:'request'}]}]]),workflows=[],businessSpec={roots:{}};
let scope='root',calls=[];const businessId=id=>'business-node.'+id,enter=(...args)=>{calls.push(args);return true;};
''' + function('openCapability') + '''
if(openCapability('unrelated'))throw Error('Unregistered capability was navigable');
if(!openCapability('request')||calls[0][0]!=='business-node.request'||calls[0][2]!==true)throw Error('Exposure was treated as a normal call');
''')

    def test_all_judgment_branches_stay_in_the_projection(self):
        self.run_js('''
const entities=new Map(),model={presentation:{}},branchOptions=d=>d.branches,chosenBranch=d=>d.branches[0],executionMembers=op=>[op.id];
const decision={id:'flag',evaluationKey:'check',branches:[{id:'yes',targets:['yes-call'],members:['yes-call']},{id:'no',targets:['no-call'],members:['no-call']}]};
function projected(shown,unresolved=false){
 const ops=[{id:'yes-call'},{id:'no-call'}],view={ops,rawOps:ops,entities:[],boundary:new Map(),representatives:new Map(),decisionAliases:new Map(),invocations:new Map(),decisions:shown?[{...decision,id:'@decision:flag'}]:[],foldedDecisions:shown?[]:[{...decision,unresolvedGuards:unresolved?[{}]:[]}],executionRequirements:[],feedback:[],foldedFeedback:[]};
 branchProjection(view,[],[]);return view.ops.map(o=>o.id).join(',');
}
''' + function('branchProjection') + '''
if(projected(false)!=='yes-call,no-call'||projected(true)!=='yes-call,no-call')throw Error('A judgment branch was hidden by projection');
if(projected(false,true)!=='yes-call,no-call')throw Error('An unresolved guard changed the visible branch set');
''')

    def test_common_successor_and_merge_survive_branch_projection(self):
        self.run_js('''
const entities=new Map(),model={presentation:{}},branchOptions=d=>d.branches,chosenBranch=d=>d.branches[0],executionMembers=op=>[op.id];
const sharedBranchNodes=d=>{const counts=new Map();for(const option of branchOptions(d)){const ids=new Set([...(option.members||[]),...(option.targets||[])]);for(const id of ids)counts.set(id,(counts.get(id)||0)+1);}const shared=new Set([...counts].filter(([,count])=>count>1).map(([id])=>id));if(d.merge)shared.add(d.merge);return shared;};
const decision={id:'flag',evaluationKey:'check',merge:'common',branches:[{id:'yes',targets:['yes-call','common'],members:['yes-call']},{id:'no',targets:['no-call','common'],members:['no-call']}]};
function projected(folded){const ops=[{id:'yes-call'},{id:'no-call'},{id:'common'}],view={ops,rawOps:ops,entities:[],boundary:new Map(),representatives:new Map(),decisionAliases:new Map(),invocations:new Map(),decisions:folded?[]:[{...decision,id:'@decision:flag'}],foldedDecisions:folded?[{...decision,unresolvedGuards:[]}]:[],executionRequirements:[],feedback:[],foldedFeedback:[]};branchProjection(view,[],[]);return view.ops.map(o=>o.id).join(',');}
''' + function('branchProjection') + '''
if(!projected(false).split(',').includes('common')||!projected(true).split(',').includes('common'))throw Error('common successor was hidden');
''')

    def test_shared_understanding_never_collapses_actual_call_positions(self):
        start = TEMPLATE.index('    for(const op of visible.ops){const key=')
        code = TEMPLATE[start:TEMPLATE.index('\n    visible.rawOps=', start)]
        self.run_js('''
const first={id:'first',implementation:'body',businessTarget:'worker',outcomes:[{condition:'success'}]},
      second={id:'second',implementation:'body',businessTarget:'worker',outcomes:[{condition:'success'}]};
const visible={ops:[first,second]},groupsByIdentity=new Map(),identity=()=> 'same-implementation',
      canContract=()=>true,operations=new Map([['body',{id:'body'}]]),label=()=> 'Shared function',
      invocations=new Map(),representatives=new Map();
''' + code + '''
if(visible.ops.length!==2)throw Error('Independent call positions were collapsed merely because their implementation is shared');
if(representatives.get('first')!=='first'||representatives.get('second')!=='second')throw Error('Invocation identity was lost');
''')

    def test_function_highlight_identity_includes_effective_components(self):
        self.run_js('''
const entities=new Map(),operations=new Map([
  ['a',{businessTarget:'engineA'}],['b',{businessTarget:'engineB'}],['again',{businessTarget:'engineA'}]]);
const businessNodes=new Map([['engineA',{identity:'function+componentA'}],['engineB',{identity:'function+componentB'}]]);
''' + next(line for line in TEMPLATE.splitlines() if line.startswith('  function identity(')) + '''
if(identity('a')===identity('b'))throw Error('Different component contexts share highlight identity');
if(identity('a')!==identity('again'))throw Error('Proven shared understanding identity was lost');
''')

    def test_reviewed_business_label_survives_interface_selection(self):
        label_code = TEMPLATE[TEMPLATE.index('  const label=item=>'):TEMPLATE.index('  const shortText=')]
        self.run_js('''
const t=x=>x,model={projectOverview:{contracts:[]}};
let selected='abstract';
const implementationOptions=()=>({selected,contract:{method:'Finder.search',kind:'protocol'},candidates:[{id:'concrete',label:'VectorFinder.search'}]});
''' + label_code + '''
const business={id:'call',businessStep:true,presentation:{label:'检索支持材料'}};
if(label(business)!=='检索支持材料')throw Error('contract overwrote the reviewed call purpose');
selected='concrete';
if(label(business)!=='检索支持材料')throw Error('implementation overwrote the reviewed call purpose');
if(label({id:'unreviewed'})!=='VectorFinder.search')throw Error('unreviewed implementation label lost');
selected='abstract';
if(label({id:'unreviewed'})!=='search · 接口')throw Error('unreviewed contract label lost');
''')

    def test_reviewed_business_description_precedes_generic_contract_text(self):
        self.run_js('''
const shortText=x=>x,mechanicalMeaning=x=>!x,label=x=>x.name;
const implementationOptions=()=>({selected:'abstract',contract:{description:'Generic contract.',kind:'protocol'},candidates:[]});
const contractKindLabel=x=>x;
''' + function('simpleDescription') + '''
const business={id:'call',businessStep:true,description:'Old generic source description.',explanation:{purpose:'把用户问题转为有来源的支持材料，交给回答阶段。'}};
if(simpleDescription(business)!==business.explanation.purpose)throw Error('contract erased source-reviewed business explanation');
if(!simpleDescription({id:'raw'}).includes('Generic contract.'))throw Error('raw contract explanation lost');
''')

    def test_interface_selection_overrides_a_reviewed_fixed_entry(self):
        self.run_js('''
const operations=new Map([['call',{id:'call',businessStep:true,businessEnter:'default-body'}],['default-body',{id:'default-body'}]]);
let scope='parent',chosen='other-body';
const dispatchFor=id=>id==='call'?{}:null,businessCalls=()=>[],implementationTarget=id=>id==='call'?chosen:id;
''' + function('entryPlan') + '''
if(entryPlan('call').target!=='other-body')throw Error('fixed business entry overrode the selected implementation');
chosen='contract';
if(entryPlan('call').target!=='contract')throw Error('fixed business entry overrode the selected abstraction');
''')

    def test_reused_canvas_node_refreshes_accessible_name_and_tooltip(self):
        start = TEMPLATE.index("    for(const [kind,items]of [['entity',visible.entities],['operation',visible.ops]])")
        refresh = TEMPLATE[start:TEMPLATE.index('\n    for(const item of visible.decisions)', start)]
        self.run_js('''
const text={},attrs={'aria-label':'函数：旧实现'},el={dataset:{},querySelector:()=>text,setAttribute:(k,v)=>attrs[k]=v,offsetWidth:100,offsetHeight:40};
const item={id:'call',name:'新实现',description:'新的实际职责'},visible={entities:[],ops:[item]},elements=new Map([['call',el]]),nodes=new Map();
const label=x=>x.name,simpleDescription=x=>x.description,makeItem=()=>{throw Error('existing node was replaced');};
''' + TEMPLATE[TEMPLATE.index('  function describeNode('):].split('\n', 1)[0] + refresh + '''
if(text.textContent!=='新实现'||attrs['aria-label']!=='业务：新实现')throw Error('canvas accessibility label stayed on old implementation');
if(!el.title.includes('新的实际职责')||!attrs['data-tooltip'].includes('新实现'))throw Error('canvas tooltip stayed on old implementation');
''')

    def test_source_fallback_retains_reviewed_projection_failure_for_audit(self):
        self.run_js('''
const operations=new Map([['call',{id:'call',implementation:'body'}],['body',{id:'body',expansion:{operations:[{}]}}]]);
const model={presentation:{internalFlows:{body:{0:{},50:{},100:{}}}}},sourceIndex={has:()=>true},businessCalls=()=>[],dispatchFor=()=>null,implementationTarget=id=>operations.get(id)?.implementation||id;
let scope='parent',invocationContext=[],history=[],granularity=50,view={};
const entities=new Map(),components=new Map(),resources=new Map(),dependencies=new Map(),boundaryContract=()=>[],branchStamp=()=>'',updateProfile=()=>{},entryPreviewCache=new Map();
const compute=()=>{throw Error('business grouping cycle');};
''' + function('entryPlan') + function('entryAvailabilityCore') + function('entryAvailability') + '''
const entry=entryAvailability('call');
if(entry.mode!=='source'||entry.projectionError!=='business grouping cycle'||entry.projectionTier!==0)throw Error('failed child review was disguised as an intentional source endpoint');
if(scope!=='parent'||granularity!==50)throw Error('audit changed the current view');
''')

    def test_source_reference_list_does_not_promise_an_unavailable_child(self):
        self.run_js('''
const entryAvailability=id=>({enabled:id==='reviewed'});
''' + function('relatedSourceDescription') + '''
if(!relatedSourceDescription({id:'reviewed'}).includes('直接阅读相关代码'))throw Error('reviewed entry is not explained');
if(!relatedSourceDescription({id:'missing'}).includes('最后一层'))throw Error('source references pretend to be a diagram');
if(relatedSourceDescription({id:'missing'}).includes('进入步骤可'))throw Error('unavailable entry was promised');
''')

    def test_entry_checks_final_projection_and_restores_call_context(self):
        self.run_js('''
const model={},sourceIndex={has:()=>false};
const operations=new Map([
 ['empty',{id:'empty',expansion:{operations:[]}}],
 ['hidden',{id:'hidden',expansion:{operations:[{}]}}],
 ['real',{id:'real',expansion:{operations:[{}]}}],
 ['judge',{id:'judge',expansion:{operations:[{}]}}],
 ['call',{id:'call',implementation:'real'}],
 ['summary',{id:'summary',businessEnter:'call'}]
]);
let scope='parent',invocationContext=['outer'],projected=[],history=[],granularity=50,view=null;
const entities=new Map(),components=new Map(),resources=new Map(),dependencies=new Map();
const entryPreviewCache=new Map(),businessCalls=()=>[],dispatchFor=()=>null,
 implementationTarget=id=>operations.get(id)?.implementation||id,branchStamp=()=>'',updateProfile=()=>{};
const compute=(changed,preview)=>{if(!preview)throw Error('layout used for probe');projected.push([scope,[...invocationContext]]);return{ops:scope==='real'?[{}]:[],decisions:scope==='judge'?[{}]:[]};};
''' + function('entryPlan') + function('entryAvailabilityCore') + function('entryAvailability') + '''
if(entryAvailability('empty').enabled)throw Error('empty body entered');
if(entryAvailability('hidden').enabled)throw Error('hidden body entered');
if(!entryAvailability('summary').enabled)throw Error('concrete body disabled');
if(scope!=='parent'||invocationContext.join(',')!=='outer')throw Error('probe changed context');
if(projected.at(-1)[0]!=='real'||projected.at(-1)[1].join(',')!=='outer,call')throw Error('wrong implementation/context probed');
entryAvailability('call');const size=projected.length;entryAvailability('call');if(projected.length!==size)throw Error('probe cache missed');
if(granularity!==50||history.length)throw Error('probe changed tier/ancestors');
if(!entryAvailability('judge').enabled)throw Error('meaningful decision-only graph disabled');
''')

    def test_disabled_entry_cannot_change_scope_or_history(self):
        self.run_js('''
const operations=new Map([['leaf',{id:'leaf'}]]);
let scope='parent',selected=null,history=[],invocationContext=['call'];
const entryAvailability=()=>({enabled:false}),select=id=>{selected=id;};
''' + function('enter') + '''
if(enter('leaf')!==false||scope!=='parent'||history.length||invocationContext.join(',')!=='call')throw Error('disabled entry navigated');
if(selected!=='leaf')throw Error('source details unavailable');
''')

    def test_definition_source_endpoint_applies_through_a_real_call(self):
        self.run_js('''
const operations=new Map([['call',{id:'call',implementation:'definition'}],['definition',{id:'definition',expansion:{operations:[{}]},stop:{reason:'simple',detail:'A source endpoint is clearer for this wrapper.'}}]]);
const model={presentation:{}};
const sourceIndex={has:op=>op?.id==='definition'},implementationTarget=id=>operations.get(id)?.implementation||id,businessCalls=()=>[],dispatchFor=()=>null;
let scope='parent';
''' + function('entryPlan') + function('entryAvailabilityCore') + function('entryAvailability') + '''
const result=entryAvailability('call');if(!result.enabled||result.mode!=='source'||result.target!=='definition')throw Error('source endpoint ignored through implementation');
if(scope!=='parent')throw Error('source inspection changed caller graph');
''')

    def test_unmapped_call_site_ports_explain_the_source_fallback(self):
        self.run_js('''
const operations=new Map([['call',{id:'call',implementation:'body'}],['body',{id:'body',expansion:{operations:[{}]}}]]);
const model={presentation:{}},sourceIndex={has:()=>true},implementationTarget=id=>operations.get(id)?.implementation||id,businessCalls=()=>[],dispatchFor=()=>null,branchStamp=()=>'';
const boundaryContract=()=>[{unmapped:true,label:'decision',direction:'input'},{unmapped:false,label:'query',direction:'input'}];
let scope='parent',invocationContext=[],history=[],granularity=50,view={};
const entities=new Map(),components=new Map(),resources=new Map(),dependencies=new Map(),updateProfile=()=>{},entryPreviewCache=new Map(),compute=()=>({ops:[{}],decisions:[]});
''' + function('entryPlan') + function('entryAvailabilityCore') + function('entryAvailability') + '''
const result=entryAvailability('call');
if(result.mode!=='source'||result.reasonKind!=='unmappedPorts'||!result.reason.includes('decision'))throw Error('unmapped port reason was hidden');
''')

    def test_reading_can_step_back_to_the_previous_node(self):
        self.run_js('''
let reading={index:2,result:{order:['a','b','c'],inactive:[],blocked:[]}},picked=null;
const decisions=new Map(),select=id=>{picked=id;},focusBounds=()=>{},showGuide=()=>{},paintReading=()=>{},beginReading=()=>{};
''' + function('retreatReading') + '''
const result=retreatReading();
if(result.index!==1||picked!=='a')throw Error('reading did not step back to the previous node');
''')

    def test_source_endpoint_keeps_nested_dispatch_choices_call_specific(self):
        self.run_js('''
const operations=new Map([['inner',{id:'inner'}]]),parents=new Map([['inner','definition']]);
let invocationContext=['outer'],scope='parent',sourceSelection={id:'caller-a',callsite:'caller-a',target:'definition'};
''' + function('implementationKey') + '''
if(implementationKey('inner')!=='outer>caller-a>inner')throw Error('source caller context missing');
sourceSelection={id:'caller-b',callsite:'caller-b',target:'definition'};
if(implementationKey('inner')!=='outer>caller-b>inner')throw Error('nested choices shared across callers');
scope='definition';invocationContext=['outer','caller-b'];
if(implementationKey('inner')!=='outer>caller-b>inner')throw Error('already-entered context duplicated');
''')

    def test_self_redirect_uses_the_child_region_instead_of_the_current_diagram(self):
        self.run_js('''
const operations=new Map([['stage',{id:'stage',businessStep:true,businessEnter:'parent',sourceMembers:['a','b']}],['parent',{id:'parent'}]]);
let scope='parent';const businessCalls=()=>[{id:'a'},{id:'b'}],implementationTarget=id=>id;
''' + function('entryPlan') + '''
const plan=entryPlan('stage');if(plan.target!=='stage'||plan.callsite!=='stage')throw Error('redirected to current diagram');
''')

    def test_unmapped_parent_interface_is_reported_instead_of_silently_dropped(self):
        self.run_js('''
const operations=new Map([['call',{id:'call',inputs:[],outcomes:[],expansion:{operations:[{}]}}]]);
let scope='parent',invocationContext=[],history=[],granularity=0,view={};
const businessCalls=()=>[],implementationTarget=id=>id,entryPreviewCache=new Map(),model={},entities=new Map(),dependencies=new Map(),
 sourceIndex={has:()=>false},boundaryContract=()=>[{unmapped:true}],compute=()=>{throw Error('incomplete interface was projected');};
''' + function('entryPlan') + function('entryAvailabilityCore') + function('entryAvailability') + '''
const result=entryAvailability('call');if(result.enabled||!result.reason||scope!=='parent')throw Error('silently dropped a direct input');
''')


    def test_multiple_calls_enter_the_aggregate_graph_without_a_list_interlude(self):
        self.run_js('''
const operations=new Map([['stage',{id:'stage',businessStep:true,sourceMembers:['a','b'],expansion:{operations:[{},{}]}}]]);
let scope='parent',selected=null,history=[],invocationContext=['caller'],camera={x:1,y:2,z:1};
const entryAvailability=()=>({enabled:true}),businessCalls=()=>[{id:'a'},{id:'b'}],
 checkpointNavigation=()=>{},showPage=()=>{},implementationTarget=id=>id,rebuild=()=>{},fit=()=>{},fitReading=()=>{},showDetails=()=>{},save=()=>{},select=()=>{throw Error('opened inspector instead of graph');},
 view={},entities=new Map(),dependencies=new Map(),boundaryContract=()=>[],model={};
''' + function('entryPlan') + function('enter') + '''
if(!enter('stage')||scope!=='stage'||history.length!==1)throw Error('aggregate was not entered');
if(invocationContext.join(',')!=='caller,stage')throw Error('wrong call path');
''')

    def test_ancestor_return_restores_context_and_cuts_only_descendant_path(self):
        self.run_js('''
let history=[{scope:null,invocationContext:[],camera:{x:1},selected:'root'},
 {scope:'outer',invocationContext:['outer-call'],camera:{x:2},selected:'inner-call'},
 {scope:'inner',invocationContext:['outer-call','inner-call'],camera:{x:3}}];
let scope='leaf',selected='leaf',invocationContext=['outer-call','inner-call','leaf-call'],restored;
const renderSource=()=>{},checkpointNavigation=()=>{},rebuild=()=>{},animateCamera=c=>{restored=c;},fit=()=>{},showDetails=()=>{},save=()=>{};
''' + function('returnTo') + function('navigationPath') + '''
returnTo(1);
if(scope!=='outer'||history.length!==1||selected!=='inner-call')throw Error('wrong ancestor');
if(invocationContext.join(',')!=='outer-call'||restored.x!==2)throw Error('context/camera lost');
if(navigationPath().map(h=>h.scope).join(',')!==',outer')throw Error('tree path differs from history');
returnTo(0);if(scope!==null||history.length||invocationContext.length)throw Error('root return failed');
''')

    def test_independent_entry_does_not_become_a_child_of_the_current_function(self):
        self.run_js('''
let scope='deep',events=[];
const entryAvailability=()=>({enabled:true}),leave=all=>{if(!all)throw Error('not root');scope=null;events.push('root');},enter=id=>{if(scope!==null)throw Error('unrelated caller retained');events.push(id);return true;};
''' + function('enterRoot') + '''
if(!enterRoot('another-entry')||events.join(',')!=='root,another-entry')throw Error('wrong root navigation');
''')


if __name__ == '__main__':
    unittest.main()
