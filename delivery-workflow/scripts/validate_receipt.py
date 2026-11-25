#!/usr/bin/env python3
"""Validate the evidence and optional manifest binding of a phase receipt.
Exit 0: approved; 1: blocked."""
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent.parent
ARC_ROOT = HERE
from storage import personal_root
SCHEMA_PATH = HERE / "schemas" / "receipt.schema.json"
VALID_STATUSES = {
    "archived", "blocked", "done", "ready", "review", "running", "scheduled", "todo", "triage"
}


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def validate_schema(instance: Dict[str, Any]) -> List[str]:
    try:
        import jsonschema  # type: ignore
        schema = load_json(SCHEMA_PATH)
        jsonschema.validate(instance, schema)
        return []
    except ImportError:
        return minimal_schema_check(instance)
    except Exception as exc:
        return [f"SCHEMA_INVALID: {exc}"]


def minimal_schema_check(instance: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    required = ["run_id", "phase", "gate", "ok", "timestamp"]
    for field in required:
        if field not in instance:
            errors.append(f"MISSING_FIELD: {field}")
    if errors:
        return errors
    if not isinstance(instance["run_id"], str):
        errors.append("FIELD_TYPE: run_id must be string")
    if not isinstance(instance["phase"], str):
        errors.append("FIELD_TYPE: phase must be string")
    if not isinstance(instance["gate"], str):
        errors.append("FIELD_TYPE: gate must be string")
    if not isinstance(instance["ok"], bool):
        errors.append("FIELD_TYPE: ok must be boolean")
    if "evidence" in instance and instance["evidence"] is not None and not isinstance(instance["evidence"], (str, dict)):
        errors.append("FIELD_TYPE: evidence must be string|object|null")
    if not isinstance(instance["timestamp"], str):
        errors.append("FIELD_TYPE: timestamp must be string")
    return errors


def resolve_path(ref: str, receipt_path: Path) -> Optional[Path]:
    raw = Path(ref).expanduser()
    candidates: List[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.extend([
            (receipt_path.parent / raw),
            (receipt_path.parent.parent / raw),
            (ARC_ROOT / raw),
            (Path.cwd() / raw),
        ])
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return None


def require_file(ref: Any, receipt_path: Path, label: str, errors: List[str]) -> Optional[Path]:
    if not isinstance(ref, str) or not ref.strip():
        errors.append(f"{label}: missing path")
        return None
    resolved = resolve_path(ref, receipt_path)
    if resolved is None or not resolved.is_file():
        errors.append(f"{label}: path not found: {ref}")
        return None
    return resolved


def require_dict(value: Any, label: str, errors: List[str]) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        errors.append(f"{label}: expected object")
        return None
    return value


def require_nonempty_str(value: Any, label: str, errors: List[str]) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: expected non-empty string")
        return None
    return value.strip()


def _default_board_db(board: str) -> Path:
    if board == "default":
        return personal_root() / "kanban.db"
    return personal_root() / "kanban" / "boards" / board / "kanban.db"


def validate_kanban_payload(payload: Any, receipt_path: Path, errors: List[str], expected_status: Optional[str] = None) -> None:
    data = require_dict(payload, "kanban", errors)
    if data is None:
        return
    board = data.get("board")
    board_db = data.get("board_db")
    if not isinstance(board_db, str) or not board_db.strip():
        board = require_nonempty_str(board, "kanban.board", errors)
        if board is not None:
            board_db_path = _default_board_db(board)
        else:
            board_db_path = None
    else:
        board_db_path = Path(board_db).expanduser().resolve()
    if board_db_path is None:
        return
    if not board_db_path.exists():
        errors.append(f"kanban.board_db: path not found: {board_db_path}")
        return
    task_ids = data.get("task_ids")
    if not isinstance(task_ids, list) or not task_ids or not all(isinstance(t, str) and t.strip() for t in task_ids):
        errors.append("kanban.task_ids: expected non-empty string list")
        return
    conn = None
    try:
        conn = sqlite3.connect(str(board_db_path), timeout=5.0)
        placeholders = ",".join("?" for _ in task_ids)
        rows = conn.execute(
            f"SELECT id, status FROM tasks WHERE id IN ({placeholders})",
            task_ids,
        ).fetchall()
    except Exception as exc:
        errors.append(f"kanban.query_failed: {exc}")
        return
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    row_map = {row[0]: row[1] for row in rows}
    missing = [task_id for task_id in task_ids if task_id not in row_map]
    if missing:
        errors.append(f"kanban.missing_tasks: {', '.join(missing)}")
    for task_id, status in row_map.items():
        if status not in VALID_STATUSES:
            errors.append(f"kanban.invalid_status[{task_id}]: {status}")
        if expected_status is not None and status != expected_status:
            errors.append(f"kanban.unexpected_status[{task_id}]: expected {expected_status}, got {status}")


def validate_understand(evidence: Dict[str, Any], receipt_path: Path, errors: List[str]) -> None:
    preflight = require_dict(evidence.get("preflight"), "understand.preflight", errors)
    if preflight is None:
        return
    status = require_nonempty_str(preflight.get("status"), "understand.preflight.status", errors)
    if status not in {"clean", "override"}:
        errors.append("understand.preflight.status: expected clean|override")
    require_file(preflight.get("evidence_ref"), receipt_path, "understand.preflight.evidence_ref", errors)
    require_file(evidence.get("problem_ref"), receipt_path, "understand.problem_ref", errors)
    require_nonempty_str(evidence.get("code_ref"), "understand.code_ref", errors)


def validate_spike(evidence: Dict[str, Any], receipt_path: Path, errors: List[str]) -> None:
    verdict = require_nonempty_str(evidence.get("verdict"), "spike.verdict", errors)
    if verdict not in {"VALIDATED", "PARTIAL", "INVALIDATED"}:
        errors.append("spike.verdict: expected VALIDATED|PARTIAL|INVALIDATED")
    require_file(evidence.get("evidence_ref"), receipt_path, "spike.evidence_ref", errors)


def validate_plan(evidence: Dict[str, Any], receipt_path: Path, errors: List[str]) -> None:
    require_file(evidence.get("plan_ref"), receipt_path, "plan.plan_ref", errors)
    # wenn vorhanden, muss er echt sein.
    if evidence.get("kanban") is not None:
        validate_kanban_payload(evidence.get("kanban"), receipt_path, errors)


def validate_constraints(evidence: Dict[str, Any], receipt_path: Path, errors: List[str]) -> None:
    require_file(evidence.get("validator_ref"), receipt_path, "constraints.validator_ref", errors)
    if evidence.get("good_case_exit_code") != 0:
        errors.append("constraints.good_case_exit_code: expected 0")
    if evidence.get("bad_case_exit_code") != 1:
        errors.append("constraints.bad_case_exit_code: expected 1")


def validate_tdd(evidence: Dict[str, Any], receipt_path: Path, errors: List[str]) -> None:
    require_file(evidence.get("red_ref"), receipt_path, "tdd.red_ref", errors)
    require_file(evidence.get("green_ref"), receipt_path, "tdd.green_ref", errors)
    if evidence.get("suite_exit_code") != 0:
        errors.append("tdd.suite_exit_code: expected 0")


def validate_integration(evidence: Dict[str, Any], receipt_path: Path, errors: List[str]) -> None:
    require_file(evidence.get("activation_ref"), receipt_path, "integration.activation_ref", errors)
    require_file(evidence.get("fallback_ref"), receipt_path, "integration.fallback_ref", errors)


def validate_cron(evidence: Dict[str, Any], receipt_path: Path, errors: List[str]) -> None:
    require_nonempty_str(evidence.get("cron_schedule"), "cron.cron_schedule", errors)
    require_file(evidence.get("artefact_path"), receipt_path, "cron.artefact_path", errors)
    if evidence.get("artefact_valid") is not True:
        errors.append("cron.artefact_valid: expected true")


def validate_doc(evidence: Dict[str, Any], receipt_path: Path, errors: List[str]) -> None:
    docs = evidence.get("updated_docs")
    if not isinstance(docs, list) or not docs:
        errors.append("doc.updated_docs: expected non-empty list")
        return
    for idx, ref in enumerate(docs):
        require_file(ref, receipt_path, f"doc.updated_docs[{idx}]", errors)


def validate_verify(evidence: Dict[str, Any], receipt_path: Path, errors: List[str]) -> None:
    checks = evidence.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("verify.checks: expected non-empty list")
        return
    live_seen = False
    for idx, check in enumerate(checks):
        item = require_dict(check, f"verify.checks[{idx}]", errors)
        if item is None:
            continue
        status = require_nonempty_str(item.get("status"), f"verify.checks[{idx}].status", errors)
        kind = require_nonempty_str(item.get("kind"), f"verify.checks[{idx}].kind", errors)
        if status != "pass":
            errors.append(f"verify.checks[{idx}].status: expected pass")
        if kind == "live":
            live_seen = True
        require_file(item.get("evidence_ref"), receipt_path, f"verify.checks[{idx}].evidence_ref", errors)
    if not live_seen:
        errors.append("verify.checks: at least one live check required")


def validate_postmortem(evidence: Dict[str, Any], receipt_path: Path, errors: List[str]) -> None:
    require_file(evidence.get("postmortem_ref"), receipt_path, "postmortem.postmortem_ref", errors)
    # aber die Extraktion muss nachweislich stattgefunden haben.
    lessons = require_dict(evidence.get("lessons"), "postmortem.lessons", errors)
    if lessons is not None:
        if not isinstance(lessons.get("extracted"), list):
            errors.append("postmortem.lessons.extracted: expected list (may be empty)")
        if "guard_impulse" in lessons and not isinstance(lessons.get("guard_impulse"), list):
            errors.append("postmortem.lessons.guard_impulse: expected list")
    if evidence.get("kanban") is not None:
        validate_kanban_payload(evidence.get("kanban"), receipt_path, errors, expected_status="done")
    cleanup = require_dict(evidence.get("cleanup"), "postmortem.cleanup", errors)
    if cleanup is None:
        return
    proof_artifacts = cleanup.get("proof_artifacts")
    if not isinstance(proof_artifacts, list) or not proof_artifacts:
        errors.append("postmortem.cleanup.proof_artifacts: expected non-empty list")
    else:
        for idx, ref in enumerate(proof_artifacts):
            require_file(ref, receipt_path, f"postmortem.cleanup.proof_artifacts[{idx}]", errors)
    process_removed = cleanup.get("process_artifacts_removed")
    if not isinstance(process_removed, list):
        errors.append("postmortem.cleanup.process_artifacts_removed: expected list")
    if process_removed:
        for idx, ref in enumerate(process_removed):
            if not isinstance(ref, str):
                errors.append(f"postmortem.cleanup.process_artifacts_removed[{idx}]: expected string")
    if cleanup.get("gitready") is not True:
        errors.append("postmortem.cleanup.gitready: expected true")


# ─── Governance-Evidence (Lifecycle Adoption Proof, nur verify-Receipts) ────

def _file_contains(path: Path, needle: str) -> bool:
    try:
        return needle.lower() in path.read_text(encoding='utf-8').lower()
    except OSError:
        return False


def validate_governance_consumer_map(gov: Dict[str, Any], receipt_path: Path,
                                     errors: List[str]) -> None:
    cm = gov.get("consumer_map")
    if not isinstance(cm, dict):
        return
    ref = require_file(cm.get("consumer_map_ref"), receipt_path,
                       "governance.consumer_map.consumer_map_ref", errors)
    if ref is None:
        return
    if not _file_contains(ref, "## Grep Evidence"):
        errors.append("governance.consumer_map: consumer map lacks '## Grep Evidence' section")
    if not _file_contains(ref, "Hardcoding"):
        errors.append("governance.consumer_map: consumer map lacks 'Hardcoding' column")


def validate_governance_quality_regression(gov: Dict[str, Any], receipt_path: Path,
                                           errors: List[str], warnings: List[str]) -> None:
    qr = gov.get("quality_regression")
    if not isinstance(qr, dict):
        return
    status = qr.get("status")
    if status == "anchor_missing":
        # Darf NICHT still als pass verschwinden — als sichtbare Warnung führen.
        missing = require_nonempty_str(qr.get("missing_anchor_for"),
                                       "governance.quality_regression.missing_anchor_for", errors)
        proposed = require_nonempty_str(qr.get("proposed_anchor_path"),
                                        "governance.quality_regression.proposed_anchor_path", errors)
        if missing and proposed:
            warnings.append(
                f"governance.quality_regression: anchor_missing for '{missing}' "
                f"— proposed anchor '{proposed}' (must not silently pass)")
        return
    require_file(qr.get("anchor_ref"), receipt_path,
                 "governance.quality_regression.anchor_ref", errors)
    require_file(qr.get("regression_review_ref"), receipt_path,
                 "governance.quality_regression.regression_review_ref", errors)


def validate_governance_pipeline_chunking(gov: Dict[str, Any], receipt_path: Path,
                                          errors: List[str]) -> None:
    pc = gov.get("pipeline_chunking")
    if not isinstance(pc, dict):
        return
    require_file(pc.get("input_validator_ref"), receipt_path,
                 "governance.pipeline_chunking.input_validator_ref", errors)
    out_ref = require_file(pc.get("validator_output_ref"), receipt_path,
                           "governance.pipeline_chunking.validator_output_ref", errors)
    llm_started = require_nonempty_str(pc.get("llm_run_started_at"),
                                       "governance.pipeline_chunking.llm_run_started_at", errors)
    if out_ref is None:
        return
    try:
        out_data = json.loads(out_ref.read_text(encoding='utf-8'))
    except Exception as exc:
        errors.append(f"governance.pipeline_chunking.validator_output_ref: unreadable JSON: {exc}")
        return
    if out_data.get("verdict") != "pass":
        errors.append("governance.pipeline_chunking: validator verdict must be 'pass', "
                      f"got '{out_data.get('verdict')}'")
    out_ts = out_data.get("timestamp")
    if not isinstance(out_ts, str) or not out_ts.strip():
        errors.append("governance.pipeline_chunking: validator output missing 'timestamp'")
    elif llm_started:
        from datetime import datetime
        try:
            validator_time = datetime.fromisoformat(out_ts.replace('Z', '+00:00'))
            llm_time = datetime.fromisoformat(llm_started.replace('Z', '+00:00'))
            if validator_time.tzinfo is None or llm_time.tzinfo is None:
                raise ValueError('timezone required')
            if validator_time >= llm_time:
                errors.append('governance.pipeline_chunking: validator must run BEFORE llm')
        except ValueError:
            errors.append('governance.pipeline_chunking: valid timezone-aware timestamps required')


def validate_governance(gov: Any, receipt_path: Path,
                        errors: List[str], warnings: List[str]) -> None:
    gov = require_dict(gov, "governance", errors)
    if gov is None:
        return
    validate_governance_consumer_map(gov, receipt_path, errors)
    validate_governance_quality_regression(gov, receipt_path, errors, warnings)
    validate_governance_pipeline_chunking(gov, receipt_path, errors)


def validate_manifest_bound_governance(evidence: Dict[str, Any], receipt_path: Path,
                                       errors: List[str]) -> None:
    manifest_ref = evidence.get("manifest_ref")
    if not manifest_ref:
        return
    manifest_path = require_file(manifest_ref, receipt_path, "verify.manifest_ref", errors)
    if manifest_path is None:
        return
    try:
        import yaml  # type: ignore
        manifest = yaml.safe_load(manifest_path.read_text(encoding='utf-8'))
    except Exception as exc:
        errors.append(f"verify.manifest_ref: unreadable manifest: {exc}")
        return
    gov_ack = manifest.get("governance_ack", []) if isinstance(manifest, dict) else []
    required = [
        str(ack.get("module")) for ack in gov_ack
        if isinstance(ack, dict)
        and ack.get("module")
        and ack.get("status") in {"included", "anchor_missing"}
    ]
    if not required:
        return
    gov = evidence.get("governance")
    if not isinstance(gov, dict):
        errors.append(
            "verify.governance.consumer_map: missing governance evidence for manifest_ack: "
            + ", ".join(required))
        return
    for module in required:
        if not isinstance(gov.get(module), dict) or not gov[module]:
            errors.append(f"verify.governance.{module}: missing evidence for manifest governance_ack")


def validate_phase(receipt: Dict[str, Any], receipt_path: Path,
                   warnings: List[str]) -> List[str]:
    errors: List[str] = []
    if receipt.get("ok") is not True:
        errors.append("receipt.ok: expected true for completed phase")
        return errors
    evidence = require_dict(receipt.get("evidence"), "receipt.evidence", errors)
    if evidence is None:
        return errors
    phase = receipt.get("phase")
    if not isinstance(phase, str):
        errors.append("receipt.phase: expected string")
        return errors
    validators = {
        "understand": validate_understand,
        "spike": validate_spike,
        "plan": validate_plan,
        "constraints": validate_constraints,
        "tdd": validate_tdd,
        "integration": validate_integration,
        "cron": validate_cron,
        "doc": validate_doc,
        "verify": validate_verify,
        "postmortem": validate_postmortem,
    }
    fn = validators.get(phase)
    if fn is None:
        errors.append(f"unknown phase: {phase}")
        return errors
    fn(evidence, receipt_path, errors)
    if phase == "verify":
        validate_manifest_bound_governance(evidence, receipt_path, errors)
    # Governance-Evidence nur für verify-Receipts (Lifecycle Adoption Proof).
    if phase == "verify" and "governance" in evidence:
        validate_governance(evidence["governance"], receipt_path, errors, warnings)
    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_receipt.py <receipt.json>", file=sys.stderr)
        return 1
    receipt_path = Path(sys.argv[1]).expanduser().resolve()
    receipt = load_json(receipt_path)
    manifest_arg: Optional[str] = None
    if "--manifest" in sys.argv:
        idx = sys.argv.index("--manifest")
        if idx + 1 < len(sys.argv):
            manifest_arg = sys.argv[idx + 1]
    if manifest_arg and receipt.get("phase") == "verify":
        evidence = receipt.setdefault("evidence", {})
        if isinstance(evidence, dict):
            evidence["manifest_ref"] = manifest_arg
    warnings: List[str] = []
    errors = validate_schema(receipt)
    if manifest_arg:
        import yaml
        bound = yaml.safe_load(Path(manifest_arg).read_text(encoding='utf-8'))
        if receipt.get("run_id") != bound.get("run_id"):
            errors.append("receipt.run_id: does not match manifest")
        if receipt.get("phase") not in {p["phase"] for p in bound["phases"] if p["decision"] == "included"}:
            errors.append("receipt.phase: not included in manifest")
    if not errors:
        errors = validate_phase(receipt, receipt_path, warnings)
    result = {
        "receipt": str(receipt_path),
        "phase": receipt.get("phase"),
        "status": "approved" if not errors else "blocked",
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
