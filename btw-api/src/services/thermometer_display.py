"""Pure deterministic customer-facing Thermometer-v1 projection."""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA_VERSION = "composite_thermometer_v1"


def _score(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "—"
    numeric = float(value)
    return f"{int(numeric):+d}" if numeric.is_integer() else f"{numeric:+.1f}"


def _bucket_for_weekly_median(value: float) -> str:
    """Classify an exact weekly median; daily score validation remains integer-only."""
    if value < -8 or value > 8:
        raise ValueError("weekly median must be in [-8, 8]")
    if value >= 6:
        return "A"
    if value >= 3:
        return "B"
    if value >= 0:
        return "C"
    if value >= -3:
        return "D"
    return "E"


def _weekly_rows(history: Any) -> list[str]:
    if not isinstance(history, list) or len(history) != 7:
        raise ValueError("display requires current W-SUN slot plus six historical v1 weekly slots")
    rows: list[str] = []
    previous: float | None = None
    for slot in history:
        if not isinstance(slot, Mapping):
            raise ValueError("display requires structured weekly slots")
        start, end = slot.get("week_start"), slot.get("week_end")
        if not isinstance(start, str) or not isinstance(end, str):
            raise ValueError("display requires W-SUN dates")
        label = f"{start[8:10]}.{start[5:7]}.–{end[8:10]}.{end[5:7]}."
        median = slot.get("median")
        median_num = float(median) if isinstance(median, (int, float)) else None
        available = slot.get("status") in {"complete", "partial"} and median_num is not None
        if available and median_num is not None:
            score = _score(median_num)
            if slot.get("status") == "partial":
                score += f" ({slot.get('complete_day_count')}/7 Datenstand)"
            bucket = _bucket_for_weekly_median(median_num)
            change = "—" if previous is None else _score(median_num - previous)
            previous = median_num
        else:
            score = bucket = change = "—"
            previous = None
        rows.append(f"| {label} | {score} | {bucket} | {change} |")
    return rows


def render_signal_score(thermometer: Mapping[str, Any]) -> str:
    """Render the canonical compact v1 table; never mixes legacy values."""
    if not isinstance(thermometer, Mapping) or thermometer.get("score_schema_version") != SCHEMA_VERSION:
        raise ValueError("display requires composite_thermometer_v1")
    status = thermometer.get("status")
    if status not in {"complete", "partial", "unavailable"}:
        raise ValueError("display requires complete, partial, or unavailable status")
    if status == "complete" and isinstance(thermometer.get("score"), Mapping):
        headline = f"**Thermometer v1:** {_score(thermometer['score'].get('value'))} — Bucket {thermometer.get('bucket')}."
    elif status == "partial":
        headline = "**Thermometer v1:** teilweise nicht verfügbar — Datenstand prüfen."
    else:
        headline = "**Thermometer v1:** nicht verfügbar — Datenstand prüfen."
    return "\n".join([
        "## Signal-Score", "", headline, "", "### 6-Wochen-Verlauf (Wochenmediane)",
        "| Kalenderwoche | Score | Bucket | Δ1W |", "|---|---:|:---:|---:|",
        *_weekly_rows(thermometer.get("weekly_history")), "",
        "*Median bei 6 oder 7 vollständigen Tageswerten. Keine Legacy-Vergleiche.*",
    ])
