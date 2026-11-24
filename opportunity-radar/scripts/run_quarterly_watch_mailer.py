#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opportunity_radar.db import RadarDB
from opportunity_radar.mailer import HimalayaTransport, deliver_mail_once
from opportunity_radar.quarterly_watch import quarter_key, validate_watch_letter_manifest
from opportunity_radar.transitions import ContractError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default=quarter_key())
    parser.add_argument("--body", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    db_path = Path(
        os.environ.get(
            "OPPORTUNITY_RADAR_DB", ROOT / "state" / "opportunity_radar.sqlite3"
        )
    )
    recipient = os.environ.get(
        "OPPORTUNITY_RADAR_RECIPIENT", "radar@example.invalid"
    )
    body_path = args.body or (
        ROOT / "output" / "watch-reviews" / f"{args.period}-watch-brief.md"
    )
    manifest_path = args.manifest or (
        ROOT / "output" / "watch-reviews" / f"{args.period}-manifest.json"
    )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = db_path.parent / ".quarterly-watch-mail.lock"
    with lock_path.open("a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        radar = RadarDB(db_path)
        radar.initialize()
        if not body_path.is_file():
            raise ContractError("quarterly watch brief body is missing or empty")
        body = body_path.read_text(encoding="utf-8")
        if not body.strip():
            raise ContractError("quarterly watch brief body is missing or empty")
        if not manifest_path.is_file():
            raise ContractError("quarterly watch manifest is missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ContractError("quarterly watch manifest must be an object")
        validate_watch_letter_manifest(radar, args.period, manifest, body=body)

        year_text, quarter_text = args.period.split("-Q")
        delivery_key = f"watch-quarterly:{args.period}"
        subject = (
            f"Stockpicker – WATCH-Brief Q{quarter_text} {year_text} "
            f"[{args.period}]"
        )
        deliver_mail_once(
            radar,
            HimalayaTransport(),
            delivery_key,
            subject,
            recipient,
            body,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
