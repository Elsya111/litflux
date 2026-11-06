"""Source endpoints expose exact original ranges rather than invented leaf graphs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/litflux/scripts'))
from route_language import route, authoring_language
from render_graph import render


class SourceEndpointTests(unittest.TestCase):
    def js(self, script):
        factory = (ROOT / 'skills/litflux/assets/source-endpoint.js').read_text(encoding='utf8')
        result = subprocess.run(['node', '-e', 'const create=' + factory + ';' + script], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_full_file_ranges_preserve_code_beyond_old_excerpt_limit(self):
        self.js(r'''
const code=Array.from({length:180},(_,i)=>'original '+(i+1)).join('\n');
const model={sourceFiles:{'app.py':{code}}},op={source:{path:'app.py',startLine:125,endLine:160}};
const index=create(model,new Map());const blocks=index.blocks(op);
if(blocks.length!==1||blocks[0].startLine!==125||blocks[0].endLine!==160||blocks[0].truncated)throw Error('incorrect exact range');
if(blocks[0].code!==code.split('\n').slice(124,160).join('\n'))throw Error('code altered');
''')

    def test_explicit_leaf_range_excludes_adjacent_processing_without_mutating_metadata(self):
        self.js(r'''
const span={path:'app.py',startLine:1,endLine:3};
const model={sourceFiles:{'app.py':{code:'prepare()\nrerank()\nexpand()'}}};
const op={source:span,sourceRanges:[{path:'app.py',startLine:2,endLine:2}]};
const blocks=create(model,new Map()).blocks(op);
if(blocks[0].code!=='rerank()'||blocks[0].endLine!==2||span.endLine!==3)throw Error('A sibling call leaked into the source leaf');
''')

    def test_partial_legacy_source_has_no_reconstructed_gap(self):
        self.js(r'''
const a={id:'a',source:{path:'a.py',startLine:10,endLine:14},sourceCode:'ten\neleven'},b={id:'b',source:{path:'a.py',startLine:14,endLine:14},sourceCode:'fourteen'};
const index=create({},new Map([['a',a],['b',b]]));const blocks=index.blocks(a);
if(blocks.length!==2||blocks[0].endLine!==11||blocks[1].startLine!==14||blocks.some(b=>!b.truncated))throw Error('missing lines were invented or hidden');
''')

    def test_trailing_newline_is_not_an_extra_source_line(self):
        self.js(r'''
const index=create({sourceFiles:{'a.py':{code:'one\n'},'empty.py':{code:''}}},new Map());
if(index.has({source:{path:'a.py',startLine:2,endLine:2}})||index.has({source:{path:'empty.py',startLine:1,endLine:1}}))throw Error('invented source line');
''')

    def test_different_files_and_receivers_keep_distinct_source(self):
        self.js(r'''
const model={sourceFiles:{'a.py':{code:'A'},'b.py':{code:'B'}}};
const a={id:'a',source:{path:'a.py',startLine:1,endLine:1}},b={id:'b',source:{path:'b.py',startLine:1,endLine:1}};
const index=create(model,new Map([['a',a],['b',b]]));const blocks=index.blocks({sourceMembers:['a','b']});
if(blocks.length!==2||blocks.map(b=>b.code).join('')!=='AB')throw Error('same-named implementations conflated');
''')

    def test_sparse_source_ranges_preserve_lines_and_real_gaps(self):
        self.js(r'''
const file={ranges:[{startLine:125,endLine:126,code:'first\n'},{startLine:160,endLine:160,code:'last'}]};
const index=create({sourceFiles:{'a.py':file}},new Map());
const blocks=index.blocks({source:{path:'a.py',startLine:125,endLine:160}});
if(blocks.length!==2||blocks[0].startLine!==125||blocks[0].endLine!==126||blocks[0].code!=='first\n'||blocks[1].code!=='last')throw Error('Sparse source lines changed');
if(index.has({source:{path:'a.py',startLine:130,endLine:130}}))throw Error('A missing source line was invented');
''')

    def test_renderer_embeds_cited_file_once_without_reading_outside_root(self):
        model = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'dataflow-example.json').read_text(encoding='utf8'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = '\n'.join('line ' + str(i) for i in range(1, 180))
            (root / 'app.py').write_text(code, encoding='utf8')
            op = model['operations'][0]
            op['source'] = {'path':'app.py', 'startLine':121, 'endLine':170, 'url':None}
            html, _ = render(model, root, source_excerpts='functions')
            blocks = model['sourceFiles']['app.py']['ranges']
            self.assertTrue(any(block['startLine'] <= 121 and block['endLine'] >= 170 for block in blocks))
            self.assertNotIn('line 179', '\n'.join(block['code'] for block in blocks))
            self.assertEqual(1, len(model['sourceFiles']))
            self.assertTrue('__LITFLUX_SOURCE_ENDPOINT__' not in html)

    def test_authored_model_cannot_be_relabelled_as_another_language(self):
        model = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'dataflow-example.json').read_text(encoding='utf8'))
        model.setdefault('presentation', {})['authoringLanguage'] = 'zh'
        with self.assertRaisesRegex(ValueError, 'authored model'):
            render(model, language='en')


class LanguageRouteTests(unittest.TestCase):
    def test_request_selects_matching_readable_instruction_file(self):
        for message, language in [('解释这个项目','zh'), ('Explain this project','en')]:
            result = route(message)
            self.assertEqual(language, result['language'])
            self.assertTrue(Path(result['instructions']).is_file())
        self.assertEqual('en', route('请用英文说明', 'en')['language'])

    def test_route_is_not_a_late_translation_switch(self):
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            authoring_language({'language':'zh'}, 'en')
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            authoring_language({'language':'en','authoringLanguage':'zh'})
        with self.assertRaisesRegex(ValueError, 'Chinese prose'):
            authoring_language({'language':'en','symbols':{'a':{'description':'中文说明'}}})
        self.assertEqual('en', authoring_language({'language':'en','symbols':{'a':{'description':'Explain the purpose', 'sourceCode':'# 原始源码'}}}))


if __name__ == '__main__':
    unittest.main()
