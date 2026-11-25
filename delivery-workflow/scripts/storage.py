"""Personal Delivery Workflow state, separate from the distributed skill and Git."""
import json
import os
from contextlib import contextmanager
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]


def private_path(value, owner=None):
    path = Path(value).expanduser().resolve()
    if path == SKILL_ROOT or SKILL_ROOT in path.parents or path in SKILL_ROOT.parents:
        raise ValueError("Personal state must be outside the distributed skill")
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise ValueError("Personal state must be outside Git repositories")
    if owner is not None:
        owner = Path(owner).expanduser().resolve()
        if path != owner and owner not in path.parents:
            raise ValueError("Personal destination redirects outside its owning folder")
    return path


def config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return private_path(Path(base) / "delivery-workflow" / "config.json")


def personal_root(required=True):
    value = os.environ.get("DELIVERY_WORKFLOW_HOME") or os.environ.get("DELIVERY_WORKFLOW_ROOT")
    if not value and config_path().is_file():
        value = json.loads(config_path().read_text(encoding="utf-8")).get("root")
    if value:
        return private_path(value)
    if required:
        raise ValueError("Choose a personal folder first: arc_run.py configure --root <folder>")
    return None


def write(path, content, owner=None):
    path = private_path(path, owner)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = private_path(path.with_name(path.name + ".tmp-" + os.urandom(4).hex()), owner)
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path, value, owner=None):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n", owner)


def configure(root):
    root = private_path(root)
    root.mkdir(parents=True, exist_ok=True)
    private_path(root / "arc_runs", root).mkdir(exist_ok=True)
    registry = private_path(root / "lessons.yaml", root)
    if not registry.exists():
        write(registry, "versions:\n  lessons: 1\nlessons: []\n", root)
    write_json(config_path(), {"root": str(root)})
    return {"status": "ok", "root": str(root), "config": str(config_path())}


@contextmanager
def locked(folder):
    folder = private_path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    lock = private_path(folder / ".delivery-workflow.lock", folder)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("Another write is active; inspect a stale lock before removing it")
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)
