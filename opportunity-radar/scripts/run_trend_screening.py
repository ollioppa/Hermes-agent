#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import yfinance as yf
from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opportunity_radar.db import RadarDB, candidate_suppression_reason, same_candidate_episode, case_suppression_reason, active_research_count
from opportunity_radar.universe import UniverseMember, download_current_universe, load_universe_sources

PROVIDER = "hf_amir_yahoo+yfinance"
REPO_ID = "AmirTrader/YahooFinance"
SOURCE_URL = "https://huggingface.co/datasets/AmirTrader/YahooFinance"
GLOBAL_SOURCE_URL = "https://finance.yahoo.com/"
ALIASES = {"BRK.B": "BRK-B", "BF.B": "BF-B"}
YAHOO_SUFFIX = {
    "XAMS": ".AS", "XBRU": ".BR", "XCSE": ".CO", "XDUB": ".IR",
    "XETR": ".DE", "XHEL": ".HE", "XLIS": ".LS", "XLON": ".L",
    "XMAD": ".MC", "XMIL": ".MI", "XOSL": ".OL", "XPAR": ".PA",
    "XSTO": ".ST", "XSWX": ".SW", "XWAR": ".WA", "XWBO": ".VI", "XATH": ".AT",
}


def month_key(value: date) -> tuple[int, int]:
    return value.year, value.month


def ordinal(month: tuple[int, int]) -> int:
    return month[0] * 12 + month[1] - 1


def trend_value(intercept: float, slope: float, run_year: int, month: tuple[int, int]) -> float:
    return intercept + slope * (4 + (ordinal(month) - ordinal((run_year - 1, 12))) / 12)


def refresh_prices(hf_root: Path, members: list[UniverseMember]) -> str:
    revision = HfApi().dataset_info(REPO_ID).sha
    if not revision:
        raise RuntimeError('missing HF revision')
    files = [f"data/daily/{ALIASES.get(member.symbol, member.symbol)}.parquet" for member in members]
    files.extend(["README.md", "data/state/ingestion_state.parquet"])
    snapshot_download(REPO_ID, repo_type="dataset", revision=revision, allow_patterns=files, local_dir=hf_root)
    return str(revision)


def yahoo_symbol(member: UniverseMember) -> str:
    if member.kind == "etf" and member.price_symbol:
        return member.price_symbol.replace(".DEX", ".DE").replace(".LON", ".L").replace(".SWX", ".SW")
    symbol = member.symbol.strip()
    if member.mic in {"XCSE", "XSTO", "XHEL"}:
        symbol = symbol.replace(" ", "-")
    if member.mic == "XLON":
        symbol = symbol.rstrip(".").replace(".", "-")
    return symbol + YAHOO_SUFFIX.get(member.mic, "")


def _csv_path(root: Path, provider_symbol: str) -> Path:
    return root / f"{provider_symbol.replace('/', '_')}.csv"


def _store_yahoo_frame(root: Path, provider_symbol: str, frame: object) -> bool:
    try:
        prices = frame[["Adj Close"]].dropna().reset_index()  # type: ignore[index]
        prices.columns = ["date", "adjusted_close"]
        prices["date"] = prices["date"].dt.strftime("%Y-%m-%d")
        if prices.empty:
            return False
        path = _csv_path(root, provider_symbol)
        _atomic_write_text(path, prices.to_csv(index=False))
        return True
    except Exception:
        return False


def refresh_global_prices(root: Path, members: list[UniverseMember]) -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    provider_symbols = sorted({yahoo_symbol(member) for member in members})
    errors: dict[str, str] = {}
    # Fetch the complete adjusted series: a recent append cannot rebase old anchors.
    for start in range(0, len(provider_symbols), 50):
        batch = provider_symbols[start : start + 50]
        try:
            data = yf.download(
                batch, period="max", auto_adjust=False, actions=False,
                group_by="ticker", progress=False, threads=True, timeout=30,
            )
        except Exception as error:
            errors.update({symbol: str(error) for symbol in batch})
            continue
        for symbol in batch:
            try:
                frame = data[symbol] if len(batch) > 1 else data
                if not _store_yahoo_frame(root, symbol, frame):
                    errors[symbol] = 'empty or invalid adjusted-price refresh'
            except Exception as error:
                errors[symbol] = str(error)
    return errors


def load_price_rows(
    old_csv: Path, hf_root: Path, members: list[UniverseMember]
) -> tuple[dict[str, list[tuple[date, float]]], dict[str, tuple[date, float]], dict[str, object], list[dict[str, object]]]:
    symbols = sorted(member.symbol for member in members)
    paths = {symbol: hf_root / "data/daily" / f"{ALIASES.get(symbol, symbol)}.parquet" for symbol in symbols}
    missing = [symbol for symbol, path in paths.items() if not path.exists()]
    if missing:
        raise RuntimeError(f"missing HF price files: {','.join(missing)}")

    con = duckdb.connect()
    quoted_symbols = ",".join("'" + symbol.replace("'", "''") + "'" for symbol in symbols)
    parquet_paths = ",".join("'" + str(path).replace("'", "''") + "'" for path in paths.values())
    con.execute(
        f"""CREATE TEMP TABLE old_prices AS
        SELECT CAST(date AS DATE) date, symbol, CAST(adjusted_close AS DOUBLE) adjusted_close
        FROM read_csv_auto('{old_csv}')
        WHERE symbol IN ({quoted_symbols}) AND adjusted_close > 0"""
    )
    con.execute(
        f"""CREATE TEMP TABLE new_raw AS
        SELECT CAST(date AS DATE) date,
               regexp_extract(filename, '/([^/]+)\\.parquet$', 1) hf_symbol,
               CAST(adj_close AS DOUBLE) adjusted_close
        FROM read_parquet([{parquet_paths}], filename=true)"""
    )
    aliases_back = {value: key for key, value in ALIASES.items()}
    cases = " ".join(f"WHEN hf_symbol='{hf}' THEN '{canonical}'" for hf, canonical in aliases_back.items())
    con.execute(
        f"""CREATE TEMP TABLE new_prices AS
        SELECT date, CASE {cases} ELSE hf_symbol END symbol, adjusted_close
        FROM new_raw WHERE adjusted_close > 0"""
    )
    factor_rows = con.execute(
        """WITH overlap AS (
          SELECT o.symbol,o.date,n.adjusted_close/o.adjusted_close ratio
          FROM old_prices o JOIN new_prices n USING(symbol,date)
          WHERE o.date BETWEEN DATE '2024-12-01' AND DATE '2024-12-31')
        SELECT symbol,COUNT(*) overlap_days,MEDIAN(ratio) factor,
               MIN(ratio) min_ratio,MAX(ratio) max_ratio,MAX(ratio)-MIN(ratio) ratio_span
        FROM overlap GROUP BY symbol ORDER BY symbol"""
    ).fetchall()
    factor_dicts = [dict(zip(("symbol", "overlap_days", "factor", "min_ratio", "max_ratio", "ratio_span"), row)) for row in factor_rows]
    accepted = {row[0]: row[2] for row in factor_rows if row[1] >= 10 and row[5] <= 0.001}
    rejected = [row[0] for row in factor_rows if row[0] not in accepted]
    if rejected:
        raise RuntimeError("incompatible adjusted-price overlap: " + ",".join(rejected))

    con.execute("CREATE TEMP TABLE factors(symbol VARCHAR, factor DOUBLE)")
    con.executemany("INSERT INTO factors VALUES (?,?)", sorted(accepted.items()))
    con.execute(
        """CREATE TEMP TABLE stitched AS
        SELECT o.date,o.symbol,o.adjusted_close*f.factor adjusted_close
          FROM old_prices o JOIN factors f USING(symbol) WHERE o.date<=DATE '2024-12-31'
        UNION ALL
        SELECT n.date,n.symbol,n.adjusted_close
          FROM new_prices n JOIN factors f USING(symbol) WHERE n.date>DATE '2024-12-31'
        UNION ALL
        SELECT n.date,n.symbol,n.adjusted_close
          FROM new_prices n LEFT JOIN factors f USING(symbol) WHERE f.symbol IS NULL"""
    )
    duplicate_count = con.execute(
        "SELECT COUNT(*) FROM (SELECT symbol,date,COUNT(*) n FROM stitched GROUP BY 1,2 HAVING n>1)"
    ).fetchone()[0]
    if duplicate_count:
        raise RuntimeError("stitched price history contains duplicate symbol/date rows")

    monthly_rows = con.execute(
        """SELECT symbol,date,adjusted_close FROM (
          SELECT symbol,date,adjusted_close,
                 ROW_NUMBER() OVER(PARTITION BY symbol,DATE_TRUNC('month',date) ORDER BY date DESC) rn
          FROM stitched) WHERE rn=1 ORDER BY symbol,date"""
    ).fetchall()
    latest_rows = {
        row[0]: (row[1], row[2])
        for row in con.execute(
            """SELECT symbol,date,adjusted_close FROM (
              SELECT symbol,date,adjusted_close,ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY date DESC) rn
              FROM new_prices) WHERE rn=1"""
        ).fetchall()
    }
    by_symbol: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for symbol, day, price in monthly_rows:
        by_symbol[symbol].append((day, price))
    latest_global = max(day for day, _ in latest_rows.values())
    quality = {
        "target_us_stocks": len(symbols),
        "eligible_us_stocks": sum(
            len({day.year for day, _ in rows if day.month == 12}) >= 5
            for rows in by_symbol.values()
        ),
        "latest_date": latest_global.isoformat(),
        "rebased_symbols": len(accepted),
        "hf_only_symbols": len(symbols) - len(accepted),
        "duplicate_symbol_dates": duplicate_count,
    }
    return by_symbol, latest_rows, quality, factor_dicts


def load_global_price_rows(
    root: Path, members: list[UniverseMember]
) -> tuple[dict[str, list[tuple[date, float]]], dict[str, tuple[date, float]], dict[str, object]]:
    available = [(member, yahoo_symbol(member), _csv_path(root, yahoo_symbol(member))) for member in members]
    available = [row for row in available if row[2].exists()]
    con = duckdb.connect()
    con.execute("CREATE TEMP TABLE symbol_map(provider_symbol VARCHAR, stable_identity VARCHAR)")
    con.executemany(
        "INSERT INTO symbol_map VALUES (?,?)",
        [(provider_symbol, member.stable_identity) for member, provider_symbol, _ in available],
    )
    paths = ",".join("'" + str(path).replace("'", "''") + "'" for _, _, path in available)
    con.execute(
        f"""CREATE TEMP TABLE global_prices AS
        SELECT m.stable_identity, CAST(p.date AS DATE) date, CAST(p.adjusted_close AS DOUBLE) adjusted_close
        FROM read_csv([{paths}], filename=true) p
        JOIN symbol_map m ON regexp_extract(p.filename, '/([^/]+)\\.csv$', 1)=m.provider_symbol
        WHERE CAST(p.adjusted_close AS DOUBLE)>0"""
    )
    monthly_rows = con.execute(
        """SELECT stable_identity,date,adjusted_close FROM (
          SELECT *,ROW_NUMBER() OVER(PARTITION BY stable_identity,DATE_TRUNC('month',date) ORDER BY date DESC) rn
          FROM global_prices) WHERE rn=1 ORDER BY stable_identity,date"""
    ).fetchall()
    latest_rows = {
        row[0]: (row[1], row[2])
        for row in con.execute(
            """SELECT stable_identity,date,adjusted_close FROM (
              SELECT *,ROW_NUMBER() OVER(PARTITION BY stable_identity ORDER BY date DESC) rn
              FROM global_prices) WHERE rn=1"""
        ).fetchall()
    }
    monthly: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for stable_identity, day, price in monthly_rows:
        monthly[stable_identity].append((day, price))
    eligible = {
        stable_identity
        for stable_identity, rows in monthly.items()
        if len({day.year for day, _ in rows if day.month == 12}) >= 5
    }
    digest_payload = "\n".join(
        f"{identity}|{day.isoformat()}|{price!r}"
        for identity, rows in sorted(monthly.items()) for day, price in rows
    )
    quality = {
        "target_eu_stocks": sum(member.kind == "stock" for member in members),
        "covered_eu_stocks": sum(member.kind == "stock" and member.stable_identity in latest_rows for member in members),
        "eligible_eu_stocks": sum(member.kind == "stock" and member.stable_identity in eligible for member in members),
        "target_etfs": sum(member.kind == "etf" for member in members),
        "covered_etfs": sum(member.kind == "etf" and member.stable_identity in latest_rows for member in members),
        "eligible_etfs": sum(member.kind == "etf" and member.stable_identity in eligible for member in members),
        "global_min_latest_date": min(day for day, _ in latest_rows.values()).isoformat(),
        "global_max_latest_date": max(day for day, _ in latest_rows.values()).isoformat(),
        "global_snapshot_digest": hashlib.sha256(digest_payload.encode()).hexdigest(),
    }
    return monthly, latest_rows, quality


def compute_current_signals(
    members: list[UniverseMember],
    monthly: dict[str, list[tuple[date, float]]],
    latest: dict[str, tuple[date, float]],
    *,
    key_by_identity: bool = False,
    source_url: str = SOURCE_URL,
    as_of: date | None = None,
) -> list[dict[str, object]]:
    as_of = as_of or datetime.now(timezone.utc).date()
    results: list[dict[str, object]] = []
    for member in members:
        symbol = member.symbol
        lookup_key = member.stable_identity if key_by_identity else symbol
        rows = [(day, price) for day, price in monthly.get(lookup_key, []) if day <= as_of]
        if not rows or lookup_key not in latest:
            continue
        series = {month_key(day): (day, price) for day, price in rows}
        latest_day, latest_price = latest[lookup_key]
        if latest_day > as_of or latest_day.year != as_of.year:
            continue
        current_month = month_key(latest_day)
        closed_months = sorted(key for key in series if key < current_month)
        episodes: list[dict[str, object]] = []
        for run_year in range(2005, latest_day.year + 1):
            anchors = [(year, 12) for year in range(run_year - 5, run_year)]
            if any(anchor not in series for anchor in anchors):
                continue
            prices = [series[anchor][1] for anchor in anchors]
            mean = sum(prices) / 5
            slope = sum((x - 2) * (price - mean) for x, price in enumerate(prices)) / 10
            intercept = mean - 2 * slope
            if slope <= 0 or intercept + 4 * slope <= 0:
                continue
            run_month: tuple[int, int] | None = None
            for key in closed_months:
                if key[0] < run_year:
                    continue
                trend = trend_value(intercept, slope, run_year, key)
                if trend <= 0:
                    continue
                if run_month is None:
                    if key[0] > run_year:
                        break
                    if series[key][1] >= 1.30 * trend:
                        run_month = key
                elif key > run_month and series[key][1] <= 1.10 * trend:
                    episodes.append(
                        {
                            "run_year": run_year,
                            "run_month": f"{run_month[0]:04d}-{run_month[1]:02d}",
                            "first_entry_month": f"{key[0]:04d}-{key[1]:02d}",
                            "anchors": [
                                {"month": f"{anchor[0]:04d}-12", "adjusted_close": round(price, 8)}
                                for anchor, price in zip(anchors, prices)
                            ],
                            "trend_slope": round(slope, 8),
                            "entry_close": round(series[key][1], 8),
                            "entry_trend": round(trend, 8),
                            "entry_ratio": round(series[key][1] / trend, 8),
                            "_slope": slope,
                            "_intercept": intercept,
                        }
                    )
                    break
        if not episodes:
            continue
        episode = max(episodes, key=lambda item: str(item["first_entry_month"]))
        current_trend = trend_value(
            float(episode.pop("_intercept")),
            float(episode.pop("_slope")),
            int(episode["run_year"]),
            current_month,
        )
        current_ratio = latest_price / current_trend if current_trend > 0 else 999.0
        if str(episode["first_entry_month"])[:4] != str(as_of.year) or current_ratio > 1.10:
            continue
        results.append(
            {
                "stable_identity": member.stable_identity,
                "symbol": member.symbol,
                "name": member.name,
                "kind": member.kind,
                "region": member.region,
                "mic": member.mic,
                **episode,
                "latest_date": latest_day.isoformat(),
                "latest_close": round(latest_price, 8),
                "current_trend": round(current_trend, 8),
                "current_ratio": round(current_ratio, 8),
                "source": source_url,
                "override_status": "BLACK_SWAN_REVIEW_PENDING",
            }
        )
    return sorted(results, key=lambda row: (str(row["first_entry_month"]), -float(row["current_ratio"]), str(row["stable_identity"])), reverse=True)


def publish(
    radar: RadarDB, signals: list[dict[str, object]], *, as_of: date, source_revision: str,
    refresh_errors: dict[str, str] | None = None,
) -> dict[str, object]:
    if refresh_errors:
        raise ValueError(f'price refresh failed: {refresh_errors}')
    for signal in signals:
        latest_day = date.fromisoformat(str(signal['latest_date']))
        entry = date.fromisoformat(str(signal['first_entry_month']) + '-01')
        if (latest_day > as_of or latest_day.year != as_of.year
                or entry.year != as_of.year or entry > latest_day):
            raise ValueError('signal dates are not eligible for as_of')
    radar.initialize()
    cycle_key = f"trend-normalization:v1:{as_of.isoformat()}:{source_revision[:12]}"
    with radar.connect() as connection:
        existing = connection.execute("SELECT id,status FROM screen_cycles WHERE cycle_key=?", (cycle_key,)).fetchone()
        if existing is not None:
            return {"status": "ALREADY_PUBLISHED", "cycle_id": int(existing["id"]), "signals": len(signals)}
        connection.execute("BEGIN IMMEDIATE")
        cycle_id = int(
            connection.execute(
                "INSERT INTO screen_cycles(cycle_key,cohort_index,provider,status,as_of) VALUES (?,0,?,'OPEN',?)",
                (cycle_key, PROVIDER, as_of.isoformat()),
            ).lastrowid
        )
        open_count = active_research_count(connection)
        remaining = max(0, 10 - open_count)
        selected = reserve = deduped = 0
        for signal in signals:
            metrics = json.dumps(signal, ensure_ascii=False, sort_keys=True)
            case_reason = case_suppression_reason(connection, str(signal['symbol']),
                str(signal['stable_identity']), str(signal['first_entry_month']))
            candidate = connection.execute(
                """SELECT id,metrics_json FROM candidate_inbox
                   WHERE stable_identity=? AND status='OPEN'""",
                (signal["stable_identity"],),
            ).fetchone()
            decision = connection.execute(
                """SELECT decision,reason,signal_date FROM candidate_decisions
                   WHERE stable_identity=? ORDER BY id DESC LIMIT 1""",
                (signal["stable_identity"],),
            ).fetchone()
            suppressed_reason = candidate_suppression_reason(
                decision, str(signal["first_entry_month"])
            ) or case_reason
            if candidate or suppressed_reason:
                disposition = "DEDUPED"
                deduped += 1
                if candidate:
                    if same_candidate_episode(
                        str(candidate["metrics_json"]), str(signal["first_entry_month"])
                    ):
                        connection.execute(
                            """UPDATE candidate_inbox
                               SET last_seen_cycle_id=?,metrics_json=json_set(?,
                                   '$.research_work',json_extract(metrics_json,'$.research_work'),
                                   '$.research_revisit_decision_id',json_extract(metrics_json,'$.research_revisit_decision_id')),
                                   updated_at=CURRENT_TIMESTAMP
                               WHERE id=?""",
                            (cycle_id, metrics, candidate["id"]),
                        )
                    else:
                        connection.execute(
                            """UPDATE candidate_inbox
                               SET last_seen_cycle_id=?,updated_at=CURRENT_TIMESTAMP
                               WHERE id=?""",
                            (cycle_id, candidate["id"]),
                        )
            elif selected < remaining:
                disposition = "SELECTED"
                selected += 1
                connection.execute(
                    """INSERT INTO candidate_inbox(
                    stable_identity,symbol,name,kind,region,mic,status,first_seen_cycle_id,last_seen_cycle_id,lane,metrics_json)
                    VALUES (?,?,?,?,?,?,'OPEN',?,?,'TREND_NORMALIZATION',?)""",
                    (
                        signal["stable_identity"], signal["symbol"], signal["name"], signal["kind"],
                        signal["region"], signal["mic"], cycle_id, cycle_id, metrics,
                    ),
                )
            else:
                disposition = "RESERVE"
                reserve += 1
            reason = (
                f"first return {signal['first_entry_month']} after run {signal['run_month']}; "
                f"current trend ratio {float(signal['current_ratio']):.4f}"
            )
            if suppressed_reason:
                reason = suppressed_reason
            connection.execute(
                """INSERT INTO screen_hits(
                cycle_id,stable_identity,symbol,name,lane,region,kind,signal_date,price_date,disposition,reason,metrics_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cycle_id, signal["stable_identity"], signal["symbol"], signal["name"],
                    "TREND_NORMALIZATION", signal["region"], signal["kind"], signal["first_entry_month"],
                    signal["latest_date"], disposition, reason, metrics,
                ),
            )
        connection.execute(
            "UPDATE screen_cycles SET status='COMPLETED',completed_at=CURRENT_TIMESTAMP WHERE id=?", (cycle_id,)
        )
    return {
        "status": "COMPLETED",
        "cycle_id": cycle_id,
        "signals": len(signals),
        "selected": selected,
        "reserve": reserve,
        "deduped": deduped,
    }


def _atomic_write_text(path: Path, body: str) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                         dir=path.parent, prefix=path.name + '.',
                                         suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(body)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_artifacts(output: Path, signals: list[dict[str, object]], quality: dict[str, object], factors: list[dict[str, object]]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    summary = json.dumps({**quality, "signals": len(signals)}, indent=2) + "\n"
    signal_body = json.dumps(signals, ensure_ascii=False, indent=2) + "\n"
    factor_body = io.StringIO(newline='')
    if factors:
        writer = csv.DictWriter(factor_body, fieldnames=list(factors[0]))
        writer.writeheader()
        writer.writerows(factors)
    # Each file is atomic; this is not a transactional multi-file generation.
    _atomic_write_text(output / "summary.json", summary)
    _atomic_write_text(output / "signals.json", signal_body)
    if factors:
        _atomic_write_text(output / "rebase_factors.csv", factor_body.getvalue())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the US, Europe and ETF trend-normalisation screening lanes")
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("OPPORTUNITY_RADAR_DB", ROOT / "state/opportunity_radar.sqlite3")))
    parser.add_argument("--old-csv", type=Path, default=Path(os.environ.get("OPPORTUNITY_RADAR_HISTORY_CSV", "state/market-data/all_sp500_prices_2000_2024_delisted_include.csv")))
    parser.add_argument("--hf-root", type=Path, default=Path(os.environ.get("OPPORTUNITY_RADAR_HF_ROOT", "state/market-data/hf/AmirTrader-YahooFinance")))
    parser.add_argument("--global-root", type=Path, default=Path(os.environ.get("OPPORTUNITY_RADAR_GLOBAL_ROOT", "state/market-data/yfinance-global")))
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--no-publish", action="store_true")
    args = parser.parse_args()

    if not args.old_csv.exists():
        raise RuntimeError(f"historical CSV missing: {args.old_csv}")
    with tempfile.TemporaryDirectory(prefix="opportunity-radar-us-universe-") as temporary:
        universe_root = download_current_universe(Path(temporary), ROOT / "config/screen_exchange_map.json")
        all_members = load_universe_sources(universe_root, ROOT / "config/screen_etfs.json")
        us_members = [
            member for member in all_members
            if member.region == "US" and member.kind == "stock"
        ]
        global_members = [
            member for member in all_members
            if (member.region == "EU" and member.kind == "stock") or member.kind == "etf"
        ]
    amir_revision = None  # Unknown local bytes must not claim today's remote SHA.
    refresh_errors: dict[str, str] = {}
    if args.refresh:
        amir_revision = refresh_prices(args.hf_root, us_members)
        refresh_errors = refresh_global_prices(args.global_root, global_members)
        if refresh_errors:
            raise RuntimeError(f'price refresh failed: {refresh_errors}')
    us_monthly, us_latest, quality, factors = load_price_rows(args.old_csv, args.hf_root, us_members)
    global_monthly, global_latest, global_quality = load_global_price_rows(args.global_root, global_members)
    quality.update(global_quality)
    # Bind the actual calculation inputs, including stitched/rebased US anchors.
    source_payload = {
        'us_monthly': us_monthly, 'us_latest': us_latest,
        'global_monthly': global_monthly, 'global_latest': global_latest,
    }
    source_revision = hashlib.sha256(
        json.dumps(source_payload, sort_keys=True, default=str, separators=(',', ':')).encode()
    ).hexdigest()
    quality["amir_revision"] = amir_revision
    quality["source_revision"] = source_revision
    signals = compute_current_signals(us_members, us_monthly, us_latest, as_of=args.as_of)
    signals.extend(
        compute_current_signals(
            global_members, global_monthly, global_latest,
            key_by_identity=True, source_url=GLOBAL_SOURCE_URL, as_of=args.as_of,
        )
    )
    signals = sorted(
        signals,
        key=lambda row: (
            str(row["first_entry_month"]), -float(row["current_ratio"]), str(row["stable_identity"])
        ),
        reverse=True,
    )
    output = ROOT / "output/screening" / args.as_of.isoformat()
    write_artifacts(output, signals, quality, factors)
    result = {"provider": PROVIDER, "as_of": args.as_of.isoformat(), **quality, "signals": len(signals)}
    if not args.no_publish:
        result["publication"] = publish(
            RadarDB(args.db), signals, as_of=args.as_of, source_revision=source_revision,
            refresh_errors=refresh_errors
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
