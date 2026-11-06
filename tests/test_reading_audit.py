"""Final acceptance requires local branch coverage and actual reading interactions."""
import copy
import json
import unittest
from pathlib import Path

from test_build_gate import full_review, write_json
from test_business_dag import fixture
from compile_review import prepare
from quality_audit import entry_manifest, receipt_errors


class ReadingAuditTests(unittest.TestCase):
    def test_final_gate_rejects_missing_cursor_or_changed_execution_order(self):
        graph, spec = fixture(); review = full_review(spec)
        prepared = prepare(graph, review); model = prepared['graph']
        path = Path(review['qa']['entryAuditFile']); original = json.loads(path.read_text(encoding='utf-8'))
        for mutate, pattern in ((lambda r: r.pop('readings'), 'reading cases'),
                (lambda r: r['readings'][0]['interaction'].update(started=False), 'UI walkthrough'),
                (lambda r: r['readings'][0]['order'].reverse(), 'source data/control order'),
                (lambda r: r['readings'][0]['executed'].append({'kind': 'component'}), 'availability')):
            receipt = copy.deepcopy(original); mutate(receipt); write_json(path, receipt)
            self.assertTrue(any(pattern in e for e in receipt_errors(model, review, prepared['qualityRevision'])))

    def test_nested_choices_do_not_enumerate_inactive_descendants(self):
        graph, spec = fixture(); review = full_review(spec)
        model = prepare(graph, review, delivery=False)['graph']
        source = {'path': 'app.py', 'startLine': 1, 'endLine': 1}
        model['presentation']['decisions'] = [
            {'id': 'outer', 'owner': 'service', 'inputs': ['request'], 'yes': ['prepare'], 'no': ['execute'], 'guards': [], 'source': source},
            {'id': 'inner', 'owner': 'service', 'inputs': ['terms'], 'yes': ['prepare'], 'no': ['execute'], 'guards': [{'decision': 'outer', 'side': 'yes'}], 'source': source},
            {'id': 'deep', 'owner': 'service', 'inputs': ['terms'], 'yes': ['prepare'], 'no': ['execute'], 'guards': [{'decision': 'inner', 'side': 'yes'}], 'source': source}]
        manifest = entry_manifest(model)
        cases = [r['choices'] for r in manifest['readings'] if r['tier'] == 100]
        self.assertEqual(4, len(cases))
        self.assertIn({'outer': 'no'}, cases)
        self.assertFalse(any(c.get('outer') == 'no' and 'deep' in c for c in cases))

    def test_local_manifest_covers_three_tiers_and_hidden_data_source_order(self):
        graph, spec = fixture(); review = full_review(spec); model = prepare(graph, review, delivery=False)['graph']
        cases = entry_manifest(model)['readings']
        self.assertEqual({0, 50, 100}, {c['tier'] for c in cases})
        self.assertTrue(all({'before': 'business.business-node.entry.0', 'after': 'business.business-node.entry.1'} in c['expectedOrder'] for c in cases))


if __name__ == '__main__': unittest.main()
