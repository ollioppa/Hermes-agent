#!/usr/bin/env python3
"""Generate an ordered phase manifest from task frontmatter; unknown or invalid decisions fail."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent.parent  # delivery-workflow/
CONFIG_DIR = HERE / "config"


def make_run_id() -> str:
    now = datetime.now()
    return f"arc_{now.strftime('%Y%m%d_%H%M%S')}_{os.urandom(2).hex()}"


def load_yaml(path: Path) -> dict:
    import yaml
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def load_phase_catalog() -> list[dict]:
    return load_yaml(CONFIG_DIR / "phase_catalog.yaml")["phases"]


def load_exclusion_rules() -> list[dict]:
    return load_yaml(CONFIG_DIR / "exclusion_rules.yaml")["rules"]


def parse_task_frontmatter(task_path: Path) -> dict:
    text = task_path.read_text(encoding='utf-8')
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        raise ValueError('Unclosed task frontmatter')
    import yaml
    try:
        result = yaml.safe_load(text[3:end]) or {}
        if not isinstance(result, dict):
            raise ValueError('Task frontmatter must be an object')
        return result
    except yaml.YAMLError as exc:
        raise ValueError('Invalid task YAML') from exc


def get_default_reasons() -> dict:
    catalog = load_phase_catalog()
    reasons = {}
    for p in catalog:
        if p.get("default_reason"):
            reasons[p["id"]] = p["default_reason"]
    return reasons


def build_manifest(task_ref: str, frontmatter: dict,
                   include_all: bool = True) -> dict:
    catalog = load_phase_catalog()
    mandatory_ids = {p["id"] for p in catalog if p.get("mandatory")}
    default_reasons = get_default_reasons()

    phases = []
    requested = frontmatter.get("phases", {})
    if not isinstance(requested, dict) or set(requested) - {p['id'] for p in catalog}:
        raise ValueError('Task phases must be an object of known phase names')
    for name, choice in requested.items():
        if not isinstance(choice, dict) or choice.get('decision') not in ('included', 'excluded'):
            raise ValueError(f'Invalid phase decision: {name}')
        if name in mandatory_ids and choice['decision'] == 'excluded':
            raise ValueError(f'Mandatory phase cannot be excluded: {name}')
    for p in catalog:
        pid = p["id"]
        if pid in mandatory_ids:
            phases.append({"phase": pid, "decision": "included"})
            continue
        requested_phase = requested.get(pid, {})
        if requested_phase.get("decision") == "excluded":
            phases.append({
                "phase": pid,
                "decision": "excluded",
                "reason_code": requested_phase.get("reason_code", default_reasons.get(pid)),
                "evidence_ref": requested_phase.get("evidence_ref", task_ref),
            })
        else:
            phases.append({"phase": pid, "decision": "included"})

    manifest = {
        "run_id": make_run_id(),
        "task_ref": task_ref,
        "phases": phases,
        "lessons_ack": frontmatter.get("lessons_ack", []),
        "governance_ack": frontmatter.get("governance_ack", []),
        "deliverables": frontmatter.get("deliverables", []),
    }

    if frontmatter.get("project_root"):
        manifest["project_root"] = str(Path(frontmatter["project_root"]).expanduser().resolve())
    for entry in phases:
        supplied = requested.get(entry["phase"], {})
        if supplied.get("deliverables"):
            entry["deliverables"] = supplied["deliverables"]
    return manifest


def write_manifest(manifest: dict, output_path: Path) -> None:
    import yaml
    from storage import private_path
    output_path = Path(output_path).expanduser()
    if output_path.is_symlink():
        raise ValueError("Manifest destination must not be a symlink")
    output_path = private_path(output_path)
    content = yaml.safe_dump(manifest, default_flow_style=False, allow_unicode=True)
    # Exclusive creation refuses existing files and restricts private path metadata.
    fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Manifest: {output_path}")
    print(f"  Phases:   {len(manifest['phases'])} — "
          f"{sum(1 for p in manifest['phases'] if p['decision'] == 'included')} included")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: generate_manifest.py <task.md> [--output <path>]", file=sys.stderr)
        return 1

    task_path = Path(sys.argv[1]).expanduser().resolve()
    if not task_path.exists():
        print(f"ERROR: task.md not found: {task_path}", file=sys.stderr)
        return 1

    # Parse args
    output_path = None
    for i, arg in enumerate(sys.argv[2:], start=2):
        if arg == "--output" and i + 1 < len(sys.argv):
            output_path = Path(sys.argv[i + 1]).expanduser()
        elif arg == "--no-default-include":
            include_all = False

    # Default output: neben task.md
    if output_path is None:
        output_path = task_path.parent / "manifest.yaml"

    task_ref = str(task_path)
    frontmatter = parse_task_frontmatter(task_path)

    manifest = build_manifest(task_ref, frontmatter, include_all=True)

    write_manifest(manifest, output_path)

    # Kurzvalidierung
    from validate_manifest import audit_manifest
    audit = audit_manifest(str(output_path))
    status = audit["status"]
    print(f"  Auditor:   {status}")
    if status == "flagged":
        for f in audit.get("flags", []):
            print(f"    ⚑ {f.get('phase')}: {f.get('reason', '')[:80]}")
        return 2
    elif status == "blocked":
        for v in audit.get("violations", []):
            print(f"    🔴 {v.get('phase')}: {v.get('detail', '')[:80]}")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
