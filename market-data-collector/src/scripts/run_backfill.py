"""Manual full historical Sheet rebuild with a reproducible Macro report."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

from src.config.settings import PROJECT_ROOT
from src.services.backfill import run


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        digest.update(str(relative).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _source_revision() -> str | None:
    # An export is not a checkout; never attribute an ancestor repository's HEAD.
    if not (PROJECT_ROOT / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _execution_report(
    data_report: dict[str, object],
    *,
    dry_run: bool,
    sheets: set[str],
    argv: list[str],
) -> dict[str, object]:
    hy_metadata_path = PROJECT_ROOT / "src/data/macro/BAMLH0A0HYM2_archive_1996_2021.metadata.json"
    bdc_manifest_path = PROJECT_ROOT / "src/data/macro/bdc_scores_initial_migration_manifest.csv"
    hy_metadata = json.loads(hy_metadata_path.read_text(encoding="utf-8"))
    return {
        "schema_version": "macro_backfill_execution_report_v1",
        "runner_command": [sys.executable, "-m", "src.scripts.run_backfill", *argv],
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "exit_status": 0,
        "dry_run": dry_run,
        "selected_sheets": sorted(sheets),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "source_revision": _source_revision(),
            "source_tree_sha256": _tree_sha256(PROJECT_ROOT / "src"),
        },
        "input_provenance": {
            "finra": "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx",
            "fred_series": [
                "NFCILEVERAGE",
                "CPIAUCSL",
                "WALCL",
                "WTREGEN",
                "RRPONTSYD",
                "BAMLH0A0HYM2",
            ],
            "hy_archive_metadata": str(hy_metadata_path.relative_to(PROJECT_ROOT)),
            "hy_archive_sha256": hy_metadata["sha256"],
            "bdc_manifest": str(bdc_manifest_path.relative_to(PROJECT_ROOT)),
            "bdc_manifest_sha256": _sha256(bdc_manifest_path),
        },
        "data_report": data_report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Full historical Sheet backfill")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_false", dest="dry_run", help="Explicitly enable destructive full Sheet replacement")
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Fetch + compute but do not write to sheet (default)",
    )
    parser.add_argument(
        "--sheet",
        action="append",
        choices=("DB", "MARKET_DATA", "MACRO_DATA"),
        help=(
            "Explicit target tab; repeat for multiple tabs. Without --sheet, only "
            "the legacy DB and MARKET_DATA tabs are rebuilt."
        ),
    )
    parser.add_argument(
        "--report-path",
        help="Optional JSON path for the emitted MACRO_DATA execution report",
    )
    args = parser.parse_args(argv)
    invocation = list(argv) if argv is not None else sys.argv[1:]
    sheets = set(args.sheet) if args.sheet else {"DB", "MARKET_DATA"}
    data_report = run(dry_run=args.dry_run, sheets=sheets)
    if data_report is not None:
        report = _execution_report(
            data_report,
            dry_run=args.dry_run,
            sheets=sheets,
            argv=invocation,
        )
        rendered = json.dumps(report, indent=2, sort_keys=True)
        if args.report_path:
            path = Path(args.report_path).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
