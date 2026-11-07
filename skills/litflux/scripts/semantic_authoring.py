"""Load one agent-authored project module, verify declarations, package an offline viewer.

This module never infers meaning, line timing or layout: every data edge carries an
explicit timing, every position comes from the author's draw() function.
"""
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path

TYPES = {'business', 'data', 'resource', 'component', 'decision', 'boundary'}
RELATION_TYPES = {'data', 'control', 'failure', 'loop', 'effect', 'capability'}
# Relations that describe execution order; effect/capability describe resources instead.
FORWARD = {'data', 'control', 'failure'}
MODULE_FIELDS = 'title summary scope language files workflows unknowns coverage author'
FLOW_FIELDS = 'title sources objects relations reading draw'
OBJECT_FIELDS = 'id type title text sources detail choices'
RELATION_FIELDS = 'id from to type label sources when branch timing timingNote'
ID_RE = re.compile(r'[A-Za-z0-9_.-]+')
REF_RE = re.compile(r'([\w-]+):(\d+)(?:-(\d+))?')

NODE_WRAPPER = r"""
const fs = require('fs'), vm = require('vm');
const file = process.argv[2], timeout = Number(process.argv[3] || 2000);
const source = fs.readFileSync(file, 'utf8');
const sandboxModule = { exports: {} };
const context = vm.createContext({ module: sandboxModule, exports: sandboxModule.exports });
vm.runInContext(source, context, { timeout, filename: 'project.js' });
const exported = sandboxModule.exports;
const model = JSON.parse(JSON.stringify(exported));
const flows = Array.isArray(model.workflows) ? model.workflows : [];
const draws = flows.map((flow) => {
  const original = (exported.workflows || []).find((item) => item && item.id === flow.id);
  return Boolean(original && original.flow && typeof original.flow.draw === 'function');
});
process.stdout.write(JSON.stringify({ model, draws }));
"""


def engine_revision() -> str:
    """Bind evidence to the current compiler, drawing primitives and viewer."""
    skill = Path(__file__).resolve().parents[1]
    paths = [*(skill / 'scripts').glob('*.py'), *(skill / 'assets').glob('*')]
    fingerprint = hashlib.sha256()
    for path in sorted(p for p in paths if p.is_file()):
        fingerprint.update(path.relative_to(skill).as_posix().encode('utf-8') + b'\0')
        fingerprint.update(hashlib.sha256(path.read_bytes()).digest())
    return fingerprint.hexdigest()


def html_filename(name: str) -> str:
    """Produce a readable filename that is valid on Windows."""
    value = unicodedata.normalize('NFC', str(name or '')).strip()
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).rstrip(' .')
    if not value or value in ('.', '..'):
        value = 'project'
    if re.match(r'^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', value, re.IGNORECASE):
        value = '_' + value
    value = value[:80].rstrip(' .') or 'project'
    return 'litflux_' + value + '.html'


def evaluate_module(module_path: Path, timeout_ms: int = 2000) -> dict:
    """Evaluate the module with Node in a context without require/process/file access."""
    node = shutil.which('node')
    if not node:
        raise ValueError('Node.js is required to evaluate the project module; none found on PATH')
    with tempfile.TemporaryDirectory(prefix='litflux-eval-') as folder:
        wrapper = Path(folder) / 'run.js'
        wrapper.write_text(NODE_WRAPPER, encoding='utf-8')
        try:
            result = subprocess.run([node, str(wrapper), str(module_path), str(timeout_ms)],
                                    capture_output=True, text=True, encoding='utf-8', errors='replace',
                                    timeout=max(5, timeout_ms / 1000 + 5))
        except subprocess.TimeoutExpired:
            raise ValueError(f'Evaluating {module_path.name} exceeded {timeout_ms} ms; draw() or top-level code never loops')
        if result.returncode:
            message = (result.stderr or result.stdout).strip().splitlines()
            raise ValueError('Module did not evaluate: ' + (message[-1] if message else 'unknown error'))
        return json.loads(result.stdout)


def _fields(value, allowed, place, errors):
    if not isinstance(value, dict):
        errors.append(f'{place}: expected an object')
        return False
    for key in sorted(value.keys() - set(allowed.split())):
        errors.append(f'{place}.{key}: unknown field; it would not be rendered')
    return True


def relation_conditions(relation: dict) -> list[dict]:
    """Declared AND clauses, joined by OR; never infer guards from prose."""
    when = relation.get('when')
    clauses = when if isinstance(when, list) else [when or {}]
    branch = {relation['from']: relation['branch']} if relation.get('branch') is not None else {}
    return [dict(clause, **branch) for clause in clauses
            if all(key not in clause or clause[key] == value for key, value in branch.items())]


def intermediate_path(forward: dict, direct: dict, budget: int = 10000) -> bool | None:
    """Find a compatible path of >=2 edges. None means the bounded search stopped."""
    start, goal = direct['from'], direct['to']
    queue = [(start, condition, frozenset([start])) for condition in relation_conditions(direct)]
    seen = set()
    while queue:
        budget -= 1
        if budget < 0:
            return None  # ponytail: bounded local search; report uncertainty instead of a SAT engine.
        node, condition, visited = queue.pop()
        state = (node, tuple(sorted(condition.items())), visited)
        if state in seen:
            continue
        seen.add(state)
        for edge in forward.get(node, []):
            if edge is direct or edge['to'] in visited:
                continue
            for clause in relation_conditions(edge):
                if any(key in condition and condition[key] != value for key, value in clause.items()):
                    continue
                if edge['to'] == goal:
                    if len(visited) > 1:
                        return True
                    continue
                queue.append((edge['to'], {**condition, **clause}, visited | {edge['to']}))
    return False


def compile_module(module_path: Path, root: Path) -> dict:
    """Validate one module and resolve its source references."""
    errors, excerpts, notes, warnings = [], {}, [], []
    loaded = {}
    counts = dict(views=0, objects=0, relations=0, business=0, data=0, resource=0, component=0)

    evaluated = evaluate_module(module_path)
    model = evaluated['model']
    if not isinstance(model, dict):
        raise ValueError('module.exports must be an object')
    _fields(model, MODULE_FIELDS, 'module', errors)
    files = model.get('files') or {}
    if not isinstance(files, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in files.items()):
        errors.append('module.files: expected {alias: repo-relative path}')
        files = {}
    for alias, rel in files.items():
        target = (root / rel).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            errors.append(f'module.files.{alias}: not a file inside source-root: {rel}')

    def source_refs(refs, place):
        if refs is None:
            return
        items = refs if isinstance(refs, list) else [refs]
        if not items:
            errors.append(f'{place}: provide source ranges or omit the field')
            return
        for ref in items:
            match = REF_RE.fullmatch(ref) if isinstance(ref, str) else None
            if not match:
                errors.append(f'{place}: source must look like alias:start-end, got {ref!r}')
                continue
            alias, start, end = match[1], int(match[2]), int(match[3] or match[2])
            rel = files.get(alias)
            target = (root / rel).resolve() if rel else None
            if target is None or not target.is_relative_to(root) or not target.is_file():
                errors.append(f'{place}: unknown source alias {alias!r}')
                continue
            if target not in loaded:
                loaded[target] = target.read_bytes()
            raw = loaded[target]
            lines = raw.decode('utf-8-sig').splitlines()
            if not 1 <= start <= end <= len(lines):
                errors.append(f'{place}: {ref} is outside {rel} ({len(lines)} lines)')
                continue
            excerpts[ref] = dict(path=rel, start=start, end=end,
                                 sha256=hashlib.sha256(raw).hexdigest(), lines=lines[start - 1:end])

    def flow(view, place, owner=None):
        if not _fields(view, FLOW_FIELDS, place, errors):
            return
        if not isinstance(view.get('objects'), list) or not isinstance(view.get('relations'), list):
            errors.append(f'{place}: objects and relations must be arrays')
            return
        counts['views'] += 1
        if any(not isinstance(item, dict) for item in view['objects'] + view['relations']):
            errors.append(f'{place}: objects and relations must contain objects')
            return
        ids = [o.get('id') for o in view['objects']]
        relations_ids = [r.get('id') for r in view['relations']]
        for value in ids + relations_ids:
            if not isinstance(value, str) or not ID_RE.fullmatch(value):
                errors.append(f'{place}: IDs use letters, digits, dot, dash or underscore')
                return
        if len(set(ids)) != len(ids):
            errors.append(f'{place}: object IDs must be unique')
        if len(set(relations_ids)) != len(relations_ids):
            errors.append(f'{place}: relation IDs must be unique')
        source_refs(view.get('sources'), place + '/sources')
        by_id = {}
        for obj in view['objects']:
            item = place + '/' + str(obj.get('id'))
            _fields(obj, OBJECT_FIELDS, item, errors)
            counts['objects'] += 1
            kind = obj.get('type')
            if kind not in TYPES:
                errors.append(f'{item}: type must be one of {sorted(TYPES)}')
                continue
            counts[kind] = counts.get(kind, 0) + 1
            if not obj.get('title'):
                errors.append(f'{item}: title is required')
            source_refs(obj.get('sources'), item + '/sources')
            if kind != 'business' and 'detail' in obj:
                errors.append(f'{item}: only business objects can hold a detail flow')
            if kind == 'business' and not (obj.get('detail') or obj.get('sources') or obj.get('text')):
                warnings.append(f'{item}: business without detail, sources or text; check that the level explains it')
            choices = obj.get('choices')
            if choices is not None:
                if (not isinstance(choices, list) or not choices
                        or any(not isinstance(c, dict) or not c.get('id') or not c.get('label') for c in choices)
                        or len({c['id'] for c in choices}) != len(choices)):
                    errors.append(f'{item}: choices need distinct id and label')
                else:
                    by_id[obj['id']] = {c['id'] for c in choices}
            if obj.get('detail') is not None:
                flow(obj['detail'], item + '/detail')

        idset = set(ids)
        forward = {}
        for rel in view['relations']:
            item = place + '/' + str(rel.get('id'))
            _fields(rel, RELATION_FIELDS, item, errors)
            counts['relations'] += 1
            kind = rel.get('type')
            if kind not in RELATION_TYPES:
                errors.append(f'{item}: type must be one of {sorted(RELATION_TYPES)}')
            if rel.get('from') not in idset or rel.get('to') not in idset:
                errors.append(f'{item}: unknown endpoint')
            if 'label' in rel and not isinstance(rel['label'], str):
                errors.append(f'{item}: label must be a string or omitted')
            source_refs(rel.get('sources'), item + '/sources')
            timing = rel.get('timing')
            if kind == 'data':
                if timing not in ('immediate', 'deferred'):
                    errors.append(f'{item}: agent must declare timing=immediate or deferred')
            elif 'timing' in rel:
                errors.append(f'{item}: timing applies only to data dependencies')
            if kind != 'data' and 'timingNote' in rel:
                errors.append(f'{item}: timingNote applies only to data dependencies')
            owner_choices = by_id.get(rel.get('from'))
            if rel.get('branch') is not None:
                if not owner_choices or rel['branch'] not in owner_choices:
                    errors.append(f'{item}: branch must name a choice of the source object')
                if kind not in ('control', 'failure'):
                    errors.append(f'{item}: branch belongs to control/failure relations')
            elif owner_choices and kind in ('control', 'failure'):
                errors.append(f'{item}: outgoing control from a decision needs branch')
            when = rel.get('when')
            if when is not None:
                pairs = when if isinstance(when, list) else [when]
                for pair in pairs:
                    if not isinstance(pair, dict) or not pair:
                        errors.append(f'{item}: when is {decision: choice} or a list of those')
                        continue
                    for key, value in pair.items():
                        if value not in by_id.get(key, set()):
                            errors.append(f'{item}: when references an unknown choice {key}:{value}')
            if kind in FORWARD and rel.get('from') in idset and rel.get('to') in idset:
                forward.setdefault(rel['from'], []).append(rel)

        if errors:
            return
        for rel in view['relations']:
            if rel.get('type') != 'data':
                continue
            path = intermediate_path(forward, rel)
            if path is not False and not str(rel.get('timingNote') or '').strip():
                message = ('a compatible intermediate path exists under the declared conditions; '
                           'a timingNote may help explain your choice' if path else
                           'intermediate-path search reached its limit; timing remains your declaration')
                warnings.append(f"{place}/{rel['id']}: {message}")
            if rel.get('timingNote'):
                notes.append(f"{place}/{rel['id']}")

    if not model.get('title') or not model.get('summary') or not model.get('scope'):
        errors.append('module needs title, summary and an explicit scope')
    if model.get('language', 'zh') not in ('zh', 'en'):
        errors.append('module.language: expected zh or en')
    workflows = model.get('workflows')
    if not isinstance(workflows, list) or not workflows:
        errors.append('module.workflows: at least one real entrance is required')
        workflows = []
    seen_ids = set()
    for index, workflow in enumerate(workflows):
        place = f'workflows[{index}]'
        if not isinstance(workflow, dict):
            errors.append(f'{place}: expected an object')
            continue
        _fields(workflow, 'id title entry flow sources', place, errors)
        source_refs(workflow.get('sources'), place + '/sources')
        if not isinstance(workflow.get('id'), str) or not ID_RE.fullmatch(workflow['id']) or workflow['id'] in seen_ids:
            errors.append(f'{place}: unique alphanumeric id is required')
        else:
            seen_ids.add(workflow['id'])
        if not workflow.get('title'):
            errors.append(f'{place}: title is required')
        entry = workflow.get('entry')
        if not isinstance(entry, dict) or not entry.get('trigger'):
            errors.append(f'{place}: entry.trigger must name the real call or command')
        elif _fields(entry, 'trigger sources notes', place + '/entry', errors):
            source_refs(entry.get('sources'), place + '/entry/sources')
        if index < len(evaluated['draws']) and not evaluated['draws'][index]:
            errors.append(f'{place}: flow.draw must be a function')
        if workflow.get('flow') is not None:
            flow(workflow['flow'], place + '/flow')

    if errors:
        raise ValueError('\n'.join(errors))
    return dict(model=model, excerpts=excerpts, counts=counts,
                requiredNotes=[], timingNotes=notes, warnings=warnings,
                boundary='Structure, sources and the author\'s own timing declarations were checked; '
                         'source entailment and visual readability need a separate judgement.')


def compile_module_file(module_path: Path, root: Path) -> dict:
    if not module_path.is_file():
        raise ValueError(f'project module not found: {module_path}')
    return compile_module(module_path, root)


def _escape_script(source: str) -> str:
    return re.sub(r'</script', lambda match: '<\\/' + match[0][2:], source, flags=re.IGNORECASE)


def render_viewer(compiled: dict, module_source: str, assets: Path, payload: dict) -> str:
    template = (assets / 'semantic-viewer.html').read_text(encoding='utf-8')
    replacements = {
        '__DRAWING__': (assets / 'drawing.js').read_text(encoding='utf-8'),
        '__MODULE__': _escape_script(module_source),
        '__PAYLOAD__': _escape_script(json.dumps(payload, ensure_ascii=False)),
        '__AUDIT__': (assets / 'semantic-audit.js').read_text(encoding='utf-8'),
        '__LOCALIZER__': (assets / 'localizer.js').read_text(encoding='utf-8'),
        '__MESSAGES__': (assets / 'semantic-messages.en.json').read_text(encoding='utf-8'),
    }
    for marker in replacements:
        if marker not in template:
            raise ValueError(f'viewer template is missing {marker}')
    # Replace template markers once; source text containing a marker stays literal.
    return re.sub('|'.join(map(re.escape, replacements)), lambda match: replacements[match[0]], template)


def check_review(qa_path: Path, revision: str, author: str) -> dict:
    if qa_path is None or not Path(qa_path).is_file():
        return {'status': 'missing', 'error': 'no review.json; reviewed status not requested'}
    data = json.loads(Path(qa_path).read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        return {'status': 'failed', 'errors': ['review.json must be an object']}
    errors = []
    if data.get('revision') != revision:
        errors.append('review.json revision does not match this build')
    if not isinstance(data.get('reviewer'), str) or not data['reviewer'].strip() or data['reviewer'] == author:
        errors.append('reviewer must be a separate agent session, not the author')
    checks = data.get('checks') or {}
    if not isinstance(checks, dict):
        checks = {}
    evidence = data.get('evidence')
    if not isinstance(evidence, list) or not evidence or any(not isinstance(e, str) or not e.strip() for e in evidence):
        errors.append('provide a non-empty evidence file list')
        evidence = []
    for name in ('coverage', 'semantics', 'visuals'):
        value = checks.get(name)
        passed = value == 'passed' or (isinstance(value, dict) and value.get('status') == 'passed')
        if not passed:
            errors.append(f'{name} review is not passed')
        refs = value.get('evidence', evidence) if isinstance(value, dict) else evidence
        if not isinstance(refs, list) or not refs or any(ref not in evidence for ref in refs):
            errors.append(f'{name} evidence must reference the evidence file list')
    for item in evidence:
        target = Path(qa_path).parent / item
        if not target.is_file():
            errors.append(f'evidence file missing: {item}')
    return {'status': 'failed' if errors else 'passed', 'errors': errors,
            'reviewer': data.get('reviewer'), 'revision': revision,
            'trustBoundary': 'Reviewer identity and observations are declarations; file checks cannot prove them.'}


def build_semantic(module_path: Path, output: Path, source_root: Path, language=None, *,
                   draft=False, qa_path=None, browser=True, check_only=False, geometry_only=False) -> dict:
    started = time.monotonic()
    if geometry_only and (not browser or check_only or qa_path):
        raise ValueError('--geometry-only requires browser rendering and cannot combine with --check-only/--no-browser/--review')
    assets = Path(__file__).resolve().parents[1] / 'assets'
    module_path = Path(module_path).resolve()
    root = Path(source_root).resolve()
    compiled = compile_module_file(module_path, root)
    model = compiled['model']
    module_source = module_path.read_text(encoding='utf-8-sig')
    if language and model.get('language', 'zh') != language:
        raise ValueError(f'module.language is {model.get("language", "zh")} but --language is {language}')
    source_hashes = sorted({(s['path'], s['sha256']) for s in compiled['excerpts'].values()})
    revision = hashlib.sha256((module_source + engine_revision() + json.dumps(source_hashes)).encode('utf-8')).hexdigest()[:16]
    payload = {
        'revision': revision,
        'sources': compiled['excerpts'],
        'status': 'draft',
        'timingNotes': compiled['timingNotes'],
    }
    html = render_viewer(compiled, module_source, assets, payload)
    if check_only:
        return {'valid': True, 'deliveryStatus': 'draft', 'counts': compiled['counts'],
                'qualityRevision': revision, 'outputs': [], 'semanticAudit': {'errors': [], 'warnings': compiled['warnings']}}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    page = (output / html_filename(model.get('title'))).resolve()
    page.write_text(html, encoding='utf-8')
    (output / 'litflux.graph.json').write_text(
        json.dumps({'revision': revision, 'project': model, 'sources': compiled['excerpts']},
                   ensure_ascii=False, indent=2), encoding='utf-8')
    audit = {'errors': [], 'warnings': compiled['warnings'], 'browser': {'status': 'not-run'}, 'geometry': {'status': 'not-run'}}
    prepared = time.monotonic()
    delivery = 'draft'
    if browser:
        from semantic_browser import browser_check
        audit['browser'] = browser_check(page, revision, geometry_only=geometry_only)
        failures = audit['browser'].get('failures') or []
        geometry = audit['browser'].get('geometry') or {}
        if geometry.get('status') in ('passed', 'warnings'):
            audit['geometry'] = {'status': 'passed' if not geometry.get('warnings') else 'failed',
                                 'warnings': geometry.get('warnings') or []}
        else:
            audit['geometry'] = {'status': 'not-run', 'warnings': []}
        if not geometry_only and audit['browser'].get('status') == 'passed' and audit['geometry']['status'] == 'passed':
            delivery = 'checked'
        else:
            audit['errors'].extend(failures)
    review = check_review(qa_path, revision, model.get('author') or 'agent')
    if delivery == 'checked' and review['status'] == 'passed':
        delivery = 'reviewed'
    if delivery != 'draft':
        # The badge is part of the page payload, so keep the file and the report in step.
        payload['status'] = delivery
        page.write_text(render_viewer(compiled, module_source, assets, payload), encoding='utf-8')
    report = {'valid': True, 'deliveryStatus': delivery, 'counts': compiled['counts'],
              'qualityRevision': revision, 'outputs': [str(page)],
              'semanticAudit': audit, 'review': review,
              'boundary': compiled['boundary'], 'mode': 'geometry-only' if geometry_only else 'full',
              'timingsMs': {'prepare': round((prepared-started)*1000), 'total': round((time.monotonic()-started)*1000)}}
    (output / 'litflux.build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if geometry_only:
        (output / 'litflux.geometry-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report
