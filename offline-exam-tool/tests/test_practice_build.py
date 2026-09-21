"""Run: python -m unittest discover -s offline-exam-tool/tests -p 'test_*.py'."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL))
from build_practice_data import build_practice_data


class PracticeIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = (TOOL / 'data.js').read_text(encoding='utf-8')
        cls.data = json.loads(raw[len('window.EXAM_DATA='):].strip().removesuffix(';'))

    def test_catalog_matches_reviewed_source(self):
        catalog = build_practice_data(self.data, TOOL.parent)
        self.assertEqual(set(catalog['subjects']), {'文字・词汇', '语法'})
        grammar = {q['id'] for exam in self.data['exams'].values() for q in exam['语法']}
        tagged = {qid for qid, meta in catalog['questions'].items() if meta['subject'] == '语法'}
        self.assertEqual(tagged, grammar)
        self.assertEqual(len(tagged), 609)
        self.assertEqual(len(catalog['questions']), 1384)
        for q in catalog['questions'].values():
            if q['problemNumber'] == 7:
                self.assertGreater(len(q['sharedPassage']), 100)

    def test_stale_annotation_rejected(self):
        data = json.loads(json.dumps(self.data))
        data['exams']['2025.12']['文字'][0]['rightAnswer'] = 999
        with self.assertRaisesRegex(ValueError, 're-review'):
            build_practice_data(data, TOOL.parent)

    def test_special_history_roundtrip_and_latest_merge(self):
        spec = importlib.util.spec_from_file_location('test_exam_server', TOOL / 'start_offline_exam.py')
        server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server)
        with tempfile.TemporaryDirectory() as directory:
            server.RECORDS_DIR = Path(directory) / 'records'
            record = {'id': 'test-special', 'mode': 'special', 'year': '专项练习', 'category': '文字・词汇＋语法',
                      'submittedAt': '2026-09-20T10:00:00Z', 'timezoneOffsetMinutes': -480,
                      'practice': {'filters': {'subject': '', 'problem': '', 'tag': ''}, 'questionIds': ['a', 'b']},
                      'details': [{'id': 'a', 'sourceYear': '2025.12', 'sourceCategory': '文字', 'selected': [1], 'results': [True]},
                                  {'id': 'b', 'sourceYear': '2021.07', 'sourceCategory': '语法', 'order': [2, 1, 3, 4], 'results': [False]}]}
            server.save_records([record])
            server.save_records([record])
            self.assertEqual(server.read_history(), [record])
            self.assertEqual(len(list(server.RECORDS_DIR.glob('*.json'))), 1)


if __name__ == '__main__':
    unittest.main()
