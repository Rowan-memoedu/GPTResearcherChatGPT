from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from mcp_state import CONTENT_FIELDS, CONSTRUCTOR_FIELDS, DurableResearchers, JsonStore


class ResearchStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gptr-state-', dir='D:/Caches/GPTResearcher/tmp')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state.sqlite3'

    def test_restart_restores_content_without_serializing_authorization(self):
        obj = SimpleNamespace(**{name: None for name in CONSTRUCTOR_FIELDS + CONTENT_FIELDS})
        obj.query = 'public fixture'
        obj.context = ['A file context manager closes the file on exit.']
        obj.visited_urls = {'https://docs.python.org/3/tutorial/inputoutput.html'}
        obj.research_sources = [{'title': 'Python docs', 'content': 'A public source'}]
        obj.research_costs = 1.25
        obj.tone = 'Objective'
        obj.headers = {'authorization': 'must-not-be-saved'}
        obj.cfg = SimpleNamespace(secret='must-not-be-saved')
        DurableResearchers(self.path, SimpleNamespace)['fixture-id'] = obj
        reopened = DurableResearchers(self.path, SimpleNamespace)
        self.assertIn('fixture-id', reopened)
        restored = reopened['fixture-id']
        self.assertEqual(restored.context, obj.context)
        self.assertEqual(restored.research_sources, obj.research_sources)
        self.assertEqual(restored.visited_urls, obj.visited_urls)
        self.assertEqual(restored.research_costs, 1.25)
        self.assertNotIn(b'must-not-be-saved', self.path.read_bytes())
        self.assertIsNot(restored, reopened['fixture-id'])

    def test_topic_cache_and_research_ids_have_separate_namespaces(self):
        first = JsonStore(self.path, 'topics')
        first['same'] = {'context': ['saved']}
        self.assertNotIn('same', JsonStore(self.path, 'researchers'))
        self.assertEqual(JsonStore(self.path, 'topics')['same']['context'], ['saved'])

    def test_full_database_preserves_previously_saved_result(self):
        store = JsonStore(self.path, 'bounded', max_bytes=32768)
        store['prior'] = {'context': 'keep'}
        with self.assertRaises(RuntimeError):
            store['huge'] = {'context': 'x' * 100000}
        self.assertEqual(store['prior']['context'], 'keep')
        self.assertNotIn('huge', store)

    def test_failed_serialization_does_not_replace_saved_result(self):
        store = JsonStore(self.path, 'atomic')
        store['id'] = {'context': 'keep'}
        with self.assertRaises(TypeError):
            store['id'] = {'bad': object()}
        self.assertEqual(store['id']['context'], 'keep')


if __name__ == '__main__':
    unittest.main()
