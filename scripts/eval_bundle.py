"""Create collision-safe, hash-addressed evaluation run bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__:
    from .eval_catalog import validate_catalog
    from .eval_suites import validate_suites
else:
    from eval_catalog import validate_catalog
    from eval_suites import validate_suites


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _skill_version(path: Path) -> str:
    match = re.search(r"(?m)^\s*version:\s*([^\s]+)\s*$", path.read_text(encoding="utf-8"))
    return match.group(1) if match else "unavailable"


def _git_commit(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"
    return result.stdout.strip() or "unavailable"


def _unique_directory(parent: Path, stem: str) -> Path:
    candidate = parent / stem
    suffix = 1
    while candidate.exists():
        suffix += 1
        candidate = parent / f"{stem}-{suffix}"
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def _candidate_files(root: Path, fixture: str | None) -> list[dict[str, str]]:
    if not fixture:
        return []
    fixture_path = root / fixture
    candidate_root = fixture_path / "sources"
    if not candidate_root.is_dir():
        candidate_root = fixture_path
    files: list[dict[str, str]] = []
    for path in sorted(candidate_root.rglob("*")):
        if not path.is_file() or path.name == "ground-truth.json":
            continue
        files.append({
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256_file(path),
        })
    return files


def create_bundle(
    *,
    root: Path,
    suites_path: Path,
    catalog_path: Path,
    suite_id: str,
    mode: str,
    model: str,
    output_parent: Path,
    repeat: int = 1,
    tools: list[str] | None = None,
    now: datetime | None = None,
) -> tuple[Path, dict[str, Any]]:
    suites = json.loads(suites_path.read_text(encoding="utf-8"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_validation = validate_catalog(catalog)
    if catalog_validation["verdict"] != "PASS":
        raise ValueError(f"Invalid case catalog: {catalog_validation['issues']}")
    validation = validate_suites(suites, catalog)
    if validation["verdict"] != "PASS":
        raise ValueError(f"Invalid suite manifest: {validation['issues']}")
    suite = next((item for item in suites["suites"] if item["id"] == suite_id), None)
    if suite is None:
        raise ValueError(f"Unknown suite: {suite_id}")
    if mode not in suite["modes"]:
        raise ValueError(f"Mode {mode!r} is not declared by suite {suite_id!r}.")
    if not 1 <= repeat <= suite["repeats"]:
        raise ValueError(f"repeat must be from 1 to {suite['repeats']} for {suite_id}.")
    if not model.strip():
        raise ValueError("model must be recorded explicitly; use 'unavailable' when hidden.")
    try:
        suites_path.relative_to(root)
        catalog_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("catalog and suite manifests must be inside the repository root") from exc

    cases_by_id = {case["id"]: case for case in catalog["cases"]}
    commit = _git_commit(root)
    created = now or datetime.now(UTC)
    created_utc = created.astimezone(UTC)
    timestamp = created_utc.strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}-{suite_id}-{mode}-r{repeat}"
    bundle_dir = _unique_directory(output_parent, run_id)

    case_records: list[dict[str, Any]] = []
    for case_id in suite["case_ids"]:
        case = cases_by_id[case_id]
        fixture = case.get("fixture")
        case_records.append({
            "id": case_id,
            "prompt": case["prompt"],
            "prompt_sha256": _sha256_bytes(case["prompt"].encode("utf-8")),
            "fixture": fixture,
            "candidate_files": _candidate_files(root, fixture),
        })

    skill_path = root / "SKILL.md"
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "run": {
            "id": bundle_dir.name,
            "created_at": created_utc.isoformat().replace("+00:00", "Z"),
            "status": "prepared",
            "suite_id": suite_id,
            "mode": mode,
            "repeat": repeat,
            "model": model,
            "tools": tools or [],
            "source_access": suite["source_access"],
            "live_web": suite["live_web"],
            "prompt_revision": f"catalog-v{catalog['schema_version']}@{commit[:7]}",
        },
        "skill": {
            "name": "evidence-deep-research",
            "version": _skill_version(skill_path),
            "commit": commit,
            "sha256": _sha256_file(skill_path),
        },
        "inputs": {
            "catalog": {
                "path": catalog_path.relative_to(root).as_posix(),
                "sha256": _sha256_file(catalog_path),
            },
            "suites": {
                "path": suites_path.relative_to(root).as_posix(),
                "sha256": _sha256_file(suites_path),
            },
        },
        "cases": case_records,
        "artifacts": {},
        "scope_note": (
            "This bundle prepares prompts and candidate evidence only. It does not run a model, "
            "score truth, or expose evaluator ground truth."
        ),
    }
    manifest_path = bundle_dir / "manifest.json"
    temporary_path = bundle_dir / "manifest.json.tmp"
    temporary_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(manifest_path)
    return bundle_dir, manifest


def _safe_input_path(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    resolved = (root / relative).resolve()
    return resolved if resolved.is_relative_to(root) else None


def validate_bundle(bundle_dir: Path, root: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []

    def issue(code: str, path: str, message: str) -> None:
        issues.append({"code": code, "path": path, "message": message})

    manifest_path = bundle_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        issue("bundle.unreadable_manifest", "$.manifest", str(exc))
        return _bundle_finish(issues, {})
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        issue("bundle.schema_version", "$.schema_version", "schema_version must be 1.")
        return _bundle_finish(issues, {})

    run = manifest.get("run")
    if not isinstance(run, dict) or run.get("id") != bundle_dir.name:
        issue("bundle.run_id_mismatch", "$.run.id",
              "run.id must match the bundle directory name.")
    skill = manifest.get("skill")
    if not isinstance(skill, dict):
        issue("bundle.missing_skill", "$.skill", "skill metadata is required.")
    else:
        skill_path = root / "SKILL.md"
        if not skill_path.is_file() or skill.get("sha256") != _sha256_file(skill_path):
            issue("bundle.skill_hash_mismatch", "$.skill.sha256",
                  "SKILL.md does not match the prepared bundle.")

    inputs = manifest.get("inputs")
    if not isinstance(inputs, dict):
        issue("bundle.missing_inputs", "$.inputs", "catalog and suite inputs are required.")
        inputs = {}
    for name in ("catalog", "suites"):
        record = inputs.get(name)
        path = f"$.inputs.{name}"
        if not isinstance(record, dict):
            issue("bundle.missing_input", path, f"{name} input metadata is required.")
            continue
        target = _safe_input_path(root, record.get("path"))
        if target is None or not target.is_file():
            issue("bundle.invalid_input_path", f"{path}.path",
                  f"{name} path must be a repository-relative file.")
        elif record.get("sha256") != _sha256_file(target):
            issue("bundle.input_hash_mismatch", f"{path}.sha256",
                  f"{name} input changed after bundle creation.")

    cases = manifest.get("cases")
    checked_files = 0
    if not isinstance(cases, list) or not cases:
        issue("bundle.invalid_cases", "$.cases", "cases must be a non-empty array.")
        cases = []
    for case_index, case in enumerate(cases):
        case_path = f"$.cases[{case_index}]"
        if not isinstance(case, dict) or not isinstance(case.get("prompt"), str):
            issue("bundle.invalid_case", case_path, "Each case requires a prompt.")
            continue
        prompt_hash = _sha256_bytes(case["prompt"].encode("utf-8"))
        if case.get("prompt_sha256") != prompt_hash:
            issue("bundle.prompt_hash_mismatch", f"{case_path}.prompt_sha256",
                  "Prompt text does not match its recorded hash.")
        candidate_files = case.get("candidate_files")
        if not isinstance(candidate_files, list):
            issue("bundle.invalid_candidate_files", f"{case_path}.candidate_files",
                  "candidate_files must be an array.")
            continue
        for file_index, record in enumerate(candidate_files):
            file_path = f"{case_path}.candidate_files[{file_index}]"
            if not isinstance(record, dict):
                issue("bundle.invalid_candidate_file", file_path,
                      "Candidate file metadata must be an object.")
                continue
            relative_value = record.get("path")
            if isinstance(relative_value, str) and "ground-truth" in relative_value.lower():
                issue("bundle.ground_truth_exposed", f"{file_path}.path",
                      "Evaluator ground truth cannot be candidate material.")
            target = _safe_input_path(root, relative_value)
            if target is None or not target.is_file():
                issue("bundle.invalid_candidate_path", f"{file_path}.path",
                      "Candidate path must be a repository-relative file.")
            elif record.get("sha256") != _sha256_file(target):
                issue("bundle.candidate_hash_mismatch", f"{file_path}.sha256",
                      "Candidate file changed after bundle creation.")
            else:
                checked_files += 1
    return _bundle_finish(
        issues,
        {"case_count": len(cases), "candidate_files_checked": checked_files},
    )


def create_matrix(
    *, root: Path, suites_path: Path, catalog_path: Path, suite_id: str,
    model: str, output_parent: Path, tools: list[str] | None = None,
    now: datetime | None = None,
) -> tuple[Path, dict[str, Any]]:
    suites = json.loads(suites_path.read_text(encoding="utf-8"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_validation = validate_catalog(catalog)
    if catalog_validation["verdict"] != "PASS":
        raise ValueError(f"Invalid case catalog: {catalog_validation['issues']}")
    validation = validate_suites(suites, catalog)
    if validation["verdict"] != "PASS":
        raise ValueError(f"Invalid suite manifest: {validation['issues']}")
    suite = next((item for item in suites["suites"] if item["id"] == suite_id), None)
    if suite is None:
        raise ValueError(f"Unknown suite: {suite_id}")
    if not model.strip():
        raise ValueError("model must be recorded explicitly; use 'unavailable' when hidden.")
    created = (now or datetime.now(UTC)).astimezone(UTC)
    timestamp = created.strftime("%Y%m%dT%H%M%SZ")
    matrix_dir = _unique_directory(output_parent, f"{timestamp}-{suite_id}-matrix")
    bundles: list[dict[str, Any]] = []
    blind_ids: set[str] = set()
    for repeat in range(1, suite["repeats"] + 1):
        for mode in suite["modes"]:
            bundle_dir, _ = create_bundle(
                root=root,
                suites_path=suites_path,
                catalog_path=catalog_path,
                suite_id=suite_id,
                mode=mode,
                model=model,
                output_parent=matrix_dir,
                repeat=repeat,
                tools=tools,
                now=created,
            )
            manifest_path = bundle_dir / "manifest.json"
            blind_id = ""
            while not blind_id or blind_id in blind_ids:
                blind_id = f"candidate-{secrets.token_hex(6)}"
            blind_ids.add(blind_id)
            bundles.append({
                "mode": mode,
                "repeat": repeat,
                "blind_id": blind_id,
                "path": bundle_dir.relative_to(matrix_dir).as_posix(),
                "manifest_sha256": _sha256_file(manifest_path),
            })
    matrix = {
        "schema_version": 1,
        "suite_id": suite_id,
        "model": model,
        "modes": suite["modes"],
        "repeats": suite["repeats"],
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "expected_run_count": len(suite["modes"]) * suite["repeats"],
        "bundles": bundles,
        "scope_note": (
            "This matrix prepares isolated run bundles only. It does not execute a model "
            "or claim that any repeated pilot was completed."
        ),
    }
    temporary = matrix_dir / "matrix.json.tmp"
    temporary.write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(matrix_dir / "matrix.json")
    return matrix_dir, matrix


def validate_matrix(matrix_dir: Path, root: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []

    def issue(code: str, path: str, message: str) -> None:
        issues.append({"code": code, "path": path, "message": message})

    try:
        matrix = json.loads((matrix_dir / "matrix.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        issue("matrix.unreadable", "$.matrix", str(exc))
        return _bundle_finish(issues, {})
    if not isinstance(matrix, dict) or matrix.get("schema_version") != 1:
        issue("matrix.schema_version", "$.schema_version", "schema_version must be 1.")
        return _bundle_finish(issues, {})
    bundles = matrix.get("bundles")
    if not isinstance(bundles, list) or not bundles:
        issue("matrix.invalid_bundles", "$.bundles", "bundles must be a non-empty array.")
        bundles = []
    if matrix.get("expected_run_count") != len(bundles):
        issue("matrix.run_count_mismatch", "$.expected_run_count",
              "expected_run_count must equal the recorded bundle count.")
    modes = matrix.get("modes")
    repeats = matrix.get("repeats")
    if not isinstance(modes, list) or not modes or not all(_text(mode) for mode in modes) \
            or len(modes) != len(set(modes)):
        issue("matrix.invalid_modes", "$.modes", "modes must be a non-empty unique array.")
        modes = []
    if not isinstance(repeats, int) or isinstance(repeats, bool) or repeats < 1:
        issue("matrix.invalid_repeats", "$.repeats", "repeats must be a positive integer.")
        repeats = 0
    expected_combinations = {
        (mode, repeat) for mode in modes for repeat in range(1, repeats + 1)
    }
    combinations: set[tuple[Any, Any]] = set()
    blind_ids: set[str] = set()
    checked = 0
    resolved_matrix = matrix_dir.resolve()
    for index, record in enumerate(bundles):
        path = f"$.bundles[{index}]"
        if not isinstance(record, dict):
            issue("matrix.invalid_bundle", path, "Bundle record must be an object.")
            continue
        mode = record.get("mode")
        repeat = record.get("repeat")
        if not _text(mode) or not isinstance(repeat, int) or isinstance(repeat, bool) \
                or repeat < 1:
            issue("matrix.invalid_run", path,
                  "Bundle mode must be text and repeat must be a positive integer.")
            continue
        combination = (mode, repeat)
        if combination in combinations:
            issue("matrix.duplicate_run", path, f"Duplicate run: {combination}")
        combinations.add(combination)
        blind_id = record.get("blind_id")
        if not isinstance(blind_id, str) or not re.fullmatch(
            r"candidate-[0-9a-f]{12}", blind_id
        ):
            issue("matrix.invalid_blind_id", f"{path}.blind_id",
                  "blind_id must be an opaque candidate identifier.")
        elif blind_id in blind_ids:
            issue("matrix.duplicate_blind_id", f"{path}.blind_id",
                  f"Duplicate blind_id: {blind_id}")
        else:
            blind_ids.add(blind_id)
        relative = record.get("path")
        if not isinstance(relative, str) or not relative.strip():
            issue("matrix.invalid_path", f"{path}.path", "Bundle path is required.")
            continue
        bundle_dir = (matrix_dir / relative).resolve()
        if not bundle_dir.is_relative_to(resolved_matrix) or bundle_dir == resolved_matrix:
            issue("matrix.unsafe_path", f"{path}.path",
                  "Bundle path must stay inside the matrix directory.")
            continue
        manifest_path = bundle_dir / "manifest.json"
        if not manifest_path.is_file():
            issue("matrix.missing_manifest", f"{path}.path", "Bundle manifest is missing.")
            continue
        if record.get("manifest_sha256") != _sha256_file(manifest_path):
            issue("matrix.manifest_hash_mismatch", f"{path}.manifest_sha256",
                  "Bundle manifest hash does not match the matrix.")
            continue
        validation = validate_bundle(bundle_dir, root)
        if validation["verdict"] != "PASS":
            issue("matrix.invalid_bundle", path,
                  f"Bundle validation failed: {validation['issues']}")
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        run = manifest["run"]
        if (run.get("mode"), run.get("repeat")) != combination:
            issue("matrix.run_metadata_mismatch", path,
                  "Bundle mode/repeat differs from the matrix record.")
            continue
        if run.get("suite_id") != matrix.get("suite_id") or run.get("model") != matrix.get("model"):
            issue("matrix.fingerprint_mismatch", path,
                  "Bundle suite or model differs from the matrix fingerprint.")
            continue
        checked += 1
    if combinations != expected_combinations:
        issue("matrix.combination_mismatch", "$.bundles",
              f"Mode/repeat coverage differs; expected={sorted(expected_combinations)}, "
              f"observed={sorted(combinations)}.")
    return _bundle_finish(
        issues,
        {"bundle_count": len(bundles), "bundles_checked": checked},
    )


def _bundle_finish(issues: list[dict[str, str]], summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": "PASS" if not issues else "FAIL",
        "error_count": len(issues),
        "summary": summary,
        "issues": issues,
        "scope_note": (
            "Bundle validation checks recorded bytes and isolation metadata; "
            "it does not run a model or prove research quality."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or validate evaluation run bundles.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create", help="Create a prepared run bundle.")
    create_parser.add_argument("--suite", required=True)
    create_parser.add_argument("--mode", required=True)
    create_parser.add_argument("--model", required=True)
    create_parser.add_argument("--output", type=Path, required=True)
    create_parser.add_argument("--repeat", type=int, default=1)
    create_parser.add_argument("--tool", action="append", default=[])
    create_parser.add_argument("--root", type=Path, default=Path.cwd())
    create_parser.add_argument("--suites", type=Path)
    create_parser.add_argument("--catalog", type=Path)
    validate_parser = subparsers.add_parser("validate", help="Verify a prepared bundle.")
    validate_parser.add_argument("bundle", type=Path)
    validate_parser.add_argument("--root", type=Path, default=Path.cwd())
    validate_parser.add_argument("--json", action="store_true")
    matrix_parser = subparsers.add_parser(
        "create-matrix", help="Create every declared mode and repeat bundle for a suite.",
    )
    matrix_parser.add_argument("--suite", required=True)
    matrix_parser.add_argument("--model", required=True)
    matrix_parser.add_argument("--output", type=Path, required=True)
    matrix_parser.add_argument("--tool", action="append", default=[])
    matrix_parser.add_argument("--root", type=Path, default=Path.cwd())
    matrix_parser.add_argument("--suites", type=Path)
    matrix_parser.add_argument("--catalog", type=Path)
    validate_matrix_parser = subparsers.add_parser(
        "validate-matrix", help="Verify every prepared bundle in a matrix.",
    )
    validate_matrix_parser.add_argument("matrix", type=Path)
    validate_matrix_parser.add_argument("--root", type=Path, default=Path.cwd())
    validate_matrix_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command in {"validate", "validate-matrix"}:
        result = (
            validate_bundle(args.bundle.resolve(), root)
            if args.command == "validate"
            else validate_matrix(args.matrix.resolve(), root)
        )
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            count_field = "case_count" if args.command == "validate" else "bundle_count"
            count_label = "cases" if args.command == "validate" else "bundles"
            print(f"{result['verdict']}: {result['summary'].get(count_field, 0)} "
                  f"{count_label}, {result['error_count']} errors")
            for item in result["issues"]:
                print(f"- ERROR {item['code']} {item['path']}: {item['message']}")
            print(result["scope_note"])
        return 0 if result["verdict"] == "PASS" else 1

    suites_path = (args.suites or root / "evals" / "suites.json").resolve()
    catalog_path = (args.catalog or root / "evals" / "cases.json").resolve()
    try:
        if args.command == "create-matrix":
            matrix_dir, matrix = create_matrix(
                root=root,
                suites_path=suites_path,
                catalog_path=catalog_path,
                suite_id=args.suite,
                model=args.model,
                output_parent=args.output.resolve(),
                tools=args.tool,
            )
            print(f"Created {matrix_dir}")
            print(matrix["scope_note"])
            return 0
        bundle_dir, manifest = create_bundle(
            root=root,
            suites_path=suites_path,
            catalog_path=catalog_path,
            suite_id=args.suite,
            mode=args.mode,
            model=args.model,
            output_parent=args.output.resolve(),
            repeat=args.repeat,
            tools=args.tool,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: could not create bundle: {exc}", file=sys.stderr)
        return 2
    print(f"Created {bundle_dir}")
    print(manifest["scope_note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
