"""Regressions reproduced in the isolated DeepSeek usage trial."""
import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/litflux'
sys.path.insert(0, str(SKILL / 'scripts'))
from validate_graph import validate


class Landmarks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.mains = 0
        self.panels = {}
        self.flow_title = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'main':
            self.mains += 1
        classes = attrs.get('class', '').split()
        for panel in ('sf-workflows', 'sf-overview', 'sf-main'):
            if panel in classes:
                self.panels[panel] = 'main' in self.stack
        if tag == 'h1' and 'sf-flow-title' in classes:
            self.flow_title = 'main' in self.stack and 'section' in self.stack
        if tag not in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                       'link', 'meta', 'param', 'source', 'track', 'wbr'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.stack:
            del self.stack[len(self.stack) - 1 - self.stack[::-1].index(tag):]


class DeepSeekRegressions(unittest.TestCase):
    def external_model(self):
        model = json.loads((SKILL / 'examples/authoring-cases.json').read_text(encoding='utf-8'))['cases']['simple']['model']
        model.setdefault('definitions', []).append({
            'id': 'external.probe', 'name': 'Known API boundary', 'operationKind': 'external',
            'definition': None, 'signature': None,
            'note': 'Known API; third-party implementation has not been read.',
            'phase': model['phases'][0]['id'], 'trigger': 'all', 'inputs': [],
            'outcomes': [{'id': 'done', 'condition': None, 'outputs': []}],
            'effects': [], 'evidence': [model['evidence'][0]['id']], 'expansion': None})
        return model

    def test_external_boundary_without_source_is_a_valid_complete_definition(self):
        result = validate(self.external_model())
        self.assertTrue(result['valid'], result['errors'])

    def test_present_source_must_be_an_object_even_for_external_apis(self):
        model = copy.deepcopy(self.external_model())
        model['definitions'][-1]['source'] = None
        result = validate(model)
        self.assertFalse(result['valid'])
        self.assertTrue(any('source: expected object' in error for error in result['errors']))

    def test_main_contains_each_page_and_flow_has_its_own_heading(self):
        parser = Landmarks()
        parser.feed((SKILL / 'assets/viewer.html').read_text(encoding='utf-8'))
        self.assertEqual(1, parser.mains)
        self.assertEqual({'sf-workflows': True, 'sf-overview': True, 'sf-main': True}, parser.panels)
        self.assertTrue(parser.flow_title)


if __name__ == '__main__':
    unittest.main()
