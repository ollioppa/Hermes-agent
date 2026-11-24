from __future__ import annotations

from datetime import date
from typing import Iterable


def evaluate_finra_window(
    boundaries: Iterable[dict[str, str]],
    *,
    window_days: int,
    immutable_vintage_count: int,
    revision_change_ages_days: list[int] | None = None,
) -> dict[str, object]:
    """Separate publication-boundary coverage from real revision-vintage proof.

    A window of N days writes replay_date-(N-1) through replay_date inclusive.
    Publication-policy samples cannot prove historical revision latency.
    """
    if window_days < 1:
        raise ValueError("window_days must be positive")
    captured: list[str] = []
    missed: list[str] = []
    ages: dict[str, int] = {}
    for boundary in boundaries:
        identity = boundary["reference_month"]
        signal_date = date.fromisoformat(boundary["signal_date"])
        replay_after = date.fromisoformat(boundary["replay_after"])
        age_days = (replay_after - signal_date).days
        ages[identity] = age_days
        if 0 <= age_days < window_days:
            captured.append(identity)
        else:
            missed.append(identity)

    publication_verdict = "pass" if len(captured) >= 12 and not missed else "fail"
    if immutable_vintage_count < 12 or revision_change_ages_days is None:
        revision_verdict = "blocked_missing_vintage_evidence"
        missed_revisions: list[int] | None = None
    else:
        missed_revisions = [age for age in revision_change_ages_days if age >= window_days]
        revision_verdict = "pass" if not missed_revisions else "fail"
    production_verdict = (
        "pass"
        if publication_verdict == "pass" and revision_verdict == "pass"
        else "blocked"
    )
    return {
        "chosen_window_days": window_days,
        "replayed_boundaries": len(captured) + len(missed),
        "captured_publication_boundaries": captured,
        "missed_publication_boundaries": missed,
        "publication_change_age_days": ages,
        "publication_window_verdict": publication_verdict,
        "immutable_vintage_count": immutable_vintage_count,
        "missed_revisions": missed_revisions,
        "revision_window_verdict": revision_verdict,
        "production_verdict": production_verdict,
    }
