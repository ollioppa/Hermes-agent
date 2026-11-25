#!/usr/bin/env python3
"""Delivery Workflow coordinator: audit, record evidence, resume and check. Never pushes Git."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from storage import SKILL_ROOT, configure, locked, personal_root, private_path, write, write_json

HERE = SKILL_ROOT


def now():
    return datetime.now(timezone.utc).isoformat()


def make_run_id():
    return f"arc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(2).hex()}"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_phase_catalog():
    import yaml
    return yaml.safe_load((HERE / 'config/phase_catalog.yaml').read_text(encoding='utf-8'))['phases']


def assignment(phase):
    """Reuse the catalog's current phase instruction; no separate prompt registry."""
    item = next((p for p in load_phase_catalog() if p['id'] == phase), None)
    if item is None:
        return {}
    return {'phase': phase, 'instruction': item['gate'],
            'evidence_help': str(HERE / 'references/execution.md') + '#receipts',
            'then': 'Save actual evidence and record this phase before starting the next. Ask and wait if a material user decision is missing.'}


def run_tool(script, *args):
    result = subprocess.run([sys.executable, '-X', 'utf8', str(HERE / 'scripts' / script), *map(str, args)],
                            capture_output=True, text=True, encoding='utf-8', timeout=60)
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        payload = {'status': 'blocked', 'errors': [result.stderr.strip() or result.stdout.strip() or 'No tool output']}
    if result.returncode and payload.get('status') in ('approved', 'ok'):
        payload = {'status': 'blocked', 'errors': ['Tool failed despite a passing payload']}
    return payload


def run_preflight(target_path, ignore_paths=None):
    result = subprocess.run([sys.executable, '-X', 'utf8', str(HERE / 'scripts/preflight_worktree.py'),
                             str(target_path), *(ignore_paths or [])],
                            capture_output=True, text=True, encoding='utf-8', timeout=30)
    return {'status': {0: 'approved', 2: 'flagged'}.get(result.returncode, 'blocked'),
            'target': str(target_path), 'exit_code': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr}


def run_auditor(manifest_path):
    return run_tool('validate_manifest.py', manifest_path)


def run_receipt_validator(receipt_path, manifest_path=None):
    args = [receipt_path] + (['--manifest', manifest_path] if manifest_path else [])
    return run_tool('validate_receipt.py', *args)


def load_manifest(run):
    import yaml
    return yaml.safe_load((run / 'manifest.yaml').read_text(encoding='utf-8'))


def owned_run(value):
    run = private_path(value)
    state = json.loads((run / 'run.json').read_text(encoding='utf-8'))
    root = personal_root()
    if str(root) != state['personal_root'] or private_path(run, root / 'arc_runs') != run:
        raise ValueError('Run does not belong to the configured personal folder')
    if run.parent != (root / 'arc_runs').resolve() or run.name != state['run_id']:
        raise ValueError('Run location does not match its recorded identity')
    # Check nested write targets even for resumed runs.
    for name in ('receipts', 'report.md', 'ledger.jsonl', 'check_result.json'):
        private_path(run / name, run)
    return run


def append_event(run, event, **fields):
    path = private_path(run / 'ledger.jsonl', run)
    payload = {'event': event, 'run_id': run.name, 'ts': now(), **fields}
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + '\n')


def events(run):
    path = run / 'ledger.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []


def save_report(run, result):
    state = json.loads((run / 'run.json').read_text(encoding='utf-8'))
    try:
        manifest = load_manifest(run) if (run / 'manifest.yaml').exists() else {}
    except Exception:
        manifest = {}
    completed = {e.get('phase') for e in events(run) if e['event'] == 'phase_done' and e.get('ok')}
    lines = ['# Delivery Workflow report', '', f"Status: **{result['status']}**", '',
             f"Run: `{run.name}`", f"Project: `{state['project_root']}`", '']
    if manifest.get('task_ref'):
        lines += [f"[Task and scope](<{manifest['task_ref']}>)", '']
    if 'postmortem' in completed:
        try:
            receipt = json.loads((run / 'receipts/postmortem.json').read_text(encoding='utf-8'))
            source = Path(receipt['evidence']['postmortem_ref'])
            outcome = source.read_text(encoding='utf-8').strip().splitlines()
            if outcome and outcome[0].startswith('# '):
                outcome = outcome[1:]
            lines += ['## Recorded outcome and remaining work', '', '\n'.join(outcome).strip(), '',
                      f'[Full postmortem](<{source}>)', '']
        except (OSError, ValueError, KeyError):
            lines += ['Recorded postmortem is unavailable; inspect the check errors below.', '']
    lines += ['## Phase evidence', '', '| Phase | State | Evidence |', '| --- | --- | --- |']
    for phase in manifest.get('phases', []):
        name = phase['phase']
        if phase['decision'] == 'excluded':
            lines.append(f"| {name} | excluded: {phase['reason_code']} | {phase.get('evidence_ref', '')} |")
        else:
            done = name in completed
            lines.append(f"| {name} | {'recorded' if done else 'pending'} | {'[receipt](receipts/' + name + '.json)' if done else ''} |")
    lines += ['', '## Latest check', '', '```json', json.dumps(result, ensure_ascii=False, indent=2), '```', '',
              '## Scope and limits', '',
              'The coordinator checks evidence structure, file references and recorded order. It does not prove',
              'semantic correctness, a model identity, or that a supplied log describes an actual execution.',
              'Read the task, phase evidence and postmortem for changes, observed behavior and remaining gaps.',
              'Git changes and publication are separate from evidence completion. This coordinator never commits or pushes.', '']
    write(run / 'report.md', '\n'.join(lines), run)
    response = {**result, 'run_dir': str(run), 'report': str(run / 'report.md')}
    if result.get('next') in {p.get('phase') for p in manifest.get('phases', [])}:
        response['assignment'] = assignment(result['next'])
    return response


def cmd_audit(task_ref, force=False, max_phases=None, project=None, override_reason=None):
    import yaml
    from generate_manifest import build_manifest, parse_task_frontmatter
    from validate_manifest import load_lessons
    task = Path(task_ref).expanduser().resolve()
    if not task.is_file():
        raise ValueError('Task file does not exist')
    root = personal_root()
    private_path(task, root)  # Request content stays outside the shared repository.
    front = parse_task_frontmatter(task)
    project_root = Path(project or front.get('project_root') or '').expanduser().resolve()
    if not (project or front.get('project_root')) or not project_root.is_dir():
        raise ValueError('An existing --project directory or task project_root is required')
    if force and not override_reason:
        raise ValueError('--force requires --override-reason describing the agreed handling of existing changes')
    runs = private_path(root / 'arc_runs', root)
    runs.mkdir(parents=True, exist_ok=True)
    run = private_path(runs / make_run_id(), runs)
    run.mkdir(exist_ok=False)
    (run / 'receipts').mkdir()
    state = {'run_id': run.name, 'personal_root': str(root), 'project_root': str(project_root), 'created_at': now()}
    write_json(run / 'run.json', state, run)
    # An incomplete report exists before executing external checks.
    save_report(run, {'status': 'incomplete', 'next': 'preflight'})
    preflight = run_preflight(project_root)
    preflight['override_reason'] = override_reason if force else None
    write_json(run / 'preflight_result.json', preflight, run)
    if preflight['status'] == 'blocked' or (preflight['status'] == 'flagged' and not force):
        return save_report(run, {'status': preflight['status'], 'preflight': preflight})
    manifest = build_manifest(str(task), front)
    manifest.update(run_id=run.name, project_root=str(project_root))
    write(run / 'manifest.yaml', yaml.safe_dump(manifest, sort_keys=False), run)
    write(run / 'lessons_snapshot.yaml', yaml.safe_dump({'lessons': load_lessons()}, sort_keys=False), run)
    audit = run_auditor(run / 'manifest.yaml')
    if max_phases is not None and sum(p['decision'] == 'included' for p in manifest['phases']) > max_phases:
        audit['status'] = 'blocked'
        audit.setdefault('violations', []).append({'rule': 'MAX_PHASES', 'detail': 'Included phases exceed requested limit'})
    audit.update(task_sha256=digest(task), lessons_sha256=digest(run / 'lessons_snapshot.yaml'),
                 preflight_sha256=digest(run / 'preflight_result.json'))
    write_json(run / 'audit_result.json', audit, run)
    append_event(run, 'audit', status=audit['status'])
    return save_report(run, {'status': audit['status'], 'audit': audit,
                             'next': 'understand' if audit['status'] == 'approved' else 'Resolve the audit findings and create a revised run'})


def integrity_errors(run, manifest):
    errors = []
    audit = json.loads((run / 'audit_result.json').read_text(encoding='utf-8'))
    state = json.loads((run / 'run.json').read_text(encoding='utf-8'))
    if audit.get('status') != 'approved' or audit.get('run_id') != manifest.get('run_id') or manifest.get('run_id') != run.name:
        errors.append('A matching approved audit is required')
    if manifest.get('project_root') != state.get('project_root'):
        errors.append('Project identity changed after initialization')
    for key, path in [('manifest_sha256', run / 'manifest.yaml'), ('task_sha256', Path(manifest['task_ref'])),
                      ('lessons_sha256', run / 'lessons_snapshot.yaml'), ('preflight_sha256', run / 'preflight_result.json')]:
        if not path.is_file() or digest(path) != audit.get(key):
            errors.append(f'{key}: evidence changed or is missing; create a revised audit')
    return errors


def cmd_record(run_value, receipt_value):
    run = owned_run(run_value)
    with locked(run):
        manifest = load_manifest(run)
        errors = integrity_errors(run, manifest)
        receipt_path = Path(receipt_value).expanduser().resolve()
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        if receipt.get('phase') == 'understand':
            observed = json.loads((run / 'preflight_result.json').read_text(encoding='utf-8'))
            claimed = receipt.get('evidence', {}).get('preflight', {})
            expected = 'override' if observed['status'] == 'flagged' else 'clean'
            if claimed.get('status') != expected or Path(claimed.get('evidence_ref', '')).resolve() != (run / 'preflight_result.json').resolve():
                errors.append('Understand receipt must cite this run\'s actual preflight and status')
        included = [p['phase'] for p in manifest['phases'] if p['decision'] == 'included']
        done = [e['phase'] for e in events(run) if e['event'] == 'phase_done' and e.get('ok')]
        if any(e['event'] == 'stopped' for e in events(run)):
            errors.append('This run was stopped; revise the approach in a new run')
        for prior in done:
            prior_path = private_path(run / 'receipts' / f'{prior}.json', run)
            recorded = next(e for e in events(run) if e['event'] == 'phase_done' and e['phase'] == prior)
            if not prior_path.is_file() or digest(prior_path) != recorded.get('receipt_sha256'):
                errors.append(f'{prior}: earlier evidence changed or is missing')
            elif run_receipt_validator(prior_path, run / 'manifest.yaml').get('status') != 'approved':
                errors.append(f'{prior}: earlier evidence no longer validates')
        phase = receipt.get('phase')
        if done != included[:len(done)] or len(done) == len(included) or phase != included[len(done)]:
            errors.append('Receipt must be for the next included phase; recorded phases cannot be overwritten')
        result = run_receipt_validator(receipt_path, run / 'manifest.yaml')
        errors += result.get('errors', [])
        if result.get('status') != 'approved' and not result.get('errors'):
            errors.append('Receipt validator did not approve')
        if errors:
            return save_report(run, {'status': 'blocked', 'errors': errors})
        destination = private_path(run / 'receipts' / f'{phase}.json', run)
        if destination.exists():
            raise ValueError('Receipt already exists; inspect interrupted writes before recovery')
        # References must be absolute, or resolve from the final receipt location too.
        write_json(destination, receipt, run)
        bound = run_receipt_validator(destination, run / 'manifest.yaml')
        if bound.get('status') != 'approved':
            destination.unlink()
            return save_report(run, {'status': 'blocked', 'errors': bound.get('errors', ['Evidence paths do not resolve at the saved location'])})
        append_event(run, 'phase_done', phase=phase, ok=True, receipt_sha256=digest(destination))
        result = {'status': 'incomplete', 'recorded': phase, 'warnings': bound.get('warnings', []),
                  'next': included[len(done) + 1] if len(done) + 1 < len(included) else 'check'}
        if phase == 'spike' and receipt['evidence'].get('verdict') == 'INVALIDATED':
            append_event(run, 'stopped', reason='Approach invalidated')
            result.update(status='stopped', next='Revise the approach in a new run')
        return save_report(run, result)


def _task_git_root(manifest, run_dir):
    task = Path(manifest['task_ref'])
    if not task.is_file():
        return None, 'task_not_found'
    project = Path(manifest.get('project_root', task.parent))
    if not project.is_dir():
        return None, 'project_not_found'
    result = subprocess.run(['git', '-C', str(project), 'rev-parse', '--show-toplevel'], capture_output=True, text=True, timeout=15)
    if result.returncode:
        if any((p / '.git').exists() for p in (project, *project.parents)):
            return None, 'git_error'
        return None, 'no_git'
    return Path(result.stdout.strip()).resolve(), None


def git_state(manifest, run):
    root, reason = _task_git_root(manifest, run)
    if reason and reason != 'no_git':
        return {'status': 'error', 'error': 'GIT GATE: ' + reason}
    if root is None:
        return {'status': 'no-git', 'publication': 'not-applicable'}
    result = subprocess.run(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=all'], capture_output=True, text=True, timeout=15)
    if result.returncode:
        return {'status': 'error', 'error': 'Git status could not be read'}
    head = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=15)
    return {'status': 'working-changes' if result.stdout.strip() else 'clean', 'root': str(root),
            'head': head.stdout.strip() if head.returncode == 0 else None,
            'changes': result.stdout.splitlines(), 'publication': 'not-checked'}


def cmd_check(run_value, dry_run=False):
    run = owned_run(run_value)
    with locked(run):
        manifest = load_manifest(run)
        errors = integrity_errors(run, manifest)
        warnings = []
        ledger = events(run)
        if any(e['event'] == 'stopped' for e in ledger):
            errors.append('Approach was invalidated; this run is stopped')
        included = [p['phase'] for p in manifest['phases'] if p['decision'] == 'included']
        for phase in included:
            receipt_path = private_path(run / 'receipts' / f'{phase}.json', run)
            if not receipt_path.is_file():
                errors.append(f'{phase}: missing receipt')
                continue
            receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
            if receipt.get('phase') != phase:
                errors.append(f'{phase}: receipt identity mismatch')
            result = run_receipt_validator(receipt_path, run / 'manifest.yaml')
            if result.get('status') != 'approved':
                errors += result.get('errors', [f'{phase}: invalid receipt'])
            warnings += result.get('warnings', [])
            recorded = [e for e in ledger if e['event'] == 'phase_done' and e.get('phase') == phase]
            if len(recorded) != 1 or recorded[0].get('receipt_sha256') != digest(receipt_path):
                errors.append(f'{phase}: receipt is not bound to exactly one ledger event')
        ledger_result = run_tool('validate_ledger.py', run, run / 'manifest.yaml')
        if ledger_result.get('status') != 'ok':
            errors += ledger_result.get('issues', []) + [f'Missing phases: {ledger_result.get("missing_phases", [])}']
        git = git_state(manifest, run)
        if git['status'] == 'error':
            errors.append(git['error'])
        result = {'status': 'failed' if errors else 'complete', 'errors': errors, 'warnings': warnings,
                  'git': git, 'closeout': 'no-git' if git['status'] == 'no-git' else 'local',
                  'checked_at': now()}
        write_json(run / 'check_result.json', result, run)
        if not errors and not any(e['event'] == 'run_complete' for e in ledger):
            append_event(run, 'run_complete', status='complete')
        return save_report(run, result)


def cmd_status(run_value):
    run = owned_run(run_value)
    manifest = load_manifest(run) if (run / 'manifest.yaml').exists() else {}
    ledger = events(run)
    done = [e.get('phase') for e in ledger if e['event'] == 'phase_done']
    pending = [p['phase'] for p in manifest.get('phases', []) if p['decision'] == 'included' and p['phase'] not in done]
    result = {'status': 'saved', 'run_dir': str(run), 'report': str(run / 'report.md'), 'recorded': done,
              'pending': pending, 'next': pending[0] if pending else 'check',
              'note': 'Run check to validate current evidence; saved progress alone does not prove completion'}
    if any(e['event'] == 'stopped' for e in ledger):
        result.update(status='stopped', next='Revise the approach in a new run')
    elif not manifest:
        result.update(status='blocked', next='Read the saved report, resolve preflight and audit a revised task')
    else:
        errors = integrity_errors(run, manifest)
        if errors:
            result.update(status='blocked', errors=errors, next='Resolve the audit/integrity problem before continuing')
        elif pending:
            result['assignment'] = assignment(pending[0])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    c = sub.add_parser('configure'); c.add_argument('--root', required=True)
    a = sub.add_parser('audit'); a.add_argument('task'); a.add_argument('--project'); a.add_argument('--force', action='store_true'); a.add_argument('--override-reason'); a.add_argument('--max-phases', type=int)
    r = sub.add_parser('record'); r.add_argument('run'); r.add_argument('--receipt', required=True)
    c = sub.add_parser('check'); c.add_argument('run'); c.add_argument('--dry-run', action='store_true', help='Compatibility option; checks never publish')
    s = sub.add_parser('status'); s.add_argument('run')
    args = parser.parse_args()
    try:
        if args.command == 'configure': result = configure(args.root)
        elif args.command == 'audit': result = cmd_audit(args.task, args.force, args.max_phases, args.project, args.override_reason)
        elif args.command == 'record': result = cmd_record(args.run, args.receipt)
        elif args.command == 'check': result = cmd_check(args.run, args.dry_run)
        else: result = cmd_status(args.run)
    except Exception as exc:
        result = {'status': 'blocked', 'errors': [str(exc)]}
        if getattr(args, 'run', None):
            try:
                run = owned_run(args.run)
                with locked(run):
                    result = save_report(run, result)
            except Exception:
                pass  # Preserve evidence when its destination or lock is unsafe.
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 1 if result['status'] in ('failed', 'blocked', 'stopped') else 2 if result['status'] == 'flagged' else 0


if __name__ == '__main__':
    raise SystemExit(main())
