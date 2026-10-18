"""Conservative, stdlib-only reader derived from specification-v0.1.txt.

The neutral JSON envelope is an input adapter, not an inferred normative
schema. Explicit textual contradictions reject; missing semantic definitions
or unavailable evidence produce cannot-tell. No network or external code.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re

STATES = ('pass', 'fail', 'not-exercised', 'inconclusive', 'void')
VERDICTS = ('pass', 'fail')
CAUSES = frozenset(('not_applicable', 'disabled_by_policy', 'unsupported_input',
                   'resource_exhausted', 'failed', 'unavailable', 'out_of_scope',
                   'withheld', 'evidence-does-not-hold', 'integrity-failure',
                   'availability-failure', 'precondition-unsatisfiable',
                   'confinement-failed-during-check'))
SHAPES = ('flat', 'rfc6962', 'RFC9162_SHA256')
PROJECTIONS = {'verdict': 'verdict', 'fired-rule list': 'rules'}
OPAQUE_PROJECTIONS = frozenset(('error list',))


def text(value):
    return isinstance(value, str) and bool(value.strip())


def count(value):
    return type(value) is int and value >= 0


def strings(value):
    return isinstance(value, list) and all(text(v) for v in value)


def digest(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-fA-F]{64}', value) is not None


def stable(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


class Findings:
    def __init__(self):
        self.failures = set()
        self.uncertainties = set()

    def reject(self, ground, reason):
        self.failures.add((ground, reason))

    def uncertain(self, ground, reason):
        self.uncertainties.add((ground, reason))

    def result(self):
        selected = self.failures or self.uncertainties
        if not selected:
            return {'verdict': 'accept', 'grounds': ['§1', '§2', '§4', '§5'],
                    'reason': 'All applicable text-defined checks passed; no unresolved claim was found.'}
        verdict = 'reject' if self.failures else 'cannot-tell'
        ordered = sorted(selected)
        reasons = [reason for _, reason in ordered]
        result = {'verdict': verdict,
                  'grounds': sorted({ground for ground, _ in ordered}),
                  'reason': '; '.join(reasons)}
        if self.failures and self.uncertainties:
            result['unresolved'] = [{'ground': g, 'reason': r} for g, r in sorted(self.uncertainties)]
        return result


class Reader:
    def __init__(self, envelope):
        self.envelope = envelope
        self.f = Findings()
        self.domain = None
        self.store = {}
        self.evidence = collections.defaultdict(list)
        self.evidence_results = {}

    def run(self):
        if not isinstance(self.envelope, dict):
            self.f.uncertain('§1–§5 representation', 'Input is not a JSON object representing a report.')
            return self.f.result()
        if self.envelope.get('subjectType') != 'report' or not isinstance(self.envelope.get('subject'), dict):
            self.f.uncertain('§1–§5 representation', 'Report subject or subjectType is missing or unsupported; no normative JSON schema is supplied.')
            return self.f.result()
        report = self.envelope['subject']
        self.store = self.envelope.get('resolves', {})
        if not isinstance(self.store, dict):
            self.f.uncertain('§3 reading table', 'Resolver store is malformed.')
            self.store = {}
        domain = report.get('domain')
        if not isinstance(domain, dict) or not text(domain.get('id')):
            self.f.reject('§2 run domain', 'Run domain is not declared once with an identifier.')
        else:
            self.domain = domain['id']
        checks = report.get('checks')
        if not isinstance(checks, list) or not all(isinstance(c, dict) for c in checks):
            self.f.uncertain('§1–§5 representation', 'Declared checks are missing or are not a list of records.')
            return self.f.result()
        identifiers = [c.get('check') for c in checks]
        if not all(text(i) for i in identifiers):
            self.f.uncertain('§5.1 declared checks', 'A check has no usable declared identifier.')
        valid_ids = [i for i in identifiers if text(i)]
        if len(set(valid_ids)) != len(valid_ids):
            self.f.uncertain('§5.1 declared checks', 'Duplicate check identifiers leave the population identity ambiguous.')
        evidence = report.get('evidence', [])
        if not isinstance(evidence, list):
            self.f.uncertain('§2 evidence object', 'Evidence is not a list of objects.')
            evidence = []
        for ev in evidence:
            if not isinstance(ev, dict):
                self.f.uncertain('§2 evidence object', 'An evidence entry is not an object.')
                continue
            identifier = ev.get('id')
            if not text(identifier):
                self.f.uncertain('§2; §3 evidence references', 'Evidence identifier is missing; references cannot be assigned.')
                # Adapter identity affects referencing, not object-local rows.
                self.inspect_evidence(ev)
            else:
                self.evidence[identifier].append(ev)
        for identifier in sorted(self.evidence):
            entries = self.evidence[identifier]
            if len(entries) != 1:
                self.f.uncertain('§2; §3 evidence references',
                                 'Duplicate evidence identifier ' + repr(identifier) + ' has no text-defined disambiguation rule.')
            results = [self.inspect_evidence(ev) for ev in sorted(entries, key=stable)]
            if len(entries) == 1:
                self.evidence_results[identifier] = results[0]
        for check in sorted(checks, key=stable):
            self.inspect_check(check)
        if 'check-set' in report:
            self.inspect_collection(report['check-set'], len(checks), 'Declared check set')
        self.inspect_rollup(report, checks)
        return self.f.result()

    def qualifier(self, check, name):
        if name not in check:
            return {'value': 'unknown'}
        value = check[name]
        choices = ('unknown', 'demonstrated') if name == 'discrimination' else (
            'unknown', 'possible-not-demonstrated', 'demonstrated', 'foreclosed')
        if not isinstance(value, dict) or value.get('value') not in choices:
            self.f.reject('§1 qualifier vocabulary', name + ' is not one of its defined values.')
            return {'value': 'unknown'}
        return value

    def referenced_evidence(self, qualifier):
        ref = qualifier.get('ref')
        if not text(ref):
            self.f.reject('§4 row 11', 'An asserted qualifier has no evidence reference.')
            return None
        if ref not in self.evidence:
            self.f.uncertain('§3 reading table', 'Qualifier evidence reference ' + repr(ref) + ' does not resolve.')
            return None
        if len(self.evidence[ref]) != 1:
            return None
        return self.evidence_results[ref]

    def inspect_check(self, check):
        state = check.get('state')
        if state not in STATES:
            self.f.reject('§1 state vocabulary', 'A check is missing state or uses an undefined state.')
        code = None
        if 'cause' in check:
            cause = check['cause']
            code = cause.get('code') if isinstance(cause, dict) else cause
            if not isinstance(code, str) or code not in CAUSES:
                self.f.reject('§1.2 cause vocabulary', 'Cause is not a defined disposition.')
        if state in ('not-exercised', 'inconclusive', 'void') and ('cause' not in check or code is None):
            self.f.reject('§4 row 1', 'A non-verdict state has no cause.')
        if state == 'void' and code in ('not_applicable', 'out_of_scope', 'withheld'):
            self.f.reject('§4 row 2', 'Void carries a disposition excluded by row 2.')
        if state == 'not-exercised' and code == 'integrity-failure':
            self.f.reject('§4 row 3', 'Not-exercised carries integrity-failure.')
        if code == 'confinement-failed-during-check' and state != 'void':
            self.f.reject('§4 row 4', 'Confinement failure during the check is declared outside void.')
        if code == 'precondition-unsatisfiable' and state in ('pass', 'fail', 'inconclusive', 'void'):
            self.f.reject('§1.2 precondition-unsatisfiable', 'A cause saying the check cannot run accompanies a state saying it ran.')
        exclusion = check.get('declared-exclusion', False)
        if type(exclusion) is not bool:
            self.f.uncertain('§4 row 5', 'Declared-exclusion has no unambiguous boolean representation.')
        elif exclusion and state != 'not-exercised':
            self.f.reject('§4 row 5', 'A declared exclusion has a state other than not-exercised.')
        ov, disc = self.qualifier(check, 'other-verdict'), self.qualifier(check, 'discrimination')
        if state in ('not-exercised', 'inconclusive', 'void') and any(q['value'] != 'unknown' for q in (ov, disc)):
            self.f.reject('§4 row 6', 'A non-verdict state carries a non-unknown qualifier.')
        if state in VERDICTS and 'cause' in check:
            self.f.reject('§4 row 7', 'A verdict state carries a cause.')
        if ov['value'] == 'foreclosed' and disc['value'] == 'demonstrated':
            self.f.reject('§4 row 8', 'Foreclosure and demonstrated discrimination are asserted together.')
        if disc['value'] == 'demonstrated' and ov['value'] in ('unknown', 'possible-not-demonstrated'):
            self.f.reject('§4 row 9', 'Demonstrated discrimination accompanies unknown or undemonstrated other-verdict.')
        if ov['value'] == 'foreclosed':
            if not text(ov.get('constraint-set')) or not text(ov.get('domain')):
                self.f.reject('§4 row 10', 'Foreclosure lacks a constraint-set identifier or domain identifier.')
            if 'domain' in ov and ov['domain'] != self.domain:
                self.f.reject('§2 run domain', 'Foreclosure domain is not the run domain identifier.')
        for qualifier in (ov, disc):
            if qualifier['value'] in ('demonstrated', 'foreclosed'):
                self.referenced_evidence(qualifier)
            elif qualifier['value'] == 'possible-not-demonstrated' and not text(qualifier.get('ref')):
                self.f.uncertain('§1.3; §4 row 11', 'Text does not explicitly settle whether possible-not-demonstrated asserts a value requiring an evidence reference.')
        if disc['value'] == 'demonstrated':
            ev = self.referenced_evidence(disc)
            if ev:
                if ev['changed'] == 'checker rule':
                    self.f.reject('§4 row 12', 'Discrimination cites a changed checker rule.')
                elif ev['changed'] != 'input artifact':
                    self.f.reject('§1.3 discrimination', 'Discrimination requires two delta-related inputs under fixed constraints.')
                if ev['moved'] == set() and ev['comparison_complete']:
                    self.f.reject('§1.3 discrimination', 'The observation pair differs on no compared projection.')
        if ov['value'] == 'demonstrated':
            ev = self.referenced_evidence(ov)
            if ev:
                if 'verdict' in ev['known'] and 'verdict' not in ev['moved']:
                    self.f.reject('§4 row 13', 'Other-verdict demonstration cites evidence whose recomputed moved lacks verdict.')
                elif 'verdict' not in ev['known']:
                    self.f.uncertain('§3 reading table; §4 row 13', 'Other-verdict evidence lacks a recomputable verdict projection; row 13 degrades.')

    def observation(self, item):
        if not isinstance(item, dict):
            return None, False
        carried = item.get('carried')
        ref = item.get('reference')
        has_carry = isinstance(carried, dict)
        has_ref = isinstance(ref, dict) and text(ref.get('vector')) and digest(ref.get('sha256'))
        if not has_carry and not has_ref:
            return None, False
        resolved = None
        if has_ref:
            resolved = self.store.get(ref['vector'])
            if resolved is None:
                self.f.uncertain('§3 reading table', 'Observation reference ' + repr(ref['vector']) + ' is unresolved; moved-dependent rows degrade.')
            elif not isinstance(resolved, dict) or not digest(resolved.get('sha256')):
                self.f.uncertain('§3 reading table', 'Resolved observation lacks a usable verified digest.')
                resolved = None
            elif ref['sha256'].lower() != resolved['sha256'].lower():
                self.f.reject('§3 reading table', 'Resolved observation digest differs from the reference: integrity failure.')
                resolved = None
        conflicts = set()
        if has_carry and has_ref:
            # The specification permits carry or reference but gives no
            # precedence for a contradictory projection. Agreement on a
            # different projection remains independently usable.
            if resolved is not None:
                conflicts = {label for label, key in PROJECTIONS.items()
                             if key in carried and key in resolved and carried[key] != resolved[key]}
            if conflicts:
                self.f.uncertain('§3 carry or reference',
                                 'Carried and referenced observations contradict on ' + ', '.join(sorted(conflicts))
                                 + '; those projections have no specified precedence, while independent agreed projections remain usable.')
        result = carried if has_carry else resolved
        if has_carry and resolved is not None:
            # Presence of a carried object does not establish every
            # projection. Fill only absent supported projections from the
            # digest-matching resolution; disagreements stay local below.
            result = dict(carried)
            for key in PROJECTIONS.values():
                if key not in result and key in resolved:
                    result[key] = resolved[key]
        if conflicts:
            result = {key: value for key, value in result.items()
                      if key not in {PROJECTIONS[label] for label in conflicts}}
        # Which projections are required depends on compared/moved. A
        # verdict-only observation need not carry a fired-rule projection.
        return result, True

    def inspect_evidence(self, ev):
        changed = ev.get('changed')
        if changed not in ('input artifact', 'checker rule', 'constraint'):
            self.f.reject('§2 changed', 'Evidence does not name one of the three changed-object kinds.')
        fixed = ev.get('fixed')
        if not isinstance(fixed, dict):
            fixed = {}
        if any(not text(fixed.get(k)) for k in ('checker', 'constraint-set', 'domain')):
            self.f.reject('§2 fixed', 'Evidence fixed slot must name checker identity, constraint set and domain.')
        if fixed.get('domain') != self.domain or not text(fixed.get('domain')):
            self.f.reject('§2 run domain', 'Evidence domain is not a reference to the run domain identifier.')
        compared, declared_moved = ev.get('compared'), ev.get('moved')
        if not strings(compared) or not strings(declared_moved):
            self.f.reject('§2 evidence slots', 'Evidence compared or moved is missing or is not a list of named projections.')
            compared, declared_moved = [], []
        # §§2.1, 6.1 and 7.1 distinguish machine-comparable projections
        # from the recompute-opaque error-list primitive, which no row reads.
        declared_comparable = set(declared_moved) & set(PROJECTIONS)
        if not declared_comparable.issubset(set(compared)):
            self.f.reject('§2 moved subset', 'Declared comparable moved includes a projection outside compared.')
        unsupported = (set(compared) | set(declared_moved)) - set(PROJECTIONS) - OPAQUE_PROJECTIONS
        if unsupported:
            self.f.uncertain('§6.1; §7.1 observation composition', 'Projection composition is open for ' + ', '.join(sorted(unsupported)) + '.')
        delta = ev.get('delta')
        if not isinstance(delta, dict) or not isinstance(delta.get('changes'), list):
            self.f.reject('§2 delta', 'Evidence lacks a concrete delta.')
        else:
            changes = delta['changes']
            if not changes or not all(isinstance(c, dict) and text(c.get('field')) and 'before' in c and 'after' in c for c in changes):
                self.f.reject('§2 delta', 'Delta does not state a concrete field and before/after change.')
            else:
                effective = {c['field'] for c in changes if stable(c['before']) != stable(c['after'])}
                if not effective:
                    self.f.reject('§2 delta', 'Delta contains no concrete change.')
                # Optional declared arity has no authority over the delta.
                # No normative rejection row reads it, so it is ignored.
        observations = ev.get('observations')
        computed = None
        known = set()
        if not isinstance(observations, list) or len(observations) != 2:
            self.f.reject('§4 row 14', 'Moved is asserted without both carried observations or digested references.')
        else:
            parsed = [self.observation(o) for o in observations]
            if not all(form for _, form in parsed):
                self.f.reject('§4 row 14', 'An observation is neither carried nor referenced with a digest.')
            actual = [o for o, _ in parsed]
            if all(o is not None for o in actual):
                left, right = actual
                usable = {'verdict': lambda value: value in VERDICTS,
                          'fired-rule list': strings}
                known = {label for label, key in PROJECTIONS.items()
                         if key in left and key in right
                         and usable[label](left[key]) and usable[label](right[key])}
                computed = {label for label in known if left[PROJECTIONS[label]] != right[PROJECTIONS[label]]}
                required = (set(compared) | set(declared_moved)) & set(PROJECTIONS)
                unavailable = required - known
                if unavailable:
                    self.f.uncertain('§2; §7.1 observation composition',
                                     'Observation pair lacks usable compared projections: ' + ', '.join(sorted(unavailable)) + '.')
                if not computed.issubset(set(compared)):
                    self.f.reject('§2 moved subset', 'Recomputed moved includes a projection outside compared.')
                # Unknown projections do not mask a decidable falsehood in
                # the supported projections actually present on both sides.
                if computed != declared_comparable & known:
                    self.f.reject('§2 moved recomputation', 'Declared moved differs from the supplied observation projections.')
        return {'changed': changed, 'moved': computed, 'known': known,
                'comparison_complete': set(compared).issubset(known), 'fixed': fixed}

    def inspect_collection(self, collection, size, label):
        if not isinstance(collection, dict):
            self.f.uncertain('§3.1 collection representation', label + ' digest declaration is malformed.')
            return
        if not count(collection.get('leaf-count')):
            self.f.reject('§3.1 count binding', label + ' digest has no nonnegative integer leaf count.')
        elif size is not None and collection['leaf-count'] != size:
            self.f.reject('§3.1 count binding', label + ' leaf count differs from its declared population.')
        shape = collection.get('tree-shape')
        if shape not in SHAPES:
            self.f.reject('§3.1 closed tree-shape set', label + ' omits a registered tree-shape identifier or uses free text.')
        if not digest(collection.get('sha256')):
            self.f.uncertain('§3.1 collection digest', label + ' lacks a usable SHA-256 digest.')
        if shape == 'flat':
            self.f.uncertain('§3.1; §11 O3', 'Flat tree construction is undefined in the text; its digest and cryptographic count binding cannot be verified.')
        elif shape in SHAPES:
            self.f.uncertain('§3.1 collection digest', 'Text supplies no collection leaf serialization or count-binding encoding for ' + shape + '; root correctness cannot be verified.')

    def inspect_rollup(self, report, checks):
        if 'roll-up' not in report:
            # Section 5 describes what a report may add up, not a normative
            # JSON requirement that every report contain a roll-up object.
            return
        roll = report['roll-up']
        if not isinstance(roll, dict):
            self.f.uncertain('§5 roll-up representation', 'Roll-up is not an object.')
            return
        valid = all(c.get('state') in STATES for c in checks)
        counts = collections.Counter(c.get('state') for c in checks if isinstance(c.get('state'), str))
        if not count(roll.get('declared')) or roll.get('declared') != len(checks):
            self.f.reject('§5.1 complete denominator', 'Aggregate denominator is absent, invalid or inconsistent with declared checks.')
        exercised = len(checks) - counts['not-exercised']
        if not count(roll.get('exercised')) or (valid and roll['exercised'] != exercised):
            self.f.reject('§5.1 complete denominator', 'Aggregate exercised denominator is absent, invalid or inconsistent with check states.')
        for state in STATES:
            if not count(roll.get(state)) or (valid and roll[state] != counts[state]):
                self.f.reject('§1.1 state-only counts; §5.1 aggregate', 'Roll-up count for ' + state + ' is missing, invalid or disagrees with the check states.')
        verdict_records = counts['pass'] + counts['fail']
        for name in ('carried', 'referenced'):
            if not count(roll.get(name)):
                self.f.uncertain('§5.3 disclosure counter', name + ' disclosure counter is missing or invalid; the text says this counter is not rejection.')
            elif valid and roll[name] > verdict_records:
                self.f.uncertain('§5.3 disclosure counter',
                                 name + ' disclosure count ' + str(roll[name]) + ' exceeds the '
                                 + str(verdict_records) + ' relevant verdict records; §5.3 supplies no rejection row for this disclosure.')
        self.inspect_counter_topology(checks)
        self.inspect_completeness(roll.get('completeness', {}), counts, len(checks), exercised)
        self.inspect_negative(roll.get('negative-capable'), report, checks, counts)

    def inspect_counter_topology(self, checks):
        """Only actual shared or mixed evidence needs a counter convention."""
        users = collections.defaultdict(set)
        for index, check in enumerate(checks):
            if check.get('state') not in VERDICTS:
                continue
            refs = set()
            for name in ('other-verdict', 'discrimination'):
                qualifier = check.get(name)
                if (isinstance(qualifier, dict)
                        and qualifier.get('value') in ('demonstrated', 'foreclosed')
                        and text(qualifier.get('ref'))):
                    refs.add(qualifier['ref'])
            modes = set()
            for ref in refs:
                entries = self.evidence.get(ref, [])
                if len(entries) != 1:
                    continue  # Resolution/identity uncertainty is recorded separately.
                users[ref].add(index)
                observations = entries[0].get('observations', [])
                if not isinstance(observations, list):
                    continue
                for observation in observations:
                    if not isinstance(observation, dict):
                        continue
                    if isinstance(observation.get('carried'), dict):
                        modes.add('carried')
                    if isinstance(observation.get('reference'), dict):
                        modes.add('referenced')
            if len(modes) > 1:
                self.f.uncertain('§5.3 disclosure counter',
                                 'A verdict record uses both carried and referenced observations; the text does not specify its counter assignment.')
        if any(len(records) > 1 for records in users.values()):
            self.f.uncertain('§5.3 disclosure counter',
                             'An evidence object is shared by multiple verdict records; the text does not specify the counter assignment for shared observations.')

    def inspect_completeness(self, claims, counts, declared, exercised):
        if not isinstance(claims, dict):
            self.f.uncertain('§5.2 completeness', 'Completeness claims are not an object.')
            return
        for name in sorted(claims):
            claim = claims[name]
            if name not in ('accounting', 'execution', 'evidence', 'no-void'):
                self.f.uncertain('§5.2 completeness', 'Unknown completeness claim ' + repr(name) + '.')
                continue
            if not isinstance(claim, dict) or not count(claim.get('population')):
                self.f.reject('§4 run-level completeness count', 'Completeness claim ' + name + ' lacks its population count.')
                continue
            expected_population = counts['pass'] + counts['fail'] if name == 'evidence' else declared
            if claim['population'] != expected_population:
                self.f.reject('§5.2 completeness population', name + ' claim population differs from the population specified in §5.2.')
            assertion = claim.get('claim')
            if assertion not in ('satisfied', 'not-satisfied', 'not-claimable'):
                self.f.uncertain('§5.2 completeness', name + ' claim has no recognized truth status.')
                continue
            if expected_population == 0:
                if assertion != 'not-claimable':
                    self.f.reject('§5.2 empty population', 'A completeness claim over an empty population is not reported as not-claimable.')
            elif name == 'no-void':
                expected = 'satisfied' if counts['void'] == 0 else 'not-satisfied'
                if assertion != expected:
                    self.f.reject('§5.2 no-void claim', 'No-void claim disagrees with the declared void count.')
            elif name == 'execution':
                expected = 'satisfied' if exercised == declared else 'not-satisfied'
                if assertion != expected:
                    self.f.reject('§5.2 execution completeness', 'Execution claim disagrees with whether every declared check ran.')
            else:
                self.f.uncertain('§5.2 completeness definitions', 'The text supplies the ' + name + ' population but not a complete satisfaction algorithm.')

    def inspect_negative(self, negative, report, checks, counts):
        if not isinstance(negative, dict) or not text(negative.get('kind')):
            self.f.reject('§5.4 disclosure', 'Roll-up is silent about negative capability.')
            return
        kind = negative['kind']
        if kind == 'nothing':
            return
        if kind == 'shown-by-run':
            if counts['fail'] == 0:
                self.f.reject('§5.4 negative verdict', 'Run claims negative capability without a declared check in state fail.')
            return
        ids = {c['check'] for c in checks if text(c.get('check'))}
        if kind == 'control-failed':
            control = negative.get('control')
            if not isinstance(control, dict):
                self.f.reject('§5.4 control', 'Control evidence is absent.')
                return
            if control.get('state') != 'fail':
                self.f.reject('§5.4 control', 'Control did not return the negative verdict fail.')
            witnesses = control.get('checks')
            if not strings(witnesses) or not witnesses or not set(witnesses).issubset(ids):
                self.f.reject('§5.4 control', 'Control does not name a witness among the run’s declared checks.')
            self.inspect_binding(report.get('fixed'), control.get('fixed'))
        elif kind == 'prior-discriminating-run':
            identities = negative.get('check-identity')
            if not strings(identities) or not identities:
                self.f.uncertain('§5.4 prior-run identity', 'Prior-run check identity is not established by the adapter or resolved evidence.')
            elif not set(identities).issubset(ids):
                self.f.reject('§5.4 prior-run identity', 'Prior-run evidence does not identify the relevant declared checks.')
            reference = negative.get('reference')
            if not isinstance(reference, dict):
                self.f.reject('§5.4 prior-run reference', 'Prior negative capability has no reference.')
                return
            if 'leaf-count' in reference or 'tree-shape' in reference:
                self.inspect_collection(reference, None, 'Prior-run observation set')
            self.f.uncertain('§3 reading table; §5.4 prior run', 'Prior report cannot be resolved with verified identity, fail results and checker/configuration binding from the supplied envelope.')
        else:
            self.f.reject('§5.4 disclosure', 'Negative capability names none of the text’s permitted alternatives.')

    def inspect_binding(self, current, witness):
        if not isinstance(current, dict) or not isinstance(witness, dict):
            self.f.uncertain('§5.4 checker/configuration binding; §10 text precedence',
                             'Missing checker/configuration binding cannot establish the normative §5.4 condition; §10 reports a permissive corpus treatment.')
            return
        keys = ('checker', 'constraint-set')
        missing = [key for key in keys if not text(current.get(key)) or not text(witness.get(key))]
        differing = [key for key in keys if key not in missing and current[key] != witness[key]]
        if missing:
            self.f.uncertain('§5.4 checker/configuration binding',
                             'Control and run do not both name required binding components: ' + ', '.join(missing) + '.')
        if differing:
            self.f.reject('§5.4 checker/configuration binding',
                          'Control differs from the supported run on binding components: ' + ', '.join(differing) + '.')
        # Equal supplied fixed-slot identities establish the declared binding.
        # This remains a consistency check, not independent provenance proof.


def assess(envelope):
    return Reader(envelope).run()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON object member')
        result[key] = value
    return result


def no_nonfinite(value):
    raise ValueError('non-finite JSON number')


def assess_json(raw):
    try:
        envelope = json.loads(raw, object_pairs_hook=unique_object, parse_constant=no_nonfinite)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return {'verdict': 'cannot-tell', 'grounds': ['§1–§5 representation'],
                'reason': 'Malformed or ambiguous JSON cannot be read as a report; no normative JSON serialization/error policy is supplied.'}
    return assess(envelope)


def verify_bundle(root):
    """Verify listed inputs, confine paths, and enumerate cases from the manifest."""
    root = root.resolve()
    cases = []
    manifest = root / 'SHA256SUMS'
    for line in manifest.read_text().splitlines():
        expected, relative = line.split(None, 1)
        relative = relative.lstrip('* ')
        path = (root / relative).resolve()
        if root not in path.parents:
            raise ValueError('Manifest path escapes input bundle')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Input hash mismatch: ' + relative)
        if path.parent == root / 'cases' and path.suffix == '.json':
            cases.append(path)
    if len(set(cases)) != len(cases):
        raise ValueError('Duplicate case path in input manifest')
    return sorted(cases, key=lambda p: p.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--predictions', required=True, type=Path)
    parser.add_argument('--counts', required=True, type=Path)
    args = parser.parse_args()
    paths = verify_bundle(args.inputs)
    rows = [dict(case_id=p.stem, **assess_json(p.read_bytes())) for p in paths]
    counts = collections.Counter(row['verdict'] for row in rows)
    summary = {'total': len(rows), **{key: counts[key] for key in ('accept', 'reject', 'cannot-tell')}}
    args.predictions.write_text(''.join(stable(row) + '\n' for row in rows), encoding='utf-8')
    args.counts.write_text(stable(summary) + '\n', encoding='utf-8')
    print(stable(summary))


if __name__ == '__main__':
    main()
