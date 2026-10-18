"""Replay the frozen adversarial data mutations against the pinned Lars reader."""

import argparse
import copy
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile


LARS_COMMIT = "6d8ee54b01d20a819869ceb9fcea096d59251f8c"
READER_SHA256 = "82a316b548397b5bc3ff37d33285473f754e7b4c6bd1408660a18f2dc2154477"
SPEC_SHA256 = "35625d73baa56f2705bb2fffe7e2a4075293fa6df075bc61bdd349a5d3618d9d"
BASELINE_SHA256 = "505dfb71a640e7ef0eceb7f2d859e5cf08dac4c81bed80672135e0eb51b92130"
A = "v0090b52048ca1f51"
B = "vf9b5623144960dda"
C = "v1032eb59a7cdb30f"
BAD = "v0e286b53de78162a"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_path(path):
    return sha256_bytes(path.read_bytes())


def normalized_stderr_sha256(data, repo, directory):
    """Hash traceback content after replacing only run-local absolute paths."""
    text = data.decode("utf-8", errors="backslashreplace")
    replacements = set()
    for path, marker in ((directory, "<CASE-DIRECTORY>"), (repo, "<LARS-REPOSITORY>")):
        replacements.add((str(pathlib.Path(path)), marker))
        replacements.add((str(pathlib.Path(path).resolve()), marker))
    for actual, marker in sorted(replacements, key=lambda pair: len(pair[0]), reverse=True):
        text = text.replace(actual, marker)
    return sha256_bytes(text.encode("utf-8"))


def tree_digest(directory):
    digest = hashlib.sha256()
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        relative = path.relative_to(directory).as_posix().encode()
        digest.update(relative + b"\0" + bytes.fromhex(sha256_path(path)))
    return digest.hexdigest()


def add(recipes, name, member=A, mutate=None, special=None):
    recipes.append({"name": name, "member": member, "mutate": mutate, "special": special})


def recipes():
    result = []
    add(result, "baseline")
    add(result, "omit_rejected_member", BAD, special="omit")
    add(result, "duplicate_member_file", A, special="duplicate-file")
    add(result, "missing_member_id", A, lambda m: m.pop("id"))
    add(result, "duplicate_member_id", A, lambda m: m.update(id=BAD))
    add(result, "unknown_field", A, lambda m: m["subject"].update(extra="ordinary unknown field"))
    add(result, "unicode_description", A, lambda m: m["subject"]["domain"].update(description="Café / 東京 / 🐙"))
    add(result, "missing_state", A, lambda m: m["subject"]["checks"][0].pop("state"))
    add(result, "unknown_state", A, lambda m: m["subject"]["checks"][0].update(state="PASS"))
    add(result, "forbidden_cause", A, lambda m: m["subject"]["checks"][0].update(cause="unavailable"))
    add(result, "missing_evidence_changed", B, lambda m: m["subject"]["evidence"][0].pop("changed"))
    add(result, "checker_changed", B, lambda m: m["subject"]["evidence"][0].update(changed="checker rule"))
    add(result, "missing_negative_field", A, lambda m: m["subject"]["roll-up"].pop("negative-capable"))
    add(result, "wrong_state_total", A, lambda m: m["subject"]["roll-up"].update(**{"pass": 999}))
    add(result, "wrong_observation_total", A, lambda m: m["subject"]["roll-up"].update(referenced=999))
    add(result, "boolean_state_total", A, lambda m: m["subject"]["roll-up"].update(**{"pass": True}))
    add(result, "float_leaf_count", A, lambda m: m["subject"]["check-set"].update(**{"leaf-count": 1.0}))
    add(result, "malformed_check_append", A, lambda m: m["subject"]["checks"].append("not a check object"))
    add(result, "malformed_evidence_append", A, lambda m: m["subject"]["evidence"].append("not evidence"))
    add(result, "duplicate_check_id", C, lambda m: m["subject"]["checks"][1].update(check=m["subject"]["checks"][0]["check"]))
    add(result, "reverse_check_records", B, lambda m: m["subject"]["checks"].reverse())
    add(result, "duplicate_evidence_append", B, special="evidence-append")
    add(result, "duplicate_evidence_prepend", B, special="evidence-prepend")
    add(result, "duplicate_evidence_reverse", B, special="evidence-reverse")
    add(result, "unhashable_evidence_id", B, lambda m: m["subject"]["evidence"][0].update(id=[]))
    add(result, "integer_observations", B, lambda m: m["subject"]["evidence"][0].update(observations=1))
    add(result, "list_negative_kind", A, lambda m: m["subject"]["roll-up"]["negative-capable"].update(kind=[]))
    add(result, "same_digest_changed_verdict", B, lambda m: m["resolves"]["obs-fail"].update(verdict="pass"))
    add(result, "invalid_json", A, special="invalid-json")
    add(result, "top_level_array", A, special="top-array")
    add(result, "uppercase_extension", BAD, special="uppercase")
    add(result, "rename_file", A, special="rename")
    add(result, "replace_reject_by_accept_same_id", A, special="replace-reject")
    add(result, "duplicate_json_key", BAD, special="duplicate-json-key")
    add(result, "empty_directory", A, special="empty")
    return result


def apply_recipe(directory, recipe):
    member = recipe["member"]
    path = directory / f"{member}.json"
    obj = json.loads(path.read_text()) if path.exists() else {}
    mutate = recipe["mutate"]
    special = recipe["special"]
    if mutate:
        mutate(obj)
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    if special == "omit":
        path.unlink()
    elif special == "duplicate-file":
        shutil.copy2(path, directory / "duplicate.json")
    elif special in ("evidence-append", "evidence-prepend", "evidence-reverse"):
        duplicate = dict(copy.deepcopy(obj["subject"]["evidence"][0]), changed="checker rule")
        if special == "evidence-prepend":
            obj["subject"]["evidence"].insert(0, duplicate)
        else:
            obj["subject"]["evidence"].append(duplicate)
            if special == "evidence-reverse":
                obj["subject"]["evidence"].reverse()
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    elif special == "invalid-json":
        path.write_text("{")
    elif special == "top-array":
        path.write_text("[]")
    elif special == "uppercase":
        path.rename(path.with_suffix(".JSON"))
    elif special == "rename":
        path.rename(directory / "zzz.json")
    elif special == "replace-reject":
        accepting = json.loads((directory / f"{A}.json").read_text())
        accepting["id"] = BAD
        (directory / f"{BAD}.json").write_text(json.dumps(accepting, indent=2) + "\n")
    elif special == "duplicate-json-key":
        raw = path.read_text()
        if raw.count('"value": "demonstrated"') != 1:
            raise ValueError("duplicate-key mutation anchor drifted")
        path.write_text(raw.replace('"value": "demonstrated"', '"value": "demonstrated", "value": "unknown"'))
    elif special == "empty":
        shutil.rmtree(directory)
        directory.mkdir()
    return obj


def verify_repo(repo):
    repo = pathlib.Path(repo).resolve()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    if head != LARS_COMMIT:
        raise ValueError(f"Lars repository is at {head}, expected {LARS_COMMIT}")
    if sha256_path(repo / "reader.py") != READER_SHA256:
        raise ValueError("pinned reader.py hash mismatch")
    if sha256_path(repo / "spec" / "v01-text.txt") != SPEC_SHA256:
        raise ValueError("pinned specification hash mismatch")
    if sha256_path(repo / "out" / "run.jsonl") != BASELINE_SHA256:
        raise ValueError("pinned baseline output hash mismatch")
    return repo


def replay(repo):
    repo = verify_repo(repo)
    source_tree = tree_digest(repo / "members")
    results = []
    with tempfile.TemporaryDirectory(prefix="lars-mutation-replay-") as tmp:
        root = pathlib.Path(tmp)
        for recipe in recipes():
            directory = root / recipe["name"]
            shutil.copytree(repo / "members", directory)
            obj = apply_recipe(directory, recipe)
            input_tree = tree_digest(directory)
            proc = subprocess.run(
                [sys.executable, "-I", str(repo / "reader.py"), str(directory)],
                capture_output=True,
                timeout=20,
            )
            lines = [json.loads(line) for line in proc.stdout.decode().splitlines()]
            if recipe["special"] in ("rename", "replace-reject", "duplicate-json-key", "empty"):
                watched = {BAD}
            else:
                watched = {recipe["member"], obj.get("id"), "None"}
            results.append({
                "case": recipe["name"],
                "source_members_tree_sha256": source_tree,
                "mutated_input_tree_sha256": input_tree,
                "exit": proc.returncode,
                "output_lines": len(lines),
                "stdout_sha256": sha256_bytes(proc.stdout),
                "stderr_sha256": sha256_bytes(proc.stderr),
                "stderr_normalized_sha256": normalized_stderr_sha256(proc.stderr, repo, directory),
                "summary": proc.stderr.decode().strip().splitlines()[-1] if proc.stderr.strip() else "",
                "affected": [line for line in lines if line.get("id") in watched],
            })
    return {
        "source_commit": LARS_COMMIT,
        "reader_sha256": READER_SHA256,
        "specification_sha256": SPEC_SHA256,
        "baseline_output_sha256": BASELINE_SHA256,
        "source_members_tree_sha256": source_tree,
        "python_implementation": sys.implementation.name,
        "python_version": sys.version,
        "recipes": results,
    }


def portable_replay(result):
    """Remove host-local forensic fields while retaining semantic and normalized evidence."""
    portable = copy.deepcopy(result)
    portable.pop("python_version", None)
    for recipe in portable["recipes"]:
        recipe.pop("stderr_sha256", None)
    return portable


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=pathlib.Path)
    parser.add_argument("--check", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    result = replay(args.repo)
    encoded = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.check and portable_replay(result) != portable_replay(json.loads(args.check.read_text())):
        raise SystemExit("mutation replay differs from frozen artifact")
    if args.output:
        args.output.write_text(encoded)
    if not args.check and not args.output:
        print(encoded, end="")


if __name__ == "__main__":
    main()
