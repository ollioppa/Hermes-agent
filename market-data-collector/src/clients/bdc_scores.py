from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BDC_INBOX = PROJECT_ROOT / "data/inbox/bdc_scores"
_DATED_EXPORT = re.compile(r"^bdc_scores_(\d{4}-\d{2}-\d{2})\.json$")
_SCORE_KEYS = {
    "stage1_kreditqualitaet": "stage1_credit_quality",
    "stage2_wrapper_repricing": "stage2_wrapper_repricing",
    "stage3_funding_stress": "stage3_funding_stress",
    "stage4_kreditangebot": "stage4_credit_supply",
    "stage5_makro_folgen": "stage5_macro_effects",
    "stage6_rueckkopplung": "stage6_feedback",
}
_REGIME_KEYS = {
    "A_sektorales_repricing": "regime_a_probability",
    "B_slow_burn_japanisierung": "regime_b_probability",
    "C_gekoppelte_eskalation": "regime_c_probability",
}


def _require_number(mapping: dict[str, Any], source_key: str, path: Path) -> float:
    if source_key not in mapping:
        raise ValueError(f"{path}: missing {source_key}")
    try:
        return float(mapping[source_key])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path}: {source_key} must be numeric") from exc


def _load_export(path: Path, export_date: str) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: BDC payload must be an object")
    as_of = str(payload.get("as_of", ""))[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
        raise ValueError(f"{path}: invalid as_of date")
    scores = payload.get("scores")
    regimes = payload.get("regime_probabilities")
    if not isinstance(scores, dict):
        raise ValueError(f"{path}: scores must be an object")
    if not isinstance(regimes, dict):
        raise ValueError(f"{path}: regime_probabilities must be an object")

    row: dict[str, Any] = {
        "export_date": export_date,
        "bdc_as_of_date": as_of,
    }
    for source_key, target_key in _SCORE_KEYS.items():
        row[target_key] = _require_number(scores, source_key, path)
    for source_key, target_key in _REGIME_KEYS.items():
        row[target_key] = _require_number(regimes, source_key, path)
    status_label = str(payload.get("status_label", "")).strip()
    row["status_code"] = status_label.split("—", 1)[0].strip()
    row["source_status"] = "ok"
    return row


def load_bdc_exports(inbox: Path = DEFAULT_BDC_INBOX) -> list[dict[str, Any]]:
    """Read validated dated exports from the market_data_collector-owned inbox only."""
    inbox = Path(inbox)
    if not inbox.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(inbox.glob("bdc_scores_*.json")):
        match = _DATED_EXPORT.fullmatch(path.name)
        if match is None:
            continue
        rows.append(_load_export(path, match.group(1)))
    return rows
