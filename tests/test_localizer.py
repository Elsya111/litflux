"""The offline translator changes presentation text, never source identifiers."""
from pathlib import Path
import json
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]


class LocalizerTests(unittest.TestCase):
    def test_description_translates_before_word_safe_truncation(self):
        template=(ROOT/'skills/litflux/assets/viewer.html').read_text(encoding='utf8')
        short=next(line.strip() for line in template.splitlines() if line.strip().startswith('const shortText='))
        raw='用于复核答案数字归属的完整说明。'*20
        translated=('Review numeric attribution against the source evidence before returning the answer. '*8).strip()
        script='const interfaceState={language:"en"};const raw='+json.dumps(raw)+';const translated='+json.dumps(translated)+';const t=s=>s===raw?translated:s;'+short+'''
const result=shortText(raw);
if(/[\u3400-\u9fff]/.test(result)||!result.startsWith('Review numeric'))throw Error('translated a truncated source key');
if(result.length>240||!translated.startsWith(result.slice(0,-1)))throw Error('wrong truncation');
if(translated[result.length-1]!==' ')throw Error('cut an English word');
interfaceState.language='zh';if(shortText('短说明')!=='短说明')throw Error('Chinese changed');
'''
        result=subprocess.run(['node','-e',script],capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_reviewed_text_switches_both_ways_and_unknown_content_stays_original(self):
        factory=(ROOT/'skills/litflux/assets/localizer.js').read_text(encoding='utf8')
        script='''
global.MutationObserver=class {disconnect(){} observe(){}};
const state={language:'en'},create='''+factory+''';
const localizer=create(null,state,{'进入':'Explore ','图':'Diagram','调用 foo.bar()':'Invoke foo.bar()'});
if(localizer.text('进入检索材料')!=='进入检索材料')throw Error('invented a translation for unknown content');
if(localizer.text('调用 foo.bar()')!=='Invoke foo.bar()')throw Error('regex special characters changed');
if(localizer.text('self.search(query)')!=='self.search(query)')throw Error('identifier translated');
if(localizer.text('未审阅的业务说明。')!=='未审阅的业务说明。')throw Error('invented translation');
state.language='zh';if(localizer.text('进入检索材料')!=='进入检索材料')throw Error('original language not restored');
'''
        result=subprocess.run(['node','-e',script],capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
