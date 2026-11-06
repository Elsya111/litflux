"""Package the self-contained skill and verify rendering from the extracted archive."""
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'plugin.json').read_text(encoding='utf-8'))
version=manifest['version'];name=manifest['name']
archive=ROOT/'dist'/f'{name}-{version}.zip'
archive.parent.mkdir(parents=True,exist_ok=True)
files=[ROOT/p for p in ('plugin.json','SPEC.md','README.md','README.zh-CN.md','CHANGELOG.md','LICENSE','THIRD_PARTY_NOTICES.md')]+[p for p in (ROOT/'skills'/name).rglob('*')
    if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as package:
    for p in sorted(files):package.write(p,p.relative_to(ROOT).as_posix())
destination=ROOT/'test-results'/'package-smoke'/f'{name}-{version}'
destination.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(archive) as package:package.extractall(destination)
skill=destination/'skills'/name
for asset in ('function-graph-layout.js','function-graph.js','boundary-contract.js','localizer.js','source-endpoint.js'):
    subprocess.run(['node','--check',str(skill/'assets'/asset)],check=True)
template=(skill/'assets'/'viewer.html').read_text(encoding='utf-8')
syntax=destination/'viewer-syntax.js'
syntax.write_text(template[template.rindex('<script>')+8:template.rindex('</script>')],encoding='utf-8')
subprocess.run(['node','--check',str(syntax)],check=True)
subprocess.run([sys.executable,'-B',str(skill/'scripts'/'render_graph.py'),str(skill/'references'/'event-example.json'),
                str(destination/'event-smoke.html')],check=True)
print(json.dumps({'archive':str(archive),'files':len(files),'bytes':archive.stat().st_size,'extractRenderPassed':True,
                  'eventExampleRendered':True}))
