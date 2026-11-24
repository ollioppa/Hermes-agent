from datetime import date, timedelta

from src.services.finra_replay import evaluate_finra_window


def test_120_day_window_captures_twelve_publication_boundaries_but_not_revision_gate():
    boundaries = []
    for month_index in range(12):
        reference_month = date(2025 + (5 + month_index) // 12, (5 + month_index) % 12 + 1, 1)
        signal_month = date(
            reference_month.year + (reference_month.month // 12),
            reference_month.month % 12 + 1,
            1,
        )
        boundaries.append(
            {
                "reference_month": reference_month.isoformat(),
                "signal_date": signal_month.isoformat(),
                "replay_after": (signal_month + timedelta(days=21)).isoformat(),
            }
        )

    report = evaluate_finra_window(
        boundaries,
        window_days=120,
        immutable_vintage_count=0,
    )

    assert report["replayed_boundaries"] == 12
    assert report["missed_publication_boundaries"] == []
    assert report["publication_window_verdict"] == "pass"
    assert report["revision_window_verdict"] == "blocked_missing_vintage_evidence"
    assert report["production_verdict"] == "blocked"


def test_finra_window_inclusive_edge_is_explicit():
    replay_date = date(2026, 7, 21)
    boundaries = [
        {"reference_month": "edge-119", "signal_date": (replay_date - timedelta(days=119)).isoformat(), "replay_after": replay_date.isoformat()},
        {"reference_month": "edge-120", "signal_date": (replay_date - timedelta(days=120)).isoformat(), "replay_after": replay_date.isoformat()},
    ]

    report = evaluate_finra_window(boundaries, window_days=120, immutable_vintage_count=12)

    assert report["captured_publication_boundaries"] == ["edge-119"]
    assert report["missed_publication_boundaries"] == ["edge-120"]
