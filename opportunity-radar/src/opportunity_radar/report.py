from __future__ import annotations

import hashlib
import json

from pathlib import Path
from typing import Any

from .db import RadarDB, active_research_count
from .market import latest_market_metrics


def _reader_rows(radar: RadarDB) -> list[dict[str, Any]]:
    with radar.connect() as connection:
        rows = connection.execute(
            """SELECT c.id,c.symbol,c.name,c.kind,c.sector_symbol,c.status,
                      r.id review_id,r.payload_json,
                      (SELECT reason FROM transitions t WHERE t.case_id=c.id ORDER BY t.id DESC LIMIT 1) transition_reason
               FROM cases c LEFT JOIN reviews r ON r.id=(
                   SELECT id FROM reviews WHERE case_id=c.id ORDER BY version DESC LIMIT 1)
               WHERE c.status IN ('READY','WATCH','INBOX','INVALIDATED')
               ORDER BY CASE c.status WHEN 'READY' THEN 0 WHEN 'WATCH' THEN 1 WHEN 'INBOX' THEN 2 ELSE 3 END,c.symbol"""
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item['review'] = json.loads(item.pop('payload_json')) if item.get('payload_json') else {}
            item['conditions'] = [dict(c) for c in connection.execute(
                'SELECT kind,description,status,fulfilled_reason FROM watch_conditions WHERE case_id=? ORDER BY id', (row['id'],))]
            item['sources'] = [source['url'] for source in connection.execute(
                'SELECT url FROM sources WHERE review_id=? ORDER BY id', (row['review_id'],))] if row['review_id'] is not None else []
            metrics = latest_market_metrics(connection, int(row['id']))
            item.update(price=metrics['price'] if metrics else None,
                        price_date=metrics['price_date'] if metrics else None,
                        currency=metrics['currency'] if metrics else None,
                        reference=metrics,
                        relative_observation={'spy_pp':metrics['relative_spy_pp'], 'sector_pp':metrics['relative_sector_pp'], 'days':metrics['days']} if metrics else None)
            result.append(item)
        return result


def _screening_rows(radar: RadarDB) -> tuple[list[dict[str, Any]], dict[str, Any] | None, int, int, int, int]:
    with radar.connect() as connection:
        try:
            cycle = connection.execute(
                """SELECT id, cycle_key, cohort_index, provider, status, as_of, completed_at, failure_reason
                   FROM screen_cycles
                   ORDER BY id DESC LIMIT 1"""
            ).fetchone()
        except Exception:
            return [], None, 0, 10, 0, 0
        rows = connection.execute(
            """SELECT ci.stable_identity,ci.symbol,ci.name,ci.kind,ci.region,ci.status,ci.lane,ci.metrics_json,
                      d.decision,d.report_path,d.revisit_after,d.revisit_trigger
               FROM candidate_inbox ci LEFT JOIN candidate_decisions d ON d.id=(
                   SELECT MAX(id) FROM candidate_decisions WHERE stable_identity=ci.stable_identity)
                   AND d.signal_date=json_extract(ci.metrics_json,'$.first_entry_month')
               WHERE ci.status='OPEN' ORDER BY ci.created_at,ci.stable_identity"""
        ).fetchall()
        open_count = active_research_count(connection)
        reserve_count = 0 if cycle is None else int(connection.execute(
            "SELECT COUNT(*) FROM screen_hits WHERE cycle_id = ? AND disposition = 'RESERVE'", (cycle["id"],)
        ).fetchone()[0])
        stale_count = 0 if cycle is None else int(connection.execute(
            """SELECT COUNT(*) FROM candidate_inbox ci
               JOIN screen_cycles last_cycle ON last_cycle.id = ci.last_seen_cycle_id
               WHERE ci.status = 'OPEN' AND julianday(?) - julianday(last_cycle.as_of) > 28""",
            (cycle["as_of"],),
        ).fetchone()[0])
        result = []
        for row in rows:
            item = dict(row)
            item["metrics"] = json.loads(str(item.pop("metrics_json")))
            result.append(item)
        return result, dict(cycle) if cycle is not None else None, open_count, max(0, 10 - open_count), reserve_count, stale_count


def build_screening_section(radar: RadarDB) -> str:
    screening_rows, cycle, open_count, remaining, reserve_count, stale_count = _screening_rows(radar)
    lines = ["## SCREENING-INBOX", ""]
    lines.append("Screening findet Review-Kandidaten; WATCH, READY und Archiv bleiben manuelle Entscheidungen.")
    lines.append(f"Unvollständige Recherche: {open_count}/10 · freie Plätze: {remaining} · fertige Nutzervorlagen zählen nicht")
    if cycle is not None:
        lines.append(f"Letzter Screen: {cycle['cycle_key']} · Stand {cycle['as_of']}")
        lines.append(f"Coverage: {cycle['status']} · Provider {cycle['provider']}")
        if cycle["failure_reason"]:
            lines.append(f"Technischer Grund: {cycle['failure_reason']}")
    lines.append(f"Reserve: {reserve_count} · Stale-Review-Vorschläge: {stale_count}")
    lines.append("Cadence: wöchentlich US-Aktien, STOXX Europe 600 und kuratierte ETFs; gemeinsame Kapazitätsgrenze.")
    if not screening_rows:
        lines.extend(["Keine offenen Screening-Kandidaten.", ""])
    else:
        lines.append("")
        for candidate in screening_rows:
            metrics = candidate["metrics"]
            lines.append(f"**{candidate['symbol']} — {candidate['lane']}**")
            lines.append(f"{candidate['name']} · {str(candidate['kind']).upper()} · {candidate['region']} · {candidate['stable_identity']}")
            research = {"AWAITING_USER": "Gespeicherter Vorschlag für Owner; Umfang im Bericht prüfen",
                        "RESEARCH_INCOMPLETE": "Wartet auf einen entscheidenden Beleg"}
            work = metrics.get('research_work') or []
            lines.append("Fortsetzbarer Budgetarbeitsstand" if work and candidate["decision"] != "AWAITING_USER" else research.get(candidate["decision"], "Noch nicht recherchiert"))
            if work:
                lines.append(f"Arbeitsbericht: {work[-1]['report_path']} · Quellenstand: {work[-1]['source_as_of']}")
                lines.append(f"Fortsetzen bei: {work[-1]['resume_from']}")
            if candidate["revisit_after"] or candidate["revisit_trigger"]:
                lines.append(f"Wiedervorlage: {candidate['revisit_after'] or candidate['revisit_trigger']}")
            if candidate["report_path"]:
                lines.append(f"Bericht: {candidate['report_path']}")
            lines.append(
                f"Run {metrics['run_month']} · erste Research-Zone {metrics['first_entry_month']} · "
                f"Kursstand {metrics['latest_date']}"
            )
            lines.append(
                f"Kurs {float(metrics['latest_close']):.2f} · Trend {float(metrics['current_trend']):.2f} · "
                f"Abstand {float(metrics['current_ratio']) * 100:.2f} %"
            )
            lines.append(f"OLS-Steigung: {float(metrics['trend_slope']):.4f} · Black-Swan-Review offen")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def research_history(radar: RadarDB, *, include_reports: bool = False) -> list[dict[str, Any]]:
    root = Path(__file__).resolve().parents[2]
    with radar.connect() as connection:
        items = [dict(row) for row in connection.execute("""SELECT d.*,(
            SELECT name FROM candidate_inbox ci WHERE ci.stable_identity=d.stable_identity
            ORDER BY id DESC LIMIT 1) name FROM candidate_decisions d ORDER BY d.id DESC""")]
    known = set()
    for item in items:
        if item['report_path']:
            path = Path(item['report_path'])
            known.add((path if path.is_absolute() else root / path).resolve())
    for folder in (root / 'research',root / 'output/reviews'):
        for path in sorted(folder.rglob('*.md')):
            if path.resolve() not in known:
                items.append(dict(report_path=str(path.relative_to(root)),decision=None,
                                  reader_text="Direktes Researchdokument; Urteil/Anker siehe Original"))
    for item in items:
        if not include_reports or not item.get('report_path'):
            continue
        path = Path(item['report_path'])
        path = path if path.is_absolute() else root / path
        try:
            body = path.read_text(encoding='utf-8').splitlines()
        except OSError:
            item['report_available'] = False
            continue
        item['report_available'] = True
        item['title'] = next((line.lstrip('# ').strip() for line in body if line.startswith('# ')),path.stem)
        # Quote original anchors/conclusions, never infer missing historic metadata.
        excerpts = []
        for index,line in enumerate(body):
            if any(key in line.lower() for key in ('datenstand','quellenstand','referenzkurs','urteil','fazit','entscheidung:')):
                excerpts.extend(body[index:index+3])
        item['original_anchors'] = '\n'.join(excerpts)
    return items


def build_research_history(radar: RadarDB) -> str:
    lines = ['## RESEARCHHISTORIE', '', 'Historische Urteile, keine automatische Aufnahme.', '']
    root = Path(__file__).resolve().parents[2]
    items = research_history(radar)
    lines.append(f"{len(items)} gespeicherte Entscheidungen/Dokumente; vollständige Historie: research-history.")
    for item in items[:10]:
        lines.append(f"- {item.get('symbol') or ''} {item.get('name') or ''} · {item.get('created_at') or 'Datum im Original'} · {item.get('decision') or 'Researchdokument'}")
        lines.append(f"  {item.get('reader_text') or item.get('reason') or ''}")
        if item.get('title'):
            lines.append(f"  **{item['title']}**")
        if item.get('original_anchors'):
            lines.extend('  > ' + line for line in item['original_anchors'].splitlines())
        if item.get('report_path'):
            path = Path(item['report_path'])
            path = path if path.is_absolute() else root / path
            lines.append(f"  Vollbericht (Urteil, Preis-/Informationsanker, Quellen): [{item['report_path']}]({path.as_uri()})")
    return '\n'.join(lines) + '\n'


def _specific_lines(kind: str, review: dict[str, object]) -> list[str]:
    if kind == "stock":
        lines = [
            "Aktiencheck:",
            f"- Bewertung: {review['valuation']}",
            f"- Margen: {review['margins']}",
            f"- Cash Conversion: {review['cash_conversion']}",
            f"- Verwässerung: {review['dilution']}",
        ]
        customer_economics = review.get("customer_economics")
        if isinstance(customer_economics, dict):
            lines.append(
                "- Kundenökonomie: "
                f"{customer_economics['rent_quality']} · "
                f"Margenherkunft/-verwendung: {customer_economics['margin_source_and_use']}"
            )
        return lines
    return [
        "ETF-Check:",
        f"- Index: {review['index_methodology']}",
        f"- Holdings: {review['holdings_transmission']}",
        f"- Konzentration: {review['concentration']}",
        f"- Kosten/Liquidität: {review['costs_liquidity']}",
        f"- Rebalancing: {review['rebalancing']}",
        f"- Überschneidung: {review['overlap']}",
    ]


def build_report(radar: RadarDB) -> str:
    rows = _reader_rows(radar)
    lines = ["# Opportunity Radar", ""]
    lines.extend(build_screening_section(radar).rstrip().splitlines())
    lines.extend(["",build_research_history(radar),""])
    for status in ("READY", "WATCH", "INBOX", "INVALIDATED"):
        lines.extend([f"## {status}", ""])
        selected = [row for row in rows if row["status"] == status]
        if not selected:
            lines.extend(["Keine Fälle.", ""])
            continue
        for row in selected:
            review: dict[str, object] = row["review"]
            lines.append(f"**{row['symbol']} — {status}**")
            lines.append(f"{row['name']} · {str(row['kind']).upper()}")
            if row.get("price") is not None:
                lines.append(f"Kurs: {float(row['price']):,.2f} {row['currency']} · Kursstand {row['price_date']}")
                reference = row['reference']
                lines.append(f"Referenz: {reference['reference_price']:.2f} {reference['reference_currency']} · {reference['reference_date']}")
            else:
                lines.append("Keine passende gemeinsame Kursgrundlage; Preisvergleich offen.")
            if review:
                lines.append(f"Quellenstand: {review['evidence_as_of']}")
                lines.append(f"Umfeld: {review['environment']}")
                lines.append(f"Warum interessant: {review['motor']}")
                lines.append(f"Relativ: {review['relative_strength']}")
                observation = row.get("relative_observation")
                if observation is not None:
                    lines.append(
                        "Lokale Preisbewegung seit Review (ohne Dividenden/FX): "
                        f"vs SPY {float(observation['spy_pp']):+.2f} pp · "
                        f"vs {row['sector_symbol']} {float(observation['sector_pp']):+.2f} pp · "
                        f"{int(observation['days'])} Kalendertage"
                    )
                lines.append(f"Erwartung: {review['expectation']}")
                lines.append(f"Asymmetrie: {review['asymmetry']}")
                lines.append(f"Benchmark: SPY und {row['sector_symbol']}")
                lines.append(f"Gegenpfad: {review['counterpath']}")
                lines.append(f"Falsifikator: {review['falsifier']}")
                lines.extend(_specific_lines(str(row["kind"]), review))
                for source in row["sources"]:
                    lines.append(f"Quelle: {source}")
            open_conditions = [condition for condition in row["conditions"] if condition["status"] == "OPEN"]
            if open_conditions:
                lines.append("Fehlt: " + "; ".join(str(condition["description"]) for condition in open_conditions))
            if status in {"WATCH", "INVALIDATED"} and row.get("transition_reason"):
                lines.append(f"Grund: {row['transition_reason']}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_change_only(radar: RadarDB, output_path: Path | str) -> str | None:
    body = build_report(radar)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    output = Path(output_path)
    with radar.connect() as connection:
        previous = connection.execute("SELECT digest FROM report_state WHERE name = 'reader'").fetchone()
        if previous is not None and previous["digest"] == digest and output.exists():
            return None
        output.parent.mkdir(parents=True, exist_ok=True)
        # Replacement is atomic for the file, not jointly with the DB commit.
        import tempfile
        if not all(section in body for section in ('## READY', '## WATCH')):
            raise ValueError('incomplete reader structure')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                             prefix=output.name + '.', suffix='.tmp', delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(body)
            temporary.replace(output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        connection.execute(
            """INSERT INTO report_state(name, digest) VALUES ('reader', ?)
               ON CONFLICT(name) DO UPDATE SET digest = excluded.digest""",
            (digest,),
        )
    return body
