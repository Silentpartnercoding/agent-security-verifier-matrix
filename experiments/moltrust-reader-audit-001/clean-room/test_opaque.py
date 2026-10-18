"""Specification-only tests of the machine-comparable/opaque boundary."""
import unittest

from reader import assess
from test_reader import demonstrated


def resolved_pair():
    data = demonstrated()
    data['subject']['evidence'][0]['observations'] = [
        {'reference': {'vector': 'left', 'sha256': 'a' * 64}},
        {'reference': {'vector': 'right', 'sha256': 'b' * 64}}]
    data['resolves'] = {
        'left': {'verdict': 'pass', 'rules': [], 'sha256': 'a' * 64},
        'right': {'verdict': 'fail', 'rules': ['changed-rule'], 'sha256': 'b' * 64}}
    data['subject']['roll-up'].update(carried=0, referenced=1)
    return data


class OpaqueProjectionReviewTests(unittest.TestCase):
    def test_opaque_error_list_does_not_invalidate_correct_comparable_moved(self):
        data = resolved_pair()
        data['subject']['evidence'][0]['moved'].append('error list')
        result = assess(data)
        self.assertEqual(result['verdict'], 'accept', result)

    def test_opaque_addition_leaves_real_comparable_mismatch_isolated(self):
        data = resolved_pair()
        data['resolves']['left'].update(verdict='fail', rules=['old-rule'])
        data['subject']['evidence'][0]['moved'] = ['verdict', 'error list']
        result = assess(data)
        self.assertEqual(result['verdict'], 'reject', result)
        # Rule-list movement contradicts the declared verdict movement.
        # The opaque primitive itself must add no rejection/uncertainty.
        self.assertEqual(set(result['grounds']), {'§2 moved recomputation', '§4 row 13'}, result)
        self.assertNotIn('unresolved', result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
