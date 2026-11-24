from src.services.thermometer_display import render_signal_score


def _slot(start, end, status, median, count):
    return {"week_start": start, "week_end": end, "status": status, "median": median, "complete_day_count": count}


def _snapshot(status="partial"):
    return {"score_schema_version":"composite_thermometer_v1","status":status,"score":{"value":5} if status == "complete" else None,"bucket":"B" if status == "complete" else None,"weekly_history":[
      _slot("2026-07-13","2026-07-19","partial",3,6),_slot("2026-07-06","2026-07-12","complete",5,7),
      _slot("2026-06-29","2026-07-05","complete",6,7),_slot("2026-06-22","2026-06-28","complete",6,7),
      _slot("2026-06-15","2026-06-21","complete",6,7),_slot("2026-06-08","2026-06-14","complete",4,7),
      _slot("2026-06-01","2026-06-07","unavailable",None,0)]}


def test_compact_v1_table_is_current_slot_plus_six_historical_wsun_rows_and_marks_6_of_7():
    rendered=render_signal_score(_snapshot())
    assert "## Signal-Score" in rendered
    assert "| 13.07.–19.07. | +3 (6/7 Datenstand) | B | — |" in rendered
    assert "| 06.07.–12.07. | +5 | B | +2 |" in rendered
    assert "| 01.06.–07.06. | — | — | — |" in rendered
    assert sum(line.startswith("| ") and len(line) > 4 and line[2:4].isdigit() for line in rendered.splitlines()) == 7
    assert "Keine Legacy-Vergleiche" in rendered
    assert "reason_code" not in rendered


def test_partial_current_status_has_no_partial_score_or_bucket():
    rendered=render_signal_score(_snapshot("partial"))
    assert "teilweise nicht verfügbar" in rendered
    assert "**Thermometer v1:** +" not in rendered


def test_weekly_half_median_is_not_truncated_and_uses_its_numeric_bucket_range():
    score = _snapshot()
    score["weekly_history"][0] = _slot("2026-07-13", "2026-07-19", "partial", 2.5, 6)
    score["weekly_history"][1] = _slot("2026-07-06", "2026-07-12", "complete", 3.5, 7)

    rendered = render_signal_score(score)

    assert "| 13.07.–19.07. | +2.5 (6/7 Datenstand) | C | — |" in rendered
    assert "| 06.07.–12.07. | +3.5 | B | +1 |" in rendered


def test_unavailable_current_status_is_not_described_as_partially_available():
    rendered = render_signal_score(_snapshot("unavailable"))

    assert "nicht verfügbar" in rendered
    assert "teilweise nicht verfügbar" not in rendered
