"""
Deprecated legacy entry point.

Do not use this module against the live Google Sheet. The active cron-safe
entry point is:

    python -m src.scripts.run_daily --lookback-days 5
"""

import sys

MESSAGE = (
    "Deprecated legacy entry point: src.jobs.run_daily must not be used. "
    "Use: python -m src.scripts.run_daily --lookback-days 5"
)


def run(*args, **kwargs) -> None:
    raise RuntimeError(MESSAGE)


if __name__ == "__main__":
    print(MESSAGE, file=sys.stderr)
    sys.exit(2)
