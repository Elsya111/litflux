"""Fixed providers, persistent branches and availability/reading boundaries."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'skills/litflux/scripts')]
from quality_audit import compile_default_bindings, default_binding_errors, decision_branch_errors, compile_overview
from validate_graph import validate
from test_business_dag import fixture, operation
from test_navigation import function


def provider_fixture():
    graph, spec = fixture()
    graph['components'].append({**graph['components'][0], 'id':'alternative', 'name':'Remote engine'})
    graph['definitions'] = [operation('local.run',['terms'],['reply']), operation('remote.run',['terms'],['reply'])]
    graph['components'][0]['componentClass']='LocalEngine'
    graph['components'][1]['componentClass']='RemoteEngine'
    graph['definitions'][0]['declaringClass']='LocalEngine'
    graph['definitions'][1]['declaringClass']='RemoteEngine'
    graph['entities'] += [{**graph['entities'][0], 'id':v, 'name':v, 'scope':'project'} for v in ('local.input','local.output','remote.input','remote.output')]
    graph['definitions'][0]['inputs'][0]['entity']='local.input';graph['definitions'][0]['outcomes'][0]['outputs'][0]['entity']='local.output'
    graph['definitions'][1]['inputs'][0]['entity']='remote.input';graph['definitions'][1]['outcomes'][0]['outputs'][0]['entity']='remote.output'
    graph['definitions'][1]['inputs'].append({'port':'receiver','entity':'alternative','role':'capture','required':True})
    call=graph['operations'][0]['expansion']['operations'][1]
    call['inputs'][1]['relation']='invocation';call['methodCall']={'receivers':['engine'],'method':'run'}
    source={'path':'app.py','startLine':1,'endLine':1}
    binding={'workflow':'main','owner':'entry','call':'execute','component':'engine','implementation':'local.run',
        'selection':'project-default','reason':'The effective fixture config selects the local engine.',
        'configuration':{'state':'unique','evidence':[source]},'evidence':[source],
        'provider':{'kind':'instance','member':'run','source':source},
        'alternatives':[{'component':'alternative','implementation':'remote.run','description':'A concrete remote provider.','source':source}]}
    review={'businessDAG':spec,'defaultBindings':[binding]}
    compile_default_bindings(graph,review)
    return graph,review,binding


class RedesignContractTests(unittest.TestCase):
    def run_js(self,script):
        run=subprocess.run(['node','-e',script],capture_output=True,text=True)
        self.assertEqual(0,run.returncode,run.stderr)

    def test_unique_default_needs_direct_concrete_provider(self):
        graph,review,binding=provider_fixture()
        self.assertEqual([],default_binding_errors(graph,review))
        graph['operations'][0]['expansion']['operations'][1]['inputs'][1]['relation']='dependency'
        graph['operations'][0]['expansion']['operations'][1]['methodCall']['receivers']=[]
        self.assertTrue(any('directly provide' in e for e in default_binding_errors(graph,review)))

    def test_explicit_method_receiver_is_direct_provider(self):
        graph,review,binding=provider_fixture()
        call=graph['operations'][0]['expansion']['operations'][1]
        call['inputs'][1]['relation']='dependency';call['methodCall']={'receivers':['engine'],'method':'run'}
        self.assertEqual([],default_binding_errors(graph,review))

    def test_parallel_defaults_require_actual_user_answer(self):
        graph,review,binding=provider_fixture()
        compiled=graph['presentation']['defaultBindings'][0]
        compiled['configuration']['state']='multiple';compiled['selection']='user-selected';compiled['clarification']='config'
        self.assertTrue(default_binding_errors(graph,review))
        review['clarifications']=[{'id':'config','status':'answered','answer':'Use local','confirmedByUser':True}]
        self.assertEqual([],default_binding_errors(graph,review))
        review['clarifications'][0]['confirmedByUser']=False
        self.assertTrue(default_binding_errors(graph,review))

    def test_absent_config_is_labelled_analysis_and_can_be_callable(self):
        graph,review,binding=provider_fixture();compiled=graph['presentation']['defaultBindings'][0]
        compiled['configuration']={'state':'absent','evidence':[]};compiled['selection']='analysis';compiled['provider']['kind']='callable';compiled['provider']['callable']='local.run';graph['components'][0]['callable']='local.run'
        self.assertEqual([],default_binding_errors(graph,review))
        compiled['selection']='project-default'
        self.assertTrue(any('contradicts' in e for e in default_binding_errors(graph,review)))

    def test_default_binding_identity_includes_owner_and_workflow(self):
        graph,review,binding=provider_fixture();records=graph['presentation']['defaultBindings']
        records.append(copy.deepcopy(records[0]))
        self.assertTrue(any('duplicate' in e for e in default_binding_errors(graph,review)))

    def test_bound_choice_cannot_disagree_with_reviewed_business(self):
        graph,review,binding=provider_fixture();review['businessDAG']['nodes'][0]['implementationChoices']={'execute':'remote.run'}
        self.assertTrue(any('conflicts' in e for e in default_binding_errors(graph,review)))

    def test_component_cannot_provide_another_class_method(self):
        graph,review,binding=provider_fixture();graph['presentation']['defaultBindings'][0]['implementation']='remote.run'
        self.assertTrue(any('component class' in e for e in default_binding_errors(graph,review)))

    def test_inherited_method_keeps_receiver_and_definition_evidence(self):
        graph,review,binding=provider_fixture();graph['definitions'][0]['declaringClass']='BaseEngine'
        provider=graph['presentation']['defaultBindings'][0]['provider']
        provider.update({'receiverClass':'LocalEngine','definedOn':'BaseEngine','inheritanceEvidence':[provider['source']]})
        self.assertEqual([],default_binding_errors(graph,review))
        provider['inheritanceEvidence']=[]
        self.assertTrue(default_binding_errors(graph,review))

    def test_mislocated_definition_source_is_rejected(self):
        graph,review,binding=provider_fixture();graph['presentation']['defaultBindings'][0]['provider']['source']={'path':'elsewhere.py','startLine':1,'endLine':1}
        self.assertTrue(any('provider.source' in e for e in default_binding_errors(graph,review)))

    def test_fixed_default_cannot_jump_via_the_call_identity(self):
        from business_dag import compile_dag
        graph,review,binding=provider_fixture();spec=review['businessDAG']
        spec['nodes'][0]['implementationChoices']={'execute':'local.run'}
        with self.assertRaisesRegex(ValueError, 'fixed default implementation scope'):
            compile_dag(graph,spec)
        graph['operations'][0]['expansion']['operations'][1]['implementation']='remote.run'
        self.assertTrue(any('actual concrete call' in e for e in default_binding_errors(graph,review)))

    def test_fixed_callable_default_survives_complete_prepare(self):
        from test_build_gate import full_review
        from compile_review import prepare
        graph,minimal,binding=provider_fixture();spec=minimal['businessDAG']
        spec['nodes'][2]['scope']='local.run'
        review=full_review(spec);review['defaultBindings']=[binding]
        compiled=prepare(graph,review,delivery=False)
        entry=next(n for n in compiled['graph']['presentation']['businessDAG']['nodes'] if n['id']=='entry')
        self.assertEqual('local.run',entry['implementationChoices']['execute'])
        self.assertEqual([],compiled['semanticAudit']['defaultBindings']['errors'])

    def test_three_branch_shared_nodes_stay_outside_all_frames(self):
        dagre=str(Path(__file__).resolve().parents[1]/'skills/litflux/assets/dagre-1.1.5.min.js')
        setup="const dagre=require("+json.dumps(dagre)+");const viewport={clientWidth:1440,clientHeight:800},density=35,dependencies=new Map();"
        self.run_js(setup+function('bounds')+function('compactLayout')+function('branchLayout')+"""
const nodes=new Map([['gate',{w:200,h:80,kind:'decision'}],['shared',{w:100,h:60,kind:'operation'}],...['a','b','c'].map(id=>[id,{w:220,h:60,kind:'branchFrame'}])]);
const branchFrames=['a','b','c'].map(id=>({id,decision:'gate',side:id,members:['shared']}));
const visible={branchFrames,branchRegions:branchFrames,decisions:[],decisionAliases:new Map()};
const groups=branchLayout(nodes,branchFrames.map(f=>({from:'gate',to:f.id,decisionControl:true})),visible);
if([...groups.values()].some(f=>f.members.has('shared')))throw Error('Shared node remained in one of three branches');
""")

    def test_same_class_different_method_is_not_the_invoked_provider(self):
        graph,review,binding=provider_fixture();definition=graph['definitions'][0]
        definition['definition']='LocalEngine.other';graph['presentation']['defaultBindings'][0]['provider']['member']='other'
        self.assertTrue(any('actual invoked method' in e for e in default_binding_errors(graph,review)))

    def test_selected_implementation_must_belong_to_declared_callable_set(self):
        graph,review,binding=provider_fixture()
        review['semanticInventory']={'entry':{'implementationSets':[{'call':'execute','candidates':['remote.run']}]}}
        self.assertTrue(any('not in the declared compatible set' in e for e in default_binding_errors(graph,review)))

    def test_malformed_implementation_sets_report_fields_without_type_errors(self):
        for value in (None, 'candidate', {}, [{'call':'execute','candidates':None}], [{'call':[],'candidates':[]}], [{'call':'execute','candidates':[{}]}]):
            graph,review,binding=provider_fixture()
            review['semanticInventory']={'entry':{'implementationSets':value}}
            self.assertTrue(any('implementationSets' in e for e in default_binding_errors(graph,review)))

    def test_terminal_branch_needs_evidence_but_not_fake_business(self):
        graph,_=fixture();decision={'id':'choice','yes':['prepare'],'no':[]}
        graph['presentation']['decisions']=[decision]
        self.assertIn('missing real branch target',decision_branch_errors(graph)[0])
        decision['terminals']={'no':{'kind':'return','description':'Return an empty answer.','source':{'path':'app.py','startLine':1,'endLine':1},'evidence':['example']}}
        self.assertEqual([],decision_branch_errors(graph))
        decision['terminals']['no']['evidence']=[]
        self.assertTrue(decision_branch_errors(graph))

    def test_default_lookup_ignores_mutable_browser_choice(self):
        self.run_js("""
const workflowId='main',scope='root',operations=new Map([['root',{businessId:'entry'}],['call',{sourceIdentity:'execute'}]]),implementationChoices=new Map([['execute','remote.run']]);
const model={presentation:{defaultBindings:[{workflow:'main',owner:'other',call:'execute',implementation:'remote.run'},{workflow:'main',owner:'entry',call:'execute',implementation:'local.run'}]}};
"""+function('defaultBinding')+"""
if(defaultBinding('call').implementation!=='local.run')throw Error('User exploration overrode canonical owner binding');
""")

    def test_decision_scheduler_and_resource_availability_are_separate(self):
        self.run_js("""
const componentLink=l=>!!l.capabilityProvider,decisions=new Map([['gate',{branches:[{id:'yes',targets:['work'],members:['work']},{id:'no',targets:[],members:[]}]}]]);
const branchOptions=d=>d.branches,chosenBranch=()=>({id:'yes'});
const node=(id,kind,prerequisites=[],extra={})=>({id,kind,prerequisites,guards:[],sourceDecisions:[],...extra});
const requirement=from=>({alternatives:[{from}]});
const plan={nodes:[node('config','resource',[],{provided:true}),node('component','component',[],{provided:true}),node('gate','decision',[requirement('config')]),node('work','operation',[requirement('component')],{guards:[{decision:'gate',side:'yes'}]})],links:[{id:'criterion',from:'config',to:'gate',decisionControl:true},{id:'branch',from:'gate',to:'work',decisionControl:true,guard:{decision:'gate',side:'yes'}}],requirements:[],foldedDecisions:[],scope:'project'};
const readingPlan=()=>plan;
"""+function('walkExecution')+"""
const run=walkExecution();
if(JSON.stringify(run.order)!==JSON.stringify(['gate','work']))throw Error('Special control schedule lost or availability counted as execution');
if(run.events.filter(e=>e.type==='available').length!==2||!run.complete)throw Error('Availability facts not recorded');
plan.nodes[1].provided=false;plan.nodes[1].prerequisites=[requirement('missing')];
if(walkExecution().order.includes('work'))throw Error('Invisible provider dependency was waived');
""")

    def test_guide_editorial_fields_are_compiled_once(self):
        graph,_=fixture();source={'path':'app.py','startLine':1,'endLine':1}
        record={'title':'A specific mechanism','description':'What the source does.','why':'How it changes results.','scenario':'The actual default workflow.','source':source,'definition':'service'}
        review={'summary':{},'guide':{'runtimeStory':'Read the request, prepare it and answer.','mechanisms':[record],'focus':[]}}
        guide=compile_overview(graph,review)
        self.assertEqual([record],guide['mechanisms']);self.assertEqual([],guide['focus'])
        self.assertIsNot(guide['mechanisms'],review['guide']['mechanisms'])

if __name__=='__main__': unittest.main()
