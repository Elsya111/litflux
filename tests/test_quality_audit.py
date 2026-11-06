"""Delivery quality is checked against explicit source and runtime inventories."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'skills/litflux/scripts'), str(ROOT / 'tests')]
from compile_review import prepare, split_warning_policy, warning_summary
from quality_audit import audit, compile_overview, entry_manifest, receipt_errors, revision
from test_business_dag import fixture
from test_build_gate import full_review, attach_receipts, write_json


class QualityAuditTests(unittest.TestCase):
    def case(self):
        graph, spec = fixture()
        return graph, full_review(spec)

    def test_guide_uses_every_authored_file_and_rejects_dual_write(self):
        graph, review = self.case()
        for index in range(13):
            review['files']['module' + str(index) + '.py'] = {'description': 'An explicitly reviewed module.'}
        overview = compile_overview(graph, review)
        self.assertEqual(14, len(overview['files']))
        graph['projectOverview']['files'].pop()
        with self.assertRaisesRegex(ValueError, 'projectOverview conflicts'):
            compile_overview(graph, review)

    def test_complex_or_unreviewed_source_cannot_be_certified_simple(self):
        for field, value in (('complexity', 'complex'), ('wrapper', True), ('sourceCalls', None)):
            graph, review = self.case()
            review['semanticInventory']['prep'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'simple eligibility|sourceCalls'):
                prepare(graph, review)

    def test_known_branch_and_loop_require_representation(self):
        for kind in ('branches', 'loops', 'exceptions'):
            graph, review = self.case()
            review['semanticInventory']['entry']['control'][kind] = [{
                'id': 'known-control', 'importance': 'business', 'reason': 'Changes the returned result.',
                'source': {'path': 'app.py', 'startLine': 1, 'endLine': 1}}]
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'Business control has no'):
                prepare(graph, review)

    def test_code_and_mixed_final_delivery_require_actual_source(self):
        for kind in ('code', 'mixed'):
            graph, review = self.case()
            graph['project']['sourceKind'] = kind
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'requires --source-root'):
                prepare(copy.deepcopy(graph), review)
            draft = prepare(graph, review, delivery=False)
            self.assertEqual('draft', draft['deliveryStatus'])
            self.assertEqual('unverified', draft['graph']['presentation']['sourceFingerprint']['mode'])

    def test_source_and_engine_changes_invalidate_old_evidence(self):
        graph, review = self.case()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'app.py'
            source.write_text("def answer(): return 'first'\n", encoding='utf-8')
            attach_receipts(graph, review, root)
            before = prepare(copy.deepcopy(graph), review, source_root=root)
            source.write_text("def answer(): return 'other'\n", encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'different model/review revision'):
                prepare(copy.deepcopy(graph), review, source_root=root)
            after = prepare(copy.deepcopy(graph), review, source_root=root, delivery=False)
            self.assertNotEqual(before['qualityRevision'], after['qualityRevision'])
            self.assertNotEqual(before['graph']['presentation']['sourceFingerprint'], after['graph']['presentation']['sourceFingerprint'])
        graph, review = self.case()
        with patch('compile_review.engine_revision', return_value='changed-engine'):
            with self.assertRaisesRegex(ValueError, 'different model/review revision'):
                prepare(graph, review)

    def test_delegated_control_requires_a_child_view_and_traceable_fact(self):
        graph, review = self.case()
        fact = {'id': 'parent-check', 'reason': 'Changes the result.',
                'source': {'path': 'app.py', 'startLine': 1, 'endLine': 1}, 'childNode': 'prep'}
        review['semanticInventory']['entry']['control']['branches'] = [fact]
        with self.assertRaisesRegex(ValueError, 'traceable child control'):
            prepare(copy.deepcopy(graph), review)
        graph, baseline = self.case()
        compiled = prepare(graph, baseline)['graph']
        child = next(node for node in compiled['presentation']['businessDAG']['nodes'] if node['id'] == 'prep')
        child.pop('stop')
        child['views'] = {'100': {'steps': [], 'concepts': [],
            'story': compiled['presentation']['businessDAG']['nodes'][0]['views']['100']['story']}}
        compiled['presentation']['decisions'] = [{'id': 'real-check', 'owner': 'prepare'}]
        baseline['semanticInventory']['entry']['control']['branches'] = [fact]
        fact['childControl'] = 'child-check'
        baseline['semanticInventory']['prep']['control']['branches'] = [{
            'id': 'child-check', 'reason': 'Explains the same business condition.',
            'source': fact['source'], 'decision': 'real-check'}]
        result = audit(compiled, baseline)
        self.assertTrue(result['complete'], result['errors'])
        self.assertEqual([], result['branchesWithoutDecision'])
        self.assertEqual(['real-check'], result['views']['prep']['expectedDecisions'])
        fact['childControl'] = 'missing-check'
        self.assertTrue(audit(compiled, baseline)['branchesWithoutDecision'])

    def test_guide_reuses_the_referenced_source_signature(self):
        graph, review = self.case()
        source = graph['operations'][0]['source']
        review['symbols']['Service'] = {'kind': 'class', 'label': 'Service', 'description': 'The source owner.', 'source': source}
        review['symbols']['Service.run'] = {'kind': 'method', 'owner': 'Service', 'definition': 'execute',
            'label': 'Produce reply', 'description': 'Use the actual source method.', 'source': source}
        overview = compile_overview(graph, review)
        self.assertEqual('execute()', overview['files'][0]['classes'][0]['methods'][0]['signature'])

    def test_renaming_a_primary_complex_stop_omitted_is_not_a_waiver(self):
        graph, review = self.case()
        review['businessDAG']['nodes'][1]['stop']['reason'] = 'omitted'
        review['businessDAG']['nodes'][1]['stop']['review']['reopen'] = 'When more detail is requested.'
        review['semanticInventory']['prep'].update(role='algorithm', complexity='complex')
        with self.assertRaisesRegex(ValueError, 'Primary complex implementation cannot be omitted'):
            prepare(graph, review)

    def test_zero_decisions_does_not_mean_source_was_not_reviewed(self):
        graph, review = self.case()
        report = prepare(graph, review)
        self.assertEqual(0, report['semanticAudit']['workflows'][0]['decisions'])
        self.assertTrue(report['semanticAudit']['complete'])
        self.assertTrue(report['semanticAudit']['sourceParsing'] is False)
        graph, review = self.case()
        review.pop('semanticInventory')
        with self.assertRaisesRegex(ValueError, 'semanticInventory'):
            prepare(graph, review)

    def test_partial_project_requires_capability_specific_user_approval(self):
        graph, review = self.case()
        graph['project']['coverage'][0]['status'] = 'partial'
        graph['project']['coverage'][0]['reason'] = 'HTTP management remains uncovered.'
        review['delivery']['goals'][0].update(status='partial', reason='Management omitted.',
            coverageEntry='Process a request')
        with self.assertRaisesRegex(ValueError, 'scope approval|coverage is incomplete'):
            prepare(graph, review)
        review['delivery']['goals'][0]['scopeApproval'] = 'scope-management'
        review['clarifications'] = [{'id': 'scope-management', 'question': 'Exclude management?',
            'status': 'answered', 'answer': 'Yes, exclude management in this delivery.', 'confirmedByUser': True}]
        attach_receipts(graph, review)
        self.assertTrue(prepare(graph, review)['valid'])

    def test_primary_file_inventory_needs_complete_reading(self):
        graph, review = self.case()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app.py').write_text('first\nsecond\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'complete body'):
                prepare(graph, review, source_root=root)

    def test_scoped_files_cannot_silently_disappear_from_inventory(self):
        graph, review = self.case()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app.py').write_text('pass\n', encoding='utf-8')
            (root / 'other.py').write_text('pass\n', encoding='utf-8')
            review['sourceScope']['include'] = ['*.py']
            with self.assertRaisesRegex(ValueError, 'missing from sourceScope.files'):
                prepare(graph, review, source_root=root)

    def test_view_story_and_required_guide_symbols_are_not_optional(self):
        graph, review = self.case()
        review['businessDAG']['nodes'][0]['views']['0']['story'].pop('branches')
        with self.assertRaisesRegex(ValueError, 'story needs branches'):
            prepare(graph, review)
        graph, review = self.case()
        review['guide'] = {'symbols': []}
        with self.assertRaisesRegex(ValueError, 'required public/main symbol'):
            prepare(graph, review)

    def test_direct_resource_and_invocation_omissions_are_visible(self):
        graph, review = self.case()
        graph = prepare(graph, review)['graph']
        graph['resources'] = [{'id': 'db', 'name': 'Stored requests', 'kind': 'database',
            'scope': 'project', 'type': 'Database', 'evidence': ['example']}]
        child = graph['operations'][0]['expansion']['operations'][0]
        child['inputs'].append({'port': 'db', 'entity': 'db', 'role': 'capture', 'required': True, 'resourceMode': 'read'})
        child['inputs'].append({'port': 'provider', 'entity': 'engine', 'role': 'capture', 'required': True, 'relation': 'invocation', 'presentation': {'importance': 'main'}})
        for plan in graph['presentation']['businessDAG']['nodes'][0]['views'].values():
            plan['concepts'] = [item for item in plan['concepts'] if 'engine' not in item['members']]
        result = audit(graph, review)
        self.assertIn('resourceNotVisible', {item['kind'] for item in result['warnings']})
        self.assertIn('componentNotVisible', {item['kind'] for item in result['warnings']})

    def test_blanket_warning_confirmation_cannot_hide_raw_counts(self):
        original = [{'kind': 'resourceNotVisible', 'scope': 'entry', 'target': 'db', 'severity': 'warning'}]
        warnings, hints, accepted = split_warning_policy(original, {'acknowledge': [
            {'kind': 'resourceNotVisible', 'reason': 'accept all'}]})
        self.assertEqual(original, warnings)
        self.assertEqual([], accepted)
        warnings, hints, accepted = split_warning_policy(original, {'acknowledge': [
            {'kind': 'resourceNotVisible', 'scope': 'entry', 'target': 'db',
             'reason': 'The child graph explains this store.', 'evidence': 'app.py:1'}]})
        self.assertEqual([], warnings)
        self.assertEqual(1, warning_summary(warnings, hints, accepted)['rawTotal'])

    def test_qa_evidence_cannot_be_stale_or_missing(self):
        graph, review = self.case()
        path = Path(review['qa']['checklistFile'])
        receipt = json.loads(path.read_text(encoding='utf-8'))
        receipt['revision'] = 'stale-model'
        write_json(path, receipt)
        with self.assertRaisesRegex(ValueError, 'different model/review revision'):
            prepare(copy.deepcopy(graph), review)
        attach_receipts(graph, review)
        path = Path(review['qa']['checklistFile'])
        (path.parent / 'declared-evidence.md').write_text('Changed after acceptance.', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'evidence hash changed'):
            prepare(copy.deepcopy(graph), review)

    def test_dom_only_acceptance_is_an_explicit_draft(self):
        graph, review = self.case()
        path = Path(review['qa']['checklistFile'])
        receipt = json.loads(path.read_text(encoding='utf-8'))
        receipt['checks']['visuals']['capability'] = 'dom'
        write_json(path, receipt)
        with self.assertRaisesRegex(ValueError, 'inspected images'):
            prepare(copy.deepcopy(graph), review)
        self.assertEqual('draft', prepare(graph, review, delivery=False)['deliveryStatus'])

    def test_entry_receipt_covers_every_call_context_and_tier(self):
        graph, review = self.case()
        path = Path(review['qa']['entryAuditFile'])
        receipt = json.loads(path.read_text(encoding='utf-8'))
        receipt['calls'].pop()
        write_json(path, receipt)
        with self.assertRaisesRegex(ValueError, 'call contexts'):
            prepare(graph, review)

    def test_entry_preflight_alone_cannot_claim_enter_and_return(self):
        graph, review = self.case()
        path = Path(review['qa']['entryAuditFile'])
        receipt = json.loads(path.read_text(encoding='utf-8'))
        receipt['calls'][0].pop('interaction')
        write_json(path, receipt)
        with self.assertRaisesRegex(ValueError, 'actual enter/return evidence'):
            prepare(graph, review)

    def test_receipt_rejects_wrong_targets_and_hidden_semantic_relations(self):
        graph, review = self.case()
        compiled = prepare(graph, review)['graph']
        path = Path(review['qa']['entryAuditFile'])
        receipt = json.loads(path.read_text(encoding='utf-8'))
        receipt['calls'][0]['target'] = 'business-node.some-other-call'
        write_json(path, receipt)
        self.assertTrue(any('different implementation/context' in error for error in
                            receipt_errors(compiled, review, receipt['revision'])))
        compiled['presentation']['semanticExpectations']['entry'] = {'decisions': ['real-guard']}
        self.assertTrue(any('hides required' in error for error in
                            receipt_errors(compiled, review, receipt['revision'])))

    def test_source_only_workflow_roots_must_be_audited(self):
        graph, review = self.case()
        compiled = prepare(graph, review)['graph']
        compiled['presentation']['businessDAG']['roots'] = {'source-only': 'prep'}
        manifest = entry_manifest(compiled)
        self.assertEqual([], manifest['scopes'])
        self.assertEqual('source', manifest['roots'][0]['expected'])
        path = Path(review['qa']['entryAuditFile'])
        receipt = json.loads(path.read_text(encoding='utf-8'))
        receipt.update(scopes=[], calls=[], roots=[])
        write_json(path, receipt)
        self.assertTrue(any('missing source/boundary' in error for error in
                            receipt_errors(compiled, review, receipt['revision'])))

    def test_revision_excludes_receipts_but_keeps_business_fields_with_same_names(self):
        graph, review = self.case()
        original = revision(graph, review)
        review['qa']['agent'] = 'another-reviewer'
        self.assertEqual(original, revision(graph, review))
        graph['project']['qa'] = 'Business capability, not a receipt.'
        self.assertNotEqual(original, revision(graph, review))

    def test_runtime_inventory_matches_the_python_manifest_and_restores_state(self):
        graph, review = self.case()
        graph = prepare(graph, review)['graph']
        factory = (ROOT / 'skills/litflux/assets/entry-audit.js').read_text(encoding='utf-8')
        manifest = entry_manifest(graph)
        script = 'const create=' + factory + ';const model=' + json.dumps(graph) + ';const expected=' + json.dumps(manifest) + ''';
let restores=0,scopes=0;
const declaredReading=d=>{const order=d.expectedDecisions.concat(d.expectedActiveCalls);return {order,complete:true,iterationComplete:true,blocked:[],invalid:[],interaction:{started:true,advanced:order.length,selected:order}};};
const auditor=create({dag:model.presentation.businessDAG,expectations:model.presentation.semanticExpectations,readings:model.presentation.readingManifest,readCase:declaredReading,revision:'test',snapshot:()=>({}),
 guides:()=>expected.guides,probeGuide:d=>({enabled:true,entered:true,returned:true,target:d.definition}),
 probeCall:()=>({entered:true,returned:true}),
 restore:()=>restores++,openScope:()=>scopes++,availability:id=>id.endsWith('.0')?
 {enabled:true,mode:'source',target:'business-node.prep'}:{enabled:false,reason:'Declared external boundary.'}});
if(JSON.stringify(auditor.listEntries())!==JSON.stringify(expected))throw Error('Call identities differ across compiler/viewer');
const result=auditor.auditEntries();
if(result.status!=='passed'||restores!==1||scopes!==3||result.calls.length!==6)throw Error('Bulk audit lost scopes, tiers or restore');
'''
        result = subprocess.run(['node'], input=script, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_runtime_audit_rejects_missing_relations_and_source_root_fallback(self):
        graph, review = self.case()
        graph = prepare(graph, review)['graph']
        factory = (ROOT / 'skills/litflux/assets/entry-audit.js').read_text(encoding='utf-8')
        script = 'const create=' + factory + ';const model=' + json.dumps(graph) + ''';
let restores=0;
const api={dag:model.presentation.businessDAG,expectations:{entry:{decisions:['guard'],resources:['db']}},
 snapshot:()=>({}),restore:()=>restores++,openScope:()=>({decisions:['guard'],resources:[]}),
 availability:()=>({enabled:true,mode:'source',target:'business-node.wrong'})};
const result=create(api).auditEntries();
if(result.status!=='failed'||!result.scopes.every(x=>x.missing.resources.includes('db'))||restores!==1)
 throw Error('Hidden resource relation or state restoration was lost');
api.dag={...api.dag,roots:{source:'prep'}};api.openRoot=()=>{};
api.rootAvailability=()=>({enabled:true,mode:'graph',target:'business-node.prep'});
const roots=create(api).auditEntries();
if(roots.status!=='failed'||roots.roots[0].status!=='failed')throw Error('Source root entered an incorrect graph');
'''
        result = subprocess.run(['node'], input=script, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_runtime_audit_reports_failed_state_restoration(self):
        factory = (ROOT / 'skills/litflux/assets/entry-audit.js').read_text(encoding='utf-8')
        script = 'const create=' + factory + ''';
const result=create({dag:{nodes:[],roots:{}},snapshot:()=>({}),restore:()=>false}).auditEntries();
if(result.status!=='failed'||result.failures[0].kind!=='stateRestoreMismatch')throw Error('Failed restoration was reported as passed');
'''
        result = subprocess.run(['node'], input=script, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_background_audit_yields_progress_and_cancellation_restores_state(self):
        graph, review = self.case()
        graph = prepare(graph, review)['graph']
        factory = (ROOT / 'skills/litflux/assets/entry-audit.js').read_text(encoding='utf-8')
        script = 'const create=' + factory + ';const model=' + json.dumps(graph) + ''';
(async()=>{
 let restores=0,heartbeat=false;
 const declaredReading=d=>{const order=d.expectedDecisions.concat(d.expectedActiveCalls);return {order,complete:true,iterationComplete:true,blocked:[],invalid:[],interaction:{started:true,advanced:order.length,selected:order}};};
 const api={dag:model.presentation.businessDAG,readings:model.presentation.readingManifest,readCase:declaredReading,snapshot:()=>({}),restore:()=>{restores++;},openScope:()=>({}),
  availability:id=>id.endsWith('.0')?{enabled:true,mode:'source',target:'business-node.prep'}:{enabled:false,reason:'External dependency'},
  probeCall:()=>({entered:true,returned:true})};
 const auditor=create(api);setTimeout(()=>{heartbeat=true},0);
 const started=auditor.startEntryAudit();
 if(started.status!=='running'||started.completed>=started.total)throw Error('Audit blocked its caller');
 const receipt=await auditor.auditEntriesAsync();
 if(!heartbeat||receipt.status!=='passed'||restores!==1||auditor.entryAuditStatus().completed!==12)throw Error('Cooperative audit lost coverage, heartbeat or restore');
 auditor.startEntryAudit();if(auditor.entryAuditResult()!==null)throw Error('An active audit leaked its stale receipt');
 auditor.cancelEntryAudit();await auditor.auditEntriesAsync();
 if(auditor.entryAuditStatus().status!=='cancelled'||restores!==2)throw Error('Cancellation failed to restore navigation');
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1});
'''
        result = subprocess.run(['node'], input=script, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_id_only_expansion_reports_the_nested_source_field(self):
        graph, review = self.case()
        graph['operations'][0]['expansion']['operations'] = ['prepare']
        with self.assertRaisesRegex(ValueError, r'operations\[0\]\.expansion\.operations\[0\].*inline business object'):
            prepare(graph, review, delivery=False)


if __name__ == '__main__':
    unittest.main()
