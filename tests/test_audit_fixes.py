"""Behavior regressions for the seven independently reproduced audit findings."""
import copy
import json
from pathlib import Path
import subprocess
import unittest

from test_business_dag import fixture, operation
from test_build_gate import full_review
from test_redesign_contracts import provider_fixture
from test_navigation import function
from business_views import compile_views
from compile_review import prepare
from quality_audit import compile_default_bindings, default_binding_errors


class AuditFixTests(unittest.TestCase):
    def js(self, setup, assertions):
        helpers = function('executionMembers') + function('componentLink') + function('readingPlan') + function('walkExecution')
        result = subprocess.run(['node'], input=setup + helpers + assertions, capture_output=True, text=True, encoding='utf8')
        self.assertEqual(0, result.returncode, result.stderr)

    def base(self, extra):
        return r"""
const scope='service',label=x=>x?.name||x?.id,events=new Map(),decisions=new Map();
const aliases=new Map(),model={presentation:{executionRequirements:[]}};
const request={id:'request',name:'Request',originKind:'parameter'},reply={id:'reply',name:'Reply'};
const branchOptions=d=>[{id:'yes',targets:d.yes,members:d.yes},{id:'no',targets:d.no,members:d.no}],chosenBranch=()=>({id:'yes'});
const edge=(id,from,to,entity,extra={})=>({id,from,to,entity,logicalIds:[id],...extra});
""" + extra

    def test_existing_write_target_is_available_before_the_write(self):
        self.js(self.base(r"""
const db={id:'db',name:'Existing database',originKind:'external-resource'},components=new Map(),resources=new Map([['db',db]]),dependencies=new Map(resources);
const entities=new Map([['request',request],['reply',reply],['db',db]]);
const writer={id:'write',inputs:[{entity:'request',required:true},{entity:'db',required:true,resourceMode:'target'}],outcomes:[{outputs:[{entity:'reply'}]}],accesses:[{resource:'db',mode:'write'}]};
const operations=new Map([['write',writer]]),links=[edge('input','request','write','request'),edge('result','write','reply','reply'),edge('effect','write','db','db',{role:'effect',resourceOperation:true})];
const view={ops:[writer],entities:[request,reply,db],decisions:[],foldedDecisions:[],representatives:new Map(),boundary:new Map([['request','input'],['reply','output'],['db','output']]),logicalLinks:links,executionLinks:links};
"""), r"""
const run=walkExecution();
if(!run.complete||!run.order.includes('write')||!run.order.includes('reply'))throw Error('Existing write target deadlocked its writer');
if(run.order.includes('db')||!run.events.some(e=>e.type==='available'&&e.node==='db'))throw Error('Resource availability became a reading step');
""")

    def test_existing_resource_reference_does_not_recreate_its_carrier(self):
        self.js(self.base(r"""
const file={id:'file',name:'Existing file',originKind:'external-resource'},components=new Map(),resources=new Map([['file',file]]),dependencies=new Map(resources),entities=new Map([['file',file],['reply',reply]]);
const open={id:'open',inputs:[{entity:'file',required:true,resourceMode:'target'}],outcomes:[{outputs:[{entity:'file',role:'reference'}]}]},parse={id:'parse',inputs:[{entity:'file',required:true,resourceMode:'read'}],outcomes:[{outputs:[{entity:'reply'}]}]};
const operations=new Map([['open',open],['parse',parse]]),links=[edge('reference','open','file','file',{role:'reference',resourceOperation:true}),edge('read','file','parse','file',{resourceOperation:true}),edge('result','parse','reply','reply')];
const view={ops:[open,parse],entities:[file,reply],decisions:[],foldedDecisions:[],representatives:new Map(),boundary:new Map([['file','input'],['reply','output']]),logicalLinks:links,executionLinks:links,executionRequirements:[{from:'open',to:'parse',guards:[]}]};
"""),r"""
const result=walkExecution();if(!result.complete||result.order.indexOf('open')>result.order.indexOf('parse')||result.order.includes('file'))throw Error('Pass-through resource reference deadlocked or waived real open-before-parse order');
""")

    def test_inactive_component_result_does_not_block_the_other_branch(self):
        self.js(self.base(r"""
const created={id:'created',name:'Created client',originKind:'local-definition'},fallback={id:'fallback',name:'Fallback result'};
const components=new Map([['created',created]]),resources=new Map(),dependencies=new Map(components),entities=new Map([['request',request],['created',created],['fallback',fallback]]);
const create={id:'create',inputs:[{entity:'request',required:true}],outcomes:[{outputs:[{entity:'created',role:'reference'}]}]},other={id:'other',inputs:[{entity:'request',required:true}],outcomes:[{outputs:[{entity:'fallback'}]}]};
const operations=new Map([['create',create],['other',other]]),gate={id:'@decision:g',kind:'decision',question:'Create client?',inputs:['request'],yes:['create'],no:['other'],sourceDecisions:['g']};decisions.set(gate.id,gate);
const links=[edge('criterion','request',gate.id,'request',{decisionControl:true}),edge('create-in','request','create','request'),edge('create-out','create','created','created',{resourceOperation:true}),edge('other-in','request','other','request'),edge('other-out','other','fallback','fallback')];
const view={ops:[create,other],entities:[request,created,fallback],decisions:[gate],foldedDecisions:[],decisionAliases:new Map([['g',gate.id]]),representatives:new Map(),boundary:new Map([['request','input'],['created','output'],['fallback','output']]),logicalLinks:links,executionLinks:links};
"""), r"""
for(const side of ['yes','no']){const run=walkExecution({g:side});if(!run.complete)throw Error('Inactive constructed component blocked '+side);if(side==='no'&&(!run.inactive.includes('created')||run.order.includes('create')))throw Error('Component did not follow its inactive producer');}
other.inputs.push({entity:'created',required:true});
const blocked=walkExecution({g:'no'});if(blocked.complete||!blocked.blocked.some(x=>x.node==='other'))throw Error('An active consumer ignored a missing constructed component');
""")

    def test_hidden_data_retains_its_producer_prerequisite(self):
        self.js(self.base(r"""
const terms={id:'terms',name:'Prepared data',originKind:'call-result'},components=new Map(),resources=new Map(),dependencies=new Map(),entities=new Map([['request',request],['reply',reply],['terms',terms]]);
const prepare={id:'prepare',inputs:[{entity:'request',required:true}],outcomes:[{outputs:[{entity:'terms'}]}]},execute={id:'execute',inputs:[{entity:'terms',required:true}],outcomes:[{outputs:[{entity:'reply'}]}]};
const operations=new Map([['prepare',prepare],['execute',execute]]),links=[edge('input','request','prepare','request'),edge('output','execute','reply','reply')];
const view={ops:[execute,prepare],entities:[request,reply],decisions:[],foldedDecisions:[],representatives:new Map(),boundary:new Map([['request','input'],['reply','output']]),logicalLinks:links,executionLinks:links};
"""), r"""
const run=walkExecution();if(!run.complete||run.order.indexOf('prepare')>run.order.indexOf('execute'))throw Error('Hidden data waived its actual source dependency');
if(run.order.includes('terms'))throw Error('Hidden detail was exposed as a reading step');
""")

    def test_tiers_filter_concepts_and_keep_processing_fixed(self):
        graph,spec=fixture();view=spec['nodes'][0]['views']['0'];next(c for c in view['concepts'] if c['members']==['terms'])['importance']='auxiliary'
        plans=compile_views(graph,{'service':{'100':view}})['service']
        self.assertTrue(all([s['operation'] for s in plans[str(t)]['steps']]==['prepare','execute'] for t in [0,50,100]))
        self.assertNotIn('terms',{m for c in plans['0']['concepts'] for m in c['members']})
        self.assertNotIn('terms',{m for c in plans['50']['concepts'] for m in c['members']})
        self.assertIn('terms',{m for c in plans['100']['concepts'] for m in c['members']})

    def test_write_target_does_not_become_a_read_wire_in_business_view(self):
        # Exercise the projection with real source ports, not a CSS/markup assertion.
        self.js_business_target()

    def js_business_target(self):
        script=r"""
const scope='service',granularity=100,components=new Map(),resources=new Map([['db',{}]]),dependencies=new Map(resources),businessScopes=new Map(),parents=new Map(),depths=new Map();
const entities=new Map([['request',{id:'request'}],['db',{id:'db'}]]);
const call={id:'write',inputs:[{entity:'request'},{entity:'db',resourceMode:'target'}],outcomes:[],accesses:[{resource:'db'}]};
const root={id:'service',inputs:call.inputs,outcomes:[],internalFlow:{100:{steps:[{operation:'write',label:'Write request',description:'Persist request.'}],concepts:[{members:['request'],label:'Request'},{members:['db'],label:'Database'}]}}};
const operations=new Map([['service',root],['write',call]]),model={operations:[root]},appendEvents=x=>x,decisionSpecs=()=>[],decisionApplies=()=>false;
"""+function('registerProjectedEntity')+function('businessProject')+r"""
const visible=businessProject();if(visible.portVisible(call.inputs[1]))throw Error('Write-only target exposed as a read');if(!visible.portVisible(call.accesses[0]))throw Error('Actual resource effect was hidden');
"""
        run=subprocess.run(['node'],input=script,capture_output=True,text=True,encoding='utf8');self.assertEqual(0,run.returncode,run.stderr)

    def test_alternatives_must_be_compatible_and_owned_by_their_component(self):
        graph,review,binding=provider_fixture();review['businessDAG']['nodes'][2]['scope']='local.run'
        graph['presentation']['dispatch']={'execute':{'contract':{'id':'contract','method':'run'},'candidates':[{'id':'local.run'},{'id':'remote.run'}]}}
        graph['definitions'].append(operation('unrelated.erase',['remote.input'],['remote.output']))
        graph['presentation']['defaultBindings'][0]['alternatives'].append({'component':'alternative','implementation':'unrelated.erase','description':'An unrelated function.','source':binding['provider']['source']})
        self.assertTrue(any('alternative' in e.lower() for e in default_binding_errors(graph,review)))
        graph,review,binding=provider_fixture();graph['definitions'][1]['declaringClass']='ForeignEngine'
        self.assertTrue(any('alternative' in e.lower() for e in default_binding_errors(graph,review)))

    def test_workflow_binding_owner_must_be_reachable_from_that_root(self):
        graph,review,binding=provider_fixture();graph['presentation']['workflows'].append({'id':'other','root':'prepare'})
        review['businessDAG']['roots']['other']='prep';graph['presentation']['defaultBindings'][0]['workflow']='other'
        self.assertTrue(any('workflow' in e.lower() for e in default_binding_errors(graph,review)))

    def test_fifty_only_authoring_uses_the_same_detail_selection_as_compiler(self):
        graph,review,binding=provider_fixture();node=review['businessDAG']['nodes'][0];node['views']['50']=node['views'].pop('0')
        self.assertEqual([],default_binding_errors(graph,review))

    def test_default_binding_shapes_fail_before_dag_mutation(self):
        for field in ['workflow','owner','call','component','implementation']:
            graph,review,binding=provider_fixture();graph['presentation'].pop('defaultBindings');review['defaultBindings'][0][field]=[]
            with self.assertRaisesRegex(ValueError,r'defaultBindings\[0\].'+field):compile_default_bindings(graph,review)
        graph,review,binding=provider_fixture();graph['presentation'].pop('defaultBindings');review['defaultBindings'][0]['call']=[]
        authored=full_review(review['businessDAG']);authored['defaultBindings']=review['defaultBindings']
        with self.assertRaisesRegex(ValueError,r'defaultBindings\[0\].call'):prepare(graph,authored,delivery=False)

    def test_resource_state_still_waits_for_its_actual_writer(self):
        self.js(self.base(r"""
const db={id:'db',originKind:'external-resource'},state={id:'state',stateViewOf:'db',name:'Written state'},components=new Map(),resources=new Map([['db',db],['state',state]]),dependencies=new Map(resources),entities=new Map([['request',request],['reply',reply],['db',db],['state',state]]);
const write={id:'write',inputs:[{entity:'request',required:true},{entity:'db',resourceMode:'target',required:true}],outcomes:[],accesses:[{resource:'state',mode:'write'}]},read={id:'read',inputs:[{entity:'state',required:true,resourceMode:'read'}],outcomes:[{outputs:[{entity:'reply'}]}]};
const operations=new Map([['write',write],['read',read]]),links=[edge('request','request','write','request'),edge('effect','write','state','state',{role:'effect',resourceOperation:true}),edge('read','state','read','state',{resourceOperation:true}),edge('reply','read','reply','reply')];
const view={ops:[read,write],entities:[request,reply,state],decisions:[],foldedDecisions:[],representatives:new Map(),boundary:new Map([['request','input'],['reply','output']]),logicalLinks:links,executionLinks:links};
"""), r"""
const run=walkExecution();if(!run.complete||run.order.indexOf('write')>run.order.indexOf('read'))throw Error('A real resource state was made available before its write');
view.entities=[request,reply];view.executionLinks=view.logicalLinks=[links[0],links[3]];
const hidden=walkExecution();if(!hidden.complete||hidden.order.indexOf('write')>hidden.order.indexOf('read')||hidden.order.includes('state'))throw Error('Hiding the resource state waived its writer prerequisite');
""")

    def test_shared_business_requires_binding_provenance_for_each_workflow(self):
        graph,review,binding=provider_fixture();graph['presentation']['workflows'].append({'id':'second','root':'service'});review['businessDAG']['roots']['second']='entry'
        self.assertTrue(any('second/entry/execute' in e for e in default_binding_errors(graph,review)))
        other=copy.deepcopy(graph['presentation']['defaultBindings'][0]);other['workflow']='second';graph['presentation']['defaultBindings'].append(other)
        self.assertEqual([],default_binding_errors(graph,review))

    def test_registered_workflow_root_keeps_its_own_binding_context(self):
        graph,review,binding=provider_fixture()
        graph['presentation']['workflows'].append({'id':'other','root':'prepare'})
        review['businessDAG']['roots']['other']='prep'
        review['businessDAG']['nodes'][1]['exposes']=[{'node':'entry'}]
        self.assertEqual([],default_binding_errors(graph,review))

    def test_inherited_and_callable_alternative_proofs_are_checked(self):
        graph,review,binding=provider_fixture();alternative=graph['presentation']['defaultBindings'][0]['alternatives'][0]
        graph['definitions'][1]['declaringClass']='BaseEngine'
        alternative['provider']={'kind':'class','member':'run','source':alternative['source'],'receiverClass':'RemoteEngine','definedOn':'BaseEngine','inheritanceEvidence':[alternative['source']]}
        self.assertEqual([],default_binding_errors(graph,review))
        alternative['provider']['inheritanceEvidence']=[]
        self.assertTrue(any('alternative' in e for e in default_binding_errors(graph,review)))
        graph['components'][1]['callable']='remote.run';alternative['provider']={'kind':'callable','member':'run','source':alternative['source'],'callable':'remote.run'}
        self.assertEqual([],default_binding_errors(graph,review))
        alternative['provider']['kind']='unknown'
        self.assertTrue(any('alternative' in e for e in default_binding_errors(graph,review)))

    def test_decision_criteria_and_fixed_providers_stay_visible_in_core(self):
        graph,spec=fixture();view=spec['nodes'][0]['views']['0']
        for c in view['concepts']:
            if c['members'] in (['terms'],['engine']):c['importance']='auxiliary'
        graph['presentation']['decisions']=[{'id':'guard','owner':'service','question':'Continue?','condition':'terms exist','inputs':['terms'],'yes':['execute'],'no':['execute'],'merge':'execute','evidence':['example']}]
        graph['presentation']['defaultBindings']=[{'call':'execute','component':'engine'}]
        plans=compile_views(graph,{'service':{'100':view}})['service']
        self.assertTrue({'terms','engine'}<={m for c in plans['0']['concepts'] for m in c['members']})

    def test_entry_expectations_distinguish_hidden_detail_from_missing_resource(self):
        from quality_audit import entry_manifest
        plans={str(t):{'steps':[],'concepts':([{'members':['db']}] if t==100 else [])} for t in [0,50,100]}
        graph={'presentation':{'businessDAG':{'roots':{'main':'root'},'nodes':[{'id':'root','views':plans}]},'semanticExpectations':{'root':{'resources':['db','missing'],'components':[]}}}}
        expected=[s['expected']['resources'] for s in entry_manifest(graph)['scopes']]
        self.assertEqual([['missing'],['missing'],['db','missing']],expected)
        factory=(Path(__file__).resolve().parents[1]/'skills/litflux/assets/entry-audit.js').read_text(encoding='utf8')
        script='const create='+factory+';const model='+json.dumps(graph)+';const expected='+json.dumps(expected)+r""";
const got=create({dag:model.presentation.businessDAG,expectations:model.presentation.semanticExpectations}).listEntries().scopes.map(s=>s.expected.resources);
if(JSON.stringify(got)!==JSON.stringify(expected))throw Error(JSON.stringify(got));
"""
        run=subprocess.run(['node'],input=script,capture_output=True,text=True,encoding='utf8');self.assertEqual(0,run.returncode,run.stderr)

if __name__=='__main__': unittest.main()
