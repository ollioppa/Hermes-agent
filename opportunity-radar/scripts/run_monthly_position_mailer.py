#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opportunity_radar.db import RadarDB
from opportunity_radar.mailer import HimalayaTransport, deliver_mail_once
from opportunity_radar.position_review import monthly_brief_context
from opportunity_radar.transitions import ContractError

MONTH_NAMES = (
    "", "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default=date.today().strftime("%Y-%m"))
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
        ROOT / "output" / "position-reviews" / f"{args.period}-portfolio-brief.md"
    )
    manifest_path = args.manifest or body_path.with_name(f"{args.period}-manifest.json")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = db_path.parent / ".monthly-position-mail.lock"
    with lock_path.open("a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        radar = RadarDB(db_path)
        radar.initialize()
        status = radar.monthly_position_review_status(args.period)
        if not status["complete"]:
            missing_symbols = status["missing_symbols"]
            if not isinstance(missing_symbols, list):
                raise ContractError("monthly position status returned invalid missing_symbols")
            missing = ", ".join(str(symbol) for symbol in missing_symbols)
            raise ContractError(f"monthly position brief is incomplete; missing: {missing}")
        if not body_path.is_file():
            raise ContractError("monthly position brief body is missing or empty")
        body = body_path.read_text(encoding="utf-8")
        if not body.strip():
            raise ContractError("monthly position brief body is missing or empty")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        context = monthly_brief_context(radar, args.period)
        if manifest.get("period") != args.period or manifest.get("context_digest") != context["context_digest"]:
            raise ContractError("monthly brief context is stale")
        if manifest.get("body_sha256") != hashlib.sha256(body.encode("utf-8")).hexdigest():
            raise ContractError("monthly brief body does not match its reviewed manifest")

        delivery_key = f"position-monthly:{args.period}"
        year_text, month_text = args.period.split("-")
        subject = (
            f"Stockpicker – Monatsbrief {MONTH_NAMES[int(month_text)]} "
            f"{year_text} [{args.period}]"
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