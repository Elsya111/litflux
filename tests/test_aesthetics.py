"""Naming, counting, branch emphasis and relation presentation contracts."""
import json
import re
import unittest
import subprocess
import itertools
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'litflux'


class AestheticContractTests(unittest.TestCase):
    def setUp(self):
        self.template = (SKILL / 'assets' / 'viewer.html').read_text(encoding='utf-8')
        self.css = (SKILL / 'assets' / 'interface.css').read_text(encoding='utf-8')
        self.design = (SKILL / 'references' / 'design.md').read_text(encoding='utf-8')
        self.messages = json.loads((SKILL / 'assets' / 'messages.en.json').read_text(encoding='utf-8'))

    def test_overall_artifact_is_the_project_atlas(self):
        self.assertIn('项目脉络图', self.template)
        self.assertNotIn('>流程地图<', self.template)
        self.assertEqual('Project Atlas', self.messages['项目脉络图'])
        self.assertIn('项目脉络图', self.design)

    def test_declaration_counts_and_no_numeric_duplicate_suffix(self):
        self.assertIn("DETAIL_NODE_BUDGET=30", self.template)
        self.assertIn("DETAIL_DECISION_BUDGET=5", self.template)
        self.assertIn("decisionSpecs().filter(decisionApplies).length", self.template)
        self.assertIn("声明 '+budget.authoredNodes", self.template)
        self.assertIn('边界副本', self.template)
        self.assertNotIn("same.indexOf(e.id)+1", self.template)
        self.assertNotIn("'作者 '", self.template)
        self.assertNotIn('visible.ops.length+visible.entities.length>profile.nodeBudget', self.template)
        self.assertIn('resetReadingState', self.template)
        self.assertIn("has('reset')", self.template)
        self.assertIn('clearReadingStorage', self.template)
        self.assertIn("key!=='litflux:interface'", self.template)
        self.assertIn('visits.reset()', self.template)
        self.assertIn('Declared ', self.template)

    def test_decisions_use_branch_emphasis_and_provider_relations_are_distinct(self):
        self.assertNotIn('sf-decision-frame', self.template)
        self.assertNotIn('sf-decision-frame', self.css)
        self.assertIn('decisionLabelLayout', self.template)
        self.assertIn('sf-provider-core', self.template)
        self.assertIn('sf-provider-marker', self.template)
        self.assertIn('sf-branch-inactive', self.template)

    def test_design_spec_covers_hierarchy_type_naming_and_acceptance(self):
        for phrase in ('层次顺序', '字体与文字', '几何与间距', '判断与分支选择', '命名与字段规范',
                       '动效与可访问性', '验收清单', '结果1'):
            self.assertIn(phrase, self.design)

    def test_reference_book_preserves_the_declared_scene_relations(self):
        scenes = json.loads((SKILL / 'examples/reference-scenes.json').read_text(encoding='utf-8'))['scenes']
        book = (SKILL / 'examples/visual-reference.html').read_text(encoding='utf-8')
        embedded = re.search(r'<script type="application/json" id="scene-data">(.*?)</script>', book, re.S)
        self.assertIsNotNone(embedded)
        self.assertEqual(scenes, json.loads(embedded.group(1)))
        self.assertTrue({'project-guide', 'shared-dag', 'source-endpoint', 'nested-branches'} <= {s['id'] for s in scenes})
        for scene in scenes:
            identities = {node['id'] for node in scene['nodes']}
            self.assertEqual(len(scene['nodes']), len(identities))
            for edge in scene['edges']:
                self.assertTrue({edge['from'], edge['to']} <= identities)
                if edge['kind'] in ('feedback', 'resource'):
                    self.assertTrue(edge['label'])

    def test_viewer_has_no_legacy_view_or_dictionary_fallbacks(self):
        for legacy in ('scopeSummaries', 'presentation?.granularity', 'sf-locales',
                       '__LITFLUX_LOCALES__', 'superflow:', 'refitMigration'):
            self.assertNotIn(legacy, self.template)

    def test_control_reference_scenes_have_ordinary_end_to_end_paths_in_every_choice(self):
        scenes=json.loads((SKILL/'examples/reference-scenes.json').read_text(encoding='utf8'))['scenes']
        script=(SKILL/'examples/visual-reference.html').read_text(encoding='utf8')
        projection='function referenceProjection'+script.split('function referenceProjection',1)[1].split('\nfunction el',1)[0]
        for scene in scenes:
            if scene.get('mode') in ('dag','overview','source'):continue
            controls=scene.get('selections',[])
            choices=[dict(zip([c['decision'] for c in controls],values)) for values in itertools.product(*[[o['id'] for o in c['options']] for c in controls])]
            code=projection+'\nconst s='+json.dumps(scene)+';const all='+json.dumps(choices)+r''';
for(const choice of all){
 const state=referenceProjection(s,choice),ordinary=state.edges.filter(e=>['data','resource'].includes(e.kind));
 const nodes=new Map(s.nodes.map(n=>[n.id,n])),frames=new Set((s.frames||[]).map(f=>f.id));
 if(ordinary.length!==s.edges.filter(e=>['data','resource'].includes(e.kind)).length)throw Error('A branch removed real port edges');
 if(ordinary.some(e=>frames.has(e.from)||frames.has(e.to)))throw Error('A frame became a data port');
 const solid=ordinary.filter(e=>!e.deferred),incoming=new Map(),next=new Map();
 for(const e of solid){if(incoming.has(e.to))throw Error('Multiple ordinary solid predecessors');incoming.set(e.to,e);if(!next.has(e.from))next.set(e.from,[]);next.get(e.from).push(e.to);}
 const visiting=new Set(),done=new Set();function visit(id){if(visiting.has(id))throw Error('Ordinary solid cycle');if(done.has(id))return;visiting.add(id);for(const child of next.get(id)||[])visit(child);visiting.delete(id);done.add(id);}for(const id of nodes.keys())visit(id);
 const active=ordinary.filter(e=>!e.inactive);
 for(const n of s.nodes.filter(n=>n.role==='operation'&&!state.inactive.has(n.id))){
  if(!active.some(e=>e.to===n.id))throw Error('Business is an unexplained ordinary source: '+n.id);
  if(!active.some(e=>e.from===n.id))throw Error('Business replaces the actual final value/effect: '+n.id);
 }
 const reached=new Set(s.nodes.filter(n=>!['operation','decision','component'].includes(n.role)&&!state.inactive.has(n.id)&&!active.some(e=>e.to===n.id)).map(n=>n.id));
 for(let changed=true;changed;){changed=false;for(const e of active)if(reached.has(e.from)&&!reached.has(e.to)){reached.add(e.to);changed=true;}}
 for(const n of s.nodes.filter(n=>n.role==='operation'&&!state.inactive.has(n.id)))if(!reached.has(n.id))throw Error('Business is reachable only through control: '+n.id);
}
'''
            result=subprocess.run(['node','-e',code],capture_output=True,text=True)
            self.assertEqual(0,result.returncode,scene['id']+': '+result.stderr)

    def test_branch_reference_preserves_shared_inputs_and_extra_dashed_dependencies(self):
        scene=next(s for s in json.loads((SKILL/'examples/reference-scenes.json').read_text(encoding='utf8'))['scenes'] if s['id']=='branch-merge')
        actual={(e['from'],e['to'],e['kind']) for e in scene['edges']}
        self.assertTrue({('a','c','data'),('r','c','data'),('config','c','resource'),('a','d','data'),('g','h','data')}<=actual)
        frame_members={m for f in scene['frames'] for m in f['members']}
        self.assertTrue({'a','r','config','g','h'}.isdisjoint(frame_members))

    def test_reading_camera_keeps_initial_titles_inside_left_and_top_edges(self):
        from test_primary_flow import function
        script = """
let camera={z:.2},target;
const view={nodes:new Map([['input',{x:100,y:120,w:100,h:100}],['read',{x:100,y:260,w:240,h:50}],['value',{x:100,y:390,w:100,h:100}],['gate',{x:350,y:-80,w:200,h:80}]]),groups:new Map()};
const fit=()=>{},walkExecution=()=>({order:['input','read','value','gate']}),animateCamera=t=>target=t,$=()=>({textContent:''}),t=x=>x;
""" + function('bounds') + function('fitReading') + """
fitReading(false);
for(const id of ['input','read','value']){const n=view.nodes.get(id);if((n.x-n.w/2)*target.z+target.x<23)throw Error('Initial title clipped at left edge');}
const gate=view.nodes.get('gate');if((gate.y-gate.h/2)*target.z+target.y<31)throw Error('Earlier branch clipped above viewport');
"""
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_motion_preference_before_workflow_selection_has_no_view_to_repaint(self):
        from test_primary_flow import function
        result = subprocess.run(['node', '-e', 'const view=null;'+function('paintSelection')+'paintSelection();'],
                                capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == '__main__':
    unittest.main()
