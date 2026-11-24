from __future__ import annotations

import argparse
import json

from pathlib import Path
from typing import Sequence

from .db import RadarDB
from .evaluate import evaluate_outcomes, evaluate_pre_ready_timing
from .positions import validate_position_payload
from .report import render_change_only, research_history
from .transitions import ContractError

from .watch import mark_ready_live, observe_live, record_outcome_live
from .watchdog import evaluate_watchdog, pending_events


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opportunity-radar")
    subcommands = parser.add_subparsers(dest="command", required=True)

    initialize = subcommands.add_parser("init", help="initialize a local radar database")
    initialize.add_argument("--db", required=True, type=Path)

    import_case = subcommands.add_parser("import-case", help="import one complete point-in-time case")
    import_case.add_argument("--db", required=True, type=Path)
    import_case.add_argument("--input", required=True, type=Path)

    list_command = subcommands.add_parser("list", help="list all cases and states")
    list_command.add_argument("--db", required=True, type=Path)

    invalidate = subcommands.add_parser("invalidate", help="invalidate a case with a dated reason")
    invalidate.add_argument("--db", required=True, type=Path)
    invalidate.add_argument("--symbol", required=True)
    invalidate.add_argument("--reason", required=True)

    archive = subcommands.add_parser("archive", help="archive a finished case")
    archive.add_argument("--db", required=True, type=Path)
    archive.add_argument("--symbol", required=True)
    archive.add_argument("--reason", required=True)

    priority = subcommands.add_parser("deprioritize", help="manually return READY to WATCH for personal priority")
    priority.add_argument("--db", required=True, type=Path)
    priority.add_argument("--symbol", required=True)
    priority.add_argument("--reason", required=True)
    priority.add_argument("--confirmed-by", required=True, choices=("owner",))

    revise = subcommands.add_parser("revise-review", help="append a new review version from JSON")
    revise.add_argument("--db", required=True, type=Path)
    revise.add_argument("--symbol", required=True)
    revise.add_argument("--input", required=True, type=Path)

    observe = subcommands.add_parser("observe-live", help="record a live case/SPY/sector snapshot")
    observe.add_argument("--db", required=True, type=Path)
    observe.add_argument("--symbol", required=True)

    ready = subcommands.add_parser("ready-live", help="fulfill the one open condition and mark READY")
    ready.add_argument("--db", required=True, type=Path)
    ready.add_argument("--symbol", required=True)
    ready.add_argument("--evidence", required=True)
    ready.add_argument("--reason", required=True)

    evaluate = subcommands.add_parser("evaluate", help="compare READY timing with the shadow entry")
    evaluate.add_argument("--db", required=True, type=Path)
    evaluation_case = evaluate.add_mutually_exclusive_group(required=True)
    evaluation_case.add_argument("--symbol")
    evaluation_case.add_argument("--case-id", type=int, help="evaluate one historical case explicitly")

    outcome = subcommands.add_parser("outcome-live", help="record one later case/SPY/sector outcome")
    outcome.add_argument("--db", required=True, type=Path)
    outcome.add_argument("--symbol", required=True)

    outcomes = subcommands.add_parser("outcomes", help="list raw stock/ETF outcome comparisons")
    outcomes.add_argument("--db", required=True, type=Path)

    rule = subcommands.add_parser("watchdog-rule", help="set deterministic watchdog thresholds")
    rule.add_argument("--db", required=True, type=Path)
    rule.add_argument("--symbol", required=True)
    rule.add_argument("--min-days", type=int, default=90)
    rule.add_argument("--min-relative-spy-pp", type=float, default=0.0)
    rule.add_argument("--min-relative-sector-pp", type=float, default=0.0)
    rule.add_argument("--max-price", type=float)
    rule.add_argument("--max-source-age-days", type=int, default=60)

    watchdog = subcommands.add_parser("watchdog-check", help="evaluate changed signals without changing READY")
    watchdog.add_argument("--db", required=True, type=Path)

    render = subcommands.add_parser("render", help="render the change-only reader report")
    render.add_argument("--db", required=True, type=Path)
    render.add_argument("--output", required=True, type=Path)


    promote_candidate = subcommands.add_parser("promote-candidate", help="manually promote one OPEN candidate from JSON")
    promote_candidate.add_argument("--db", required=True, type=Path)
    promote_candidate.add_argument("--candidate-id", required=True, type=int)
    promote_candidate.add_argument("--input", required=True, type=Path)

    next_candidate = subcommands.add_parser("next-candidate", help="return the next OPEN candidate needing research")
    next_candidate.add_argument("--db", required=True, type=Path)
    next_candidate.add_argument("--candidate-id", type=int, help="explicit human revisit of an existing boundary")
    next_candidate.add_argument("--confirmed-by", choices=("owner",))

    history = subcommands.add_parser("research-history", help="list historical decisions and direct local research documents")
    history.add_argument("--db", required=True, type=Path)
    work = subcommands.add_parser("candidate-work", help="save resumable work, not an economic disposition")
    work.add_argument("--db", required=True, type=Path)
    work.add_argument("--candidate-id", required=True, type=int)
    work.add_argument("--signal-date", required=True)
    work.add_argument("--report-path", required=True)
    work.add_argument("--source-as-of", required=True)
    work.add_argument("--resume-from", required=True)

    show_candidate = subcommands.add_parser("show-candidate", help="show a candidate and its latest research decision")
    show_candidate.add_argument("--db", required=True, type=Path)
    candidate_target = show_candidate.add_mutually_exclusive_group(required=True)
    candidate_target.add_argument("--symbol", help="only when exactly one candidate matches")
    candidate_target.add_argument("--candidate-id", type=int, help="exact current or historical candidate")

    candidate_decision = subcommands.add_parser("candidate-decision", help="persist a candidate research decision")
    candidate_decision.add_argument("--db", required=True, type=Path)
    candidate_decision.add_argument("--symbol", required=True)
    candidate_decision.add_argument(
        "--decision",
        required=True,
        choices=(
            "EXCLUDE",
            "DEFER_EPISODE",
            "RESEARCH_INCOMPLETE",
            "SCREEN_DISTORTED",
            "AWAITING_USER",
        ),
    )
    candidate_decision.add_argument("--reason", required=True)
    candidate_decision.add_argument("--report-path")
    candidate_decision.add_argument("--reader-text")
    candidate_decision.add_argument("--revisit-after")
    candidate_decision.add_argument("--revisit-trigger")
    candidate_decision.add_argument("--signal-date", help="bind decision/retry to first_entry_month")
    candidate_decision.add_argument("--candidate-id", type=int, help="bind the exact selected candidate")
    candidate_decision.add_argument("--decided-by", required=True, help="explicit audit actor; not authentication")

    import_position = subcommands.add_parser("import-position", help="preview or import one confirmed owned position")
    import_position.add_argument("--db", required=True, type=Path)
    import_position.add_argument("--input", required=True, type=Path)
    import_mode = import_position.add_mutually_exclusive_group(required=True)
    import_mode.add_argument("--dry-run", action="store_true")
    import_mode.add_argument("--confirmed-by")

    revise_baseline = subcommands.add_parser("revise-position-baseline", help="append a confirmed strategy baseline, never a holdings correction")
    revise_baseline.add_argument("--db", required=True, type=Path)
    revise_baseline.add_argument("--symbol", required=True)
    revise_baseline.add_argument("--input", required=True, type=Path)
    revise_baseline.add_argument("--confirmed-by", required=True)

    list_positions = subcommands.add_parser("list-positions", help="list owned positions")
    list_positions.add_argument("--db", required=True, type=Path)

    show_position = subcommands.add_parser("show-position", help="show one owned position and its baselines")
    show_position.add_argument("--db", required=True, type=Path)
    show_position.add_argument("--symbol", required=True)

    monthly_position_review_status = subcommands.add_parser(
        "monthly-position-review-status",
        help="show whether every active position has a review in one calendar month",
    )
    monthly_position_review_status.add_argument("--db", required=True, type=Path)
    monthly_position_review_status.add_argument("--period", required=True)

    monthly_context = subcommands.add_parser("monthly-position-review-context", help="read the exact completed monthly brief basis")
    monthly_context.add_argument("--db", required=True, type=Path)
    monthly_context.add_argument("--period", required=True)

    record_position_review = subcommands.add_parser(
        "record-position-review", help="append one review recommendation without changing holdings"
    )
    record_position_review.add_argument("--db", required=True, type=Path)
    record_position_review.add_argument("--symbol", required=True)
    record_position_review.add_argument("--input", required=True, type=Path)

    confirm_position_event = subcommands.add_parser(
        "confirm-position-event", help="record a Owner-confirmed TRIM or EXIT"
    )
    confirm_position_event.add_argument("--db", required=True, type=Path)
    confirm_position_event.add_argument("--symbol", required=True)
    confirm_position_event.add_argument("--input", required=True, type=Path)
    confirm_position_event.add_argument("--confirmed-by", required=True)

    return parser


def import_case_payload(radar: RadarDB, payload: dict[str, object]) -> int:
    return radar.import_case(payload)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    radar = RadarDB(args.db)
    if args.command == "init":
        radar.initialize()
        print(str(args.db))
        return 0
    if args.command == "import-case":
        radar.initialize()
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        print(import_case_payload(radar, payload))
        return 0
    if args.command == "list":
        radar.initialize()
        print(json.dumps(radar.list_cases(), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "invalidate":
        radar.initialize()
        case = radar.get_case_by_symbol(args.symbol)
        radar.transition(int(case["id"]), "INVALIDATED", args.reason)
        print(args.symbol.upper())
        return 0
    if args.command == "archive":
        radar.initialize()
        case = radar.get_case_by_symbol(args.symbol)
        radar.transition(int(case["id"]), "ARCHIVED", args.reason)
        print(args.symbol.upper())
        return 0
    if args.command == "deprioritize":
        radar.initialize()
        case = radar.get_case_by_symbol(args.symbol)
        radar.transition(int(str(case["id"])), "WATCH", args.reason, priority_confirmed_by=args.confirmed_by)
        print(args.symbol.upper())
        return 0
    if args.command == "revise-review":
        radar.initialize()
        case = radar.get_case_by_symbol(args.symbol)
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        review = payload["review"]
        sources = payload.get("sources", [])
        print(radar.freeze_review(int(case["id"]), review, source_urls=sources))
        return 0
    if args.command == "observe-live":
        radar.initialize()
        print(json.dumps(observe_live(radar, args.symbol), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "ready-live":
        radar.initialize()
        result = mark_ready_live(
            radar,
            args.symbol,
            condition_evidence=args.evidence,
            reason=args.reason,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "evaluate":
        radar.initialize()
        case = radar.get_case(args.case_id) if args.case_id is not None else radar.get_case_by_symbol(args.symbol)
        print(json.dumps(evaluate_pre_ready_timing(radar, int(case["id"])), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "outcome-live":
        radar.initialize()
        print(json.dumps(record_outcome_live(radar, args.symbol), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "outcomes":
        radar.initialize()
        print(json.dumps(evaluate_outcomes(radar), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "watchdog-rule":
        radar.initialize()
        case = radar.get_case_by_symbol(args.symbol)
        radar.set_watchdog_rule(
            int(case["id"]),
            min_days=args.min_days,
            min_relative_spy_pp=args.min_relative_spy_pp,
            min_relative_sector_pp=args.min_relative_sector_pp,
            max_price=args.max_price,
            max_source_age_days=args.max_source_age_days,
        )
        print(args.symbol.upper())
        return 0
    if args.command == "watchdog-check":
        radar.initialize()
        evaluate_watchdog(radar)
        print(json.dumps(pending_events(radar), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "render":
        radar.initialize()
        body = render_change_only(radar, args.output)
        print("UNCHANGED" if body is None else str(args.output))
        return 0

    if args.command == "promote-candidate":
        radar.initialize()
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        print(radar.promote_candidate(args.candidate_id, payload))
        return 0
    if args.command == "next-candidate":
        radar.initialize()
        candidate = radar.next_research_candidate(candidate_id=args.candidate_id, confirmed_by=args.confirmed_by)
        print("NONE" if candidate is None else json.dumps(candidate, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "research-history":
        print(json.dumps(research_history(radar, include_reports=True),ensure_ascii=False,sort_keys=True))
        return 0
    if args.command == "candidate-work":
        radar.save_candidate_work(args.candidate_id,signal_date=args.signal_date,
            report_path=args.report_path,source_as_of=args.source_as_of,resume_from=args.resume_from)
        print(args.candidate_id)
        return 0
    if args.command == "show-candidate":
        radar.initialize()
        print(json.dumps(radar.show_candidate(args.symbol, candidate_id=args.candidate_id), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "candidate-decision":
        radar.initialize()
        print(
            radar.record_candidate_decision(
                args.symbol,
                args.decision,
                args.reason,
                report_path=args.report_path,
                reader_text=args.reader_text,
                revisit_after=args.revisit_after,
                revisit_trigger=args.revisit_trigger,
                decided_by=args.decided_by,
                signal_date=args.signal_date,
                candidate_id=args.candidate_id,
            )
        )
        return 0
    if args.command == "import-position":
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        normalized = validate_position_payload(payload)
        if args.dry_run:
            preview = radar.preview_position(payload)
            print(json.dumps(preview, ensure_ascii=False, sort_keys=True))
            return 0
        if not isinstance(args.confirmed_by, str) or args.confirmed_by.strip().lower() != "owner":
            raise ContractError("position import requires --confirmed-by owner")
        radar.initialize()
        position_id = radar.import_position(payload, confirmed_by=args.confirmed_by)
        print(json.dumps(radar.show_position(str(normalized["symbol"])), ensure_ascii=False, sort_keys=True))
        if position_id <= 0:
            raise AssertionError("position import returned an invalid id")
        return 0
    if args.command == "revise-position-baseline":
        radar.initialize()
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        print(radar.revise_position_baseline(args.symbol, payload, confirmed_by=args.confirmed_by))
        return 0
    if args.command == "list-positions":
        print(json.dumps(radar.list_positions(), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "show-position":
        print(json.dumps(radar.show_position(args.symbol), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "monthly-position-review-status":
        print(
            json.dumps(
                radar.monthly_position_review_status(args.period),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "record-position-review":
        radar.initialize()
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        radar.record_position_review(args.symbol, payload)
        print(json.dumps(radar.show_position(args.symbol), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "confirm-position-event":
        radar.initialize()
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        event_id = radar.confirm_position_event(
            args.symbol, payload, confirmed_by=args.confirmed_by
        )
        print(json.dumps({"event_id": event_id, "position_id": payload["position_id"]}, sort_keys=True))
        return 0

    if args.command == "monthly-position-review-context":
        from .position_review import monthly_brief_context
        print(json.dumps(monthly_brief_context(radar, args.period), ensure_ascii=False, sort_keys=True))
        return 0

    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
