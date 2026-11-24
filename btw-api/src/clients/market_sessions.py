"""Scheduled NYSE sessions for the weekly price comparison (existing pandas)."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
from functools import lru_cache
from pandas.tseries.holiday import (AbstractHolidayCalendar, Holiday, nearest_workday,
    sunday_to_monday, USMartinLutherKingJr, USPresidentsDay, GoodFriday,
    USMemorialDay, USLaborDay, USThanksgivingDay)


class _NYSEHolidays(AbstractHolidayCalendar):
    # Extraordinary closures are not inferred from provider gaps.
    rules = [Holiday('New Year',month=1,day=1,observance=sunday_to_monday),
             USMartinLutherKingJr, USPresidentsDay, GoodFriday, USMemorialDay,
             Holiday('Juneteenth',month=6,day=19,start_date='2022-01-01',observance=nearest_workday),
             Holiday('Independence',month=7,day=4,observance=nearest_workday),
             USLaborDay, USThanksgivingDay,
             Holiday('Christmas',month=12,day=25,observance=nearest_workday)]


@lru_cache(maxsize=2048)
def session_close(day: date):
    """Expected scheduled close; missing quotes never move an anchor."""
    if day.weekday()>4 or not _NYSEHolidays().holidays(start=day,end=day).empty:
        return None
    early = ((day.month,day.day) in ((7,3),(12,24))
             or (day.month==11 and day.weekday()==4 and 23<=day.day<=29))
    return datetime(day.year,day.month,day.day,13 if early else 16,tzinfo=ZoneInfo('America/New_York'))
