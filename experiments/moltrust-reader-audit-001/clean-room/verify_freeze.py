"""Record tests and byte-identical regeneration without consulting an oracle."""
import collections
import hashlib
import io
import json
from pathlib import Path
import unittest

from reader import assess_json, stable, verify_bundle

HERE = Path(__file__).resolve().parent
INPUTS = HERE.parent / 'inputs'

suite = unittest.TestLoader().loadTestsFromNames([
    'test_reader', 'test_bundle', 'test_review', 'test_partial_evidence', 'test_opaque'])
stream = io.StringIO()
test_result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
print(stream.getvalue(), end='')
if not test_result.wasSuccessful():
    raise SystemExit('Tests failed; no freeze record written.')

cases = verify_bundle(INPUTS)
rows = [dict(case_id=p.stem, **assess_json(p.read_bytes())) for p in cases]
regenerated = ''.join(stable(row) + '\n' for row in rows).encode('utf-8')
existing = (HERE / 'predictions.jsonl').read_bytes()
if existing != regenerated:
    raise SystemExit('Prediction regeneration mismatch; no freeze record written.')
counts = collections.Counter(r['verdict'] for r in rows)
summary = {'total': len(rows), **{k: counts[k] for k in ('accept', 'reject', 'cannot-tell')}}
if (HERE / 'counts.json').read_bytes() != (stable(summary) + '\n').encode('utf-8'):
    raise SystemExit('Counts regeneration mismatch; no freeze record written.')

record = {'tests_run': test_result.testsRun, 'failures': len(test_result.failures),
          'errors': len(test_result.errors), 'skipped': len(test_result.skipped),
          'prediction_rows': len(rows), 'unique_case_ids': len({r['case_id'] for r in rows}),
          'byte_identical_regeneration': True,
          'counts': summary,
          'predictions_sha256': hashlib.sha256(existing).hexdigest(),
          'counts_sha256': hashlib.sha256((HERE / 'counts.json').read_bytes()).hexdigest(),
          'input_manifest_sha256': hashlib.sha256((INPUTS / 'SHA256SUMS').read_bytes()).hexdigest(),
          'comparison_data_accessed': False}
(HERE / 'VERIFICATION.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
files = sorted(p for p in HERE.iterdir() if p.is_file() and p.name != 'ARTIFACT-SHA256SUMS')
(HERE / 'ARTIFACT-SHA256SUMS').write_text(''.join(
    hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in files))
print(stable(record))
