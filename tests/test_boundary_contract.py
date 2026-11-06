"""Actual/formal interface alignment, independent of project terminology."""
from pathlib import Path
import subprocess,unittest
LIB=(Path(__file__).resolve().parents[1]/'skills/litflux/assets/boundary-contract.js').read_text(encoding='utf8')
class BoundaryContractTests(unittest.TestCase):
 def js(self,body):
  result=subprocess.run(['node','-e','const contract='+LIB+';'+body],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
 def test_actual_arguments_returns_resources_and_components_keep_parent_identity(self):
  self.js('''
const value=(id,name)=>({id,name,description:'Role of '+name});
const entities=new Map(['query','client','store','answer'].map(id=>[id,value(id,id)])),dependencies=new Map([['client',entities.get('client')],['store',entities.get('store')]]);
const call={id:'invoke',inputs:[{entity:'query',argument:'request'},{entity:'client',argument:'self'}],outcomes:[{id:'return',outputs:[{entity:'answer'}]}]},
 body={inputs:[{entity:'formal.request',port:'request'},{entity:'formal.self',port:'self'}],outcomes:[{id:'return',outputs:[{entity:'formal.answer'}]}],accesses:[{resource:'store'}]},
 parent={entities:[...entities.values()],representatives:new Map(),logicalLinks:[{from:'query',to:'invoke',direction:'input'},{from:'client',to:'invoke',direction:'input'},{from:'invoke',to:'answer',direction:'output'},{from:'invoke',to:'store',direction:'output'}]};
const ports=contract(call,body,parent,entities,dependencies);
if(ports.length!==4)throw Error(JSON.stringify(ports));
for(const [outer,inner]of [['query','formal.request'],['client','formal.self'],['answer','formal.answer'],['store','store']])if(!ports.some(p=>p.actual.includes(outer)&&p.inner.includes(inner)))throw Error('lost '+outer);
''')
 def test_shared_method_names_never_bind_another_receivers_argument(self):
  self.js('''
const call={id:'search',inputs:[{entity:'outer',argument:'request'}],outcomes:[]},body={inputs:[{entity:'formal',port:'unrelated'}],outcomes:[]},entities=new Map([['outer',{id:'outer',name:'query'}]]),view={entities:[...entities.values()],representatives:new Map(),logicalLinks:[{from:'outer',to:'search',direction:'input'}]};
const ports=contract(call,body,view,entities,new Map());if(ports.length!==1||!ports[0].unmapped||ports[0].inner.length)throw Error('guessed by method/label or silently lost the input');
''')
 def test_source_positional_arguments_map_to_formal_parameters(self):
  self.js('''
const call={id:'c',inputs:[{entity:'request',argument:'arg0',role:'argument'}],outcomes:[]},body={id:'f',inputs:[{entity:'formal.request',port:'service_input',role:'argument'}],outcomes:[]},entities=new Map([['request',{id:'request',name:'Request'}]]),view={entities:[...entities.values()],representatives:new Map(),logicalLinks:[{from:'request',to:'c',direction:'input'}]};
const ports=contract(call,body,view,entities,new Map());if(ports[0].unmapped||ports[0].inner[0]!=='formal.request')throw Error('positional binding lost');
''')
 def test_one_conditional_return_maps_to_its_one_call_result_without_merging_inputs(self):
  self.js('''
const call={id:'c',inputs:[],outcomes:[{id:'return',outputs:[{entity:'result'}]}]},body={inputs:[],outcomes:[{id:'yes',outputs:[{entity:'yesValue'}]},{id:'no',outputs:[{entity:'noValue'}]}]},entities=new Map([['result',{id:'result',name:'Result'}]]),view={entities:[...entities.values()],representatives:new Map(),logicalLinks:[{from:'c',to:'result',direction:'output'}]};
const ports=contract(call,body,view,entities,new Map());if(ports.length!==1||ports[0].inner.length!==2)throw Error('conditional return lost');
''')
 def test_entering_another_layer_preserves_inherited_output_and_effect_identity(self):
  self.js('''
const source={id:'boundary',name:'Published version',contractMembers:['version'],interfaceEffects:[{outer:'version',inner:'repository',operation:'publish',direction:'output'}]},entities=new Map([['boundary',source]]),
 call={id:'stage',inputs:[],outcomes:[{id:'return',outputs:[]}],accesses:[{resource:'repository'}]},body={...call,id:'inner',expansion:{operations:[{id:'cloned',sourceIdentity:'publish'}]}},
 view={entities:[source],representatives:new Map(),logicalLinks:[{from:'stage',to:'boundary',entity:'boundary',sourceEntity:'repository',direction:'output'}]};
const ports=contract(call,body,view,entities,new Map());if(ports.length!==1||!ports[0].actual.includes('boundary')||!ports[0].actual.includes('version')||ports[0].effects.length!==1)throw Error('lost recursive contract');
''')
 def test_delegated_resource_effect_rebases_to_the_next_real_call(self):
  self.js('''
const source={id:'boundary',name:'Database',contractMembers:['db'],interfaceEffects:[{outer:'db',inner:'session',operation:'delegate',via:['delegate','writer'],direction:'output'}]},entities=new Map([['boundary',source]]),
 call={id:'delegate',inputs:[],outcomes:[]},body={id:'worker',inputs:[],outcomes:[],expansion:{operations:[{id:'writer'}]}},
 view={entities:[source],representatives:new Map(),logicalLinks:[{from:'delegate',to:'boundary',sourceEntity:'session',direction:'output'}]};
const ports=contract(call,body,view,entities,new Map());if(ports[0].effects[0].operation!=='writer'||ports[0].unmapped)throw Error('delegated effect was lost');
''')
if __name__=='__main__':unittest.main()
