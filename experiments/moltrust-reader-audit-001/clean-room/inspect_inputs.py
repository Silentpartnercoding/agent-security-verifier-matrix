"""Inventory permitted input shapes; contains no outcome inference."""
import collections
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'inputs' / 'cases'
shapes = collections.defaultdict(set)
examples = {}

def visit(value, path):
    if isinstance(value, dict):
        for key, child in value.items():
            location = path + '/' + key
            shapes[location].add(type(child).__name__)
            if location not in examples:
                examples[location] = child if not isinstance(child, (dict, list)) else None
            visit(child, location)
    elif isinstance(value, list):
        for child in value:
            visit(child, path + '[]')

for path in sorted(root.glob('*.json')):
    visit(json.loads(path.read_text()), '')
for path in sorted(shapes):
    print(path, ','.join(sorted(shapes[path])), repr(examples[path]))
