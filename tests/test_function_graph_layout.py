"""Function decomposition graph layout: layered seed plus deterministic network spread."""
import subprocess
import unittest
from pathlib import Path

LAYOUT = (Path(__file__).resolve().parents[1] / 'skills/litflux/assets/function-graph-layout.js').read_text(encoding='utf8')


class FunctionGraphLayoutTests(unittest.TestCase):
    def run_js(self, assertions):
        result = subprocess.run(['node', '-e', LAYOUT + '\n' + assertions], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_chain_is_finite_non_overlapping_and_deterministic(self):
        self.run_js('''
const nodes=[],edges=[];
for(let i=0;i<60;i++)nodes.push({id:'n'+i,x:i*180,y:(i%2)*20,width:230,height:66});
for(let i=1;i<60;i++)edges.push({from:'n'+(i-1),to:'n'+i});
const first=LitFluxFunctionLayout.spread(nodes,edges),second=LitFluxFunctionLayout.spread(nodes,edges);
if(first.positions.size!==60||!Number.isFinite(first.width)||!Number.isFinite(first.height))throw Error('invalid layout');
if(JSON.stringify([...first.positions])!==JSON.stringify([...second.positions]))throw Error('layout is not deterministic');
const values=[...first.positions.values()];
for(let i=0;i<values.length;i++)for(let j=i+1;j<values.length;j++){
  const a=values[i],b=values[j];
  if(Math.abs(a.x-b.x)<(a.w+b.w)/2&&Math.abs(a.y-b.y)<(a.h+b.h)/2)throw Error('overlap '+a.id+'/'+b.id);
}
''')

    def test_shared_and_remote_edges_are_marked(self):
        self.run_js('''
const nodes=[{id:'a',x:0,y:0,width:230,height:66},{id:'b',x:0,y:100,width:230,height:66},{id:'c',x:200,y:50,width:230,height:66}];
const edges=[{from:'a',to:'b'},{from:'b',to:'c'},{from:'a',to:'c'}];
const result=LitFluxFunctionLayout.spread(nodes,edges);
if(!result.shared.includes('c'))throw Error('shared node not marked');
if(!result.remote.includes('a|c'))throw Error('remote edge not marked');
''')

    def test_empty_graph_returns_finite_bounds(self):
        self.run_js('''
const result=LitFluxFunctionLayout.spread([],[]);
if(result.positions.size!==0||!Number.isFinite(result.width)||!Number.isFinite(result.height))throw Error('invalid empty layout');
''')

    def test_large_graph_uses_the_bounded_path(self):
        self.run_js('''
const nodes=[],edges=[];
for(let i=0;i<320;i++)nodes.push({id:'n'+i,x:i*180,y:0,width:230,height:66});
for(let i=1;i<320;i++)edges.push({from:'n'+(i-1),to:'n'+i});
const result=LitFluxFunctionLayout.spread(nodes,edges);
if(result.positions.size!==320)throw Error('large graph lost nodes');
for(const value of result.positions.values())if(!Number.isFinite(value.x)||!Number.isFinite(value.y))throw Error('non-finite position');
''')


if __name__ == '__main__':
    unittest.main()
