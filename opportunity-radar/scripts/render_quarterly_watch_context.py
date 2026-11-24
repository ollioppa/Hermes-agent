#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opportunity_radar.db import RadarDB
from opportunity_radar.quarterly_watch import quarter_key, watch_letter_context


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / "state" / "opportunity_radar.sqlite3")
    parser.add_argument("--period", default=quarter_key())
    args = parser.parse_args()

    radar = RadarDB(args.db)
    radar.initialize()
    print(json.dumps(watch_letter_context(radar, args.period), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
