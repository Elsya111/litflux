"""Observable contract checks; run with python -B -m unittest discover -s tests."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "litflux"
sys.path.insert(0, str(SKILL / "scripts"))
from validate_graph import validate


def example():
    return json.loads((Path(__file__).resolve().parent / "fixtures" / "example.json").read_text(encoding="utf-8"))


def operations(graph):
    result = {}
    pending = list(graph["operations"])
    while pending:
        op = pending.pop()
        result[op["id"]] = op
        if op["expansion"]:
            pending.extend(op["expansion"]["operations"])
    return result


class ModelContractTests(unittest.TestCase):
    def test_reusable_definition_reference(self):
        graph = example()
        definition = copy.deepcopy(next(iter(operations(graph).values())))
        definition['id'] = 'def.reusable'
        definition['expansion'] = None
        definition.pop('stop', None)
        definition['inputs'] = [copy.deepcopy(definition['inputs'][0])]
        definition['outcomes'] = [{'id': 'done', 'condition': None, 'outputs': [copy.deepcopy(definition['outcomes'][0]['outputs'][0])]}]
        for endpoint, suffix in [(definition['inputs'][0], 'input'), (definition['outcomes'][0]['outputs'][0], 'output')]:
            ent = copy.deepcopy(next(e for e in graph['entities'] if e['id'] == endpoint['entity']))
            ent['id'] = 'def.entity.' + suffix
            graph['entities'].append(ent)
            endpoint['entity'] = ent['id']
        graph['definitions'] = [definition]
        graph['operations'][0]['implementation'] = definition['id']
        result = validate(graph)
        self.assertTrue(result['valid'], result['errors'])
        graph['operations'][0]['implementation'] = 'def.missing'
        self.assertIn('expected source definition', validate(graph)['errors'][0])

    def test_multiphase_nested_example(self):
        result = validate(example())
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["counts"], {"entities": 9, "resources": 1, "components": 0, "operations": 9, "phases": 3, "expansions": 3, "events": 0})

    def test_invalid_contracts(self):
        def missing_entity(graph, ops):
            ops["op.build"]["inputs"][0]["entity"] = "missing"

        def phase_cycle(graph, ops):
            graph["phases"][0]["requires"] = ["phase.startup"]

        def mismatched_boundary(graph, ops):
            ops["op.parse"]["inputs"][0]["entity"] = "ent.db"

        def missing_binding(graph, ops):
            ops["op.handle"]["expansion"]["bindings"].pop()

        def hidden_capture(graph, ops):
            ops["op.driver"]["inputs"].append({"port": "environment", "entity": "ent.source", "role": "capture", "required": True})

        def escaping_internal_output(graph, ops):
            external = copy.deepcopy(ops["op.format"])
            external["id"] = "op.external"
            external["inputs"][0]["entity"] = "ent.sql"
            graph["operations"].append(external)

        def duplicate_identity(graph, ops):
            graph["entities"].append(copy.deepcopy(graph["entities"][0]))

        def orphan_entity(graph, ops):
            orphan = copy.deepcopy(graph["entities"][0])
            orphan["id"] = "ent.orphan"
            graph["entities"].append(orphan)

        def unknown_type_without_reason(graph, ops):
            graph["entities"][0]["type"] = None

        def missing_completion(graph, ops):
            graph["phases"][1]["completion"] = None

        def unknown_signature_without_reason(graph, ops):
            ops["op.build"]["signature"] = None

        cases = [
            (missing_entity, "unknown reference"), (phase_cycle, "dependency cycle"),
            (mismatched_boundary, "boundary entity mismatch"), (missing_binding, "unmapped parent ports"),
            (hidden_capture, "undeclared external inputs"), (escaping_internal_output, "hidden output"),
            (duplicate_identity, "duplicate identity"), (orphan_entity, "orphan identities"),
            (unknown_type_without_reason, "typeReason"), (missing_completion, "required by another phase"),
            (unknown_signature_without_reason, "note"),
        ]
        for mutate, message in cases:
            with self.subTest(case=mutate.__name__):
                graph = example()
                mutate(graph, operations(graph))
                result = validate(graph)
                self.assertFalse(result["valid"])
                self.assertIn(message, result["errors"][0])

    def test_malformed_shapes_report_errors(self):
        for graph in (None, [], {}, {"schemaVersion": 123}):
            with self.subTest(value=graph):
                self.assertFalse(validate(graph)["valid"])
        graph = example()
        graph["operations"][0]["inputs"][0]["required"] = 1
        self.assertIn("expected boolean", validate(graph)["errors"][0])

    def test_returned_shared_resource_retains_identity(self):
        graph = example()
        ops = operations(graph)
        ops["op.driver"]["outcomes"][0]["outputs"].append({"port": "connection", "entity": "ent.db", "role": "reference", "label": "数据库连接"})
        self.assertTrue(validate(graph)["valid"])

    def test_phase_completion_cannot_use_hidden_internal_result(self):
        graph = example()
        ops = operations(graph)
        graph["phases"][1]["completion"]["entities"].append("ent.sql")
        result = validate(graph)
        self.assertFalse(result["valid"])
        self.assertIn("hidden output", result["errors"][0])

    def test_resource_read_must_use_an_input_port(self):
        graph = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'dataflow-example.json').read_text(encoding='utf-8'))
        op = operations(graph)['positive']
        op['accesses'] = [{'port': 'read', 'resource': 'db', 'mode': 'read', 'label': '读取',
                           'data': [], 'evidence': [graph['evidence'][0]['id']]}]
        result = validate(graph)
        self.assertFalse(result['valid'])
        self.assertIn("resourceMode 'read'", result['errors'][0])

    def test_aggregate_write_requires_a_real_descendant_write(self):
        graph = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'dataflow-example.json').read_text(encoding='utf-8'))
        save = next(op for op in graph['operations'] if op['id'] == 'save')
        save.pop('stop', None)
        child = {'id': 'write', 'name': 'write', 'definition': 'write',
                 'signature': 'write()', 'phase': save['phase'], 'trigger': 'all',
                 'operationKind': 'source-function', 'inputs': copy.deepcopy(save['inputs']),
                 'outcomes': [{'id': 'return', 'condition': None, 'outputs': []}],
                 'effects': [], 'accesses': [{'port': 'insert', 'resource': 'db', 'mode': 'write',
                                              'label': '写入', 'data': ['result'], 'evidence': ['ev.example']}],
                 'evidence': ['ev.example'], 'expansion': None,
                 'explanation': {'purpose': 'Write result.', 'steps': [], 'result': 'No return.', 'caveats': []}}
        save['accesses'][0]['aggregate'] = True
        save['expansion'] = {'operations': [child], 'bindings': [
            {'outer': 'in/i0', 'operation': 'write', 'inner': 'in/i0'},
            {'outer': 'in/i1', 'operation': 'write', 'inner': 'in/i1'},
            {'outer': 'out/effect/insert', 'operation': 'write', 'inner': 'out/effect/insert'}]}
        result = validate(graph)
        self.assertTrue(result['valid'], result['errors'])
        child['accesses'][0]['aggregate'] = True
        result = validate(graph)
        self.assertFalse(result['valid'])
        self.assertIn('aggregate write needs a real expansion', result['errors'][0])

    def test_decision_merge_must_be_a_real_non_exclusive_node(self):
        graph = example()
        operations_table = operations(graph)
        operation_id = next(iter(operations_table))
        decision = {'id': 'dec.merge', 'owner': operation_id, 'question': 'Which path?',
                    'condition': 'ready', 'inputs': [graph['entities'][0]['id']],
                    'yes': [operation_id], 'no': [operation_id],
                    'evidence': [graph['evidence'][0]['id']], 'merge': 'missing'}
        graph.setdefault('presentation', {})['decisions'] = [decision]
        self.assertFalse(validate(graph)['valid'])
        decision['merge'] = operation_id
        decision['yesMembers'] = [operation_id]
        self.assertFalse(validate(graph)['valid'])
        decision['yesMembers'] = []
        self.assertTrue(validate(graph)['valid'], validate(graph)['errors'])

    def test_exception_decision_allows_empty_inputs_and_break_needs_merge(self):
        graph = example()
        operation_id = next(iter(operations(graph)))
        decision = {'id': 'dec.exception', 'kind': 'exception', 'owner': operation_id,
                    'question': 'Did this round raise?', 'condition': 'raises', 'inputs': [],
                    'yes': [operation_id], 'no': [operation_id],
                    'evidence': [graph['evidence'][0]['id']]}
        graph.setdefault('presentation', {})['decisions'] = [decision]
        self.assertTrue(validate(graph)['valid'], validate(graph)['errors'])
        decision['kind'] = 'break'
        decision['inputs'] = [graph['entities'][0]['id']]
        self.assertFalse(validate(graph)['valid'])
        decision['merge'] = operation_id
        self.assertTrue(validate(graph)['valid'], validate(graph)['errors'])

    def test_cli_exit_status_and_report(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "graph.json"
            for contents, expected in ((json.dumps(example()), 0), ("{broken", 1)):
                path.write_text(contents, encoding="utf-8")
                result = subprocess.run([sys.executable, "-B", str(SKILL / "scripts" / "validate_graph.py"), str(path)], capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(json.loads(result.stdout)["valid"], expected == 0)


if __name__ == "__main__":
    unittest.main()
