#!/usr/bin/env python3
"""Validate run identity, audit consistency and ordered phase completion in the saved ledger."""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def _read_events(ledger_path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if not ledger_path.exists():
        return events
    with open(ledger_path, encoding='utf-8') as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                events.append({"event": "_invalid_json", "line": line_no, "error": str(exc)})
    return events


def validate(run_dir: str, manifest: dict) -> dict:
    run_path = Path(run_dir)
    ledger_path = run_path / "ledger.jsonl"
    expected_run_id = manifest.get("run_id", "unknown")
    events = _read_events(ledger_path)

    missing = [p["phase"] for p in manifest["phases"] if p["decision"] == "included"]
    issues: List[str] = []

    if not ledger_path.exists():
        return {
            "run_id": expected_run_id,
            "status": "incomplete",
            "missing_phases": missing,
            "issues": ["ledger missing"],
        }

    done_phases = set()
    audit_events = []
    observed_order = []
    previous_ts = None
    for event in events:
        if event.get("event") == "_invalid_json":
            issues.append(f"ledger invalid json at line {event.get('line')}: {event.get('error')}")
            continue
        if event.get("event") in {"manifest_proposed", "audit", "phase_done", "PENDING_JUDGMENT", "operator_approved", "run_complete"}:
            if event.get("run_id") != expected_run_id:
                issues.append(
                    f"run_id mismatch in {event.get('event')}: expected {expected_run_id}, got {event.get('run_id')}"
                )
        if event.get("event") == "audit":
            audit_events.append(event)
        if event.get("event") == "phase_done" and event.get("ok"):
            done_phases.add(event.get("phase"))
            observed_order.append(event.get("phase"))
        try:
            from datetime import datetime
            stamp = datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
            if stamp.tzinfo is None or (previous_ts is not None and stamp < previous_ts):
                issues.append("ledger timestamp order or timezone invalid")
            previous_ts = stamp
        except (KeyError, ValueError, TypeError):
            issues.append("ledger timestamp invalid")

    expected_order = [p["phase"] for p in manifest["phases"] if p["decision"] == "included"]
    if observed_order != expected_order:
        issues.append("phase_done events must match included phases exactly once in order")
    if not audit_events or audit_events[0].get("status") != "approved":
        issues.append("approved audit event required before execution")
    if events and events[0].get("event") not in {"audit", "manifest_proposed"}:
        issues.append("ledger must start with its audit or manifest event")

    missing = []
    for p in manifest["phases"]:
        if p["decision"] == "included" and p["phase"] not in done_phases:
            missing.append(p["phase"])

    audit_result_path = run_path / "audit_result.json"
    if audit_result_path.exists():
        try:
            audit_result = json.loads(audit_result_path.read_text(encoding='utf-8'))
        except Exception as exc:
            issues.append(f"audit_result unreadable: {exc}")
        else:
            if audit_result.get("run_id") != expected_run_id:
                issues.append(
                    f"audit_result run_id mismatch: expected {expected_run_id}, got {audit_result.get('run_id')}"
                )
            if audit_events:
                last_audit = audit_events[-1]
                if last_audit.get("status") != audit_result.get("status"):
                    issues.append(
                        f"audit status mismatch: ledger={last_audit.get('status')} audit_result={audit_result.get('status')}"
                    )
                if last_audit.get("status") == "approved" and audit_result.get("status") != "approved":
                    issues.append("ledger audit approved contradicts non-approved audit_result")
    elif audit_events:
        issues.append("ledger has audit event but audit_result.json is missing")

    status = "ok" if not missing and not issues else "incomplete"
    return {
        "run_id": expected_run_id,
        "status": status,
        "missing_phases": missing,
        "issues": issues,
        "errors": issues,
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: validate_ledger.py <run_dir> <manifest.yaml>", file=sys.stderr)
        sys.exit(1)

    run_dir = sys.argv[1]
    manifest_path = sys.argv[2]

    import yaml
    manifest = yaml.safe_load(Path(manifest_path).read_text(encoding='utf-8'))
    result = validate(run_dir, manifest)
    result["manifest_ref"] = manifest_path
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result["status"] != "ok":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
