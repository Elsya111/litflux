"""Reviewed workflow routing and failed tier changes preserve a usable view."""
import copy
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/litflux/scripts'))
from business_views import apply_workflows


class WorkflowTests(unittest.TestCase):
    def test_starting_at_entrances_does_not_project_an_unused_global_graph(self):
        template = (ROOT / 'skills/litflux/assets/viewer.html').read_text(encoding='utf8')
        start = template.rindex('  sizeCanvas();\n')
        end = template.index("  for(const button of root.querySelectorAll('[data-page]'))", start)
        subprocess.run(['node', '-e', '''
let currentPage='workflows',scope=null,view=null,profile=null,details=0;
const sizeCanvas=()=>{},updateProfile=()=>{profile={label:'Core'};},
rebuild=()=>{throw Error('unused global graph exceeds 15 nodes');},leave=()=>{},
showGranularity=()=>{if(!profile)throw Error('profile was not initialized');},showDetails=()=>{details++;};
''' + template[start:end] + '''
if(details||view!==null)throw Error('hidden graph was initialized on the workflow hub');
'''], check=True, capture_output=True)

    def test_review_routes_real_roots_without_rewriting_source(self):
        graph = {'operations': [{'id': 'answer'}, {'id': 'evaluate'}]}
        original = copy.deepcopy(graph['operations'])
        routes = [{'id': 'main', 'root': 'project', 'label': '主流程', 'description': '阅读主要业务。'},
                  {'id': 'evaluation', 'root': 'evaluate', 'label': '评测', 'description': '评测已有结果。'}]
        self.assertEqual(2, apply_workflows(graph, {'workflows': routes})['entries'])
        self.assertEqual(original, graph['operations'])
        self.assertEqual(routes, graph['presentation']['workflows'])
        routes[1]['root'] = 'invented'
        with self.assertRaisesRegex(ValueError, '真实函数'):
            apply_workflows(graph, {'workflows': routes})

    def test_failed_projection_does_not_leave_a_core_slider_on_30_node_view(self):
        template = (ROOT / 'skills/litflux/assets/viewer.html').read_text(encoding='utf8')
        start = template.index('  function setGranularity(')
        end = template.index('\n', start)
        subprocess.run(['node', '-e', '''
let granularity=100,profile={label:'处理细节'},view={nodes:30},displayed=100,notice='';
const snapGrain=x=>x,updateProfile=()=>{profile={label:granularity===100?'处理细节':'核心逻辑'};},
rebuild=()=>{if(granularity===0)throw Error('over budget');},
showGranularity=()=>{displayed=granularity;},showDetails=()=>{},fit=()=>{},save=()=>{},
$=()=>({set textContent(v){notice=v;}});
''' + template[start:end] + '''
if(setGranularity(0)!==false||granularity!==100||displayed!==100||view.nodes!==30||!notice.includes('已保留'))throw Error('stale 30-node graph falsely labelled core');
'''], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
