"""Metamorphic tests on allowed cases; no expected verdicts are consulted."""
import copy
import json
from pathlib import Path
import unittest

from reader import assess, assess_json, verify_bundle

INPUTS = Path(__file__).resolve().parents[1] / 'inputs'


def reverse_objects(value):
    if isinstance(value, dict):
        return {key: reverse_objects(child) for key, child in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reverse_objects(child) for child in value]
    return value


class BundleProperties(unittest.TestCase):
    def test_all_manifest_cases_emit_one_deterministic_result(self):
        paths = verify_bundle(INPUTS)
        self.assertTrue(paths)
        self.assertEqual(len(paths), len({p.stem for p in paths}))
        for path in paths:
            with self.subTest(case=path.stem):
                raw = path.read_bytes()
                result = assess_json(raw)
                self.assertEqual(result, assess_json(raw))
                self.assertIn(result['verdict'], ('accept', 'reject', 'cannot-tell'))
                self.assertTrue(result['grounds'])
                self.assertTrue(result['reason'])

    def test_case_results_are_invariant_to_unordered_input_permutations(self):
        for path in verify_bundle(INPUTS):
            with self.subTest(case=path.stem):
                data = json.loads(path.read_text())
                expected = assess(data)
                changed = reverse_objects(copy.deepcopy(data))
                report = changed.get('subject', {})
                for key in ('checks', 'evidence'):
                    if isinstance(report.get(key), list):
                        report[key].reverse()
                for ev in report.get('evidence', []):
                    if not isinstance(ev, dict):
                        continue
                    for key in ('observations', 'moved', 'compared'):
                        if isinstance(ev.get(key), list):
                            ev[key].reverse()
                    delta = ev.get('delta', {})
                    if isinstance(delta, dict) and isinstance(delta.get('changes'), list):
                        delta['changes'].reverse()
                self.assertEqual(expected, assess(changed))


if __name__ == '__main__':
    unittest.main(verbosity=2)
