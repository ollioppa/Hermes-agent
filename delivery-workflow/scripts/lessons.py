#!/usr/bin/env python3
"""Personal improvements to Delivery Workflow's method; case results stay in run files."""
import argparse
import json
import re
from datetime import date
from pathlib import Path
import yaml
from storage import locked, personal_root, private_path, write, write_json


def load_registry():
    path = private_path(personal_root() / 'lessons.yaml', personal_root())
    return yaml.safe_load(path.read_text(encoding='utf-8')) if path.is_file() else {'versions': {'lessons': 1}, 'lessons': []}


def learn(run_value, entry_value, reply):
    from arc_run import owned_run
    run = owned_run(run_value)
    if not reply.strip():
        raise ValueError('The actual user confirmation is required')
    result = json.loads((run / 'check_result.json').read_text(encoding='utf-8'))
    if result.get('status') != 'complete':
        raise ValueError('Deliver and verify the run before saving a method improvement')
    entry = json.loads(Path(entry_value).read_text(encoding='utf-8'))
    allowed = {'id', 'purpose', 'rule', 'context', 'limits', 'trigger'}
    if set(entry) - allowed or entry.get('purpose') != 'skill_improvement':
        raise ValueError('Only a skill_improvement entry is accepted; case-result fields are not allowed')
    for field in ('id', 'rule', 'context', 'limits'):
        if not isinstance(entry.get(field), str) or not entry[field].strip():
            raise ValueError(f'{field} is required')
    if not re.fullmatch(r'P-[a-z0-9-]{3,60}', entry['id']):
        raise ValueError('Personal lesson IDs use P- followed by a short lowercase identifier')
    trigger = entry.get('trigger')
    if not isinstance(trigger, dict) or not trigger or set(trigger) - {'keyword', 'phase_included', 'deliverable_glob'}:
        raise ValueError('Use a narrow keyword, phase_included or deliverable_glob trigger')
    if not all(isinstance(v, str) and v.strip() for v in trigger.values()):
        raise ValueError('Trigger values must be nonempty strings')
    if 'keyword' in trigger:
        re.compile(trigger['keyword'])
    root = personal_root()
    with locked(root):
        registry = load_registry()
        prior = next((row for row in registry['lessons'] if row['id'] == entry['id']), None)
        if prior:
            if any(prior.get(k) != entry[k] for k in allowed):
                raise ValueError('This lesson ID already has different content; use a new ID')
            if run.name in prior['source_runs']:
                return {'status': 'ok', 'action': 'unchanged', 'id': prior['id']}
            prior['source_runs'].append(run.name)
            prior['occurrences'] += 1
        else:
            prior = {**entry, 'status': 'active', 'severity': 'note', 'source_runs': [run.name], 'occurrences': 1}
            registry['lessons'].append(prior)
        prior['updated'] = date.today().isoformat()
        # Confirmation stays with the case, outside the knowledge registry.
        write_json(run / 'learning' / f"{entry['id']}.json", {'entry': entry, 'user_reply': reply}, run)
        write(root / 'lessons.yaml', yaml.safe_dump(registry, sort_keys=False), root)
        return {'status': 'ok', 'id': entry['id'], 'registry': str(root / 'lessons.yaml')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('learn'); p.add_argument('--run', required=True); p.add_argument('--entry', required=True); p.add_argument('--reply', required=True)
    sub.add_parser('list'); sub.add_parser('guard-due')
    for action in ('retire', 'remove'):
        p = sub.add_parser(action); p.add_argument('id')
        p.add_argument('--reason', help='Why the rule is obsolete, replaced or no longer applicable')
        p.add_argument('--reply', help='Compatibility alias for an already supplied reason')
    args = parser.parse_args()
    try:
        if args.command == 'learn':
            result = learn(args.run, args.entry, args.reply)
        elif args.command in ('retire', 'remove'):
            reason = args.reason or args.reply
            if not reason or not reason.strip():
                raise ValueError('A reason for retiring or removing the rule is required')
            root = personal_root()
            with locked(root):
                registry = load_registry()
                item = next((row for row in registry['lessons'] if row['id'] == args.id), None)
                if item is None:
                    raise ValueError('No personal lesson with that ID')
                if args.command == 'remove':
                    registry['lessons'].remove(item)
                else:
                    item['status'] = 'retired'
                write(root / 'lessons.yaml', yaml.safe_dump(registry, sort_keys=False), root)
                result = {'status': 'ok', 'id': args.id, 'action': args.command, 'reason': reason}
        else:
            rows = load_registry()['lessons']
            if args.command == 'guard-due': rows = [r for r in rows if r.get('occurrences', 0) >= 2 and r.get('status') == 'active']
            result = {'status': 'ok', 'lessons': rows}
    except Exception as exc:
        result = {'status': 'blocked', 'error': str(exc)}
    print(json.dumps(result, indent=2))
    return 1 if result['status'] == 'blocked' else 0


if __name__ == '__main__':
    raise SystemExit(main())
