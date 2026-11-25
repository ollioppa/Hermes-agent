#!/usr/bin/env python3
"""Inspect project state; exit 0 clean, 2 needs judgment, 1 error."""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def rel_to_repo(path: Path, repo_root: Path) -> str:
    path = path.expanduser().resolve()
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return os.path.relpath(str(path), str(repo_root)).replace(os.sep, '/')


def main() -> int:
    target = Path(sys.argv[1]).expanduser().resolve()
    ignore_inputs = [Path(p).expanduser() for p in sys.argv[2:]]

    if shutil.which('git') is None:
        print('PRE-FLIGHT ERROR: Git executable not found', file=sys.stderr)
        return 1

    if not target.is_dir():
        print('PRE-FLIGHT ERROR: project folder does not exist', file=sys.stderr)
        return 1

    inside = run(['git', '-C', str(target), 'rev-parse', '--is-inside-work-tree'])
    if inside.returncode != 0:
        if any((parent / '.git').exists() for parent in (target, *target.parents)):
            print('PRE-FLIGHT ERROR: existing Git metadata could not be inspected', file=sys.stderr)
            return 1
        print(f'PRE-FLIGHT OK: no Git repository at {target}')
        return 0

    repo_root = Path(run(['git', '-C', str(target), 'rev-parse', '--show-toplevel']).stdout.strip()).resolve()
    git_dir_raw = run(['git', '-C', str(target), 'rev-parse', '--git-dir']).stdout.strip()
    git_dir = (target / git_dir_raw).resolve() if not Path(git_dir_raw).is_absolute() else Path(git_dir_raw)

    ignore_rels = {rel_to_repo(p, repo_root) for p in ignore_inputs}

    status_proc = run(['git', '-C', str(repo_root), 'status', '--porcelain', '--untracked-files=all'])
    if status_proc.returncode:
        print('PRE-FLIGHT ERROR: Git status failed', file=sys.stderr)
        return 1
    raw_status_lines = [line.rstrip() for line in status_proc.stdout.splitlines() if line.strip()]
    status_lines = []
    for line in raw_status_lines:
        path_part = line[3:]
        if path_part in ignore_rels:
            continue
        status_lines.append(line)

    ignored_proc = run(['git', '-C', str(repo_root), 'ls-files', '-c', '--ignored', '--exclude-standard'])
    if ignored_proc.returncode:
        print('PRE-FLIGHT ERROR: tracked/ignored file inspection failed', file=sys.stderr)
        return 1
    ignored_lines = [line.rstrip() for line in ignored_proc.stdout.splitlines() if line.strip()]

    rebase_merge_state = (
        (git_dir / 'rebase-merge').exists()
        or (git_dir / 'rebase-apply').exists()
        or (git_dir / 'MERGE_HEAD').exists()
    )

    if not status_lines and not ignored_lines and not rebase_merge_state:
        print('PRE-FLIGHT OK: worktree clean')
        return 0

    print('PRE-FLIGHT FLAGGED: existing changes need a scope decision')
    if status_lines:
        print('\n[git status --porcelain]')
        print('\n'.join(status_lines))
    if ignored_lines:
        print('\n[git ls-files -c --ignored --exclude-standard]')
        print('\n'.join(ignored_lines))
    if rebase_merge_state:
        print('\n[git state]')
        print('merge or rebase in progress')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
