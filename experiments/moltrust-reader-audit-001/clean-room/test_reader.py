"""Synthetic specification tests. No neutral case IDs or expected corpus outcomes."""
import copy
import json
import unittest

from reader import assess, assess_json


def report(states=('pass',)):
    checks = [{'check': 'check-' + str(i), 'state': s} for i, s in enumerate(states)]
    for check in checks:
        if check['state'] not in ('pass', 'fail'):
            check['cause'] = {'code': 'unavailable'}
    counts = {s: states.count(s) for s in
              ('pass', 'fail', 'not-exercised', 'inconclusive', 'void')}
    rollup = dict(counts, declared=len(checks),
                  exercised=len(checks) - counts['not-exercised'],
                  carried=0, referenced=0)
    rollup['negative-capable'] = {'kind': 'shown-by-run' if counts['fail'] else 'nothing'}
    return {'subjectType': 'report', 'subject': {
        'domain': {'id': 'domain'}, 'checks': checks,
        'evidence': [], 'roll-up': rollup}, 'resolves': {}}


def evidence(identifier='pair'):
    return {'id': identifier, 'changed': 'input artifact',
            'fixed': {'checker': 'checker@revision', 'constraint-set': 'constraints',
                      'domain': 'domain'},
            'compared': ['verdict', 'fired-rule list'],
            'moved': ['verdict', 'fired-rule list'],
            'delta': {'changes': [{'field': 'input/x', 'before': 0, 'after': 1}]},
            'observations': [{'carried': {'verdict': 'pass', 'rules': []}},
                             {'carried': {'verdict': 'fail', 'rules': ['rule']}}]}


def demonstrated():
    data = report()
    data['subject']['evidence'] = [evidence()]
    data['subject']['checks'][0]['other-verdict'] = {'value': 'demonstrated', 'ref': 'pair'}
    # The counter is disclosure, not a rejection row (§5.3).
    data['subject']['roll-up']['carried'] = 1
    return data


class ReaderTests(unittest.TestCase):
    def assertReject(self, data, ground):
        result = assess(data)
        self.assertEqual(result['verdict'], 'reject', result)
        self.assertIn(ground, result['grounds'], result)

    def test_plain_record_defaults_to_unknown(self):
        self.assertEqual(assess(report())['verdict'], 'accept')

    def test_each_nonverdict_needs_cause(self):
        for state in ('not-exercised', 'inconclusive', 'void'):
            data = report((state,))
            del data['subject']['checks'][0]['cause']
            self.assertReject(data, '§4 row 1')

    def test_void_invalid_dispositions(self):
        for code in ('not_applicable', 'out_of_scope', 'withheld'):
            data = report(('void',))
            data['subject']['checks'][0]['cause'] = {'code': code}
            self.assertReject(data, '§4 row 2')

    def test_integrity_not_exercised(self):
        data = report(('not-exercised',))
        data['subject']['checks'][0]['cause'] = {'code': 'integrity-failure'}
        self.assertReject(data, '§4 row 3')

    def test_confinement_is_void_only(self):
        for state in ('pass', 'fail', 'not-exercised', 'inconclusive'):
            data = report((state,))
            data['subject']['checks'][0]['cause'] = {'code': 'confinement-failed-during-check'}
            self.assertReject(data, '§4 row 4')
        data = report(('void',))
        data['subject']['checks'][0]['cause'] = {'code': 'confinement-failed-during-check'}
        self.assertEqual(assess(data)['verdict'], 'accept')

    def test_declared_exclusion(self):
        data = report()
        data['subject']['checks'][0]['declared-exclusion'] = True
        self.assertReject(data, '§4 row 5')

    def test_nonverdict_qualifier(self):
        data = report(('inconclusive',))
        data['subject']['checks'][0]['other-verdict'] = {'value': 'demonstrated', 'ref': 'pair'}
        self.assertReject(data, '§4 row 6')

    def test_verdict_cannot_carry_cause_even_null(self):
        for cause in ({'code': 'unavailable'}, None):
            data = report()
            data['subject']['checks'][0]['cause'] = cause
            self.assertReject(data, '§4 row 7')

    def test_foreclosed_and_discrimination(self):
        data = demonstrated()
        check = data['subject']['checks'][0]
        check['other-verdict'].update(value='foreclosed', domain='domain', **{'constraint-set': 'constraints'})
        check['discrimination'] = {'value': 'demonstrated', 'ref': 'pair'}
        self.assertReject(data, '§4 row 8')

    def test_discrimination_requires_other_demonstrated(self):
        for value in ('unknown', 'possible-not-demonstrated'):
            data = demonstrated()
            check = data['subject']['checks'][0]
            check['other-verdict'] = {'value': value}
            check['discrimination'] = {'value': 'demonstrated', 'ref': 'pair'}
            self.assertReject(data, '§4 row 9')

    def test_foreclosure_needs_domain_and_constraint(self):
        data = demonstrated()
        data['subject']['checks'][0]['other-verdict']['value'] = 'foreclosed'
        self.assertReject(data, '§4 row 10')

    def test_demonstration_needs_ref(self):
        data = demonstrated()
        del data['subject']['checks'][0]['other-verdict']['ref']
        self.assertReject(data, '§4 row 11')

    def test_checker_change_is_not_discrimination(self):
        data = demonstrated()
        data['subject']['checks'][0]['discrimination'] = {'value': 'demonstrated', 'ref': 'pair'}
        data['subject']['evidence'][0]['changed'] = 'checker rule'
        self.assertReject(data, '§4 row 12')

    def test_row13_uses_recomputed_not_declared_moved(self):
        data = demonstrated()
        ev = data['subject']['evidence'][0]
        ev['observations'][1]['carried']['verdict'] = 'pass'
        self.assertReject(data, '§4 row 13')

    def test_row14_needs_both_observations(self):
        data = demonstrated()
        data['subject']['evidence'][0]['observations'].pop()
        self.assertReject(data, '§4 row 14')

    def test_missing_digest_is_form_failure(self):
        data = demonstrated()
        data['subject']['evidence'][0]['observations'][0] = {'reference': {'vector': 'unavailable'}}
        self.assertReject(data, '§4 row 14')

    def test_unresolved_reference_does_not_fire_row13(self):
        data = demonstrated()
        data['subject']['evidence'][0]['observations'][0] = {
            'reference': {'vector': 'unavailable', 'sha256': 'a' * 64}}
        result = assess(data)
        self.assertEqual(result['verdict'], 'cannot-tell', result)
        self.assertNotIn('§4 row 13', result['grounds'])

    def test_digest_mismatch_is_integrity_failure(self):
        data = demonstrated()
        data['subject']['evidence'][0]['observations'][0] = {
            'reference': {'vector': 'resolved', 'sha256': 'a' * 64}}
        data['resolves']['resolved'] = {'sha256': 'b' * 64, 'verdict': 'pass', 'rules': []}
        self.assertReject(data, '§3 reading table')

    def test_moved_must_equal_recomputation(self):
        data = demonstrated()
        data['subject']['evidence'][0]['moved'] = ['verdict']
        self.assertReject(data, '§2 moved recomputation')

    def test_recomputed_moved_must_be_compared(self):
        data = demonstrated()
        data['subject']['evidence'][0]['compared'] = ['verdict']
        self.assertReject(data, '§2 moved subset')

    def test_no_change_cannot_demonstrate_discrimination(self):
        data = demonstrated()
        data['subject']['checks'][0]['discrimination'] = {'value': 'demonstrated', 'ref': 'pair'}
        ev = data['subject']['evidence'][0]
        ev['observations'][1] = copy.deepcopy(ev['observations'][0])
        ev['moved'] = []
        self.assertReject(data, '§1.3 discrimination')

    def test_domain_is_identifier_not_restated(self):
        data = demonstrated()
        data['subject']['evidence'][0]['fixed']['domain'] = {'id': 'domain'}
        self.assertReject(data, '§2 run domain')

    def test_domain_must_be_run_domain(self):
        data = demonstrated()
        data['subject']['evidence'][0]['fixed']['domain'] = 'different'
        self.assertReject(data, '§2 run domain')

    def test_fixed_slots_are_required(self):
        for key in ('checker', 'constraint-set', 'domain'):
            data = demonstrated()
            del data['subject']['evidence'][0]['fixed'][key]
            self.assertReject(data, '§2 fixed')

    def test_unknown_cause_is_rejected(self):
        data = report(('void',))
        data['subject']['checks'][0]['cause'] = {'code': 'arbitrary prose'}
        self.assertReject(data, '§1.2 cause vocabulary')

    def test_unknown_state_is_rejected(self):
        data = report()
        data['subject']['checks'][0]['state'] = 'unavailable'
        self.assertReject(data, '§1 state vocabulary')

    def test_missing_state_is_rejected(self):
        data = report()
        del data['subject']['checks'][0]['state']
        self.assertReject(data, '§1 state vocabulary')

    def test_malformed_data_fails_closed(self):
        for text in ('{', 'null', '[]', '{"subject":NaN}', '{"x":1,"x":2}'):
            self.assertNotEqual(assess_json(text)['verdict'], 'accept', text)
        for key, value in (('checks', None), ('evidence', {}), ('roll-up', [])):
            data = report()
            data['subject'][key] = value
            self.assertNotEqual(assess(data)['verdict'], 'accept')

    def test_duplicate_evidence_identifiers_are_never_overwritten(self):
        data = demonstrated()
        data['subject']['evidence'].append(evidence())
        first = assess(data)
        self.assertEqual(first['verdict'], 'cannot-tell', first)
        data['subject']['evidence'].reverse()
        self.assertEqual(first, assess(data))

    def test_duplicate_conflicting_evidence_is_order_invariant(self):
        data = demonstrated()
        other = evidence()
        other['changed'] = 'checker rule'
        data['subject']['evidence'].append(other)
        first = assess(data)
        self.assertNotEqual(first['verdict'], 'accept')
        data['subject']['evidence'].reverse()
        self.assertEqual(first, assess(data))

    def test_contradictory_carry_and_reference_fails_closed(self):
        data = demonstrated()
        item = data['subject']['evidence'][0]['observations'][0]
        item['reference'] = {'vector': 'contradiction', 'sha256': 'a' * 64}
        data['resolves']['contradiction'] = {'sha256': 'a' * 64, 'verdict': 'fail', 'rules': ['rule']}
        self.assertNotEqual(assess(data)['verdict'], 'accept')

    def test_check_evidence_and_object_order_invariance(self):
        data = demonstrated()
        data['subject']['checks'].append({'check': 'second', 'state': 'fail'})
        data['subject']['roll-up'].update(declared=2, exercised=2, fail=1)
        data['subject']['evidence'].append(evidence('another'))
        first = assess(data)
        data['subject']['checks'].reverse()
        data['subject']['evidence'].reverse()
        for ev in data['subject']['evidence']:
            ev['observations'].reverse()
            ev['compared'].reverse()
            ev['moved'].reverse()
        data = json.loads(json.dumps(data, sort_keys=True))
        self.assertEqual(first, assess(data))

    def test_aggregate_cannot_count_void_as_pass(self):
        data = report(('void',))
        data['subject']['roll-up']['pass'] = 1
        self.assertReject(data, '§1.1 state-only counts; §5.1 aggregate')

    def test_aggregate_needs_denominator(self):
        data = report()
        del data['subject']['roll-up']['declared']
        self.assertReject(data, '§5.1 complete denominator')

    def test_boolean_count_is_not_population_integer(self):
        data = report()
        data['subject']['roll-up']['declared'] = True
        self.assertReject(data, '§5.1 complete denominator')

    def test_completeness_population_and_empty_claim(self):
        data = report()
        data['subject']['roll-up']['completeness'] = {'accounting': {'claim': 'satisfied'}}
        self.assertReject(data, '§4 run-level completeness count')
        data = report(())
        data['subject']['roll-up']['completeness'] = {'accounting': {'claim': 'satisfied', 'population': 0}}
        self.assertReject(data, '§5.2 empty population')

    def test_no_void_claim_uses_declared_population(self):
        data = report(('pass', 'void'))
        data['subject']['roll-up']['completeness'] = {'no-void': {'claim': 'satisfied', 'population': 2}}
        self.assertReject(data, '§5.2 no-void claim')

    def test_execution_and_no_void_are_independent(self):
        data = report(('not-exercised',))
        data['subject']['roll-up']['completeness'] = {
            'execution': {'claim': 'not-satisfied', 'population': 1},
            'no-void': {'claim': 'satisfied', 'population': 1}}
        self.assertEqual(assess(data)['verdict'], 'accept')

    def test_shown_by_run_requires_fail(self):
        for state in ('pass', 'inconclusive', 'void'):
            data = report((state,))
            data['subject']['roll-up']['negative-capable'] = {'kind': 'shown-by-run'}
            self.assertReject(data, '§5.4 negative verdict')

    def test_negative_capability_cannot_be_silent(self):
        data = report()
        del data['subject']['roll-up']['negative-capable']
        self.assertReject(data, '§5.4 disclosure')

    def test_control_requires_fail_and_declared_check(self):
        for control in ({'state': 'inconclusive', 'checks': ['check-0']},
                        {'state': 'fail', 'checks': ['unrelated']}):
            data = report()
            data['subject']['roll-up']['negative-capable'] = {'kind': 'control-failed', 'control': control}
            self.assertReject(data, '§5.4 control')

    def test_control_binding_conflict(self):
        data = report()
        data['subject']['fixed'] = {'checker': 'checker@one', 'constraint-set': 'x'}
        data['subject']['roll-up']['negative-capable'] = {
            'kind': 'control-failed', 'control': {'state': 'fail', 'checks': ['check-0'],
                'fixed': {'checker': 'checker@two', 'constraint-set': 'x'}}}
        self.assertReject(data, '§5.4 checker/configuration binding')

    def test_control_missing_binding_is_undetermined_not_invented_rejection(self):
        data = report()
        data['subject']['roll-up']['negative-capable'] = {
            'kind': 'control-failed', 'control': {'state': 'fail', 'checks': ['check-0']}}
        self.assertEqual(assess(data)['verdict'], 'cannot-tell')

    def test_collection_requires_count_and_closed_shape(self):
        for value, ground in (({'sha256': 'a' * 64, 'tree-shape': 'flat'}, '§3.1 count binding'),
                              ({'sha256': 'a' * 64, 'leaf-count': 1, 'tree-shape': 'my prose'}, '§3.1 closed tree-shape set')):
            data = report()
            data['subject']['check-set'] = value
            self.assertReject(data, ground)

    def test_flat_hash_construction_is_not_invented(self):
        data = report()
        data['subject']['check-set'] = {'sha256': 'a' * 64, 'leaf-count': 1, 'tree-shape': 'flat'}
        result = assess(data)
        self.assertEqual(result['verdict'], 'cannot-tell')
        self.assertIn('§3.1; §11 O3', result['grounds'])

    def test_declared_arity_does_not_override_delta(self):
        data = demonstrated()
        baseline = assess(data)
        data['subject']['evidence'][0]['delta']['arity'] = 100
        self.assertEqual(assess(data), baseline)

    def test_two_fields_are_not_automatically_rejected(self):
        data = demonstrated()
        data['subject']['evidence'][0]['delta']['changes'].append({'field': 'input/y', 'before': 0, 'after': 1})
        self.assertNotEqual(assess(data)['verdict'], 'reject')

    def test_precondition_unsatisfiable_describes_a_check_that_cannot_run(self):
        data = report(('inconclusive',))
        data['subject']['checks'][0]['cause'] = {'code': 'precondition-unsatisfiable'}
        self.assertReject(data, '§1.2 precondition-unsatisfiable')

    def test_wrong_json_types_at_every_synthetic_field_do_not_crash(self):
        original = demonstrated()
        paths = []

        def walk(value, prefix=()):
            if isinstance(value, dict):
                for key, child in value.items():
                    paths.append(prefix + (key,))
                    walk(child, prefix + (key,))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    paths.append(prefix + (index,))
                    walk(child, prefix + (index,))

        walk(original)
        for path in paths:
            for malformed in (None, False, 17, '', [], {}):
                with self.subTest(path=path, value=malformed):
                    data = copy.deepcopy(original)
                    cursor = data
                    for key in path[:-1]:
                        cursor = cursor[key]
                    cursor[path[-1]] = copy.deepcopy(malformed)
                    self.assertIn(assess_json(json.dumps(data))['verdict'],
                                  ('accept', 'reject', 'cannot-tell'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
