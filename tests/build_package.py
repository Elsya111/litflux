"""Package the self-contained skill and verify rendering from the extracted archive."""
import json
from pathlib import Path
import subprocess
import sys
import zipfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'plugin.json').read_text(encoding='utf-8'))
version=manifest['version'];name=manifest['name']
archive=ROOT/'dist'/f'{name}-{version}.zip'
archive.parent.mkdir(parents=True,exist_ok=True)
files=[ROOT/p for p in ('plugin.json','SPEC.md','README.md','LICENSE','THIRD_PARTY_NOTICES.md')]+[p for p in (ROOT/'skills'/name).rglob('*')
    if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as package:
    for p in sorted(files):package.write(p,p.relative_to(ROOT).as_posix())
destination=Path(tempfile.mkdtemp(prefix=f'litflux-package-{version}-'))
with zipfile.ZipFile(archive) as package:package.extractall(destination)
skill=destination/'skills'/name
for asset in ('drawing.js','semantic-audit.js','localizer.js'):
    subprocess.run(['node','--check',str(skill/'assets'/asset)],check=True)
subprocess.run([sys.executable,'-B',str(skill/'scripts'/'build_graph.py'),str(skill/'examples'/'project-example.js'),
                str(destination/'smoke'),'--source-root',str(skill/'examples/semantic-source'),'--no-browser'],check=True)
report=json.loads((destination/'smoke/litflux.build-report.json').read_text(encoding='utf8'))
assert report['valid'] and Path(report['outputs'][0]).is_file()
print(json.dumps({'archive':str(archive),'files':len(files),'bytes':archive.stat().st_size,'extractRenderPassed':True,
                  'extracted':str(destination),'browserChecked':False}))
