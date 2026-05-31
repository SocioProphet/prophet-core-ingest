#!/usr/bin/env python3
"""Validate WallGuard ingest label examples."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "wallguard-ingest-labels.schema.json"
EXAMPLE_DIR = ROOT / "examples" / "wallguard-ingest-labels"
RESTRICTED_CLASSES = {"client_confidential", "matter_restricted", "wall_restricted"}
UNKNOWN_VALUES = {"unknown", "", None}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_schema(instance: dict, schema: dict, *, source_label: str) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        lines = [f"{source_label} failed schema validation:"]
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            lines.append(f" - {location}: {error.message}")
        raise ValueError("\n".join(lines))


def semantic_diagnostics(record: dict) -> list[str]:
    diagnostics: list[str] = []
    classification = record["classification"]
    label_state = record["label_state"]
    restricted = classification in RESTRICTED_CLASSES
    required_scope = ["client_ref", "matter_ref", "workroom_ref", "wall_ref"]
    missing_scope = [key for key in required_scope if record.get(key) in UNKNOWN_VALUES]

    if restricted and missing_scope and label_state != "quarantined":
        diagnostics.append(f"restricted ingest with missing scope must be quarantined: {missing_scope}")
    if restricted and label_state == "complete" and missing_scope:
        diagnostics.append(f"complete restricted ingest cannot have missing scope: {missing_scope}")
    if label_state == "quarantined" and not record.get("quarantine_reason"):
        diagnostics.append("quarantined ingest requires quarantine_reason")
    if label_state == "quarantined" and record.get("clean_room_eligible") is True:
        diagnostics.append("quarantined ingest cannot be clean_room_eligible")
    if label_state == "quarantined" and record.get("permitted_destination_refs"):
        diagnostics.append("quarantined ingest cannot permit destinations")
    if label_state == "quarantined" and record.get("permitted_subject_refs"):
        diagnostics.append("quarantined ingest cannot permit subjects")
    if label_state == "complete" and restricted:
        if not record.get("permitted_destination_refs"):
            diagnostics.append("complete restricted ingest requires permitted destinations")
        if not record.get("permitted_subject_refs"):
            diagnostics.append("complete restricted ingest requires permitted subjects")
        if not record.get("policy_refs"):
            diagnostics.append("complete restricted ingest requires policy refs")
    if not any(ref.startswith("policy-fabric://") for ref in record.get("policy_refs", [])):
        diagnostics.append("policy_refs must include a Policy Fabric ref")

    return diagnostics


def main() -> int:
    schema = load_json(SCHEMA)
    Draft202012Validator.check_schema(schema)
    examples = sorted(EXAMPLE_DIR.glob("*.json"))
    if not examples:
        raise SystemExit("No WallGuard ingest label examples found")

    results = []
    for path in examples:
        record = load_json(path)
        validate_schema(record, schema, source_label=str(path.relative_to(ROOT)))
        diagnostics = semantic_diagnostics(record)
        expected = "pass"
        actual = "fail" if diagnostics else "pass"
        result = {"example": path.name, "expected": expected, "actual": actual, "diagnostics": diagnostics}
        results.append(result)
        if actual != expected:
            raise ValueError(json.dumps(result, indent=2))

    print(json.dumps({"ok": True, "checked": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
