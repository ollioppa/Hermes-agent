from __future__ import annotations

import hashlib
from datetime import date
from .market import latest_market_metrics as _latest_case_metrics

from .db import RadarDB





def evaluate_watchdog(radar: RadarDB, *, as_of: date | None = None) -> list[dict[str, object]]:
    today = as_of or date.today()
    events: list[dict[str, object]] = []
    with radar.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        cases = connection.execute(
            """SELECT c.id,c.symbol,c.name,c.kind,c.sector_symbol,c.status,r.*,
                      json_extract(v.payload_json,'$.evidence_as_of') AS evidence_as_of
               FROM cases c JOIN watchdog_rules r ON r.case_id=c.id
               JOIN reviews v ON v.id=(SELECT id FROM reviews WHERE case_id=c.id ORDER BY version DESC LIMIT 1)
               WHERE c.status IN ('WATCH','READY') ORDER BY c.symbol"""
        ).fetchall()
        for case in cases:
            metrics = _latest_case_metrics(connection, int(case["id"]))
            if metrics is None:
                continue
            source_age = (today - date.fromisoformat(str(case["evidence_as_of"]))).days
            quote_age = (today - date.fromisoformat(str(metrics["price_date"]))).days
            horizon_met = int(metrics["days"]) >= int(case["min_days"])
            signals: dict[str, tuple[bool, str]] = {
                "horizon_met": (horizon_met, f"{metrics['days']} Tage / Schwelle {case['min_days']}"),
                "relative_spy_met": (horizon_met and float(metrics["relative_spy_pp"]) >= float(case["min_relative_spy_pp"]), f"{float(metrics['relative_spy_pp']):+.2f} pp vs SPY nach {metrics['days']} Tagen"),
                "relative_sector_met": (horizon_met and float(metrics["relative_sector_pp"]) >= float(case["min_relative_sector_pp"]), f"{float(metrics['relative_sector_pp']):+.2f} pp vs {case['sector_symbol']} nach {metrics['days']} Tagen"),
                "source_review_due": (source_age >= int(case["max_source_age_days"]), f"Quellenstand {source_age} Tage alt; manuelle Primärquellenprüfung nötig"),
                "quote_stale": (quote_age > 5, f"Kursstand {quote_age} Tage alt"),
            }
            if case["max_price"] is not None:
                signals["price_met"] = (float(metrics["price"]) <= float(case["max_price"]), f"Kurs {float(metrics['price']):.2f} / Grenze ≤{float(case['max_price']):.2f}")
            for signal, (active, detail) in signals.items():
                previous = connection.execute(
                    "SELECT active FROM watchdog_signal_state WHERE case_id=? AND signal=?",
                    (case["id"], signal),
                ).fetchone()
                if previous is None:
                    connection.execute(
                        "INSERT INTO watchdog_signal_state(case_id,signal,active,detail) VALUES (?,?,?,?)",
                        (case["id"], signal, int(active), detail),
                    )
                    continue
                if bool(previous["active"]) == active:
                    connection.execute(
                        "UPDATE watchdog_signal_state SET detail=?,updated_at=CURRENT_TIMESTAMP WHERE case_id=? AND signal=?",
                        (detail, case["id"], signal),
                    )
                    continue
                event_key = hashlib.sha256(f"{case['id']}|{signal}|{int(active)}|{metrics['price_date']}|{detail}".encode()).hexdigest()
                cursor = connection.execute(
                    """INSERT OR IGNORE INTO watchdog_events(event_key,case_id,signal,old_state,new_state,detail)
                       VALUES (?,?,?,?,?,?)""",
                    (event_key, case["id"], signal, int(previous["active"]), int(active), detail),
                )
                connection.execute(
                    "UPDATE watchdog_signal_state SET active=?,detail=?,updated_at=CURRENT_TIMESTAMP WHERE case_id=? AND signal=?",
                    (int(active), detail, case["id"], signal),
                )
                if cursor.rowcount:
                    events.append({"id": int(cursor.lastrowid), "event_key": event_key, "symbol": case["symbol"], "signal": signal, "active": active, "detail": detail, "status": case["status"]})
    return events


def pending_events(radar: RadarDB) -> list[dict[str, object]]:
    with radar.connect() as connection:
        rows = connection.execute(
            """SELECT e.id,e.event_key,c.symbol,e.signal,e.new_state AS active,e.detail,c.status
               FROM watchdog_events e JOIN cases c ON c.id=e.case_id
               WHERE e.delivered_at IS NULL ORDER BY e.id"""
        ).fetchall()
        return [dict(row) for row in rows]


def event_mail(events: list[dict[str, object]]) -> str:
    lines = ["# Opportunity Radar — neues Ereignis", "", "READY bleibt eine manuelle Entscheidung im Chat.", ""]
    for event in events:
        direction = "ERREICHT" if bool(event["active"]) else "VERLOREN"
        lines.extend([f"## {event['symbol']} · {direction}", f"- Signal: `{event['signal']}`", f"- Beleg: {event['detail']}", f"- Status bleibt: **{event['status']}**", ""])
    return "\n".join(lines).rstrip() + "\n"


def event_delivery_identity(events: list[dict[str, object]]) -> tuple[str, str]:
    batch = "|".join(sorted(str(event["event_key"]) for event in events))
    digest = hashlib.sha256(batch.encode()).hexdigest()[:12]
    return f"event:{digest}", f"Opportunity Radar ALERT [{digest}]"
