"""Request parsing and Yahoo Finance downloads, shared by the HTML and JSON responses."""
import datetime
import re

import yfinance as yahooFinance

# Lambda's filesystem is read-only except /tmp; keep yfinance's timezone cache there
# so warm invocations reuse it.
yahooFinance.set_tz_cache_location('/tmp/py-yfinance')

# yfinance creates its SQLite caches on first use without a lock, so tickers fetched
# in parallel on a cold start can fail with "database is locked". Create them here,
# once, before any threads start.
from yfinance import cache as _yf_cache  # noqa: E402
_yf_cache.get_tz_cache().lookup('SPY')
_yf_cache.get_cookie_cache().lookup('basic')


class InputError(Exception):
    """A problem with the request that the user can fix; the message is shown to them."""


def parse_request(event):
    """Returns (start datetime, end datetime, tickers) or raises InputError."""
    start_date = str(event.get('start_date') or '').strip()
    end_date = str(event.get('end_date') or '').strip()
    # trims, uppercases, drops empty entries and duplicates (keeps input order)
    symbols = list(dict.fromkeys(s.strip().upper() for s in str(event.get('symbol') or '').split(',') if s.strip()))

    if not start_date or not end_date or not symbols:
        raise InputError("Please enter a start date, an end date and at least one ticker.")

    # separates the year, month, and day for both the start and end dates
    pattern = r'[/-]'
    try:
        startyear, startmonth, startday = [int(part) for part in re.split(pattern, start_date)]
        endyear, endmonth, endday = [int(part) for part in re.split(pattern, end_date)]
        start = datetime.datetime(startyear, startmonth, startday)
        end = datetime.datetime(endyear, endmonth, endday)
    except ValueError:
        raise InputError("Dates must be in YYYY-MM-DD format.")

    if start >= end:
        raise InputError("The start date must be before the end date.")

    return start, end, symbols


def get_history(symbol, start, end):
    """Daily bars for one ticker from Yahoo, with 'date' (datetime.date) and 'symbol' columns."""
    df = yahooFinance.Ticker(symbol).history(start=start, end=end)
    df = df.assign(date=[ts.date() for ts in df.index])
    df['symbol'] = symbol
    return df


def require_data(symbols, frames, start, end):
    """Raises InputError naming every ticker that returned no rows."""
    missing = [s for s, d in zip(symbols, frames) if d.empty]
    if missing:
        raise InputError("No data found for {} between {} and {}. Check the ticker symbol and the date range.".format(
            ', '.join(missing), start.date(), end.date()))
