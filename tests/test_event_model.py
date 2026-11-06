"""Event boundary roles and 0.3 component actions are source-backed, not decorations."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/litflux/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_graph import validate
from business_dag import compile_dag
from test_business_dag import fixture

EXAMPLE = Path(__file__).resolve().parents[1] / 'skills/litflux/references/event-example.json'


def event_graph():
    return json.loads(EXAMPLE.read_text(encoding='utf-8'))


def component_graph(action=None):
    output = {'port': 'engine', 'entity': 'engine', 'role': 'reference', 'label': '选定组件'}
    if action:
        output['componentAction'] = action
    return {
        'schemaVersion': '0.3',
        'project': {'name': 'component action fixture', 'scope': 'A declared component reference.',
                    'sourceKind': 'declaration',
                    'coverage': [{'entry': 'make engine', 'kind': 'business', 'status': 'covered',
                                  'operations': ['svc'], 'reason': None}]},
        'evidence': [{'id': 'ev.example', 'kind': 'declaration', 'ref': None, 'note': 'Declared fixture.'}],
        'entities': [], 'resources': [],
        'components': [{'id': 'engine', 'name': 'engine', 'kind': 'component', 'scope': 'svc',
                        'type': 'Engine', 'evidence': ['ev.example']}],
        'events': [],
        'phases': [{'id': 'main', 'label': 'main', 'requires': [], 'completion': None,
                    'evidence': ['ev.example']}],
        'operations': [{
            'id': 'svc', 'name': 'make engine', 'definition': 'fixture.make',
            'signature': 'make() -> Engine', 'phase': 'main', 'trigger': 'all',
            'operationKind': 'source-function', 'inputs': [],
            'outcomes': [{'id': 'ok', 'condition': None, 'outputs': [output]}],
            'accesses': [], 'effects': [], 'evidence': ['ev.example'], 'expansion': None,
            'source': {'path': 'fixture.py', 'startLine': 1, 'endLine': 2, 'url': None},
            'explanation': {'purpose': 'Return the selected component.', 'steps': [],
                            'result': 'A component reference.', 'caveats': []}
        }],
        'definitions': [], 'unknowns': [],
        'presentation': {'language': 'en', 'authoringLanguage': 'en',
                         'workflows': [{'id': 'main', 'root': 'svc', 'label': 'Make engine',
                                        'description': 'Expose the component reference.'}]}
    }


class EventModelTests(unittest.TestCase):
    def test_event_example_is_valid(self):
        result = validate(event_graph())
        self.assertTrue(result['valid'], result['errors'])
        self.assertEqual(2, result['counts']['events'])

    def test_event_needs_data_output(self):
        graph = event_graph()
        graph['events'][0]['outputs'] = []
        self.assertFalse(validate(graph)['valid'])

    def test_event_output_needs_a_consumer(self):
        graph = event_graph()
        graph['operations'][0]['inputs'] = []
        self.assertFalse(validate(graph)['valid'])

    def test_event_cannot_be_an_operation(self):
        graph = event_graph()
        graph['events'][0]['inputs'] = [{'port': 'x', 'entity': 'query.request', 'role': 'argument', 'required': True}]
        self.assertFalse(validate(graph)['valid'])

    def test_event_workflow_must_exist(self):
        graph = event_graph()
        graph['events'][0]['workflow'] = 'unknown'
        self.assertFalse(validate(graph)['valid'])

    def test_component_reference_requires_component_action_in_0_3(self):
        self.assertFalse(validate(component_graph())['valid'])
        self.assertTrue(validate(component_graph('select'))['valid'])

    def test_event_output_must_be_visible_in_root_view(self):
        graph, spec = fixture()
        graph['schemaVersion'] = '0.3'
        graph['events'] = [{'id': 'event.http', 'workflow': 'main', 'outputs': ['reply']}]
        compile_dag(graph, spec)
        graph['events'][0]['outputs'] = ['unknown-event-data']
        with self.assertRaisesRegex(ValueError, 'Event output data must be visible'):
            compile_dag(graph, spec)


if __name__ == '__main__':
    unittest.main()
