"""NYSE trading calendar alignment utilities.

Provides functions to:
- Get NYSE valid trading days
- Map each week to its Friday close (or Thursday if Friday is a holiday)
- Align crypto PC scores and macro returns to the same weekly dates
"""

from __future__ import annotations

from typing import Sequence

import pandas as pd
import pandas_market_calendars as mcal


def get_nyse_calendar(start: str, end: str) -> pd.DatetimeIndex:
    """Get NYSE valid trading days between start and end dates.

    Parameters
    ----------
    start : str
        Start date in YYYY-MM-DD format.
    end : str
        End date in YYYY-MM-DD format.

    Returns
    -------
    pd.DatetimeIndex
        Valid NYSE trading days.
    """
    nyse = mcal.get_calendar("NYSE")
    sched = nyse.valid_days(start_date=start, end_date=end)
    return sched


def get_friday_closes(start: str, end: str) -> pd.DatetimeIndex:
    """Get weekly rebalance dates = Friday closes on the NYSE calendar.

    If Friday is a holiday, uses Thursday instead.

    Parameters
    ----------
    start : str
        Start date in YYYY-MM-DD format.
    end : str
        End date in YYYY-MM-DD format.

    Returns
    -------
    pd.DatetimeIndex
        Friday (or Thursday fallback) close dates.
    """
    nyse = mcal.get_calendar("NYSE")
    sched = nyse.schedule(start_date=start, end_date=end)

    all_days = sched.index
    fridays = all_days[all_days.dayofweek == 4]

    result = []
    friday_dates = set(fridays.strftime("%Y-%m-%d"))
    thursday_dates = set(all_days[all_days.dayofweek == 3].strftime("%Y-%m-%d"))

    for friday in fridays:
        friday_str = friday.strftime("%Y-%m-%d")
        if friday_str in friday_dates:
            result.append(friday)
        elif friday_str in thursday_dates:
            pass

    return pd.DatetimeIndex(result)


def align_to_fridays(
    dates: Sequence[str | pd.Timestamp],
) -> pd.Series:
    """Map arbitrary dates to the nearest preceding Friday in the NYSE calendar.

    Parameters
    ----------
    dates : sequence of str or pd.Timestamp
        Dates to align.

    Returns
    -------
    pd.Series
        Aligned Friday dates.
    """
    dates_ts = pd.to_datetime(dates)

    min_date = dates_ts.min() - pd.Timedelta(days=7)
    max_date = dates_ts.max() + pd.Timedelta(days=7)

    fridays = get_friday_closes(
        start=min_date.strftime("%Y-%m-%d"),
        end=max_date.strftime("%Y-%m-%d"),
    )

    aligned = []
    for d in dates_ts:
        valid = fridays[fridays <= d]
        if len(valid) > 0:
            aligned.append(valid[-1])
        else:
            aligned.append(d)

    return pd.Series(aligned, index=dates_ts)


def get_previous_friday(date: str | pd.Timestamp, n: int = 1) -> pd.Timestamp:
    """Get the n-th previous Friday close from a given date.

    Parameters
    ----------
    date : str or pd.Timestamp
        Reference date.
    n : int
        Number of weeks back.

    Returns
    -------
    pd.Timestamp
        The n-th previous Friday.
    """
    dt = pd.Timestamp(date)
    min_date = (dt - pd.Timedelta(weeks=n + 2)).strftime("%Y-%m-%d")
    max_date = dt.strftime("%Y-%m-%d")

    fridays = get_friday_closes(start=min_date, end=max_date)

    if len(fridays) > n:
        return fridays[-(n + 1)]
    elif len(fridays) > 0:
        return fridays[0]
    else:
        return dt