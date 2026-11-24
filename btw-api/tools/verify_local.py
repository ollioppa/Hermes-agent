"""macOS-only verification with OS network/write denial, no package installation.
Usage (from export root): /path/to/existing/python -B tools/verify_local.py
Evidence stays in .verification/; remove that directory before redistribution.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".verification"
OUT.mkdir(exist_ok=True)
for name in ("home", "tmp"):
    (OUT / name).mkdir(exist_ok=True)
if not Path("/usr/bin/sandbox-exec").exists():
    raise SystemExit("OS sandbox unavailable: not verified. Use macOS sandbox-exec or a reviewed equivalent.")
profile = OUT / "offline.sb"
profile.write_text('(version 1)\n(allow default)\n(deny network*)\n(deny file-write*)\n'
                   '(allow file-write* (subpath ' + json.dumps(str(OUT)) + ') (literal "/dev/null"))\n')
env = {
    "PATH": "/usr/bin:/bin", "HOME": str(OUT / "home"), "TMPDIR": str(OUT / "tmp"),
    "PYTHONPATH": str(ROOT), "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHON_DOTENV_DISABLED": "1", "BTW_LOG_TO_FILE": "false", "LOG_LEVEL": "ERROR",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "LC_ALL": "en_US.UTF-8",
}

def execute(label, args):
    command = ["/usr/bin/sandbox-exec", "-f", str(profile), sys.executable, "-B", *args]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
    (OUT / (label + ".stdout")).write_text(result.stdout)
    (OUT / (label + ".stderr")).write_text(result.stderr)
    print(label, "exit=" + str(result.returncode))
    if result.returncode:
        print(result.stdout[-6000:]); print(result.stderr[-3000:])
        raise SystemExit(result.returncode)
    return result.stdout

probe = '''import socket
from pathlib import Path
try:
    Path('must-not-write.txt').write_text('denial probe')
except PermissionError:
    print('write outside evidence: DENIED')
else:
    raise AssertionError('write sandbox failed')
try:
    with socket.socket() as sock:
        sock.connect(('127.0.0.1', 9))
except PermissionError:
    print('network connection: DENIED')
else:
    raise AssertionError('network sandbox failed')
import src.services.backfill, src.scripts.market_briefing_snapshot, sys
root = Path.cwd().resolve()
modules = [m for n,m in sys.modules.items() if n == 'src' or n.startswith('src.')]
assert modules
for m in modules:
    assert Path(m.__file__).resolve().is_relative_to(root), m.__name__
assert not any('projects' in p and not ('site-packages' in p or 'lib/python' in p) for p in sys.path)
print('all loaded project modules: export-root only')
'''
execute("sandbox-and-imports", ["-c", probe])
a = execute("example-1", ["-m", "examples.offline_pipeline"])
b = execute("example-2", ["-m", "examples.offline_pipeline"])
assert a == b, "example not deterministic"
payload = json.loads(a)
print("deterministic_sha256=" + hashlib.sha256(a.encode()).hexdigest())
print("example rows=" + json.dumps(payload["rows"], sort_keys=True))
print("example score_status=" + payload["snapshot"]["score"]["status"])
execute("tests", ["-m", "pytest", "-q", "-p", "no:cacheprovider", "--basetemp", str(OUT / "pytest-tmp"), "tests"])
print((OUT / "tests.stdout").read_text().splitlines()[-1])
# Test-only backups/symlinks are not export artifacts. Keep textual evidence only.
shutil.rmtree(OUT / "pytest-tmp")
for name in ("run_daily", "run_backfill", "market_briefing_snapshot"):
    execute("help-" + name, ["-m", "src.scripts." + name, "--help"])
print("PASS: offline consumer, deterministic output, exported tests, CLI help, OS boundaries")
