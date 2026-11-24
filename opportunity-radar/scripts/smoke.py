#!/usr/bin/env python3
"""One isolated nominal flow; external prices and mail are explicit fixtures."""
from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opportunity_radar.cli import import_case_payload
from opportunity_radar.db import RadarDB
from opportunity_radar.evaluate import evaluate_pre_ready_timing
from opportunity_radar.mailer import deliver_mail_once
from opportunity_radar.market import NasdaqInfoProvider
from opportunity_radar.models import MarketSnapshot
from opportunity_radar.report import render_change_only
from opportunity_radar.watch import record_outcome_live


class FixturePrices(NasdaqInfoProvider):
    def fetch(self, symbol: str, kind: str, role: str) -> MarketSnapshot:
        return MarketSnapshot(symbol, role, 110.0, "2026-09-09", "2026-09-09T22:00:00Z",
                              "USD", "smoke_fixture", 'fixture close; not total return |units={"since":"2026-01-01","through":"2027-12-31","breaks":[],"source":"explicit test fixture"}')


class FixtureMail:
    def __init__(self) -> None:
        self.sent = 0

    def find_verified(self, subject: str, recipient: str) -> str | None:
        return None

    def send_and_verify(self, subject: str, recipient: str, body: str) -> str:
        self.sent += 1
        return "fixture-message"


def main() -> int:
    # Synthetic company economics: technical wiring, not investment proof.
    review: dict[str, object] = {key: "Explicit smoke fixture, not investment research" for key in (
        "motor", "environment", "relative_strength", "expectation", "asymmetry",
        "counterpath", "falsifier", "moat_competition", "cash_conversion",
        "balance_financing", "capital_allocation", "valuation", "margins", "dilution")}
    review.update(evidence_as_of="2026-09-08", missing_to_ready="Keine offene Bedingung; Review ist entscheidungsreif.",
                  customer_economics={key: "Technical fixture" for key in (
                      "historical_path", "growth_composition", "customer_value", "support_intensity",
                      "margin_source_and_use", "rent_quality", "normalization_test")})

    def initial(symbol: str, role: str) -> dict[str, object]:
        return asdict(MarketSnapshot(symbol, role, 100.0, "2026-09-08", "2026-09-08T22:00:00Z",
                                     "USD", "smoke_fixture", 'fixture close; not total return |units={"since":"2026-01-01","through":"2027-12-31","breaks":[],"source":"explicit test fixture"}'))

    with tempfile.TemporaryDirectory(prefix="stockpicker-nominal-") as temporary:
        root = Path(temporary)
        radar = RadarDB(root / "radar.sqlite3")
        radar.initialize()
        case = import_case_payload(radar, {
            "symbol": "SMOKE", "name": "Synthetic smoke company", "kind": "stock", "sector_symbol": "XLK",
            "review": review, "sources": ["https://example.com/explicit-smoke-fixture"],
            "immediate_investable": True,
            "snapshots": {"case": initial("SMOKE", "case"), "spy": initial("SPY", "benchmark"),
                          "sector": initial("XLK", "sector")}})
        assert radar.get_case(case)["status"] == "READY" and not radar.get_open_conditions(case)
        timing = evaluate_pre_ready_timing(radar, case)
        assert timing["relative_move_pp"] == 0.0
        outcome = record_outcome_live(radar, "SMOKE", provider=FixturePrices())
        assert outcome["evaluation_status"] == "valid" and outcome["observation_days"] == 1
        body = render_change_only(radar, root / "reader.md")
        assert body and "SMOKE" in body and "2026-09-09" in body
        assert render_change_only(radar, root / "reader.md") is None
        mail = FixtureMail()
        sent = deliver_mail_once(radar, mail, "smoke:nominal", "Stockpicker Smoke [nominal]", "fixture@example.com", body)
        retried = deliver_mail_once(radar, mail, "smoke:nominal", "Stockpicker Smoke [nominal]", "fixture@example.com", body)
        assert sent["status"] == "sent" and retried["status"] == "already_delivered" and mail.sent == 1
        print(json.dumps({"status": "ok", "isolated": True, "flow": "import-ready-outcome-reader-mail",
                          "return_basis": outcome["return_basis"], "live_prices": False, "live_mail": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
