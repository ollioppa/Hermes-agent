from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from .models import MarketSnapshot
from .market import canonical_snapshot, bound_snapshots, compare_price_sets
from .positions import validate_position_payload
from .position_review import validate_position_event, validate_position_review
from .transitions import ContractError
from .review import validate_review


def candidate_suppression_reason(
    decision: dict[str, object] | sqlite3.Row | None,
    signal_date: str,
) -> str | None:
    if decision is None:
        return None
    kind = str(decision["decision"])
    reason = str(decision["reason"])
    if kind == "EXCLUDE":
        return f"persistently excluded: {reason}"
    if str(decision["signal_date"]) != signal_date:
        return None
    if kind == "DEFER_EPISODE":
        return f"current signal episode deferred: {reason}"
    if kind == "SCREEN_DISTORTED":
        return f"current signal episode distorted: {reason}"
    return None


def same_candidate_episode(metrics_json: str, signal_date: str) -> bool:
    metrics = json.loads(metrics_json)
    return str(metrics.get("first_entry_month")) == signal_date


def case_suppression_reason(connection: sqlite3.Connection, symbol: str, stable_identity: str, signal_date: str) -> str | None:
    rows = connection.execute(
        """SELECT c.id,c.status,
                  (SELECT date(MAX(created_at)) FROM transitions WHERE case_id=c.id AND to_status='ARCHIVED') archived_on,
                  (SELECT json_extract(metrics_json,'$.first_entry_month') FROM candidate_inbox WHERE case_id=c.id LIMIT 1) admitted_episode
           FROM cases c LEFT JOIN case_identity_aliases a ON a.case_id=c.id
           WHERE c.symbol=? OR a.stable_identity=?""", (symbol.upper(), stable_identity),
    ).fetchall()
    closed_on = connection.execute("SELECT date(? || '-01','+1 month','-1 day')", (signal_date,)).fetchone()[0]
    for row in rows:
        if row['status'] != 'ARCHIVED':
            return 'existing non-archived case'
        if not row['archived_on'] or not closed_on or closed_on <= row['archived_on']:
            return 'archived case requires a provably later closed signal month'
        if row['admitted_episode'] and signal_date <= row['admitted_episode']:
            return 'archived case already considered this signal episode'
    return None


def active_research_count(connection: sqlite3.Connection) -> int:
    return int(connection.execute("""SELECT COUNT(*) FROM candidate_inbox ci
        WHERE ci.status='OPEN' AND NOT EXISTS (
            SELECT 1 FROM candidate_decisions d WHERE d.id=(
                SELECT MAX(id) FROM candidate_decisions
                WHERE stable_identity=ci.stable_identity
                  AND signal_date=json_extract(ci.metrics_json,'$.first_entry_month'))
            AND d.decision='AWAITING_USER')""").fetchone()[0])


def _validate_snapshot_binding(
    case_symbol: str,
    sector_symbol: str,
    snapshots: dict[str, dict[str, object]],
) -> None:
    expected = {
        "case": (case_symbol.upper(), "case"),
        "spy": ("SPY", "benchmark"),
        "sector": (sector_symbol.upper(), "sector"),
    }
    if set(snapshots) != set(expected):
        raise ContractError("snapshot binding requires case, SPY and sector")
    dates = set()
    for key, (symbol, role) in expected.items():
        snapshot = snapshots[key]
        if str(snapshot["symbol"]).upper() != symbol or snapshot["role"] != role:
            raise ContractError("snapshot binding does not match case, SPY and sector symbols")
        canonical_snapshot(snapshot)
        dates.add(str(snapshot["price_date"]))
    if len(dates) != 1:
        raise ContractError("snapshot binding requires one shared price date")


def _case_by_symbol(connection: sqlite3.Connection, symbol: str) -> sqlite3.Row | None:
    return connection.execute(
        """SELECT * FROM cases WHERE symbol=?
           ORDER BY CASE status WHEN 'ARCHIVED' THEN 1 ELSE 0 END,id DESC LIMIT 1""",
        (symbol.upper(),),
    ).fetchone()


def _validate_position_case_link(
    connection: sqlite3.Connection, case: sqlite3.Row | None, position: dict[str, object]
) -> None:
    if case is None:
        raise ContractError("linked_case_symbol does not identify an existing Radar case")
    same_symbol = position["symbol"] == str(case["symbol"]).strip().upper()
    # Only persisted identity bindings count; never infer aliases from ticker syntax.
    bound_alias = False
    if not same_symbol and position["kind"] == case["kind"]:
        bound_alias = connection.execute(
            """SELECT 1 FROM case_identity_aliases a
               JOIN candidate_inbox ci ON ci.stable_identity=a.stable_identity
               WHERE a.case_id=? AND ci.symbol=? AND ci.kind=? LIMIT 1""",
            (case["id"], position["symbol"], position["kind"]),
        ).fetchone() is not None
    if position["kind"] != case["kind"] or not (same_symbol or bound_alias):
        raise ContractError("position instrument identity does not match linked Radar case")


class RadarDB:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('stock', 'etf')),
                    sector_symbol TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'INBOX',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY,
                    case_id INTEGER NOT NULL REFERENCES cases(id),
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(case_id, version)
                );
                CREATE TABLE IF NOT EXISTS watch_conditions (
                    id INTEGER PRIMARY KEY,
                    case_id INTEGER NOT NULL REFERENCES cases(id),
                    kind TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    fulfilled_reason TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY,
                    review_id INTEGER NOT NULL REFERENCES reviews(id),
                    url TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    id INTEGER PRIMARY KEY,
                    case_id INTEGER NOT NULL REFERENCES cases(id),
                    symbol TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('case', 'benchmark', 'sector', 'ready', 'outcome')),
                    price REAL NOT NULL CHECK(price > 0),
                    price_date TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    semantics TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS shadow_entries (
                    case_id INTEGER PRIMARY KEY REFERENCES cases(id),
                    review_id INTEGER NOT NULL REFERENCES reviews(id),
                    case_snapshot_id INTEGER NOT NULL REFERENCES market_snapshots(id),
                    spy_snapshot_id INTEGER NOT NULL REFERENCES market_snapshots(id),
                    sector_snapshot_id INTEGER NOT NULL REFERENCES market_snapshots(id),
                    immediate_investable INTEGER NOT NULL CHECK(immediate_investable IN (0, 1))
                );
                CREATE TABLE IF NOT EXISTS ready_snapshot_sets (
                    case_id INTEGER NOT NULL REFERENCES cases(id),
                    case_snapshot_id INTEGER PRIMARY KEY REFERENCES market_snapshots(id),
                    spy_snapshot_id INTEGER NOT NULL REFERENCES market_snapshots(id),
                    sector_snapshot_id INTEGER NOT NULL REFERENCES market_snapshots(id)
                );
                CREATE TRIGGER IF NOT EXISTS ready_snapshot_sets_append_only_update
                BEFORE UPDATE ON ready_snapshot_sets BEGIN
                    SELECT RAISE(ABORT, 'READY endpoints are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS ready_snapshot_sets_append_only_delete
                BEFORE DELETE ON ready_snapshot_sets BEGIN
                    SELECT RAISE(ABORT, 'READY endpoints are append-only');
                END;
                CREATE TABLE IF NOT EXISTS outcome_checks (
                    id INTEGER PRIMARY KEY,
                    case_id INTEGER NOT NULL REFERENCES cases(id),
                    decision_status TEXT NOT NULL,
                    case_snapshot_id INTEGER NOT NULL REFERENCES market_snapshots(id),
                    spy_snapshot_id INTEGER NOT NULL REFERENCES market_snapshots(id),
                    sector_snapshot_id INTEGER NOT NULL REFERENCES market_snapshots(id),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS transitions (
                    id INTEGER PRIMARY KEY,
                    case_id INTEGER NOT NULL REFERENCES cases(id),
                    from_status TEXT NOT NULL,
                    to_status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS report_state (
                    name TEXT PRIMARY KEY,
                    digest TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS watchdog_rules (
                    case_id INTEGER PRIMARY KEY REFERENCES cases(id),
                    min_days INTEGER NOT NULL DEFAULT 90,
                    min_relative_spy_pp REAL NOT NULL DEFAULT 0,
                    min_relative_sector_pp REAL NOT NULL DEFAULT 0,
                    max_price REAL,
                    max_source_age_days INTEGER NOT NULL DEFAULT 60
                );
                CREATE TABLE IF NOT EXISTS watchdog_signal_state (
                    case_id INTEGER NOT NULL REFERENCES cases(id),
                    signal TEXT NOT NULL,
                    active INTEGER NOT NULL CHECK(active IN (0,1)),
                    detail TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(case_id, signal)
                );
                CREATE TABLE IF NOT EXISTS watchdog_events (
                    id INTEGER PRIMARY KEY,
                    event_key TEXT NOT NULL UNIQUE,
                    case_id INTEGER NOT NULL REFERENCES cases(id),
                    signal TEXT NOT NULL,
                    old_state INTEGER NOT NULL,
                    new_state INTEGER NOT NULL,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    delivered_at TEXT
                );
                CREATE TABLE IF NOT EXISTS mail_receipts (
                    delivery_key TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    sent_message_id TEXT NOT NULL,
                    verified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS case_identity_aliases (
                    stable_identity TEXT NOT NULL,
                    case_id INTEGER NOT NULL UNIQUE REFERENCES cases(id),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(stable_identity,case_id)
                );
                CREATE TABLE IF NOT EXISTS screen_cycles (
                    id INTEGER PRIMARY KEY,
                    cycle_key TEXT NOT NULL UNIQUE,
                    cohort_index INTEGER NOT NULL DEFAULT 0,
                    provider TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('OPEN', 'COMPLETED', 'FAILED')),
                    as_of TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    failure_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS screen_hits (
                    id INTEGER PRIMARY KEY,
                    cycle_id INTEGER NOT NULL REFERENCES screen_cycles(id),
                    stable_identity TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    lane TEXT NOT NULL,
                    region TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    signal_date TEXT NOT NULL,
                    price_date TEXT NOT NULL,
                    disposition TEXT NOT NULL CHECK(disposition IN ('SELECTED', 'RESERVE', 'DEDUPED')),
                    reason TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(cycle_id, stable_identity, lane)
                );
                CREATE TABLE IF NOT EXISTS candidate_inbox (
                    id INTEGER PRIMARY KEY,
                    stable_identity TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('stock', 'etf')),
                    region TEXT NOT NULL,
                    mic TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('OPEN', 'PROMOTED', 'ARCHIVED')),
                    first_seen_cycle_id INTEGER NOT NULL REFERENCES screen_cycles(id),
                    last_seen_cycle_id INTEGER NOT NULL REFERENCES screen_cycles(id),
                    lane TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    case_id INTEGER UNIQUE REFERENCES cases(id),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE UNIQUE INDEX IF NOT EXISTS candidate_one_open_identity
                    ON candidate_inbox(stable_identity) WHERE status = 'OPEN';
                CREATE TABLE IF NOT EXISTS candidate_decisions (
                    id INTEGER PRIMARY KEY,
                    stable_identity TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    decision TEXT NOT NULL CHECK(decision IN (
                        'EXCLUDE', 'DEFER_EPISODE', 'RESEARCH_INCOMPLETE',
                        'SCREEN_DISTORTED', 'AWAITING_USER'
                    )),
                    reason TEXT NOT NULL,
                    signal_date TEXT NOT NULL,
                    report_path TEXT,
                    reader_text TEXT,
                    revisit_after TEXT,
                    revisit_trigger TEXT,
                    decided_by TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    notified_at TEXT
                );
                CREATE INDEX IF NOT EXISTS candidate_decisions_identity
                    ON candidate_decisions(stable_identity, id DESC);
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('stock', 'etf')),
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'CLOSED')),
                    case_id INTEGER REFERENCES cases(id),
                    purchase_date TEXT NOT NULL,
                    purchase_date_is_approximate INTEGER NOT NULL CHECK(purchase_date_is_approximate IN (0, 1)),
                    average_price REAL NOT NULL CHECK(average_price > 0),
                    quantity REAL NOT NULL CHECK(quantity > 0),
                    invested_amount REAL NOT NULL CHECK(invested_amount > 0),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    closed_at TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS position_one_active_symbol
                    ON positions(symbol) WHERE status = 'ACTIVE';
                CREATE TABLE IF NOT EXISTS position_baselines (
                    id INTEGER PRIMARY KEY,
                    position_id INTEGER NOT NULL REFERENCES positions(id),
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    change_reason TEXT NOT NULL,
                    confirmed_by TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(position_id, version)
                );
                CREATE TABLE IF NOT EXISTS position_reviews (
                    id INTEGER PRIMARY KEY,
                    position_id INTEGER NOT NULL REFERENCES positions(id),
                    review_date TEXT NOT NULL,
                    recommendation TEXT NOT NULL CHECK(recommendation IN ('HOLD','TRIM','EXIT','NO_DECISION')),
                    summary TEXT NOT NULL,
                    strongest_counterevidence TEXT NOT NULL,
                    report_path TEXT NOT NULL,
                    missing_decision_fact TEXT,
                    next_check_on TEXT,
                    reviewer TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(position_id, review_date)
                );
                CREATE TABLE IF NOT EXISTS position_events (
                    id INTEGER PRIMARY KEY,
                    position_id INTEGER NOT NULL REFERENCES positions(id),
                    action TEXT NOT NULL CHECK(action IN ('TRIM','EXIT')),
                    event_date TEXT NOT NULL,
                    quantity_before REAL NOT NULL,
                    quantity_change REAL NOT NULL,
                    quantity_after REAL NOT NULL,
                    price REAL,
                    reason TEXT NOT NULL,
                    confirmed_by TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TRIGGER IF NOT EXISTS reviews_append_only_update
                BEFORE UPDATE ON reviews BEGIN
                    SELECT RAISE(ABORT, 'reviews are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS reviews_append_only_delete
                BEFORE DELETE ON reviews BEGIN
                    SELECT RAISE(ABORT, 'reviews are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS sources_append_only_update
                BEFORE UPDATE ON sources BEGIN
                    SELECT RAISE(ABORT, 'sources are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS sources_append_only_delete
                BEFORE DELETE ON sources BEGIN
                    SELECT RAISE(ABORT, 'sources are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS shadows_append_only_update
                BEFORE UPDATE ON shadow_entries BEGIN
                    SELECT RAISE(ABORT, 'shadow entries are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS shadows_append_only_delete
                BEFORE DELETE ON shadow_entries BEGIN
                    SELECT RAISE(ABORT, 'shadow entries are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS outcomes_append_only_update
                BEFORE UPDATE ON outcome_checks BEGIN
                    SELECT RAISE(ABORT, 'outcomes are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS outcomes_append_only_delete
                BEFORE DELETE ON outcome_checks BEGIN
                    SELECT RAISE(ABORT, 'outcomes are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS snapshots_append_only_update
                BEFORE UPDATE ON market_snapshots BEGIN
                    SELECT RAISE(ABORT, 'market snapshots are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS snapshots_append_only_delete
                BEFORE DELETE ON market_snapshots BEGIN
                    SELECT RAISE(ABORT, 'market snapshots are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS position_baselines_append_only_update
                BEFORE UPDATE ON position_baselines BEGIN
                    SELECT RAISE(ABORT, 'position baselines are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS position_baselines_append_only_delete
                BEFORE DELETE ON position_baselines BEGIN
                    SELECT RAISE(ABORT, 'position baselines are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS position_reviews_append_only_update
                BEFORE UPDATE ON position_reviews BEGIN
                    SELECT RAISE(ABORT, 'position reviews are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS position_reviews_append_only_delete
                BEFORE DELETE ON position_reviews BEGIN
                    SELECT RAISE(ABORT, 'position reviews are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS position_events_append_only_update
                BEFORE UPDATE ON position_events BEGIN
                    SELECT RAISE(ABORT, 'position events are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS position_events_append_only_delete
                BEFORE DELETE ON position_events BEGIN
                    SELECT RAISE(ABORT, 'position events are append-only');
                END;
                """
            )
            self._migrate_case_episodes(connection)
            self._migrate_candidate_decisions(connection)
            self._migrate_position_lifecycle(connection)
            if "body_sha256" not in {row["name"] for row in connection.execute("PRAGMA table_info(mail_receipts)")}:
                connection.execute("ALTER TABLE mail_receipts ADD COLUMN body_sha256 TEXT")

    @staticmethod
    def _migrate_position_lifecycle(connection: sqlite3.Connection) -> None:
        # Preserve IDs, historical NULLs, all columns and append-only triggers.
        # Only the old day uniqueness must go: a correction may share its date.
        connection.execute("PRAGMA foreign_keys=OFF")
        try:
            connection.execute("BEGIN IMMEDIATE")
            sql = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='position_reviews'").fetchone()[0]
            if "UNIQUE(position_id, review_date)" in sql:
                objects = connection.execute("SELECT sql FROM sqlite_master WHERE tbl_name='position_reviews' AND type IN ('index','trigger') AND sql IS NOT NULL").fetchall()
                definition = sql.replace("UNIQUE(position_id, review_date)", "CHECK(1)")
                connection.execute(definition.replace("position_reviews", "position_reviews_next", 1))
                connection.execute("INSERT INTO position_reviews_next SELECT * FROM position_reviews")
                connection.execute("DROP TABLE position_reviews")
                connection.execute("ALTER TABLE position_reviews_next RENAME TO position_reviews")
                for row in objects:
                    connection.execute(row[0])
            additions = {
                "position_baselines": {"predecessor_baseline_id": "INTEGER REFERENCES position_baselines(id)", "effective_on": "TEXT"},
                "position_reviews": {"baseline_id": "INTEGER REFERENCES position_baselines(id)", "supersedes_review_id": "INTEGER REFERENCES position_reviews(id)", "correction_reason": "TEXT"},
                "position_events": {"execution_reference": "TEXT", "payload_json": "TEXT"},
            }
            for table, fields in additions.items():
                existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
                for name, declaration in fields.items():
                    if name not in existing:
                        connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS position_execution_identity ON position_events(position_id,execution_reference) WHERE execution_reference IS NOT NULL")
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS position_review_successor ON position_reviews(supersedes_review_id) WHERE supersedes_review_id IS NOT NULL")
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS position_baseline_successor ON position_baselines(predecessor_baseline_id) WHERE predecessor_baseline_id IS NOT NULL")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ContractError("position migration would break historical foreign keys")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys=ON")

    @staticmethod
    def _migrate_case_episodes(connection: sqlite3.Connection) -> None:
        replacements = {}
        for table in ('cases', 'case_identity_aliases'):
            sql = str(connection.execute('SELECT sql FROM sqlite_master WHERE type=\'table\' AND name=?', (table,)).fetchone()[0])
            if table == 'cases' and 'symbol TEXT NOT NULL UNIQUE' in sql:
                replacements[table] = sql.replace('symbol TEXT NOT NULL UNIQUE', 'symbol TEXT NOT NULL')
            elif table == 'case_identity_aliases' and 'stable_identity TEXT PRIMARY KEY' in sql:
                replacements[table] = sql.replace('stable_identity TEXT PRIMARY KEY', 'stable_identity TEXT NOT NULL').rstrip()[:-1] + ', PRIMARY KEY(stable_identity,case_id))'
        index_sql = "CREATE UNIQUE INDEX IF NOT EXISTS case_one_current_symbol ON cases(symbol) WHERE status != 'ARCHIVED'"
        if not replacements:
            connection.execute(index_sql)
            return
        connection.execute('PRAGMA foreign_keys=OFF')
        try:
            connection.execute('BEGIN IMMEDIATE')
            for table, sql in replacements.items():
                connection.execute(sql.replace(table, table + '_next', 1))
                connection.execute(f'INSERT INTO {table}_next SELECT * FROM {table}')
                connection.execute(f'DROP TABLE {table}')
                connection.execute(f'ALTER TABLE {table}_next RENAME TO {table}')
            connection.execute(index_sql)
            if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
                raise ContractError('archive migration would break historical foreign keys')
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.execute('PRAGMA foreign_keys=ON')

    @staticmethod
    def _migrate_candidate_decisions(connection: sqlite3.Connection) -> None:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='candidate_decisions'"
        ).fetchone()
        if row is None:
            return
        columns = {
            str(column["name"])
            for column in connection.execute("PRAGMA table_info(candidate_decisions)").fetchall()
        }
        table_sql = str(row["sql"] or "")
        if {
            "revisit_after",
            "revisit_trigger",
        }.issubset(columns) and "RESEARCH_INCOMPLETE" in table_sql and "SCREEN_DISTORTED" in table_sql:
            return

        connection.execute("SAVEPOINT migrate_candidate_decisions")
        try:
            connection.execute("ALTER TABLE candidate_decisions RENAME TO candidate_decisions_legacy")
            connection.execute(
                """CREATE TABLE candidate_decisions (
                   id INTEGER PRIMARY KEY,
                   stable_identity TEXT NOT NULL,
                   symbol TEXT NOT NULL,
                   decision TEXT NOT NULL CHECK(decision IN (
                       'EXCLUDE', 'DEFER_EPISODE', 'RESEARCH_INCOMPLETE',
                       'SCREEN_DISTORTED', 'AWAITING_USER'
                   )),
                   reason TEXT NOT NULL,
                   signal_date TEXT NOT NULL,
                   report_path TEXT,
                   reader_text TEXT,
                   revisit_after TEXT,
                   revisit_trigger TEXT,
                   decided_by TEXT NOT NULL,
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   notified_at TEXT
               )"""
            )
            legacy_columns = {
                str(column["name"])
                for column in connection.execute("PRAGMA table_info(candidate_decisions_legacy)").fetchall()
            }
            revisit_after = "revisit_after" if "revisit_after" in legacy_columns else "NULL"
            revisit_trigger = "revisit_trigger" if "revisit_trigger" in legacy_columns else "NULL"
            connection.execute(
                f"""INSERT INTO candidate_decisions(
                    id, stable_identity, symbol, decision, reason, signal_date,
                    report_path, reader_text, revisit_after, revisit_trigger,
                    decided_by, created_at, notified_at)
                SELECT id, stable_identity, symbol, decision, reason, signal_date,
                       report_path, reader_text, {revisit_after}, {revisit_trigger},
                       decided_by, created_at, notified_at
                FROM candidate_decisions_legacy"""
            )
            connection.execute("DROP TABLE candidate_decisions_legacy")
            connection.execute(
                """CREATE INDEX IF NOT EXISTS candidate_decisions_identity
                   ON candidate_decisions(stable_identity, id DESC)"""
            )
            connection.execute("RELEASE SAVEPOINT migrate_candidate_decisions")
        except Exception:
            connection.execute("ROLLBACK TO SAVEPOINT migrate_candidate_decisions")
            connection.execute("RELEASE SAVEPOINT migrate_candidate_decisions")
            raise

    def add_case(self, symbol: str, name: str, kind: str, sector_symbol: str) -> int:
        if kind not in {"stock", "etf"}:
            raise ContractError("kind must be stock or etf")
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO cases(symbol, name, kind, sector_symbol) VALUES (?, ?, ?, ?)",
                (symbol.upper(), name, kind, sector_symbol.upper()),
            )
            return int(cursor.lastrowid)

    def import_case(self, payload: dict[str, object], *, candidate_id: int | None = None) -> int:
        symbol = str(payload["symbol"]).upper()
        name = str(payload["name"])
        kind = str(payload["kind"])
        sector_symbol = str(payload["sector_symbol"]).upper()
        if kind not in {"stock", "etf"}:
            raise ContractError("kind must be stock or etf")
        review = payload["review"]
        if not isinstance(review, dict):
            raise ContractError("review must be a mapping")
        validate_review(kind, review)
        sources = payload["sources"]
        if not isinstance(sources, list) or not sources or not all(str(url).startswith("https://") for url in sources):
            raise ContractError("first review requires HTTPS point-in-time sources")
        raw_snapshots = payload["snapshots"]
        if not isinstance(raw_snapshots, dict):
            raise ContractError("snapshots must be a mapping")
        snapshots = {}
        for key in ("case", "spy", "sector"):
            value = raw_snapshots.get(key)
            if not isinstance(value, dict):
                raise ContractError(f"snapshot {key} must be a mapping")
            snapshots[key] = MarketSnapshot(**value)
        _validate_snapshot_binding(
            symbol,
            sector_symbol,
            {
                key: dict(value.__dict__)
                for key, value in snapshots.items()
            },
        )
        immediate_investable = payload["immediate_investable"]
        if not isinstance(immediate_investable, bool):
            raise ContractError("immediate_investable must be a boolean")
        condition_kind = ""
        condition_description = ""
        if immediate_investable:
            if payload.get("watch_condition") is not None:
                raise ContractError("direct READY must not include a watch condition")
        else:
            condition = payload.get("watch_condition")
            if not isinstance(condition, dict):
                raise ContractError("watch_condition must be a mapping")
            condition_kind = str(condition.get("kind", ""))
            condition_description = str(condition.get("description", "")).strip()
            if condition_kind not in {"price", "event", "operating", "regime", "structure", "reaction"}:
                raise ContractError("invalid watch-condition kind")
            if not condition_description:
                raise ContractError("watch condition requires a description")

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            candidate = None
            if candidate_id is not None:
                candidate = connection.execute(
                    "SELECT id, stable_identity, symbol, name, kind, region, mic, status, case_id, metrics_json FROM candidate_inbox WHERE id = ?",
                    (candidate_id,),
                ).fetchone()
                if candidate is None:
                    raise ContractError("unknown candidate")
                if candidate["status"] != "OPEN" or candidate["case_id"] is not None:
                    raise ContractError("promotion requires an unbound OPEN candidate")
                if symbol != str(candidate["symbol"]).upper() or kind != candidate["kind"]:
                    raise ContractError("promotion payload does not match candidate identity")
                if " ".join(name.lower().split()) != " ".join(str(candidate["name"]).lower().split()):
                    raise ContractError("promotion payload does not match candidate name")
                episode = str(json.loads(candidate['metrics_json'])['first_entry_month'])
                blocked = case_suppression_reason(connection, symbol, candidate['stable_identity'], episode)
                if blocked:
                    raise ContractError(blocked)
            active = int(
                connection.execute("SELECT COUNT(*) FROM cases WHERE status IN ('WATCH', 'READY')").fetchone()[0]
            )
            if active >= 8:
                raise ContractError("active capacity of eight reached")
            if immediate_investable:
                ready_count = int(
                    connection.execute("SELECT COUNT(*) FROM cases WHERE status = 'READY'").fetchone()[0]
                )
                if ready_count >= 3:
                    raise ContractError("READY capacity of three reached")
            case_cursor = connection.execute(
                "INSERT INTO cases(symbol, name, kind, sector_symbol) VALUES (?, ?, ?, ?)",
                (symbol, name, kind, sector_symbol),
            )
            case_id = int(case_cursor.lastrowid)
            snapshot_ids = {}
            for key, snapshot in snapshots.items():
                cursor = connection.execute(
                    """INSERT INTO market_snapshots(
                           case_id, symbol, role, price, price_date, retrieved_at,
                           currency, provider, semantics
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        case_id, snapshot.symbol.upper(), snapshot.role, snapshot.price,
                        snapshot.price_date, snapshot.retrieved_at, snapshot.currency,
                        snapshot.provider, snapshot.semantics,
                    ),
                )
                snapshot_ids[key] = int(cursor.lastrowid)
            review_cursor = connection.execute(
                "INSERT INTO reviews(case_id, version, payload_json) VALUES (?, 1, ?)",
                (case_id, json.dumps(review, ensure_ascii=False, sort_keys=True)),
            )
            review_id = int(review_cursor.lastrowid)
            for url in sources:
                connection.execute("INSERT INTO sources(review_id, url) VALUES (?, ?)", (review_id, str(url)))
            connection.execute(
                """INSERT INTO shadow_entries(
                       case_id, review_id, case_snapshot_id, spy_snapshot_id,
                       sector_snapshot_id, immediate_investable
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    case_id, review_id, snapshot_ids["case"], snapshot_ids["spy"],
                    snapshot_ids["sector"], int(immediate_investable),
                ),
            )
            if immediate_investable:
                ready_ids = {}
                for key, snapshot in snapshots.items():
                    cursor = connection.execute(
                        """INSERT INTO market_snapshots(
                               case_id, symbol, role, price, price_date, retrieved_at,
                               currency, provider, semantics
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            case_id, snapshot.symbol.upper(), "ready" if key == "case" else snapshot.role,
                            snapshot.price, snapshot.price_date, snapshot.retrieved_at,
                            snapshot.currency, snapshot.provider, snapshot.semantics,
                        ),
                    )
                    ready_ids[key] = int(cursor.lastrowid)
                connection.execute(
                    'INSERT INTO ready_snapshot_sets(case_id,case_snapshot_id,spy_snapshot_id,sector_snapshot_id) VALUES (?,?,?,?)',
                    (case_id, ready_ids['case'], ready_ids['spy'], ready_ids['sector']),
                )
                connection.execute("UPDATE cases SET status = 'READY' WHERE id = ?", (case_id,))
                connection.execute(
                    "INSERT INTO transitions(case_id, from_status, to_status, reason) VALUES (?, 'INBOX', 'READY', ?)",
                    (case_id, "initial review confirms immediate decision readiness"),
                )
            else:
                connection.execute(
                    "INSERT INTO watch_conditions(case_id, kind, description) VALUES (?, ?, ?)",
                    (case_id, condition_kind, condition_description),
                )
                connection.execute("UPDATE cases SET status = 'WATCH' WHERE id = ?", (case_id,))
                connection.execute(
                    "INSERT INTO transitions(case_id, from_status, to_status, reason) VALUES (?, 'INBOX', 'WATCH', ?)",
                    (case_id, "initial review complete"),
                )
            if candidate is not None:
                connection.execute(
                    "INSERT INTO case_identity_aliases(stable_identity, case_id) VALUES (?, ?)",
                    (candidate["stable_identity"], case_id),
                )
                connection.execute(
                    """UPDATE candidate_inbox
                       SET status = 'PROMOTED', case_id = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ? AND status = 'OPEN'""",
                    (case_id, candidate_id),
                )
            return case_id

    def promote_candidate(self, candidate_id: int, payload: dict[str, object]) -> int:
        return self.import_case(payload, candidate_id=candidate_id)

    def next_research_candidate(self, *, candidate_id: int | None = None,
                                confirmed_by: str | None = None) -> dict[str, object] | None:
        if candidate_id is not None and confirmed_by != "owner":
            raise ContractError("explicit research revisit requires Owner")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("""SELECT ci.*,d.id decision_id,d.decision,
                    d.revisit_after,d.revisit_trigger
                FROM candidate_inbox ci LEFT JOIN candidate_decisions d ON d.id=(
                    SELECT MAX(id) FROM candidate_decisions
                    WHERE stable_identity=ci.stable_identity
                      AND signal_date=json_extract(ci.metrics_json,'$.first_entry_month'))
                WHERE ci.status IN ('OPEN','ARCHIVED') AND ci.case_id IS NULL
                  AND (? IS NULL OR ci.id=?)
                  AND NOT EXISTS (SELECT 1 FROM candidate_decisions x
                      WHERE x.stable_identity=ci.stable_identity AND x.decision='EXCLUDE')
                ORDER BY ci.created_at,ci.id""", (candidate_id,candidate_id)).fetchall()
            for row in rows:
                metrics = json.loads(row['metrics_json'])
                resumed = metrics.get('research_revisit_decision_id') == row['decision_id']
                if row['decision'] in {'AWAITING_USER','SCREEN_DISTORTED'}:
                    continue
                if row['decision'] in {'DEFER_EPISODE','RESEARCH_INCOMPLETE'} and not resumed:
                    due = bool(row['revisit_after'] and row['revisit_after'] <= date.today().isoformat())
                    manual = candidate_id is not None and bool(row['revisit_trigger'] or row['revisit_after'])
                    if not (due or manual):
                        continue
                    if row['status'] == 'ARCHIVED':
                        if active_research_count(connection) >= 10 or connection.execute(
                            "SELECT 1 FROM candidate_inbox WHERE stable_identity=? AND status='OPEN'",
                            (row['stable_identity'],)).fetchone():
                            continue
                    metrics['research_revisit_decision_id'] = row['decision_id']
                    connection.execute("""UPDATE candidate_inbox SET status='OPEN',metrics_json=?,
                        updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                        (json.dumps(metrics,ensure_ascii=False),row['id']))
                elif row['status'] != 'OPEN':
                    continue
                result = dict(row)
                result.pop('metrics_json')
                result['status'] = 'OPEN'
                result['metrics'] = metrics
                result['research_history'] = [dict(d) for d in connection.execute(
                    "SELECT * FROM candidate_decisions WHERE stable_identity=? ORDER BY id DESC",
                    (row['stable_identity'],))]
                result['report_handoff'] = []
                for item in [*reversed((metrics.get('research_work') or [])), *result['research_history']]:
                    path = item.get('report_path')
                    if not path:
                        continue
                    report = Path(path)
                    if not report.is_absolute():
                        report = Path(__file__).resolve().parents[2] / report
                    try:
                        body = report.read_text(encoding='utf-8')
                    except OSError:
                        body = None
                    result['report_handoff'].append({**item,'report_text':body})
                return result
        return None

    def save_candidate_work(self, candidate_id: int, *, signal_date: str,
                            report_path: str, source_as_of: str, resume_from: str) -> None:
        if not all(value.strip() for value in (report_path,source_as_of,resume_from)):
            raise ContractError("research work requires report, source cutoff and next work")
        try:
            if date.fromisoformat(source_as_of).isoformat() != source_as_of:
                raise ValueError("noncanonical date")
        except ValueError as error:
            raise ContractError("research work source_as_of must be YYYY-MM-DD") from error
        report = Path(report_path)
        if not report.is_absolute():
            report = Path(__file__).resolve().parents[2] / report
        if not report.read_bytes().strip():
            raise ContractError("research work report is empty")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM candidate_inbox WHERE id=? AND status='OPEN'",
                                     (candidate_id,)).fetchone()
            if row is None or not same_candidate_episode(row['metrics_json'],signal_date):
                raise ContractError("research work requires the selected OPEN episode")
            latest = connection.execute("""SELECT decision FROM candidate_decisions
                WHERE stable_identity=? AND signal_date=? ORDER BY id DESC LIMIT 1""",
                (row['stable_identity'],signal_date)).fetchone()
            if latest and latest['decision']=='AWAITING_USER':
                raise ContractError("completed research is not a budget pause")
            metrics = json.loads(row['metrics_json'])
            metrics['research_work'] = metrics.get('research_work') or []
            metrics['research_work'].append(dict(report_path=report_path,
                source_as_of=source_as_of,resume_from=resume_from,saved_on=date.today().isoformat()))
            connection.execute("UPDATE candidate_inbox SET metrics_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                               (json.dumps(metrics,ensure_ascii=False),candidate_id))

    def record_candidate_decision(
        self,
        symbol: str,
        decision: str,
        reason: str,
        *,
        report_path: str | None = None,
        reader_text: str | None = None,
        revisit_after: str | None = None,
        revisit_trigger: str | None = None,
        decided_by: str = "owner",
        signal_date: str | None = None,
        candidate_id: int | None = None,
    ) -> int:
        decision = decision.upper()
        allowed = {
            "EXCLUDE",
            "DEFER_EPISODE",
            "RESEARCH_INCOMPLETE",
            "SCREEN_DISTORTED",
            "AWAITING_USER",
        }
        if decision not in allowed:
            raise ContractError("invalid candidate decision")
        reason = reason.strip()
        if not reason:
            raise ContractError("candidate decision requires a reason")
        revisit_after = (revisit_after.strip() or None) if revisit_after else None
        revisit_trigger = (revisit_trigger.strip() or None) if revisit_trigger else None
        decided_by = decided_by.strip()
        if not decided_by:
            raise ContractError("candidate decision requires decided_by")
        if decision == "EXCLUDE" and decided_by.lower() != "owner":
            raise ContractError("EXCLUDE requires Owner as the human decision owner")
        if revisit_after:
            try:
                parsed_revisit_after = date.fromisoformat(revisit_after)
            except ValueError as error:
                raise ContractError("revisit_after must be YYYY-MM-DD") from error
            if parsed_revisit_after.isoformat() != revisit_after:
                raise ContractError("revisit_after must be YYYY-MM-DD")
        if decision == "RESEARCH_INCOMPLETE":
            if bool(revisit_after) == bool(revisit_trigger):
                raise ContractError(
                    "RESEARCH_INCOMPLETE requires exactly one of revisit_after or revisit_trigger"
                )
        elif decision == "DEFER_EPISODE":
            if revisit_after and revisit_trigger:
                raise ContractError("DEFER_EPISODE accepts at most one concrete revisit boundary")
        elif revisit_after or revisit_trigger:
            raise ContractError("only RESEARCH_INCOMPLETE or DEFER_EPISODE accepts a revisit boundary")
        if decision == "AWAITING_USER":
            if not isinstance(report_path, str) or not report_path.strip() or not isinstance(reader_text, str) or not reader_text.strip():
                raise ContractError("completed candidate requires report and reader text")
            report = Path(report_path)
            if not report.is_absolute():
                report = Path(__file__).resolve().parents[2] / report
            try:
                if not report.read_bytes().strip():
                    raise ContractError("completed candidate report is empty")
            except OSError as error:
                raise ContractError("completed candidate report is unavailable") from error
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            candidates = connection.execute(
                """SELECT id,stable_identity,symbol,metrics_json,status FROM candidate_inbox
                   WHERE symbol=? AND (? IS NULL OR id=?)
                     AND (? IS NULL OR json_extract(metrics_json,'$.first_entry_month')=?)
                   ORDER BY CASE status WHEN 'OPEN' THEN 0 ELSE 1 END,id DESC""",
                (symbol.upper(), candidate_id, candidate_id, signal_date, signal_date),
            ).fetchall()
            if not candidates:
                raise ContractError("candidate decision requires an OPEN candidate")
            if len(candidates) != 1:
                raise ContractError("ambiguous candidate symbol; use candidate_id")
            candidate = candidates[0]
            episode = str(json.loads(str(candidate['metrics_json']))['first_entry_month'])
            values = (decision, reason, report_path, reader_text, revisit_after, revisit_trigger, decided_by)
            previous = connection.execute(
                """SELECT id,decision,reason,report_path,reader_text,revisit_after,revisit_trigger,decided_by
                   FROM candidate_decisions WHERE stable_identity=? AND signal_date=? ORDER BY id DESC LIMIT 1""",
                (candidate['stable_identity'], episode),
            ).fetchone()
            revisited_id = json.loads(candidate['metrics_json']).get('research_revisit_decision_id')
            if previous is not None and tuple(previous)[1:] == values and revisited_id != previous['id']:
                return int(previous['id'])
            if candidate['status'] != 'OPEN':
                raise ContractError("candidate decision requires an OPEN candidate")
            cursor = connection.execute(
                """INSERT INTO candidate_decisions(
                       stable_identity,symbol,decision,reason,signal_date,report_path,
                       reader_text,revisit_after,revisit_trigger,decided_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    candidate["stable_identity"], candidate["symbol"], decision, reason,
                    episode, report_path, reader_text, revisit_after, revisit_trigger,
                    decided_by,
                ),
            )
            if decision in {"EXCLUDE", "DEFER_EPISODE", "SCREEN_DISTORTED"}:
                connection.execute(
                    "UPDATE candidate_inbox SET status='ARCHIVED',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (candidate["id"],),
                )
            decision_id = cursor.lastrowid
            if decision_id is None:
                raise RuntimeError("candidate decision insert returned no id")
            return int(decision_id)

    def show_candidate(self, symbol: str | None = None, *, candidate_id: int | None = None) -> dict[str, object]:
        if (symbol is None) == (candidate_id is None):
            raise ContractError("provide exactly one of symbol or candidate_id")
        with self.connect() as connection:
            candidates = connection.execute(
                """SELECT id, stable_identity, symbol, name, kind, region, mic, status,
                          first_seen_cycle_id, last_seen_cycle_id, lane, metrics_json,
                          case_id, created_at, updated_at
                   FROM candidate_inbox
                   WHERE (? IS NOT NULL AND id=?) OR (? IS NOT NULL AND symbol=?)
                   ORDER BY id DESC""",
                (candidate_id, candidate_id, symbol, symbol.upper() if symbol is not None else None),
            ).fetchall()
            if not candidates:
                raise ContractError("unknown candidate")
            if len(candidates) != 1:
                raise ContractError("ambiguous candidate symbol; use candidate_id")
            candidate = candidates[0]
            result = dict(candidate)
            result["metrics"] = json.loads(str(result.pop("metrics_json")))
            decision = connection.execute(
                """SELECT id, decision, reason, signal_date, report_path, reader_text,
                          revisit_after, revisit_trigger, decided_by, created_at, notified_at
                   FROM candidate_decisions
                   WHERE stable_identity = ? AND signal_date = ?
                   ORDER BY id DESC LIMIT 1""",
                (candidate["stable_identity"], result["metrics"].get("first_entry_month")),
            ).fetchone()
            result["latest_decision"] = dict(decision) if decision is not None else None
            result["research_history"] = [dict(row) for row in connection.execute(
                "SELECT * FROM candidate_decisions WHERE stable_identity=? ORDER BY id DESC",
                (candidate['stable_identity'],))]
            return result

    def preview_position(self, payload: dict[str, object]) -> dict[str, object]:
        normalized = validate_position_payload(payload)
        linked_case_symbol = normalized["linked_case_symbol"]
        linked_case_id = None
        if linked_case_symbol:
            try:
                connection = sqlite3.connect(
                    f"{self.path.resolve().as_uri()}?mode=ro", uri=True
                )
            except sqlite3.OperationalError as error:
                raise ContractError("dry-run database is not available for linked case lookup") from error
            connection.row_factory = sqlite3.Row
            try:
                case = _case_by_symbol(connection, str(linked_case_symbol))
                _validate_position_case_link(connection, case, normalized)
            except sqlite3.OperationalError as error:
                raise ContractError("dry-run database has no Radar schema") from error
            finally:
                connection.close()
            if case is None:
                raise ContractError("linked_case_symbol does not identify an existing Radar case")
            linked_case_id = int(case["id"])
        return {
            "status": "ACTIVE",
            "linked_case_id": linked_case_id,
            "baseline_version": 1,
            **normalized,
        }

    def import_position(
        self,
        payload: dict[str, object],
        *,
        confirmed_by: str,
    ) -> int:
        if confirmed_by.strip().lower() != "owner":
            raise ContractError("position import requires --confirmed-by owner")
        normalized = validate_position_payload(payload)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT 1 FROM positions WHERE symbol = ? AND status = 'ACTIVE'",
                (normalized["symbol"],),
            ).fetchone()
            if existing is not None:
                raise ContractError("an ACTIVE position already exists for this symbol")
            linked_case_id = None
            if normalized["linked_case_symbol"]:
                case = _case_by_symbol(connection, str(normalized["linked_case_symbol"]))
                _validate_position_case_link(connection, case, normalized)
                if case is None:
                    raise ContractError("linked_case_symbol does not identify an existing Radar case")
                linked_case_id = int(case["id"])
            cursor = connection.execute(
                """INSERT INTO positions(
                       symbol,name,kind,currency,status,case_id,purchase_date,
                       purchase_date_is_approximate,average_price,quantity,invested_amount)
                   VALUES (?,?,?,?,'ACTIVE',?,?,?,?,?,?)""",
                (
                    normalized["symbol"], normalized["name"], normalized["kind"],
                    normalized["currency"], linked_case_id, normalized["purchase_date"] or "",
                    int(bool(normalized["purchase_date_is_approximate"])),
                    normalized["average_price"], normalized["quantity"],
                    normalized["invested_amount"],
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("position insert returned no id")
            position_id = int(cursor.lastrowid)
            connection.execute(
                """INSERT INTO position_baselines(
                       position_id,version,payload_json,change_reason,confirmed_by,effective_on)
                   VALUES (?,1,?,'initial confirmed baseline',?,?)""",
                (
                    position_id,
                    json.dumps(normalized, ensure_ascii=False, sort_keys=True, allow_nan=False),
                    confirmed_by.strip(), normalized["baseline_as_of"],
                ),
            )
            return position_id

    def revise_position_baseline(self, symbol: str, payload: dict[str, object], *, confirmed_by: str) -> int:
        from .positions import _strict_date, _required_text
        from .position_review import _identifier
        if confirmed_by != "owner":
            raise ContractError("baseline revision requires --confirmed-by owner")
        position_id = _identifier(payload, "position_id")
        predecessor = _identifier(payload, "predecessor_baseline_id")
        effective = _strict_date(payload, "effective_on")
        reason = _required_text(payload, "change_reason")
        changes = payload.get("baseline")
        allowed = {"objective", "horizon", "exit_strategy", "benchmark_symbol", "provenance", "investment_role", "investment_frame"}
        if not isinstance(changes, dict) or not changes or set(changes) - allowed:
            raise ContractError("baseline revision accepts strategy fields only, never holdings")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            position = connection.execute("SELECT * FROM positions WHERE id=? AND symbol=? AND status='ACTIVE'", (position_id, symbol.strip().upper())).fetchone()
            previous = connection.execute("SELECT * FROM position_baselines WHERE position_id=? ORDER BY version DESC LIMIT 1", (position_id,)).fetchone()
            if position is None or previous is None or previous["id"] != predecessor:
                raise ContractError("baseline revision requires the current predecessor of this ACTIVE episode")
            prior = json.loads(previous["payload_json"])
            prior_effective = previous["effective_on"] or prior.get("baseline_as_of")
            if effective > date.today().isoformat() or (prior_effective and effective < prior_effective):
                raise ContractError("baseline effective date contradicts the known baseline chronology")
            revised = validate_position_payload({**prior, **changes, "baseline_as_of": effective})
            cursor = connection.execute("""INSERT INTO position_baselines(position_id,version,payload_json,change_reason,confirmed_by,predecessor_baseline_id,effective_on)
                VALUES (?,?,?,?,?,?,?)""", (position_id, previous["version"] + 1, json.dumps(revised, ensure_ascii=False, sort_keys=True, allow_nan=False), reason, confirmed_by, predecessor, effective))
            return int(cursor.lastrowid)

    def list_positions(self) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT p.id,p.symbol,p.name,p.kind,p.currency,p.status,p.case_id,
                          NULLIF(p.purchase_date,'') purchase_date,
                          p.average_price,p.quantity,p.invested_amount,
                          p.purchase_date_is_approximate,
                          p.created_at,p.closed_at,
                          json_extract(pb.payload_json,'$.objective') objective,
                          json_extract(pb.payload_json,'$.horizon') horizon,
                          json_extract(pb.payload_json,'$.exit_strategy') exit_strategy,
                          json_extract(pb.payload_json,'$.benchmark_symbol') benchmark_symbol,
                          pb.id baseline_id,pb.version baseline_version,
                          pb.effective_on,pb.predecessor_baseline_id,
                          json_extract(pb.payload_json,'$.investment_role') investment_role,
                          json_extract(pb.payload_json,'$.investment_frame') investment_frame,
                          json_extract(pb.payload_json,'$.baseline_as_of') baseline_as_of
                   FROM positions p
                   JOIN position_baselines pb ON pb.position_id=p.id
                   WHERE pb.version=(
                       SELECT MAX(pb2.version) FROM position_baselines pb2
                       WHERE pb2.position_id=p.id
                   )
                   ORDER BY CASE p.status WHEN 'ACTIVE' THEN 0 ELSE 1 END,p.symbol,p.id"""
            ).fetchall()
            result = [dict(row) for row in rows]
            for position in result:
                if position["status"] == "CLOSED":
                    position["quantity"] = 0.0
                position["purchase_date_is_approximate"] = bool(
                    position["purchase_date_is_approximate"]
                )
            return result

    def show_position(self, symbol: str) -> dict[str, object]:
        with self.connect() as connection:
            position = connection.execute(
                """SELECT * FROM positions WHERE symbol=?
                   ORDER BY CASE status WHEN 'ACTIVE' THEN 0 ELSE 1 END,id DESC LIMIT 1""",
                (symbol.upper(),),
            ).fetchone()
            if position is None:
                raise ContractError("unknown position")
            baselines = connection.execute(
                """SELECT id,version,payload_json,change_reason,confirmed_by,created_at,predecessor_baseline_id,effective_on
                   FROM position_baselines WHERE position_id=? ORDER BY version""",
                (position["id"],),
            ).fetchall()
            result = dict(position)
            if result["status"] == "CLOSED":
                result["quantity"] = 0.0
            if result["purchase_date"] == "":
                result["purchase_date"] = None
            result["purchase_date_is_approximate"] = bool(result["purchase_date_is_approximate"])
            result["baselines"] = [
                {
                    **{key: row[key] for key in ("id", "version", "change_reason", "confirmed_by", "created_at", "predecessor_baseline_id", "effective_on")},
                    "payload": json.loads(str(row["payload_json"])),
                }
                for row in baselines
            ]
            result["reviews"] = [
                dict(row) for row in connection.execute(
                    "SELECT * FROM position_reviews WHERE position_id=? ORDER BY review_date,id",
                    (position["id"],),
                ).fetchall()
            ]
            result["events"] = [
                dict(row) for row in connection.execute(
                    "SELECT * FROM position_events WHERE position_id=? ORDER BY event_date,id",
                    (position["id"],),
                ).fetchall()
            ]
            return result

    def monthly_position_review_status(self, period: str) -> dict[str, object]:
        try:
            parsed = date.fromisoformat(f"{period}-01")
        except ValueError as error:
            raise ContractError("period must be YYYY-MM") from error
        if parsed.strftime("%Y-%m") != period:
            raise ContractError("period must be YYYY-MM")
        with self.connect() as connection:
            active = [
                str(row["symbol"])
                for row in connection.execute(
                    "SELECT symbol FROM positions WHERE status='ACTIVE' ORDER BY id"
                ).fetchall()
            ]
            reviewed = {
                str(row["symbol"])
                for row in connection.execute(
                    """SELECT DISTINCT p.symbol
                       FROM positions p
                       JOIN position_reviews pr ON pr.position_id=p.id
                       WHERE p.status='ACTIVE' AND substr(pr.review_date,1,7)=?
                         AND pr.baseline_id=(SELECT id FROM position_baselines WHERE position_id=p.id ORDER BY version DESC LIMIT 1)
                         AND NOT EXISTS (SELECT 1 FROM position_reviews child WHERE child.supersedes_review_id=pr.id)
                         AND 1=(SELECT COUNT(*) FROM position_reviews leaf WHERE leaf.position_id=p.id
                            AND substr(leaf.review_date,1,7)=substr(pr.review_date,1,7)
                            AND NOT EXISTS (SELECT 1 FROM position_reviews child WHERE child.supersedes_review_id=leaf.id))""",
                    (period,),
                ).fetchall()
            }
        return {
            "period": period,
            "active_symbols": active,
            "reviewed_symbols": [symbol for symbol in active if symbol in reviewed],
            "missing_symbols": [symbol for symbol in active if symbol not in reviewed],
            "complete": bool(active) and all(symbol in reviewed for symbol in active),
        }

    def record_position_review(self, symbol: str, payload: dict[str, object]) -> int:
        review = validate_position_review(payload)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            position = connection.execute(
                "SELECT id,status FROM positions WHERE id=? AND symbol=?",
                (review["position_id"], symbol.strip().upper()),
            ).fetchone()
            if position is None or position["status"] != "ACTIVE":
                raise ContractError("position review requires the specified ACTIVE episode")
            baseline = connection.execute(
                "SELECT * FROM position_baselines WHERE id=? AND position_id=?",
                (review["baseline_id"], position["id"]),
            ).fetchone()
            if baseline is None:
                raise ContractError("baseline_id must identify the baseline actually reviewed in this episode")
            effective = baseline["effective_on"] or json.loads(baseline["payload_json"]).get("baseline_as_of")
            if review["review_date"] > date.today().isoformat() or (effective and review["review_date"] < effective):
                raise ContractError("review date precedes its baseline or lies in the future")
            period = review["review_date"][:7]
            leaves = connection.execute("""SELECT * FROM position_reviews pr
                WHERE position_id=? AND substr(review_date,1,7)=?
                AND NOT EXISTS (SELECT 1 FROM position_reviews child WHERE child.supersedes_review_id=pr.id)""",
                (position["id"], period)).fetchall()
            predecessor = review["supersedes_review_id"]
            if leaves:
                if len(leaves) != 1 or predecessor != leaves[0]["id"] or not review["correction_reason"]:
                    raise ContractError("monthly correction must explicitly supersede the unique current review with a reason; ambiguous legacy months require clarification")
                if review["review_date"] < leaves[0]["review_date"]:
                    raise ContractError("correction review_date cannot precede its predecessor")
            elif predecessor is not None or review["correction_reason"] is not None:
                raise ContractError("first monthly review cannot supersede another period or episode")
            cursor = connection.execute(
                """INSERT INTO position_reviews(
                       position_id,review_date,recommendation,summary,
                       strongest_counterevidence,report_path,missing_decision_fact,
                       next_check_on,reviewer,baseline_id,supersedes_review_id,correction_reason)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (position["id"], review["review_date"], review["recommendation"],
                 review["summary"], review["strongest_counterevidence"],
                 review["report_path"], review["missing_decision_fact"],
                 review["next_check_on"], review["reviewer"], review["baseline_id"],
                 predecessor, review["correction_reason"]),
            )
            return int(cursor.lastrowid)

    def confirm_position_event(
        self,
        symbol: str,
        payload: dict[str, object],
        *,
        confirmed_by: str,
    ) -> int:
        if confirmed_by != "owner":
            raise ContractError("position event requires --confirmed-by owner")
        event = validate_position_event(payload)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            position = connection.execute(
                "SELECT * FROM positions WHERE id=? AND symbol=?",
                (event["position_id"], symbol.strip().upper()),
            ).fetchone()
            if position is None:
                raise ContractError("unknown position episode for this symbol")
            serialized = json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False)
            existing = connection.execute(
                "SELECT id,payload_json FROM position_events WHERE position_id=? AND execution_reference=?",
                (position["id"], event["execution_reference"]),
            ).fetchone()
            if existing is not None:
                if existing["payload_json"] != serialized:
                    raise ContractError("execution reference already exists with a conflicting payload")
                return int(existing["id"])
            if position["status"] != "ACTIVE":
                raise ContractError("new position event requires an ACTIVE position")
            if event["event_date"] > date.today().isoformat():
                raise ContractError("execution event cannot be in the future")
            purchase = position["purchase_date"]
            # Approximate dates do not establish an exact lower bound. A sale
            # inside/before that uncertainty cannot silently mutate holdings.
            if purchase and (event["event_date"] < purchase or
                             (position["purchase_date_is_approximate"] and event["event_date"] <= purchase)):
                raise ContractError("event contradicts or cannot be ordered against the known purchase date; clarify history first")
            initial = connection.execute("SELECT payload_json FROM position_baselines WHERE position_id=? ORDER BY version LIMIT 1", (position["id"],)).fetchone()
            known_as_of = json.loads(initial["payload_json"]).get("baseline_as_of") if initial else None
            if known_as_of and event["event_date"] <= known_as_of:
                raise ContractError("event is not unambiguously after the confirmed holdings snapshot; historical correction must be clarified before mutation")
            previous = connection.execute(
                "SELECT event_date FROM position_events WHERE position_id=? ORDER BY event_date DESC,id DESC LIMIT 1",
                (position["id"],),
            ).fetchone()
            if previous is not None and event["event_date"] <= previous["event_date"]:
                raise ContractError("backdated or same-day unordered event requires explicit historical clarification, not a silent holdings mutation")
            quantity_before = float(position["quantity"])
            if event["action"] == "TRIM":
                quantity_change = float(event["quantity"])
                if quantity_change >= quantity_before:
                    raise ContractError("TRIM quantity must be less than the active quantity")
                quantity_after = quantity_before - quantity_change
                connection.execute(
                    "UPDATE positions SET quantity=? WHERE id=?",
                    (quantity_after, position["id"]),
                )
            else:
                quantity_change = quantity_before
                quantity_after = 0.0
                connection.execute(
                    "UPDATE positions SET status='CLOSED',closed_at=? WHERE id=?",
                    (event["event_date"], position["id"]),
                )
            cursor = connection.execute(
                """INSERT INTO position_events(
                       position_id,action,event_date,quantity_before,quantity_change,
                       quantity_after,price,reason,confirmed_by,execution_reference,payload_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    position["id"], event["action"], event["event_date"],
                    quantity_before, quantity_change, quantity_after, event["price"],
                    event["reason"], confirmed_by, event["execution_reference"], serialized,
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("position event insert returned no id")
            return int(cursor.lastrowid)

    def record_snapshot(self, case_id: int, snapshot: MarketSnapshot) -> int:
        canonical_snapshot(snapshot.__dict__)
        with self.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO market_snapshots(
                       case_id, symbol, role, price, price_date, retrieved_at,
                       currency, provider, semantics
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    case_id,
                    snapshot.symbol.upper(),
                    snapshot.role,
                    snapshot.price,
                    snapshot.price_date,
                    snapshot.retrieved_at,
                    snapshot.currency,
                    snapshot.provider,
                    snapshot.semantics,
                ),
            )
            return int(cursor.lastrowid)

    def record_outcome(
        self,
        case_id: int,
        case_snapshot: MarketSnapshot,
        spy_snapshot: MarketSnapshot,
        sector_snapshot: MarketSnapshot,
    ) -> int:
        with self.connect() as connection:
            case = connection.execute(
                "SELECT symbol, sector_symbol, status FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
            if case is None:
                raise ContractError("unknown case")
            snapshots = {"case": case_snapshot, "spy": spy_snapshot, "sector": sector_snapshot}
            expected = {key: dict(snapshot.__dict__, role='case' if key == 'case' else snapshot.role)
                        for key, snapshot in snapshots.items()}
            if case_snapshot.role != "outcome":
                raise ContractError("outcome case snapshot must use outcome role")
            _validate_snapshot_binding(case["symbol"], case["sector_symbol"], expected)
            compare_price_sets(bound_snapshots(connection, case_id),
                               {key: snapshot.__dict__ for key, snapshot in snapshots.items()})
            ids = {}
            for key, snapshot in snapshots.items():
                cursor = connection.execute(
                    """INSERT INTO market_snapshots(
                           case_id, symbol, role, price, price_date, retrieved_at,
                           currency, provider, semantics
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        case_id, snapshot.symbol.upper(), snapshot.role, snapshot.price,
                        snapshot.price_date, snapshot.retrieved_at, snapshot.currency,
                        snapshot.provider, snapshot.semantics,
                    ),
                )
                ids[key] = int(cursor.lastrowid)
            cursor = connection.execute(
                """INSERT INTO outcome_checks(
                       case_id, decision_status, case_snapshot_id, spy_snapshot_id, sector_snapshot_id
                   ) VALUES (?, ?, ?, ?, ?)""",
                (case_id, case["status"], ids["case"], ids["spy"], ids["sector"]),
            )
            return int(cursor.lastrowid)

    def freeze_review(
        self,
        case_id: int,
        payload: dict[str, object],
        *,
        source_urls: list[str] | None = None,
        snapshot_ids: dict[str, int] | None = None,
        immediate_investable: bool | None = None,
    ) -> int:
        with self.connect() as connection:
            case = connection.execute(
                "SELECT kind, symbol, sector_symbol FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
            if case is None:
                raise ContractError("unknown case")
            validate_review(case["kind"], payload)
            version = int(
                connection.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 FROM reviews WHERE case_id = ?",
                    (case_id,),
                ).fetchone()[0]
            )
            if version == 1:
                if not source_urls:
                    raise ContractError("first review requires point-in-time sources")
                if snapshot_ids is None or set(snapshot_ids) != {"case", "spy", "sector"}:
                    raise ContractError("first review requires case, SPY and sector snapshots")
                if immediate_investable is None:
                    raise ContractError("first review requires immediate-investable judgment")
                bound = {}
                for key, snapshot_id in snapshot_ids.items():
                    row = connection.execute(
                        "SELECT * FROM market_snapshots WHERE id = ? AND case_id = ?",
                        (snapshot_id, case_id),
                    ).fetchone()
                    if row is None:
                        raise ContractError("snapshot binding references an unknown snapshot")
                    bound[key] = dict(row)
                _validate_snapshot_binding(case["symbol"], case["sector_symbol"], bound)
            cursor = connection.execute(
                "INSERT INTO reviews(case_id, version, payload_json) VALUES (?, ?, ?)",
                (case_id, version, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
            )
            review_id = int(cursor.lastrowid)
            for url in source_urls or []:
                connection.execute("INSERT INTO sources(review_id, url) VALUES (?, ?)", (review_id, url))
            if version == 1 and snapshot_ids is not None:
                rows = {}
                for role, snapshot_id in snapshot_ids.items():
                    row = connection.execute(
                        "SELECT id, role FROM market_snapshots WHERE id = ? AND case_id = ?",
                        (snapshot_id, case_id),
                    ).fetchone()
                    if row is None or row["role"] != ("benchmark" if role == "spy" else role):
                        raise ContractError(f"invalid {role} snapshot")
                    rows[role] = snapshot_id
                connection.execute(
                    """INSERT INTO shadow_entries(
                           case_id, review_id, case_snapshot_id, spy_snapshot_id,
                           sector_snapshot_id, immediate_investable
                       ) VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        case_id,
                        review_id,
                        rows["case"],
                        rows["spy"],
                        rows["sector"],
                        int(bool(immediate_investable)),
                    ),
                )
            return review_id

    def add_watch_condition(self, case_id: int, kind: str, description: str) -> int:
        if kind not in {"price", "event", "operating", "regime", "structure", "reaction"}:
            raise ContractError("invalid watch-condition kind")
        if not description.strip():
            raise ContractError("watch condition requires a description")
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO watch_conditions(case_id, kind, description) VALUES (?, ?, ?)",
                (case_id, kind, description.strip()),
            )
            return int(cursor.lastrowid)

    def get_case(self, case_id: int) -> dict[str, object]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
            if row is None:
                raise ContractError("unknown case")
            return dict(row)

    def get_case_by_symbol(self, symbol: str) -> dict[str, object]:
        with self.connect() as connection:
            row = _case_by_symbol(connection, symbol)
            if row is None:
                raise ContractError("unknown case")
            return dict(row)

    def list_cases(self) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, symbol, name, kind, sector_symbol, status, created_at
                   FROM cases
                   ORDER BY CASE status
                       WHEN 'READY' THEN 0 WHEN 'WATCH' THEN 1 WHEN 'INBOX' THEN 2
                       WHEN 'INVALIDATED' THEN 3 ELSE 4 END, symbol"""
            ).fetchall()
            return [dict(row) for row in rows]

    def set_watchdog_rule(
        self,
        case_id: int,
        *,
        min_days: int = 90,
        min_relative_spy_pp: float = 0.0,
        min_relative_sector_pp: float = 0.0,
        max_price: float | None = None,
        max_source_age_days: int = 60,
    ) -> None:
        if min_days < 0 or max_source_age_days < 1 or (max_price is not None and max_price <= 0):
            raise ContractError("invalid watchdog rule")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO watchdog_rules(
                       case_id, min_days, min_relative_spy_pp, min_relative_sector_pp,
                       max_price, max_source_age_days
                   ) VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(case_id) DO UPDATE SET
                       min_days=excluded.min_days,
                       min_relative_spy_pp=excluded.min_relative_spy_pp,
                       min_relative_sector_pp=excluded.min_relative_sector_pp,
                       max_price=excluded.max_price,
                       max_source_age_days=excluded.max_source_age_days""",
                (case_id, min_days, min_relative_spy_pp, min_relative_sector_pp, max_price, max_source_age_days),
            )

    def get_mail_receipt(self, delivery_key: str) -> dict[str, object] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM mail_receipts WHERE delivery_key = ?", (delivery_key,)).fetchone()
            return dict(row) if row is not None else None

    def record_mail_receipt(
        self, delivery_key: str, subject: str, recipient: str, sent_message_id: str,
        body_sha256: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO mail_receipts(delivery_key, subject, recipient, sent_message_id, body_sha256)
                   VALUES (?, ?, ?, ?, ?) ON CONFLICT(delivery_key) DO NOTHING""",
                (delivery_key, subject, recipient, sent_message_id, body_sha256),
            )

    def mark_watchdog_events_delivered(self, event_ids: list[int]) -> None:
        if not event_ids:
            return
        placeholders = ",".join("?" for _ in event_ids)
        with self.connect() as connection:
            connection.execute(
                f"UPDATE watchdog_events SET delivered_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                event_ids,
            )

    def get_open_conditions(self, case_id: int) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, kind, description FROM watch_conditions
                   WHERE case_id = ? AND status = 'OPEN' ORDER BY id""",
                (case_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_shadow_entry(self, case_id: int) -> dict[str, object] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT se.review_id, c.price AS case_price, s.price AS spy_price,
                          x.price AS sector_price, c.price_date,
                          se.immediate_investable
                   FROM shadow_entries se
                   JOIN market_snapshots c ON c.id = se.case_snapshot_id
                   JOIN market_snapshots s ON s.id = se.spy_snapshot_id
                   JOIN market_snapshots x ON x.id = se.sector_snapshot_id
                   WHERE se.case_id = ?""",
                (case_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "review_id": row["review_id"],
                "case_price": row["case_price"],
                "spy_price": row["spy_price"],
                "sector_price": row["sector_price"],
                "price_date": row["price_date"],
                "immediate_investable": bool(row["immediate_investable"]),
            }

    def mark_ready(
        self,
        case_id: int,
        condition_id: int,
        *,
        condition_evidence: str,
        reason: str,
        case_snapshot: MarketSnapshot,
        spy_snapshot: MarketSnapshot,
        sector_snapshot: MarketSnapshot,
    ) -> None:
        if not condition_evidence.strip() or not reason.strip():
            raise ContractError("READY requires condition evidence and a reason")
        if case_snapshot.role != "ready":
            raise ContractError("READY case snapshot must use ready role")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            case = connection.execute(
                "SELECT symbol, sector_symbol, status FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
            if case is None:
                raise ContractError("unknown case")
            if case["status"] != "WATCH":
                raise ContractError("READY requires a WATCH case")
            condition = connection.execute(
                """SELECT id FROM watch_conditions
                   WHERE id = ? AND case_id = ? AND status = 'OPEN'""",
                (condition_id, case_id),
            ).fetchone()
            open_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM watch_conditions WHERE case_id = ? AND status = 'OPEN'",
                    (case_id,),
                ).fetchone()[0]
            )
            if condition is None or open_count != 1:
                raise ContractError("READY requires exactly one open watch condition")
            ready_count = int(
                connection.execute("SELECT COUNT(*) FROM cases WHERE status = 'READY'").fetchone()[0]
            )
            if ready_count >= 3:
                raise ContractError("READY capacity of three reached")
            _validate_snapshot_binding(
                case["symbol"],
                case["sector_symbol"],
                {
                    "case": dict(case_snapshot.__dict__, role='case'),
                    "spy": dict(spy_snapshot.__dict__),
                    "sector": dict(sector_snapshot.__dict__),
                },
            )
            snapshots = {'case': case_snapshot, 'spy': spy_snapshot, 'sector': sector_snapshot}
            compare_price_sets(bound_snapshots(connection, case_id),
                               {key: snapshot.__dict__ for key, snapshot in snapshots.items()})
            ready_ids = {}
            for key, snapshot in snapshots.items():
                cursor = connection.execute(
                    """INSERT INTO market_snapshots(
                           case_id, symbol, role, price, price_date, retrieved_at,
                           currency, provider, semantics
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        case_id, snapshot.symbol.upper(), snapshot.role, snapshot.price,
                        snapshot.price_date, snapshot.retrieved_at, snapshot.currency,
                        snapshot.provider, snapshot.semantics,
                    ),
                )
                ready_ids[key] = int(cursor.lastrowid)
            connection.execute(
                'INSERT INTO ready_snapshot_sets(case_id,case_snapshot_id,spy_snapshot_id,sector_snapshot_id) VALUES (?,?,?,?)',
                (case_id, ready_ids['case'], ready_ids['spy'], ready_ids['sector']),
            )
            connection.execute(
                """UPDATE watch_conditions
                   SET status = 'FULFILLED', fulfilled_reason = ? WHERE id = ?""",
                (condition_evidence.strip(), condition_id),
            )
            connection.execute("UPDATE cases SET status = 'READY' WHERE id = ?", (case_id,))
            connection.execute(
                """INSERT INTO transitions(case_id, from_status, to_status, reason)
                   VALUES (?, 'WATCH', 'READY', ?)""",
                (case_id, reason.strip()),
            )

    def transition(self, case_id: int, target: str, reason: str, *, priority_confirmed_by: str | None = None) -> None:
        target = target.upper()
        if not reason.strip():
            raise ContractError("transition requires a reason")
        if target == "READY":
            raise ContractError("READY must use the atomic mark_ready path")
        allowed = {
            "INBOX": {"WATCH", "INVALIDATED", "ARCHIVED"},
            "WATCH": {"INVALIDATED", "ARCHIVED"},
            "READY": {"WATCH", "INVALIDATED", "ARCHIVED"},
            "INVALIDATED": {"ARCHIVED"},
            "ARCHIVED": set(),
        }
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            case = connection.execute("SELECT status FROM cases WHERE id = ?", (case_id,)).fetchone()
            if case is None:
                raise ContractError("unknown case")
            priority_return = priority_confirmed_by is not None
            if priority_return:
                if priority_confirmed_by != "owner" or case["status"] != "READY" or target != "WATCH":
                    raise ContractError("priority return requires Owner-confirmed READY -> WATCH")
                reason = "Priorität zurückgestellt (Owner): " + reason.strip()
            if target not in allowed[case["status"]]:
                raise ContractError(f"transition {case['status']} -> {target} is not allowed")
            if target == "WATCH":
                review = connection.execute("SELECT 1 FROM reviews WHERE case_id = ? LIMIT 1", (case_id,)).fetchone()
                if review is None:
                    raise ContractError("WATCH requires a frozen review")
                condition = connection.execute(
                    "SELECT 1 FROM watch_conditions WHERE case_id = ? AND status = 'OPEN' LIMIT 1",
                    (case_id,),
                ).fetchone()
                if condition is None and not priority_return:
                    raise ContractError("WATCH requires an open condition")
            if target == "WATCH" and case["status"] not in {"WATCH", "READY"}:
                active = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM cases WHERE status IN ('WATCH', 'READY')"
                    ).fetchone()[0]
                )
                if active >= 8:
                    raise ContractError("active capacity of eight reached")
            connection.execute("UPDATE cases SET status = ? WHERE id = ?", (target, case_id))
            connection.execute(
                "INSERT INTO transitions(case_id, from_status, to_status, reason) VALUES (?, ?, ?, ?)",
                (case_id, case["status"], target, reason.strip()),
            )
