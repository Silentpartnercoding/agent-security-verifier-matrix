"""Regression tests for the seven specification-only review findings.

All fixtures are synthetic and contain no neutral case IDs or oracle results.
"""
import copy
import unittest

from reader import Reader, assess
from test_reader import demonstrated, evidence, report


class SpecificationReviewTests(unittest.TestCase):
    def test_1_missing_prior_adapter_identity_is_uncertain(self):
        data = report()
        data['subject']['roll-up']['negative-capable'] = {
            'kind': 'prior-discriminating-run',
            'reference': {'sha256': 'a' * 64}}
        result = assess(data)
        self.assertEqual(result['verdict'], 'cannot-tell', result)

    def test_2_opaque_projection_cannot_hide_supported_moved_falsehood(self):
        data = demonstrated()
        ev = data['subject']['evidence'][0]
        ev['compared'].append('opaque projection')
        ev['moved'] = ['verdict', 'opaque projection']
        result = assess(data)
        self.assertEqual(result['verdict'], 'reject', result)
        self.assertIn('§2 moved recomputation', result['grounds'])

    def test_3_verdict_only_evidence_needs_no_rule_projection(self):
        ev = evidence()
        ev['compared'] = ['verdict']
        ev['moved'] = ['verdict']
        for observation in ev['observations']:
            del observation['carried']['rules']
        reader = Reader({})
        reader.domain = 'domain'
        result = reader.inspect_evidence(ev)
        self.assertEqual(result['moved'], {'verdict'})
        self.assertEqual(reader.f.result()['verdict'], 'accept', reader.f.result())

    def test_4_matching_control_fixed_digests_can_satisfy_binding(self):
        data = report()
        fixed = {'checker': 'sha256:' + 'a' * 64,
                 'constraint-set': 'sha256:' + 'b' * 64}
        data['subject']['fixed'] = fixed
        data['subject']['roll-up']['negative-capable'] = {
            'kind': 'control-failed',
            'control': {'state': 'fail', 'checks': ['check-0'],
                        'fixed': copy.deepcopy(fixed)}}
        result = assess(data)
        self.assertEqual(result['verdict'], 'accept', result)

    def test_5_unshared_uniform_evidence_has_no_counter_ambiguity(self):
        data = demonstrated()
        result = assess(data)
        self.assertEqual(result['verdict'], 'accept', result)

        shared = copy.deepcopy(data)
        shared['subject']['checks'].append({
            'check': 'another-check', 'state': 'fail',
            'other-verdict': {'value': 'demonstrated', 'ref': 'pair'}})
        shared['subject']['roll-up'].update(declared=2, exercised=2, fail=1)
        result = assess(shared)
        self.assertEqual(result['verdict'], 'cannot-tell', result)
        self.assertIn('§5.3 disclosure counter', result['grounds'])

    def test_6_optional_arity_and_absent_rollup_create_no_uncertainty(self):
        with self.subTest(optional='arity'):
            reader = Reader({})
            reader.domain = 'domain'
            ev = evidence()
            ev['delta']['arity'] = 100
            reader.inspect_evidence(ev)
            self.assertEqual(reader.f.result()['verdict'], 'accept', reader.f.result())
        with self.subTest(optional='roll-up'):
            data = report()
            del data['subject']['roll-up']
            self.assertEqual(assess(data)['verdict'], 'accept', assess(data))

    def test_7_anonymous_evidence_still_gets_form_validation(self):
        data = report()
        ev = evidence()
        del ev['id']
        del ev['observations']
        data['subject']['evidence'] = [ev]
        result = assess(data)
        self.assertEqual(result['verdict'], 'reject', result)
        self.assertIn('§4 row 14', result['grounds'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
