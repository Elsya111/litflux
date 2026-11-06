"""Test the actual viewer's page history independently of the function tree."""
from pathlib import Path
import subprocess
import unittest

TEMPLATE = (Path(__file__).resolve().parents[1] / 'skills/litflux/assets/viewer.html').read_text(encoding='utf8')


def function(name):
    start = TEMPLATE.index('  function ' + name + '(')
    return TEMPLATE[start:TEMPLATE.index('\n  function ', start + 3)]


class VisitHistoryTests(unittest.TestCase):
    def js(self, code):
        result = subprocess.run(['node', '-e', function('createVisitHistory') + code], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_forward_branch_is_discarded_only_after_a_new_visit(self):
        self.js('''
const h=createVisitHistory(),s=n=>({page:'flow',workflow:'main',scope:n,invocationContext:[n],camera:{x:0}});
h.visit(s('a'));h.visit(s('b'));h.visit(s('c'));
if(h.move(-1).scope!=='b'||!h.forward)throw Error('back failed');
h.visit({...s('b'),camera:{x:45}});
if(!h.forward||h.entries.length!==3)throw Error('panning created a visit');
if(h.move(1).scope!=='c')throw Error('forward lost');
h.move(-1);h.visit(s('d'));
if(h.forward||h.entries.map(e=>e.scope).join(',')!=='a,b,d')throw Error('new branch retained old future');
''')

    def test_snapshots_and_getters_cannot_mutate_saved_state(self):
        self.js('''
const h=createVisitHistory(),s={page:'flow',scope:'a',history:[{scope:'root'}],camera:{x:1}};
h.visit(s);s.camera.x=99;h.visit({page:'overview'});
const back=h.move(-1);back.history[0].scope='wrong';h.entries[0].camera.x=88;
if(h.entries[0].camera.x!==1||h.entries[0].history[0].scope!=='root')throw Error('mutable snapshot');
if(h.move(-1)!==null||h.index!==0)throw Error('out of bounds');
''')

    def test_history_survives_reload_and_has_a_bounded_size(self):
        self.js('''
const h=createVisitHistory(3);for(let i=0;i<6;i++)h.visit({page:'flow',scope:String(i)});
if(h.entries.map(e=>e.scope).join(',')!=='3,4,5')throw Error('unbounded');
h.move(-1);const restored=createVisitHistory(3);restored.load({entries:h.entries,index:h.index});
if(restored.index!==1||!restored.back||!restored.forward||restored.move(1).scope!=='5')throw Error('reload failed');
''')

    def test_same_function_at_different_call_sites_is_a_distinct_visit(self):
        self.js('''
const h=createVisitHistory(),s={page:'flow',scope:'search',workflow:'a',invocationContext:['a','call1']};
h.visit(s);h.visit({...s,invocationContext:['a','call2']});h.visit({...s,workflow:'b'});
if(h.entries.length!==3)throw Error('receiver/call identity collapsed');
''')


if __name__ == '__main__':
    unittest.main()
