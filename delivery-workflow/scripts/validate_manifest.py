#!/usr/bin/env python3
"""Validate the manifest, phase catalog, exclusions, method lessons and conditional governance.
Exit 0: approved; 1: blocked; 2: flagged."""
import hashlib
import json
import os
import sys
from typing import Optional, Tuple
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # delivery-workflow/
ARC_ROOT = HERE
from storage import personal_root
SCHEMA_DIR = HERE / "schemas"
CONFIG_DIR = HERE / "config"

# Die Basen sind kontextabhängig (Task-Standort, run_dir) und werden pro
# Audit-Lauf in audit_manifest() gesetzt. Default: nur ARC_ROOT.
_RESOLUTION_BASES: list[Path] = [ARC_ROOT]


def _git_toplevel(path: Path) -> Optional[Path]:
    import subprocess
    try:
        r = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return Path(r.stdout.strip()).resolve()


def _set_resolution_bases(task_path: Optional[Path], run_dir: Optional[Path]) -> None:
    global _RESOLUTION_BASES
    bases: list[Path] = []
    if task_path is not None:
        repo = _git_toplevel(task_path.parent if task_path.is_file() else task_path)
        if repo is not None:
            bases.append(repo)
    if task_path is not None:
        bases.append(task_path.parent if task_path.is_file() else task_path)
    bases.append(ARC_ROOT)
    if run_dir is not None:
        bases.append(run_dir)
    seen: set = set()
    _RESOLUTION_BASES = [b for b in bases if not (b in seen or seen.add(b))]


def _resolve_candidates(ref: str) -> list[Path]:
    if not ref:
        return []
    p = Path(ref).expanduser()
    if p.is_absolute():
        return [p] if p.exists() else []
    hits: list[Path] = []
    for base in _RESOLUTION_BASES:
        cand = base / p
        if cand.exists() and cand not in hits:
            hits.append(cand)
    return hits

# ─── Schema laden (implementiert Prüfung 1) ────────────────────────────────

def load_schema(name: str) -> dict:
    path = SCHEMA_DIR / f"{name}.schema.json"
    return json.loads(path.read_text(encoding='utf-8'))


def validate_schema(instance: dict) -> Optional[str]:
    error, _degraded = validate_schema_with_engine(instance)
    return error


def validate_schema_with_engine(instance: dict) -> Tuple[Optional[str], bool]:
    try:
        import jsonschema
        schema = load_schema("manifest")
        jsonschema.validate(instance, schema)
        return None, False
    except ImportError:
        # Fallback: minimale Schema-Prüfung ohne jsonschema
        return _minimal_schema_check(instance), True
    except jsonschema.ValidationError as e:
        return f"SCHEMA_INVALID: {e.message}", False


def _minimal_schema_check(instance: dict) -> Optional[str]:
    required = ["run_id", "task_ref", "phases"]
    for field in required:
        if field not in instance:
            return f"SCHEMA_INVALID: missing required field '{field}'"
    if not isinstance(instance["phases"], list) or len(instance["phases"]) < 3:
        return "SCHEMA_INVALID: phases must be a list with ≥3 entries"
    for p in instance["phases"]:
        if "phase" not in p or "decision" not in p:
            return f"SCHEMA_INVALID: phase entry missing 'phase' or 'decision': {p}"
        if p["decision"] not in ("included", "excluded"):
            return f"SCHEMA_INVALID: decision must be 'included' or 'excluded', got '{p['decision']}'"
        if p["decision"] == "excluded":
            if "reason_code" not in p:
                return f"SCHEMA_INVALID: excluded phase '{p['phase']}' missing reason_code"
            if p.get("reason_code") != "OPERATOR_ASSERTED" and "evidence_ref" not in p:
                return f"SCHEMA_INVALID: excluded phase '{p['phase']}' missing evidence_ref"
    return None


# ─── Katalog laden (implementiert Prüfung 2) ────────────────────────────────

def load_catalog() -> dict:
    import yaml
    path = CONFIG_DIR / "phase_catalog.yaml"
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def get_mandatory_phases(catalog: dict) -> list[str]:
    return [p["id"] for p in catalog["phases"] if p.get("mandatory")]


def get_phase_order(catalog: dict) -> list[str]:
    return [p["id"] for p in catalog["phases"]]


# ─── Exclusion-Rules laden (implementiert Prüfung 3) ────────────────────────

def load_exclusion_rules() -> dict:
    import yaml
    path = CONFIG_DIR / "exclusion_rules.yaml"
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def get_valid_codes_for_phase(rules: dict, phase: str) -> list[str]:
    valid = []
    for rule in rules["rules"]:
        if phase in rule["valid_for"]:
            valid.append(rule["reason_code"])
    return valid


# ─── Evidence-Prüfung (implementiert Prüfung 4) ─────────────────────────────

def evidence_exists(ref: str) -> bool:
    return len(_resolve_candidates(ref)) > 0


# ─── Lessons-Registry (Prüfung 6) ───────────────────────────────────────

LESSONS_PATH = HERE / "config" / "lessons.yaml"


def load_lessons() -> list[dict]:
    import yaml
    rows = []
    root = personal_root(required=False)
    paths = [LESSONS_PATH] + ([root / "lessons.yaml"] if root else [])
    for path in paths:
        if path.is_file():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            rows.extend(raw.get("lessons", []))
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate lesson IDs across seed and personal registry")
    return rows


def _lesson_matches(trigger: dict, manifest: dict, phase_names: set) -> bool:
    # trigger.always → immer match
    if trigger.get("always"):
        return True

    # phase_included: Phase muss im Manifest sein
    if "phase_included" in trigger:
        if trigger["phase_included"] not in phase_names:
            return False

    # deliverable_glob: Prüft ob Manifest Deliverables das Muster treffen
    if "deliverable_glob" in trigger:
        import fnmatch
        dlvs = manifest.get("deliverables", [])
        pattern = trigger["deliverable_glob"]
        if not any(fnmatch.fnmatch(d, pattern) for d in dlvs):
            # Fallback: Phase-Deliverables prüfen
            phase_dlvs = []
            for p in manifest.get("phases", []):
                if p.get("deliverables"):
                    phase_dlvs.extend(p["deliverables"])
            if not any(fnmatch.fnmatch(d, pattern) for d in phase_dlvs):
                return False

    # keyword: Text in echtem task.md-Inhalt, nicht im Pfadstring.
    # Fallback auf task_ref-String nur wenn die Datei nicht auflösbar ist,
    # damit alte Fixtures ohne echtes task.md ihr bisheriges Verhalten behalten.
    if "keyword" in trigger:
        import re
        task_ref = manifest.get("task_ref", "")
        task_text = _read_ref_text_for_matching(task_ref)
        haystack = task_text if task_text is not None else task_ref
        if not re.search(trigger["keyword"], haystack, re.IGNORECASE):
            return False

    return True


def _read_ref_text_for_matching(ref: str) -> Optional[str]:
    for candidate in _resolve_candidates(ref):
        try:
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8")
                if text.startswith("---\n"):
                    text = text.split("---", 2)[-1]
                return text
        except OSError:
            continue
    return None


# ─── Governance-Module (Prüfung 7, Lifecycle Adoption Proof) ────────────────

GOVERNANCE_PATH = HERE / "config" / "governance_modules.yaml"


def _resolve_ref_path(ref: str) -> Optional[Path]:
    hits = _resolve_candidates(ref)
    return hits[0] if hits else None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_task_text(manifest: dict) -> Optional[str]:
    task_path = _resolve_ref_path(manifest.get("task_ref", ""))
    if task_path is None or not task_path.is_file():
        return None
    try:
        text = task_path.read_text(encoding="utf-8")
        return text.split("---", 2)[-1] if text.startswith("---\n") else text
    except OSError:
        return None


def load_governance_modules() -> dict:
    import yaml
    if not GOVERNANCE_PATH.exists():
        return {}
    raw = yaml.safe_load(GOVERNANCE_PATH.read_text(encoding='utf-8'))
    if not raw or "modules" not in raw:
        return {}
    return raw["modules"]


def _governance_trigger_matches(trigger: dict, text: str) -> bool:
    import re
    if "any" not in trigger and "all" not in trigger:
        return False
    ok = True
    if "any" in trigger:
        ok = ok and any(re.search(pat, text, re.IGNORECASE) for pat in trigger["any"])
    if "all" in trigger:
        ok = ok and all(re.search(pat, text, re.IGNORECASE) for pat in trigger["all"])
    return ok


# ─── Hauptprüfschleife ──────────────────────────────────────────────────────

def audit_manifest(manifest_path: str) -> dict:
    import yaml
    manifest_raw = yaml.safe_load(Path(manifest_path).read_text(encoding='utf-8'))
    catalog = load_catalog()
    rules = load_exclusion_rules()
    mandatory = get_mandatory_phases(catalog)
    phase_order = get_phase_order(catalog)

    result = {
        "run_id": manifest_raw.get("run_id", "unknown"),
        "manifest_ref": manifest_path,
        "schema_mode": "jsonschema",
        "status": "approved",
        "flags": [],
        "annotations": [],
        "violations": [],
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }

    result["manifest_sha256"] = _sha256_file(Path(manifest_path))

    # nach task_ref-Auflösung final inkl. Task-Repo.
    run_dir = Path(manifest_path).resolve().parent
    _set_resolution_bases(None, run_dir)

    # Integrity Core: task_ref ist die Quelle für Lessons/Governance-Trigger.
    # Wenn sie nicht auflösbar ist, darf die Prüfung nicht still übersprungen werden.
    task_path = _resolve_ref_path(manifest_raw.get("task_ref", ""))
    _set_resolution_bases(task_path, run_dir)
    if manifest_raw.get('project_root'):
        project = Path(manifest_raw['project_root']).expanduser().resolve()
        if not project.is_dir():
            result['violations'].append({'phase': '_project', 'rule': 'PROJECT_NOT_FOUND',
                                         'detail': 'Target workspace does not exist'})
        elif project not in _RESOLUTION_BASES:
            _RESOLUTION_BASES.insert(0, project)
    if task_path is None or not task_path.is_file():
        result["violations"].append({
            "phase": "_task",
            "rule": "TASK_REF_NOT_FOUND",
            "detail": f"task_ref cannot be resolved: {manifest_raw.get('task_ref', '')}",
        })

    # Prüfung 1: Schema validieren
    schema_error, schema_degraded = validate_schema_with_engine(manifest_raw)
    if schema_degraded:
        result["schema_mode"] = "minimal_degraded"
        result["flags"].append({
            "phase": "_schema",
            "rule": "SCHEMA_DEGRADED",
            "reason": "SCHEMA_DEGRADED: jsonschema unavailable; minimal fallback used",
            "severity": "warn",
        })
    if schema_error:
        result["status"] = "blocked"
        result["violations"].append({
            "phase": "_schema",
            "rule": "SCHEMA_INVALID",
            "detail": schema_error,
        })
        return result

    phases = manifest_raw["phases"]
    actual = [p["phase"] for p in phases]
    if actual != phase_order:
        result["violations"].append({"phase": "_catalog", "rule": "PHASE_CATALOG_MISMATCH",
                                     "detail": "Include every catalog phase exactly once, in order"})
    phase_names = {p["phase"] for p in phases if p["decision"] == "included"}

    # Schema-Validierung: lessons_ack-Einträge
    ack_list = manifest_raw.get("lessons_ack", [])
    lessons = load_lessons()
    valid_ids = {l["id"] for l in lessons}
    for ack in ack_list:
        if not isinstance(ack, dict):
            result["flags"].append({
                "phase": "_schema",
                "rule": "ACK_INVALID",
                "detail": f"lessons_ack entry is not an object: {ack}",
            })
            continue
        if ack.get("id") not in valid_ids:
            result["flags"].append({
                "phase": "_schema",
                "rule": "ACK_ID_UNKNOWN",
                "detail": f"lessons_ack.id '{ack.get('id')}' does not exist in the registry",
            })
        if ack.get("status") not in ("applied", "not_applicable"):
            result["flags"].append({
                "phase": "_schema",
                "rule": "ACK_STATUS_INVALID",
                "detail": f"lessons_ack.status '{ack.get('status')}' — expected 'applied' or 'not_applicable'",
            })

    # Prüfung 2: Mandatory-Phasen nicht excluded
    for m in mandatory:
        if m not in phase_names:
            result["status"] = "blocked"
            result["violations"].append({
                "phase": m,
                "rule": "MANDATORY_EXCLUDED",
                "detail": f"Mandatory phase '{m}' is missing from the manifest",
            })
        else:
            entry = next(p for p in phases if p["phase"] == m)
            if entry["decision"] != "included":
                result["status"] = "blocked"
                result["violations"].append({
                    "phase": m,
                    "rule": "MANDATORY_EXCLUDED",
                    "detail": f"Mandatory phase '{m}' was excluded (reason: {entry.get('reason_code', 'none')})",
                })

    # Prüfung 3+4+5: reason_codes, evidence, deliverables
    for p in phases:
        if p["decision"] != "excluded":
            continue
        code = p.get("reason_code", "")
        valid_codes = get_valid_codes_for_phase(rules, p["phase"])

        if code not in valid_codes:
            if code == "OPERATOR_ASSERTED":
                result["flags"].append({
                    "phase": p["phase"],
                    "reason": f"OPERATOR_ASSERTED — no checkable evidence",
                    "evidence": p.get("evidence_ref", "none"),
                })
            else:
                result["violations"].append({
                    "phase": p["phase"],
                    "rule": "INVALID_REASON_CODE",
                    "detail": f"'{code}' is not allowed for phase '{p['phase']}'. Allowed: {valid_codes}",
                })
        elif code == "OPERATOR_ASSERTED":
            # Auch wenn OPERATOR_ASSERTED in valid_for ist: immer flaggen.
            # Der Operator muss jeden Ausschluss bestätigen — stille Annahmen sind
            # gefährlicher als explizite Prüfung (Erkenntnis aus 2026-07-05: tested ≠ validated).
            result["flags"].append({
                "phase": p["phase"],
                "reason": "OPERATOR_ASSERTED — unresolved exclusion",
                "evidence": p.get("evidence_ref", "none"),
            })

        if code != "OPERATOR_ASSERTED":
            ev = p.get("evidence_ref", "")
            if not ev:
                result["violations"].append({
                    "phase": p["phase"],
                    "rule": "MISSING_EVIDENCE",
                    "detail": f"Phase '{p['phase']}' excluded without evidence_ref",
                })
            else:
                hits = _resolve_candidates(ev)
                if not hits:
                    result["flags"].append({
                        "phase": p["phase"],
                        "reason": f"EVIDENCE_NOT_FOUND: '{ev}' does not exist",
                        "evidence": ev,
                    })
                elif len(hits) > 1:
                    result["flags"].append({
                        "phase": p["phase"],
                        "rule": "EVIDENCE_AMBIGUOUS",
                        "reason": f"EVIDENCE_AMBIGUOUS: '{ev}' resolves at {len(hits)} locations: "
                                  + " | ".join(str(h) for h in hits),
                        "evidence": ev,
                    })

        # Prüfung 5: deliverables für NO_CODE-Prädikat
        if code == "NO_CODE":
            deliverables = manifest_raw.get("deliverables", []) + [d for phase in phases for d in phase.get("deliverables", [])]
            if deliverables:
                code_files = [d for d in deliverables if d.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".sh", ".ps1", ".go", ".java", ".rs", ".cs"))]
                if code_files:
                    result["flags"].append({
                        "phase": p["phase"],
                        "reason": f"NO_CODE with executable deliverables: {code_files}",
                        "evidence": str(deliverables),
                    })

    # Prüfung 6: Lessons-Registry
    lessons = load_lessons()
    if lessons:
        for lesson in lessons:
            if lesson.get("status") != "active":
                continue
            trigger = lesson.get("trigger", {})
            if not _lesson_matches(trigger, manifest_raw, phase_names):
                continue
            # Lesson matched → prüfe ob Manifest sie acknowledge
            ack_list = manifest_raw.get("lessons_ack", [])
            acked = next((a for a in ack_list if isinstance(a, dict) and a.get("id") == lesson["id"]), None)
            if not acked:
                entry = {
                    "phase": "_lessons",
                    "reason": f"LESSON_MATCH: {lesson['id']} — {lesson['rule'][:100]}",
                    "lessons_id": lesson["id"],
                    "rule": lesson["rule"],
                    "severity": "note",
                }
                # A match suggests relevant guidance; it does not create a new gate.
                result["annotations"].append(entry)
                continue
            if acked.get("status") not in ("applied", "not_applicable"):
                result["flags"].append({
                    "phase": "_lessons",
                    "reason": f"LESSON_ACK_INVALID: {lesson['id']} — status must be 'applied' or 'not_applicable'",
                    "lessons_id": lesson["id"],
                    "ack_status": acked.get("status"),
                })
                continue
            if acked.get("status") == "not_applicable":
                reason = acked.get("reason")
                if not isinstance(reason, str) or not reason.strip():
                    result["flags"].append({
                        "phase": "_lessons", "rule": "LESSON_ACK_NO_REASON",
                        "lessons_id": lesson["id"],
                        "reason": "Explain why this lesson does not apply in the existing task",
                    })
                else:
                    result["annotations"].append({
                        "phase": "_lessons", "lessons_id": lesson["id"],
                        "reason": "LESSON_NOT_APPLICABLE", "ack_reason": reason,
                        "severity": "note",
                    })
            # Guidance acknowledgments do not require separate proof artifacts.
            # Actual work is evidenced by the selected phase receipts.

    # Prüfung 7: Governance-Module (Lifecycle Adoption Proof)
    gov_modules = load_governance_modules()
    task_text = read_task_text(manifest_raw)
    if gov_modules and task_text is not None:
        gov_ack = manifest_raw.get("governance_ack", [])
        acks_by_module = {a.get("module"): a for a in gov_ack if isinstance(a, dict)}
        for mod_name, mod in gov_modules.items():
            if not _governance_trigger_matches(mod.get("trigger", {}), task_text):
                continue
            ack = acks_by_module.get(mod_name)
            if ack is None:
                result["annotations"].append({
                    "phase": "_governance", "module": mod_name,
                    "reason": f"GOVERNANCE_SUGGESTION: assess '{mod_name}' against the current task; keyword matches do not require extra work",
                    "severity": "note",
                })
                continue
            # Ack vorhanden → Status + Planzeit-Felder prüfen
            status = ack.get("status")
            if status not in ("included", "not_applicable", "anchor_missing"):
                result["flags"].append({
                    "phase": "_governance",
                    "module": mod_name,
                    "reason": f"GOVERNANCE_ACK_STATUS_INVALID: '{status}' for module '{mod_name}'",
                })
                continue
            if status == "not_applicable" and not ack.get("reason"):
                result["flags"].append({
                    "phase": "_governance",
                    "module": mod_name,
                    "reason": f"GOVERNANCE_ACK_NO_REASON: '{mod_name}' marked not_applicable without a reason",
                })
            if mod_name == "pipeline_chunking" and status == "included":
                for field in ("input_validator_ref", "validator_command", "validator_output_ref"):
                    if not ack.get(field):
                        result["flags"].append({
                            "phase": "_governance",
                            "module": mod_name,
                            "reason": f"GOVERNANCE_PLAN_FIELD_MISSING: pipeline_chunking.included without '{field}' (observed verdict belongs in the receipt)",
                        })

    # Finaler Status: blocked > flagged > approved
    if len(result["violations"]) > 0:
        result["status"] = "blocked"
    elif len(result["flags"]) > 0:
        result["status"] = "flagged"
    else:
        result["status"] = "approved"

    return result


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: validate_manifest.py <manifest.yaml>", file=sys.stderr)
        sys.exit(1)

    manifest_path = sys.argv[1]
    if not os.path.exists(manifest_path):
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    result = audit_manifest(manifest_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result["status"] == "blocked":
        sys.exit(1)
    elif result["status"] == "flagged":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
