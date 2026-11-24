from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from opportunity_radar.cli import import_case_payload
from opportunity_radar.db import RadarDB
from opportunity_radar.mailer import deliver_mail_once, headers_match, subject_search_token
from opportunity_radar.market import parse_nasdaq_quote
from opportunity_radar.models import MarketSnapshot
from opportunity_radar.transitions import ContractError
from opportunity_radar.watchdog import evaluate_watchdog, event_delivery_identity


NASDAQ = {
    "data": {
        "symbol": "UNH",
        "assetClass": "STOCKS",
        "primaryData": {
            "lastSalePrice": "$400.84",
            "lastTradeTimestamp": "Sep 8, 2026",
            "isRealTime": False,
        },
    }
}


def test_nasdaq_quote_preserves_price_date_and_semantics() -> None:
    snapshot = parse_nasdaq_quote(NASDAQ, "UNH", "case", "2026-09-09T05:00:00Z")
    assert snapshot.price == 400.84
    assert snapshot.price_date == "2026-09-08"
    assert snapshot.currency == "USD"
    assert snapshot.provider == "nasdaq_info"
    assert snapshot.semantics == "last sale price; price return only; not total return"


def test_nasdaq_quote_accepts_live_timestamp_with_time_suffix() -> None:
    payload = json.loads(json.dumps(NASDAQ))
    payload["data"]["primaryData"]["lastTradeTimestamp"] = "Sep 9, 2026 4:46 AM ET"
    snapshot = parse_nasdaq_quote(payload, "UNH", "case", "2026-09-09T08:46:00Z")
    assert snapshot.price_date == "2026-09-09"


def test_nasdaq_quote_rejects_missing_price() -> None:
    broken = {"data": {"symbol": "UNH", "primaryData": {"lastSalePrice": "N/A", "lastTradeTimestamp": "Sep 8, 2026"}}}
    with pytest.raises(ContractError, match="usable last-sale price"):
        parse_nasdaq_quote(broken, "UNH", "case", "2026-09-09T05:00:00Z")


def snapshot(symbol: str, role: str, price: float, price_date: str) -> MarketSnapshot:
    return MarketSnapshot(symbol, role, price, price_date, "2026-12-08T22:45:00Z", "USD", "nasdaq_info", 'last sale price; price return only; not total return |units={"since":"2026-01-01","through":"2027-12-31","breaks":[],"source":"explicit test fixture"}')


def test_watchdog_baselines_then_emits_changed_signals_without_setting_ready(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    payload = json.loads(Path("tests/fixtures/stock_case.json").read_text(encoding="utf-8"))
    case_id = import_case_payload(radar, payload)
    radar.set_watchdog_rule(case_id, min_days=90, min_relative_spy_pp=0.0, min_relative_sector_pp=0.0, max_source_age_days=60)

    assert evaluate_watchdog(radar, as_of=date(2026, 9, 9)) == []
    radar.record_snapshot(case_id, snapshot("UNH", "case", 450.0, "2026-12-08"))
    radar.record_snapshot(case_id, snapshot("SPY", "benchmark", 800.0, "2026-12-08"))
    radar.record_snapshot(case_id, snapshot("XLV", "sector", 170.0, "2026-12-08"))

    events = evaluate_watchdog(radar, as_of=date(2026, 12, 8))
    changed = {event["signal"] for event in events}
    assert {"horizon_met", "relative_spy_met", "relative_sector_met"} <= changed
    assert radar.get_case(case_id)["status"] == "WATCH"
    assert evaluate_watchdog(radar, as_of=date(2026, 12, 8)) == []


class FakeTransport:
    def __init__(self) -> None:
        self.sent: dict[str, tuple[str, str]] = {}
        self.send_count = 0

    def find_verified(self, subject: str, recipient: str) -> str | None:
        return subject if subject in self.sent else None

    def send_and_verify(self, subject: str, recipient: str, body: str) -> str:
        self.send_count += 1
        self.sent[subject] = (recipient, body)
        return f"message-{self.send_count}"


def test_mail_delivery_is_receipt_and_sent_folder_idempotent(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    transport = FakeTransport()
    first = deliver_mail_once(radar, transport, "event-key", "Radar Test", "radar@example.invalid", "Body")
    second = deliver_mail_once(radar, transport, "event-key", "Radar Test", "radar@example.invalid", "Body")
    assert first["status"] == "sent"
    assert second["status"] == "already_delivered"
    assert transport.send_count == 1
    with pytest.raises(ContractError, match="body bytes"):
        deliver_mail_once(radar, transport, "event-key", "Radar Test", "radar@example.invalid", "Changed Body")
    assert transport.send_count == 1


def test_ambiguous_send_is_recovered_without_second_smtp(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()

    class AmbiguousTransport(FakeTransport):
        def send_and_verify(self, subject: str, recipient: str, body: str) -> str:
            self.send_count += 1
            self.sent[subject] = (recipient, body)
            raise ContractError("mail sent but exact Sent verification failed")

    transport = AmbiguousTransport()
    with pytest.raises(ContractError, match="Sent verification failed"):
        deliver_mail_once(
            radar, transport, "quarter-key", "WATCH [2026-Q3]",
            "radar@example.invalid", "Body",
        )

    with pytest.raises(ContractError, match="body bytes"):
        deliver_mail_once(radar, transport, "quarter-key", "WATCH [2026-Q3]", "radar@example.invalid", "Changed Body")
    recovered = deliver_mail_once(
        radar, transport, "quarter-key", "WATCH [2026-Q3]",
        "radar@example.invalid", "Body",
    )
    assert recovered["status"] == "recovered_from_sent"
    assert transport.send_count == 1


def test_delivery_identity_and_recipient_verification_are_exact() -> None:
    events = [{"event_key": "abc"}, {"event_key": "def"}]
    key, subject = event_delivery_identity(events)
    assert subject_search_token(subject) == subject.removeprefix("Opportunity Radar ALERT [").removesuffix("]")
    assert subject_search_token("Opportunity Radar Weekly - 2026-W37") == "2026-W37"
    assert key == "event:" + subject.removeprefix("Opportunity Radar ALERT [").removesuffix("]")
    assert headers_match(b"To: radar@example.invalid\nSubject: Radar\n\nBody", "Radar", "radar@example.invalid")
    assert not headers_match(
        b"To: radar@example.invalid, unintended@example.net\nSubject: Radar\n\nBody",
        "Radar",
        "radar@example.invalid",
    )
    assert not headers_match(
        b"To: radar@example.invalid, radar@example.invalid\nSubject: Radar\n\nBody",
        "Radar",
        "radar@example.invalid",
    )


@pytest.mark.parametrize("state", ["receipt", "pending", "receipt_and_pending"])
@pytest.mark.parametrize("field", ["subject", "recipient", "delivery_key", "body_sha256"])
@pytest.mark.parametrize("missing", [False, True])
def test_mail_identity_mismatch_blocks_before_transport(tmp_path, state, field, missing):
    import hashlib
    from opportunity_radar.mailer import mail_attempt_path

    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    identity = dict(delivery_key="event-key", subject="Exact Subject",
                    recipient="Exact@example.net", body_sha256=hashlib.sha256(b"Body").hexdigest())
    changed = dict(identity)
    if missing:
        changed.pop(field)
    else:
        changed[field] = "different"

    class NoTransport:
        def find_verified(self, *args):
            pytest.fail("identity mismatch reached Sent")
        def send_and_verify(self, *args):
            pytest.fail("identity mismatch reached SMTP")

    if state in {"receipt", "receipt_and_pending"}:
        # Stub only lookup to probe even malformed/legacy receipt columns.
        receipt = dict(changed if state == "receipt" else identity, sent_message_id="sent-1")
        radar.get_mail_receipt = lambda key: receipt
    if state in {"pending", "receipt_and_pending"}:
        path = mail_attempt_path(radar, "event-key")
        path.parent.mkdir()
        path.write_text(json.dumps(changed))
    with pytest.raises(ContractError, match="identity/body bytes"):
        deliver_mail_once(radar, NoTransport(), "event-key", "Exact Subject", "Exact@example.net", "Body")


def event_entry_fixture(tmp_path, monkeypatch):
    import importlib.util
    import fcntl
    spec = importlib.util.spec_from_file_location("event_entry", "scripts/run_watchdog_event_mailer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    payload = json.loads(Path("tests/fixtures/stock_case.json").read_text())
    case_id = import_case_payload(radar, payload)
    monkeypatch.setenv("OPPORTUNITY_RADAR_DB", str(radar.path))
    monkeypatch.setenv("OPPORTUNITY_RADAR_RECIPIENT", "Exact@example.net")

    def assert_locked(*args, **kwargs):
        with (tmp_path / ".watchdog-event-mail.lock").open("a") as lock:
            with pytest.raises(BlockingIOError):
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    monkeypatch.setattr(module, "observe_live", assert_locked)
    monkeypatch.setattr(module, "evaluate_watchdog", assert_locked)

    def add_event(label):
        with radar.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO watchdog_events(event_key,case_id,signal,old_state,new_state,detail) VALUES (?,?,?,0,1,?)",
                (label, case_id, "horizon_met", label + " original ä\nbody"),
            )
            return int(cursor.lastrowid)

    return module, radar, add_event, assert_locked


@pytest.mark.parametrize("crash", ["none", "ambiguous", "receipt_before_mark", "mark_before_unlink"])
def test_event_entry_resumes_original_batch_before_new_events(tmp_path, monkeypatch, crash):
    from opportunity_radar.mailer import mail_attempt_path
    from opportunity_radar.watchdog import pending_events
    module, radar, add_event, assert_locked = event_entry_fixture(tmp_path, monkeypatch)
    a = add_event("A")
    key, subject = event_delivery_identity(pending_events(radar))
    original_body = module.event_mail(pending_events(radar))

    class EventTransport(FakeTransport):
        visible = False
        calls = []
        def find_verified(self, subject, recipient):
            assert_locked()
            return super().find_verified(subject, recipient) if self.visible else None
        def send_and_verify(self, subject, recipient, body):
            assert_locked()
            self.calls.append((subject, recipient, body))
            result = super().send_and_verify(subject, recipient, body)
            if crash == "ambiguous" and self.send_count == 1:
                raise ContractError("ambiguous A")
            return result

    transport = EventTransport()
    monkeypatch.setattr(module, "HimalayaTransport", lambda: transport)
    real_mark = RadarDB.mark_watchdog_events_delivered
    marked = []
    def mark(self, ids):
        assert_locked()
        marked.append(list(ids))
        if crash == "receipt_before_mark":
            raise RuntimeError("crash before mark")
        real_mark(self, ids)
        if crash == "mark_before_unlink":
            raise RuntimeError("crash after mark")
    monkeypatch.setattr(RadarDB, "mark_watchdog_events_delivered", mark)
    if crash == "none":
        assert module.main() == 0
    else:
        with pytest.raises((ContractError, RuntimeError), match="ambiguous A|crash"):
            module.main()
        assert mail_attempt_path(radar, key).exists()
        if crash != "ambiguous":
            assert radar.get_mail_receipt(key) is not None
    b = add_event("B")
    # Mutable case/event details must not regenerate the attempted A body.
    with radar.connect() as connection:
        connection.execute("UPDATE watchdog_events SET detail='changed after attempt' WHERE id=?", (a,))
    if crash == "ambiguous":
        with pytest.raises(ContractError, match="unresolved"):
            module.main()
        assert transport.send_count == 1
        assert [event["id"] for event in pending_events(radar)] == [a, b]
    transport.visible = True
    monkeypatch.setattr(RadarDB, "mark_watchdog_events_delivered", real_mark)
    if crash != "none":
        assert module.main() == 0
        assert transport.send_count == 1
        assert [event["id"] for event in pending_events(radar)] == [b]
        assert not mail_attempt_path(radar, key).exists()
    assert module.main() == 0
    assert transport.send_count == 2
    assert transport.calls[0] == (subject, "Exact@example.net", original_body)
    assert "B original" in transport.calls[1][2]
    assert "A original" not in transport.calls[1][2]
    assert "changed after attempt" not in transport.calls[1][2]
    assert pending_events(radar) == []
    assert module.main() == 0
    assert transport.send_count == 2


@pytest.mark.parametrize("damage", ["legacy", "body", "recipient", "unknown", "malformed", "multiple"])
def test_event_entry_unknown_pending_blocks_before_acquisition(tmp_path, monkeypatch, damage):
    import hashlib
    from opportunity_radar.mailer import mail_attempt_path
    from opportunity_radar.watchdog import pending_events
    module, radar, add_event, assert_locked = event_entry_fixture(tmp_path, monkeypatch)
    a = add_event("A")
    key, subject = event_delivery_identity(pending_events(radar))
    body = module.event_mail(pending_events(radar))
    attempt = dict(delivery_key=key, subject=subject, recipient="Exact@example.net",
                   body=body, body_sha256=hashlib.sha256(body.encode()).hexdigest(), event_ids=[a])
    if damage == "legacy":
        del attempt["event_ids"]
        del attempt["body"]
    elif damage == "body":
        attempt["body"] += "changed"
    elif damage == "recipient":
        attempt["recipient"] = "other@example.net"
    elif damage == "unknown":
        del attempt["delivery_key"]
    path = mail_attempt_path(radar, key)
    path.parent.mkdir()
    path.write_text("{" if damage == "malformed" else json.dumps(attempt))
    if damage == "multiple":
        other = dict(attempt, delivery_key="event:other")
        mail_attempt_path(radar, other["delivery_key"]).write_text(json.dumps(other))
    def forbidden(*args, **kwargs):
        pytest.fail("unbound pending reached acquisition or transport")
    monkeypatch.setattr(module, "observe_live", forbidden)
    monkeypatch.setattr(module, "evaluate_watchdog", forbidden)
    monkeypatch.setattr(module, "HimalayaTransport", forbidden)
    with pytest.raises(ContractError):
        module.main()
    assert [event["id"] for event in pending_events(radar)] == [a]
    assert path.exists()


def test_yahoo_listing_currency_and_completed_bars() -> None:
    import io
    from datetime import datetime, timezone
    from opportunity_radar.market import YahooChartProvider
    stamp = int(datetime(2026, 10, 12, tzinfo=timezone.utc).timestamp())
    result = {"meta": {"symbol": "AD.AS", "currency": "EUR", "instrumentType": "EQUITY",
        "exchangeTimezoneName": "Europe/Amsterdam", "currentTradingPeriod": {"regular": {"end": stamp + 3600}}},
        "timestamp": [stamp, stamp + 86400], "indicators": {"quote": [{"close": [31.61, None]}]}}
    opener = lambda *a, **k: io.BytesIO(json.dumps({"chart": {"result": [result]}}).encode())
    provider = YahooChartProvider("AD.AS", "EUR", opener)
    quote = provider.fetch("AD", "stock", "case")
    assert quote.symbol == "AD" and quote.currency == "EUR" and quote.price == 31.61
    assert quote.provider == "yahoo_chart:AD.AS" and quote.price_date == "2026-10-12"
    result["meta"]["currency"] = "USD"
    with pytest.raises(ContractError, match="bound listing/currency"):
        provider.fetch("AD", "stock", "case")
    wrong = json.loads(json.dumps(NASDAQ)); wrong["data"]["symbol"] = "OTHER"
    with pytest.raises(ContractError, match="requested symbol"):
        parse_nasdaq_quote(wrong, "UNH", "case", "2026-10-15T00:00:00Z")
