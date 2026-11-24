"""
Deprecated legacy MARKET_DATA job.

MARKET_DATA is now written by the consolidated daily refresh in
src.services.backfill.run_daily(), which uses the current schema including:
- btc_etf_total_flow_usd_m
- etf_flow_source_status
- updated_at_utc

Use:
    python -m src.scripts.run_daily --lookback-days 5
"""

import sys

MESSAGE = (
    "Deprecated legacy MARKET_DATA job: use "
    "python -m src.scripts.run_daily --lookback-days 5"
)


def run(*args, **kwargs) -> None:
    raise RuntimeError(MESSAGE)


if __name__ == "__main__":
    print(MESSAGE, file=sys.stderr)
    sys.exit(2)
