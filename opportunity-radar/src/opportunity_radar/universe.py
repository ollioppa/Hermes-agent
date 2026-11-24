from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from urllib.request import Request, urlopen


UNIVERSE_URLS = {
    "spy.xlsx": "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx",
    "nasdaq100.json": "https://api.nasdaq.com/api/quote/list-type/nasdaq100",
    "exsa.csv": "https://www.ishares.com/ch/individual/en/products/251931/ishares-stoxx-europe-600-ucits-etf-de-fund/1495092304805.ajax?fileType=csv&fileName=EXSA_holdings&dataType=fund",
}

@dataclass(frozen=True)
class UniverseMember:
    stable_identity: str
    symbol: str
    name: str
    kind: str
    region: str
    mic: str
    currency: str
    source: str
    price_symbol: str | None = None
    memberships: tuple[str, ...] = ()


def _cohort_index(stable_identity: str, policy_version: str, cohort_count: int) -> int:
    digest = hashlib.sha256(f"{policy_version}|{stable_identity}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % cohort_count


def assign_cohorts(
    members: Iterable[UniverseMember], *, policy_version: str = "screen-v1", cohort_count: int = 6
) -> dict[int, list[UniverseMember]]:
    cohorts = {index: [] for index in range(cohort_count)}
    for member in members:
        cohorts[_cohort_index(member.stable_identity, policy_version, cohort_count)].append(member)
    for values in cohorts.values():
        values.sort(key=lambda item: item.stable_identity)
    return cohorts



def _xlsx_rows(path: Path) -> list[dict[str, str]]:
    namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    tag = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
    with ZipFile(path) as archive:
        strings_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = ["".join(text.text or "" for text in item.iter(tag)) for item in strings_root]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    rows: list[dict[str, str]] = []
    for row in sheet.findall(".//m:row", namespace):
        values: dict[str, str] = {}
        for cell in row.findall("m:c", namespace):
            ref = str(cell.get("r", ""))
            match = re.match(r"[A-Z]+", ref)
            value_node = cell.find("m:v", namespace)
            value = "" if value_node is None or value_node.text is None else value_node.text
            if cell.get("t") == "s" and value:
                value = shared[int(value)]
            if match is not None:
                values[match.group()] = value.strip()
        rows.append(values)
    return rows


def _is_spy_equity_candidate(row: dict[str, str]) -> bool:
    ticker = row.get("B", "").strip()
    identifier = row.get("C", "").strip().upper()
    currency = row.get("H", "").strip()
    return bool(
        ticker
        and ticker not in {"Ticker", "-"}
        and currency == "USD"
        and "CVR" not in identifier
    )


def _load_us(root: Path) -> dict[str, UniverseMember]:
    members: dict[str, UniverseMember] = {}
    spy_rows = _xlsx_rows(root / "spy.xlsx")
    for row in spy_rows:
        ticker = row.get("B", "").strip()
        name = row.get("A", "").strip()
        currency = row.get("H", "").strip()
        if not _is_spy_equity_candidate(row):
            continue
        stable_identity = f"US:{ticker}"
        members[stable_identity] = UniverseMember(
            stable_identity=stable_identity,
            symbol=ticker,
            name=name,
            kind="stock",
            region="US",
            mic="US",
            currency="USD",
            source="SPY",
            price_symbol=ticker,
            memberships=("SPY",),
        )
    if not 490 <= len(members) <= 520:
        raise ValueError(f"SPY semantic row count mismatch: {len(members)}")

    payload = json.loads((root / "nasdaq100.json").read_text(encoding="utf-8"))
    data = payload["data"]
    rows = data["data"]["rows"]
    if int(data["totalrecords"]) != len(rows) or not 95 <= len(rows) <= 110:
        raise ValueError("Nasdaq-100 semantic row count mismatch")
    for row in rows:
        ticker = str(row["symbol"]).strip()
        name = str(row["companyName"]).strip()
        stable_identity = f"US:{ticker}"
        existing = members.get(stable_identity)
        if existing is not None:
            members[stable_identity] = UniverseMember(
                **{**existing.__dict__, "memberships": tuple(sorted(set(existing.memberships) | {"NASDAQ100"}))}
            )
        else:
            members[stable_identity] = UniverseMember(
                stable_identity=stable_identity,
                symbol=ticker,
                name=name,
                kind="stock",
                region="US",
                mic="US",
                currency="USD",
                source="NASDAQ100",
                price_symbol=ticker,
                memberships=("NASDAQ100",),
            )
    if not 490 <= len(members) <= 540:
        raise ValueError(f"US identity union outside expected range: {len(members)}")
    return members


def _load_europe(root: Path) -> dict[str, UniverseMember]:
    exchange_payload = json.loads((root / "exchange-map-v1.json").read_text(encoding="utf-8"))
    exchange_map = exchange_payload["producer_exchange_map"]
    lines = (root / "exsa.csv").read_text(encoding="utf-8-sig").splitlines()
    rows = list(csv.DictReader(lines[2:]))
    equities = [row for row in rows if row.get("Asset Class") == "Equity"]
    if not 580 <= len(equities) <= 620:
        raise ValueError("EXSA semantic row count mismatch")
    members: dict[str, UniverseMember] = {}
    for row in equities:
        ticker = str(row["Ticker"]).strip()
        name = str(row["Name"]).strip()
        exchange = str(row["Exchange"]).strip()
        mapping = exchange_map.get(exchange)
        if not ticker or not name or mapping is None:
            raise ValueError(f"unsupported EXSA identity: {ticker} / {exchange}")
        mic = str(mapping["mic"])
        stable_identity = f"{mic}:{ticker}"
        if stable_identity in members:
            raise ValueError(f"duplicate EXSA identity: {stable_identity}")
        suffix = mapping.get("alpha_suffix")
        price_symbol = f"{ticker}{suffix}" if suffix else None
        members[stable_identity] = UniverseMember(
            stable_identity=stable_identity,
            symbol=ticker,
            name=name,
            kind="stock",
            region="EU",
            mic=mic,
            currency=str(row["Market Currency"]).strip(),
            source="EXSA",
            price_symbol=price_symbol,
            memberships=("EXSA",),
        )
    if not 580 <= len(members) <= 620:
        raise ValueError(f"EXSA identity count mismatch: {len(members)}")
    return members


def _load_etfs(path: Path) -> dict[str, UniverseMember]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or len(rows) != 14:
        raise ValueError("curated ETF registry must contain exactly 14 rows")
    members: dict[str, UniverseMember] = {}
    for row in rows:
        stable_identity = str(row["stable_identity"])
        member = UniverseMember(
            stable_identity=stable_identity,
            symbol=str(row["symbol"]),
            name=str(row["name"]),
            kind="etf",
            region=str(row["region"]),
            mic=str(row["mic"]),
            currency=str(row["currency"]),
            source="CURATED_ETF",
            price_symbol=str(row["price_symbol"]),
            memberships=("CURATED_ETF",),
        )
        if stable_identity in members:
            raise ValueError(f"duplicate ETF identity: {stable_identity}")
        members[stable_identity] = member
    return members


def load_universe_sources(root: Path | str, etf_registry: Path | str) -> list[UniverseMember]:
    fixture_root = Path(root)
    combined: dict[str, UniverseMember] = {}
    for partition in (_load_us(fixture_root), _load_europe(fixture_root), _load_etfs(Path(etf_registry))):
        overlap = set(combined).intersection(partition)
        if overlap:
            raise ValueError(f"identity collision across asset partitions: {sorted(overlap)}")
        combined.update(partition)
    cohorts = assign_cohorts(combined.values(), policy_version="screen-v1", cohort_count=6)
    for index, members in cohorts.items():
        if len(members) > 216:
            raise ValueError(f"cohort {index} exceeds freshness capacity")
        if not {"US", "EU"}.issubset({member.region for member in members}) or not any(member.kind == "etf" for member in members):
            raise ValueError(f"cohort {index} lacks mixed-region/ETF coverage")
    return sorted(combined.values(), key=lambda member: member.stable_identity)



def universe_source_metadata(root: Path | str) -> dict[str, tuple[date, int]]:
    source_root = Path(root)
    spy_rows = _xlsx_rows(source_root / "spy.xlsx")
    spy_label = next(row.get("B", "") for row in spy_rows if row.get("A") == "Holdings:")
    spy_date = datetime.strptime(spy_label.removeprefix("As of "), "%d-%b-%Y").date()
    spy_count = sum(
        1 for row in spy_rows
        if row.get("B") and row.get("B") not in {"Ticker", "-"} and row.get("H") == "USD"
    )
    nasdaq = json.loads((source_root / "nasdaq100.json").read_text(encoding="utf-8"))["data"]
    nasdaq_label = str(nasdaq["date"])
    try:
        nasdaq_date = datetime.strptime(nasdaq_label, "%b %d, %Y").date()
    except ValueError:
        nasdaq_date = datetime.strptime(nasdaq_label, "%b %d, %Y %I:%M %p").date()
    nasdaq_count = len(nasdaq["data"]["rows"])
    exsa_lines = (source_root / "exsa.csv").read_text(encoding="utf-8-sig").splitlines()
    match = re.search(r"(\d{1,2})/(\w+)/(\d{4})", exsa_lines[0])
    if match is None:
        raise ValueError("EXSA source date missing")
    day, month, year = match.groups()
    exsa_date = datetime.strptime(f"{day}/{month.replace('Sept', 'Sep')}/{year}", "%d/%b/%Y").date()
    exsa_count = sum(1 for row in csv.DictReader(exsa_lines[2:]) if row.get("Asset Class") == "Equity")
    return {
        "SPY": (spy_date, spy_count),
        "NASDAQ100": (nasdaq_date, nasdaq_count),
        "EXSA": (exsa_date, exsa_count),
    }


def download_current_universe(
    destination: Path | str,
    exchange_map: Path | str,
    *,
    timeout: float = 60.0,
) -> Path:
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    for filename, url in UNIVERSE_URLS.items():
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 opportunity-radar/1"})
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
        temporary = target / f".{filename}.tmp"
        temporary.write_bytes(payload)
        temporary.replace(target / filename)
    shutil.copyfile(exchange_map, target / "exchange-map-v1.json")
    return target
