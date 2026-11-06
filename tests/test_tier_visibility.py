"""Core/main/detail differ only by importance, never by processing steps."""
import subprocess
import unittest
from pathlib import Path

TEMPLATE = (Path(__file__).resolve().parents[1] / 'skills/litflux/assets/viewer.html').read_text(encoding='utf8')
START = TEMPLATE.index('  const importanceFloor=')
END = TEMPLATE.index('  const contractKindLabel=', START)
SHOWN = TEMPLATE[START:END]
DECISION = next(line for line in TEMPLATE.splitlines() if line.startswith('  const decisionVisible='))


class TierVisibilityTests(unittest.TestCase):
    def run_js(self, script):
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_importance_controls_only_data_resources_and_decisions(self):
        self.run_js('''
const operations=new Map([['op',{}]]),events=new Map([['event',{}]]);
const contextual=()=>true;
let granularity=0;
''' + SHOWN + '''
const main={id:'main',presentation:{importance:'main'}};
const supporting={id:'supporting',presentation:{importance:'supporting'}};
const auxiliary={id:'auxiliary',presentation:{importance:'auxiliary'}};
const legacy={id:'legacy',presentation:{minGranularity:50}};
const op={id:'op',presentation:{importance:'auxiliary'}};
const event={id:'event',presentation:{importance:'auxiliary'}};
if(!shown(main)||shown(supporting)||shown(auxiliary)||shown(legacy)||!shown(op)||!shown(event))throw Error('core filter');
granularity=50;
if(!shown(main)||!shown(supporting)||shown(auxiliary)||!shown(legacy)||!shown(op))throw Error('main filter');
granularity=100;
if(!shown(main)||!shown(supporting)||!shown(auxiliary)||!shown(legacy)||!shown(op))throw Error('detail filter');
''')

    def test_hidden_flag_cannot_hide_processing_or_events(self):
        self.run_js('''
const operations=new Map([['op',{}]]),events=new Map([['event',{}]]);
const contextual=()=>true;
let granularity=100;
''' + SHOWN + '''
const hiddenOp={id:'op',presentation:{hidden:true}};
const hiddenEvent={id:'event',presentation:{hidden:true}};
const hiddenData={id:'data',presentation:{hidden:true}};
if(!shown(hiddenOp)||!shown(hiddenEvent)||shown(hiddenData))throw Error('hidden flag leaked into the fixed spine');
''')

    def test_decisions_are_visible_at_every_tier(self):
        self.run_js(DECISION + '''
for(const granularity of [0,50,100])if(!decisionVisible({importance:'auxiliary',minGranularity:100}))throw Error('decision hidden at tier '+granularity);
''')
        self.assertIn('本图的内部判断', TEMPLATE)
        self.assertIn('decisionBudgetOverflow', TEMPLATE)


if __name__ == '__main__':
    unittest.main()
