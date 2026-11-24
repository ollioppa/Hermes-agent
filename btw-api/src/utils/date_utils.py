from datetime import date, timedelta


def today() -> str:
    return date.today().isoformat()


def last_n_dates(n: int) -> list[str]:
    """Return the last n calendar dates (today included), newest first."""
    base = date.today()
    return [(base - timedelta(days=i)).isoformat() for i in range(n)]


def date_range(start: str, end: str) -> list[str]:
    """Return all dates between start and end (inclusive), newest first."""
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    days = (e - s).days + 1
    return [(e - timedelta(days=i)).isoformat() for i in range(days)]


def to_unix_ms(date_str: str) -> int:
    """Convert YYYY-MM-DD to Unix timestamp in milliseconds (UTC midnight)."""
    d = date.fromisoformat(date_str)
    from datetime import datetime, timezone
    dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def to_unix_s(date_str: str) -> int:
    """Convert YYYY-MM-DD to Unix timestamp in seconds (UTC midnight)."""
    return to_unix_ms(date_str) // 1000
