#!/usr/bin/env python3
from __future__ import annotations

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
from opportunity_radar.mailer import HimalayaTransport, deliver_mail_once, mail_attempt_path
from opportunity_radar.transitions import ContractError
from opportunity_radar.watch import observe_live
from opportunity_radar.watchdog import evaluate_watchdog, event_delivery_identity, event_mail, pending_events


def open_event_attempt(radar: RadarDB) -> dict | None:
    """Read the existing pending mechanism, never reconstruct an attempted body."""
    attempts = []
    for path in sorted((radar.path.parent / "mail-attempts").glob("*.pending")):
        try:
            attempt = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise ContractError("unreadable mail attempt; reconcile explicitly") from exc
        key = attempt.get("delivery_key") if isinstance(attempt, dict) else None
        if not isinstance(key, str) or path != mail_attempt_path(radar, key):
            raise ContractError("unknown mail attempt identity; reconcile explicitly")
        if key.startswith(("watch-quarterly:", "position-monthly:")):
            continue
        if not key.startswith("event:"):
            raise ContractError("unknown mail attempt owner; reconcile explicitly")
        ids = attempt.get("event_ids")
        body = attempt.get("body")
        if (not isinstance(ids, list) or not ids
                or any(type(value) is not int or value <= 0 for value in ids)
                or len(set(ids)) != len(ids)
                or not isinstance(body, str)
                or attempt.get("body_sha256") != hashlib.sha256(body.encode("utf-8")).hexdigest()
                or not isinstance(attempt.get("subject"), str)
                or not isinstance(attempt.get("recipient"), str)):
            raise ContractError("legacy or unbound event batch; reconcile explicitly")
        attempts.append(attempt)
    if len(attempts) > 1:
        raise ContractError("multiple open event batches; reconcile explicitly")
    return attempts[0] if attempts else None


def main() -> int:
    db_path = Path(os.environ.get("OPPORTUNITY_RADAR_DB", ROOT / "state" / "opportunity_radar.sqlite3"))
    recipient = os.environ.get("OPPORTUNITY_RADAR_RECIPIENT", "radar@example.invalid")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with (db_path.parent / ".watchdog-event-mail.lock").open("a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        radar = RadarDB(db_path)
        radar.initialize()
        attempt = open_event_attempt(radar)
        if attempt is not None:
            # Finish only the original batch. New events wait for the next run.
            if attempt["recipient"] != recipient:
                raise ContractError("open event batch recipient changed; reconcile explicitly")
            delivery_key, subject = attempt["delivery_key"], attempt["subject"]
            body, event_ids = attempt["body"], attempt["event_ids"]
        else:
            for case in radar.list_cases():
                if case["status"] in {"WATCH", "READY"}:
                    observe_live(radar, str(case["symbol"]))
            evaluate_watchdog(radar, as_of=date.today())
            events = pending_events(radar)
            if not events:
                return 0
            delivery_key, subject = event_delivery_identity(events)
            body = event_mail(events)
            event_ids = [int(event["id"]) for event in events]
        deliver_mail_once(radar, HimalayaTransport(), delivery_key, subject, recipient, body, event_ids=event_ids)
        radar.mark_watchdog_events_delivered(event_ids)
        # A crash here leaves a receipt+pending; replaying the mark is idempotent.
        mail_attempt_path(radar, delivery_key).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
