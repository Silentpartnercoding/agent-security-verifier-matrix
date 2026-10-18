"""Specification-only regressions for partial evidence and counter bounds."""
import json
from pathlib import Path
import unittest

from reader import assess, verify_bundle
from test_reader import demonstrated, report


class PartialEvidenceReviewTests(unittest.TestCase):
    def test_1_missing_configuration_does_not_hide_checker_mismatch(self):
        data = report()
        data['subject']['fixed'] = {'checker': 'checker@one', 'constraint-set': 'configuration'}
        data['subject']['roll-up']['negative-capable'] = {
            'kind': 'control-failed',
            'control': {'state': 'fail', 'checks': ['check-0'],
                        'fixed': {'checker': 'checker@two'}}}
        result = assess(data)
        self.assertEqual(result['verdict'], 'reject', result)
        self.assertIn('§5.4 checker/configuration binding', result['grounds'])

    def test_2_missing_checker_does_not_hide_constraint_mismatch(self):
        data = report()
        data['subject']['fixed'] = {'checker': 'checker@one', 'constraint-set': 'configuration-a'}
        data['subject']['roll-up']['negative-capable'] = {
            'kind': 'control-failed',
            'control': {'state': 'fail', 'checks': ['check-0'],
                        'fixed': {'constraint-set': 'configuration-b'}}}
        result = assess(data)
        self.assertEqual(result['verdict'], 'reject', result)
        self.assertIn('§5.4 checker/configuration binding', result['grounds'])

    def test_3_rule_conflict_preserves_agreed_verdict_for_row13(self):
        data = demonstrated()
        ev = data['subject']['evidence'][0]
        ev['compared'] = ['verdict']
        ev['moved'] = ['verdict']
        ev['observations'] = [
            {'carried': {'verdict': 'pass', 'rules': []},
             'reference': {'vector': 'agreed-verdict', 'sha256': 'a' * 64}},
            {'carried': {'verdict': 'pass'}}]
        data['resolves']['agreed-verdict'] = {
            'verdict': 'pass', 'rules': ['conflicting-rule'], 'sha256': 'a' * 64}
        result = assess(data)
        self.assertEqual(result['verdict'], 'reject', result)
        self.assertIn('§4 row 13', result['grounds'])

    def test_4a_impossible_synthetic_disclosure_counter_is_not_accepted(self):
        data = report()
        data['subject']['roll-up']['carried'] = 100
        result = assess(data)
        self.assertEqual(result['verdict'], 'cannot-tell', result)
        self.assertIn('§5.3 disclosure counter', result['grounds'])
        self.assertIn('exceeds', result['reason'])

    def test_4b_supplied_impossible_reference_counters_are_explicit(self):
        # Select by the textual population bound, never by case ID or label.
        applicable = 0
        inputs = Path(__file__).resolve().parents[1] / 'inputs'
        for path in verify_bundle(inputs):
            data = json.loads(path.read_text())
            subject = data['subject']
            referenced = subject.get('roll-up', {}).get('referenced')
            verdicts = sum(check.get('state') in ('pass', 'fail') for check in subject['checks'])
            if type(referenced) is not int or referenced <= verdicts:
                continue
            applicable += 1
            with self.subTest(case=path.stem):
                result = assess(data)
                self.assertNotEqual(result['verdict'], 'accept', result)
                grounds = result['grounds'] + [item['ground'] for item in result.get('unresolved', [])]
                reasons = result['reason'] + ' '.join(item['reason'] for item in result.get('unresolved', []))
                self.assertIn('§5.3 disclosure counter', grounds)
                self.assertIn('exceeds', reasons)
        self.assertGreater(applicable, 0)

    def test_5_partial_carriage_cannot_hide_resolved_verdict_contradiction(self):
        for carried in ({}, {'rules': []}):
            with self.subTest(carried=carried):
                data = demonstrated()
                ev = data['subject']['evidence'][0]
                ev['compared'] = ['verdict']
                ev['moved'] = ['verdict']
                ev['observations'] = [
                    {'carried': carried,
                     'reference': {'vector': 'resolved-verdict', 'sha256': 'a' * 64}},
                    {'carried': {'verdict': 'pass'}}]
                data['resolves']['resolved-verdict'] = {
                    'verdict': 'pass', 'sha256': 'a' * 64}
                result = assess(data)
                self.assertEqual(result['verdict'], 'reject', result)
                self.assertIn('§4 row 13', result['grounds'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
