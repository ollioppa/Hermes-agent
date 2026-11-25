#!/usr/bin/env python3
"""Remember Discovery's private folder and save reports without accidental overwrite."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


def config_path():
    base = Path(os.environ.get('APPDATA', str(Path.home() / 'AppData/Roaming'))) if os.name == 'nt' else Path.home() / '.config'
    return base / 'discovery-agent/location.json'


def private_path(value, owner=None, directory=False):
    path = Path(value).expanduser().resolve()
    skill = Path(__file__).resolve().parents[1]
    if path == skill or skill in path.parents:
        raise ValueError('Choose a private location outside the shared skill')
    if owner is not None and path != owner and owner not in path.parents:
        raise ValueError('A private path redirects outside its owning folder')
    repo = next((p for p in (path, *path.parents) if (p / '.git').exists()), None)
    if repo is not None:
        relative = path.relative_to(repo).as_posix()
        ignore_target = relative + '/' if directory or path.is_dir() else relative
        ignored = subprocess.run(['git', '-C', str(repo), 'check-ignore', '--quiet', '--', ignore_target], capture_output=True)
        tracked = subprocess.run(['git', '-C', str(repo), 'ls-files', '--', relative], capture_output=True)
        if ignored.returncode != 0 or tracked.returncode != 0 or tracked.stdout:
            raise ValueError('Choose a location outside Git or an already ignored, untracked private folder')
    return path


def read_root(config):
    data = json.loads(config.read_text(encoding='utf-8'))
    value = data.get('root')
    if not isinstance(value, str) or not value.strip() or not Path(value).is_absolute():
        raise ValueError('Stored root must be an absolute path; ask the user for a location')
    return private_path(value, directory=True)


def status(config):
    if not config.exists():
        return {'status': 'needs_location', 'next': 'Ask the user for a private folder and wait'}
    root = read_root(config)
    if not root.is_dir() or not os.access(root, os.W_OK):
        raise ValueError('Configured folder is unavailable; ask the user for an accessible location')
    return {'status': 'ready', 'root': str(root),
            'reports': str(private_path(root / 'reports', root, directory=True)),
            'kb': str(private_path(root / 'discovery_kb.md', root))}


def write_file(path, content, overwrite=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite:
        # Exclusive creation prevents a concurrent save from replacing another report.
        with path.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(content)
        return
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(content)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def configure(config, value, replace=False):
    if not value.strip() or not Path(value).expanduser().is_absolute():
        raise ValueError('Use the absolute private folder chosen by the user')
    root = private_path(value, directory=True)
    if config.exists() and not replace and read_root(config) != root:
        raise ValueError('A different root is configured; --replace requires the user to request that change')
    reports = private_path(root / 'reports', root, directory=True)
    kb = private_path(root / 'discovery_kb.md', root)
    reports.mkdir(parents=True, exist_ok=True)
    if not kb.exists():
        write_file(kb, '# Personal Discovery KB\n')
    write_file(config, json.dumps({'root': str(root)}, ensure_ascii=False) + '\n', overwrite=True)
    return status(config)


def save(config, source, name=None, output=None, overwrite=False):
    location = status(config)
    if location['status'] != 'ready':
        raise ValueError('Configure the user-chosen personal folder before saving')
    if output is not None:
        if not Path(output).expanduser().is_absolute():
            raise ValueError('The one-run output must be an absolute user-supplied path')
        target = private_path(output)
    else:
        if not name or name in ('.', '..') or '/' in name or '\\' in name or Path(name).suffix.lower() != '.md':
            raise ValueError('Use a Markdown filename such as DISCOVERY_short-title.md')
        root = Path(location['root'])
        reports = private_path(root / 'reports', root, directory=True)
        target = private_path(reports / name, reports)
    content = Path(source).read_text(encoding='utf-8')
    if not content.strip():
        raise ValueError('Report is empty; keep working or provide a useful draft')
    write_file(target, content, overwrite)
    return {'status': 'saved', 'report': str(target), 'kb': location['kb']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=config_path(), help='Explicit local pointer, for isolated use/tests')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    p = sub.add_parser('configure'); p.add_argument('--root', required=True); p.add_argument('--replace', action='store_true')
    p = sub.add_parser('save'); p.add_argument('--source', required=True)
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument('--name'); target.add_argument('--output')
    p.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'status': result = status(args.config)
        elif args.command == 'configure': result = configure(args.config, args.root, args.replace)
        else: result = save(args.config, args.source, args.name, args.output, args.overwrite)
    except (OSError, ValueError, TypeError) as exc:
        result = {'status': 'blocked', 'error': str(exc)}
    # ASCII escaping also works with Windows terminals that cannot print every filename.
    print(json.dumps(result))
    return 1 if result['status'] == 'blocked' else 0


if __name__ == '__main__':
    sys.exit(main())
