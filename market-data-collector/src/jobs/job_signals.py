"""
Deprecated legacy job.

This job used the old DB schema and must not write to the live sheet.
Use the cron-safe consolidated daily refresh instead:

    python -m src.scripts.run_daily --lookback-days 5
"""

import sys

MESSAGE = (
    "Deprecated legacy job: this module must not be used against the live sheet. "
    "Use: python -m src.scripts.run_daily --lookback-days 5"
)


def run(*args, **kwargs) -> None:
    raise RuntimeError(MESSAGE)


if __name__ == "__main__":
    print(MESSAGE, file=sys.stderr)
    sys.exit(2)
