"""Projected boundary roles survive recursive context and resource reuse."""
from pathlib import Path
import subprocess,unittest
TEMPLATE=(Path(__file__).resolve().parents[1]/'skills/litflux/assets/viewer.html').read_text(encoding='utf8')
start=TEMPLATE.index('  function alignBoundary(')
helper=TEMPLATE.index('  function registerProjectedEntity(')
FUNCTION=TEMPLATE[helper:TEMPLATE.index('\n  function ',helper+3)]+TEMPLATE[start:TEMPLATE.index('\n  function ',start+3)]
class BoundaryProjectionTests(unittest.TestCase):
 def js(self,setup,assertions):
  script=setup+'\n'+FUNCTION+'\n'+assertions
  result=subprocess.run(['node','-e',script],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
 def test_budget_projection_preserves_a_valid_unpacked_return(self):
  start=TEMPLATE.index('  function budgetView(')
  function=TEMPLATE[start:TEMPLATE.index('\n  function ',start+3)]
  setup='''
const result={id:'price',name:'Quoted price'},op={id:'quote',inputs:[],outcomes:[{outputs:[{entity:'price'}]}]};
const scope=null,model={operations:[op]},dependencies=new Map(),profile={nodeBudget:30};
const selectedSourceBranch=v=>v,splitBoundaryOutputs=v=>v,sharedReturnView=v=>v,compactCore=v=>v;
const decisionSpecs=()=>[],decisionApplies=()=>true,label=e=>e.name,identity=id=>id;
const view={ops:[op],entities:[result],boundary:new Map([['price','output']]),portVisible:()=>true};
'''
  result=subprocess.run(['node','-e',setup+function+'''
const projected=budgetView(view,'project');
if(projected.ops[0]!==op||projected.entities[0]!==result)throw Error('valid return changed during budget projection');
'''],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
 def terminal_case(self,reuse,assertions):
  self.js('''
const result={id:'result',name:'Quoted price'},entities=new Map([['result',result]]),components=new Map(),resources=new Map(),dependencies=new Map(),scope='child',executionMembers=o=>[o.id];
const history=[{childContract:[{direction:'output',label:'Quoted price',description:'Returned to the caller',value:result,inner:['result'],actual:['caller.result']}]}];
const compute={id:'compute',inputs:[],outcomes:[{outputs:[{entity:'result'}]}]};
const view={ops:[compute],entities:[result],boundary:new Map([['result','output']]),portVisible:()=>true};
'''+('view.ops.push({id:"consume",inputs:[{entity:"result"}],outcomes:[]});'if reuse else ''),assertions)
 def test_raw_return_is_replaced_by_one_aligned_terminal(self):
  self.terminal_case(False,'''
const projected=alignBoundary(view);
if(projected.entities.length!==1||projected.entities[0].id==='result')throw Error('duplicate raw and aligned return');
if(projected.boundary.get(projected.entities[0].id)!=='output')throw Error('return role missing');
''')
 def test_internally_reused_return_keeps_only_boundary_copy_terminal(self):
  self.terminal_case(True,'''
const projected=alignBoundary(view);
if(projected.entities.length!==2)throw Error('internal reuse was lost');
if(projected.boundary.has('result'))throw Error('internal value incorrectly remains a terminal');
if(projected.entities.filter(e=>projected.boundary.get(e.id)==='output').length!==1)throw Error('multiple terminal views');
''')
 def test_component_context_stays_external_when_other_inputs_are_aligned(self):
  self.js('''
const entities=new Map([['component',{id:'component',name:'Index service'}],['request',{id:'request',name:'Request'}]]),components=new Map([['component',entities.get('component')]]),resources=new Map(),dependencies=new Map(components),scope='child',executionMembers=o=>[o.id];
const history=[{childContract:[{direction:'input',label:'Index service',description:'Receives the method call',value:entities.get('component'),inner:[],actual:['parent.component'],context:true},{direction:'input',label:'Request',value:entities.get('request'),inner:['request'],actual:['parent.request']}]}];
const view={ops:[{id:'process',inputs:[{entity:'request'}],outcomes:[]}],entities:[entities.get('request')],boundary:new Map(),portVisible:()=>true};
''','''
const projected=alignBoundary(view),component=projected.entities.find(e=>components.has(e.id));
if(projected.boundary.get(component.id)!=='input')throw Error('context lost external-input role');
if(!projected.interfaceLinks.some(l=>l.from===component.id&&l.to==='process'&&l.componentOperation))throw Error('context has no real scope dependency');
''')
 def test_read_and_write_of_same_resource_share_external_before_state(self):
  self.js('''
const store={id:'store',name:'Repository'},entities=new Map([['store',store]]),components=new Map(),resources=new Map([['store',store]]),dependencies=new Map(resources),scope='child',executionMembers=o=>[o.id];
const history=[{childContract:['input','output'].map(direction=>({direction,label:'Repository',value:store,inner:['store'],actual:[direction+'.store']}))}];
const view={ops:[{id:'update',inputs:[{entity:'store'}],outcomes:[],accesses:[{resource:'store'}]}],entities:[store],boundary:new Map(),portVisible:()=>true};
''','''
const projected=alignBoundary(view);if(projected.entities.length!==1)throw Error('duplicate before-state resources');
const e=projected.entities[0];if(projected.boundary.get(e.id)!=='both')throw Error('read changed to output-only');
if(!e.contractMembers.includes('input.store')||!e.contractMembers.includes('output.store'))throw Error('parent identity lost');
''')
if __name__=='__main__':unittest.main()
