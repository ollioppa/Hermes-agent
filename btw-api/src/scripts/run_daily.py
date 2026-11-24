"""
Entry point for the cron-safe daily refresh.

Fetches only a small lookback window and upserts rows into DB and MARKET_DATA.
Does not clear or rewrite full sheets.

Usage:
  python -m src.scripts.run_daily
  python -m src.scripts.run_daily --dry-run
  python -m src.scripts.run_daily --lookback-days 5
"""

import argparse
import errno
import fcntl
import os
import sys
from pathlib import Path

from src.config.settings import LOG_DIR
from src.services.backfill import run_daily

LOCK_FILE = Path(LOG_DIR) / "run_daily.lock"


class LockBusy(Exception):
    """Another process holds the daily CLI lock."""


class FileLock:
    """Small non-blocking lock to prevent overlapping launchd/manual runs."""

    def __init__(self, path: Path):
        self.path = path
        self.fd: int | None = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno in (errno.EACCES, errno.EAGAIN):
                    raise LockBusy(str(self.path)) from exc
                raise
            os.ftruncate(self.fd, 0)
            os.lseek(self.fd, 0, os.SEEK_SET)
            os.write(self.fd, str(os.getpid()).encode())
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
                self.fd = None
        # Keep the inode: unlink would let another process lock a different file.


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily DB + MARKET_DATA refresh")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True, help="Fetch + compute but do not write to sheets (default)")
    mode.add_argument("--write", action="store_false", dest="dry_run", help="Explicitly enable live Sheet writes")
    parser.add_argument("--lookback-days", type=int, default=5, help="Number of recent days to refresh")
    args = parser.parse_args()

    try:
        with FileLock(LOCK_FILE):
            result = run_daily(dry_run=args.dry_run, lookback_days=args.lookback_days)
    except LockBusy:
        print(f"btw_api daily already running; lock held: {LOCK_FILE}", file=sys.stderr)
        return 75  # EX_TEMPFAIL
    if result["status"] == "partial":
        print(f"btw_api daily partial: macro={result['macro_failures']} "
              f"window={result['window_failures']}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
