"""Statistics for the JSON response. Pure functions over pandas data; no network.

Definitions match docs/json-api.md. Inputs are daily bars indexed by trading date
(tz-naive Timestamps), including history before the requested start date so the
moving averages and rolling volatility are valid from the first day in range.
"""
import math

import numpy as np
import pandas as pd

TRADING_DAYS = 252
RISK_FREE_RATE = 0.0
HISTOGRAM_BINS = 40
LOOKBACK_DAYS = 400  # calendar days fetched before start: enough for a 200 trading-day average
WEEKLY_AFTER_YEARS = 5  # longer ranges send weekly bars for charts, keeping the response under 6 MB


def clean(value, digits=6):
    """A JSON-safe number: rounded, with NaN and infinity as None."""
    if value is None:
        return None
    value = float(value)
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def clean_list(values, digits=6):
    return [clean(v, digits) for v in values]


def day(ts):
    return None if ts is None else pd.Timestamp(ts).strftime('%Y-%m-%d')


def days(index):
    return [day(ts) for ts in index]


def daily_bars(df):
    """yfinance history (tz-aware index) to bars indexed by tz-naive trading date."""
    out = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    out.index = pd.DatetimeIndex([pd.Timestamp(ts.date()) for ts in df.index], name='date')
    return out[~out.index.duplicated(keep='last')].sort_index()


def use_weekly(start, end):
    return pd.Timestamp(end) > pd.Timestamp(start) + pd.DateOffset(years=WEEKLY_AFTER_YEARS)


def _week_end_dates(index):
    """Each week's last trading day (weeks end on Friday)."""
    weeks = index.to_period('W-FRI')
    return weeks, pd.DatetimeIndex(pd.Series(index, index=index).groupby(weeks).last().to_numpy(), name='date')


def weekly(bars):
    """Weekly bars dated by each week's last trading day: first open, max high, min low, last close, total volume."""
    weeks, dates = _week_end_dates(bars.index)
    out = bars.groupby(weeks).agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
    out.index = dates
    return out


def chart_close(close, weekly_bars):
    """The closes the charts use: daily, or each week's last close."""
    if not weekly_bars:
        return close
    weeks, dates = _week_end_dates(close.index)
    out = close.groupby(weeks).last()
    out.index = dates
    return out


def in_range(frame, start, end):
    """Rows with start <= date < end (end is exclusive, as in yfinance)."""
    return frame[(frame.index >= pd.Timestamp(start)) & (frame.index < pd.Timestamp(end))]


def daily_returns(close):
    """close_t / close_{t-1} - 1, dropping the first day (it has no previous close)."""
    return close.pct_change().iloc[1:]


def drawdown(close):
    """Close / running peak - 1."""
    return close / close.cummax() - 1


def max_drawdown(close):
    """(depth, peak date, trough date, recovery date or None). Depth 0 means no drawdown."""
    dd = drawdown(close)
    trough = dd.idxmin()
    depth = dd.loc[trough]
    if not depth < 0:
        return 0.0, None, None, None
    peak = close.loc[:trough].idxmax()
    after = close.loc[trough:]
    recovered = after[after >= close.loc[peak]]
    return float(depth), peak, trough, (recovered.index[0] if len(recovered) else None)


def annual_return(total_return, n_returns):
    if n_returns < 1 or total_return is None or total_return <= -1:
        return None
    return (1 + total_return) ** (TRADING_DAYS / n_returns) - 1


def annual_volatility(returns):
    if len(returns) < 2:
        return None
    return returns.std(ddof=1) * math.sqrt(TRADING_DAYS)


def sharpe(returns):
    vol = annual_volatility(returns)
    if not vol:  # None or 0 (flat prices)
        return None
    return (returns.mean() * TRADING_DAYS - RISK_FREE_RATE) / vol


def beta(returns, benchmark_returns):
    joined = pd.concat([returns, benchmark_returns], axis=1, join='inner').dropna()
    if len(joined) < 2:
        return None
    var = joined.iloc[:, 1].var(ddof=1)
    if not var:
        return None
    return joined.iloc[:, 0].cov(joined.iloc[:, 1]) / var


def return_stats(returns):
    """Histogram and distribution statistics of daily returns."""
    stats = {'histogram': {'edges': [], 'counts': []}, 'mean': None, 'median': None, 'std': None,
             'skew': None, 'kurtosis': None, 'var_95': None}
    if len(returns) < 2:
        return stats
    counts, edges = np.histogram(returns.to_numpy(), bins=HISTOGRAM_BINS)
    stats.update(
        histogram={'edges': clean_list(edges), 'counts': [int(c) for c in counts]},
        mean=clean(returns.mean()),
        median=clean(returns.median()),
        std=clean(returns.std(ddof=1)),
        skew=clean(returns.skew()),          # bias-corrected sample skewness
        kurtosis=clean(returns.kurt()),      # bias-corrected excess kurtosis (normal = 0)
        var_95=clean(returns.quantile(0.05)),
    )
    return stats


def monthly_returns(close_in_range, history_dates, end):
    """Month-over-month returns of the closes in range.

    The first month is measured from the first close in range. A month is partial when
    the range starts after its first trading day (history has an earlier bar that month)
    or ends before the month is over.
    """
    if close_in_range.empty:
        return []
    month_end = close_in_range.groupby(close_in_range.index.to_period('M')).last()
    previous = month_end.shift(1)
    previous.iloc[0] = close_in_range.iloc[0]
    returns = month_end / previous - 1

    first_day = close_in_range.index[0]
    first_period = first_day.to_period('M')
    starts_mid_month = any((d.to_period('M') == first_period) and d < first_day for d in history_dates)
    last_covered = pd.Timestamp(end) - pd.Timedelta(days=1)
    last_period = close_in_range.index[-1].to_period('M')
    ends_mid_month = last_covered.to_period('M') == last_period and last_covered < last_period.end_time.normalize()

    out = []
    for i, (period, value) in enumerate(returns.items()):
        partial = (i == 0 and starts_mid_month) or (i == len(returns) - 1 and ends_mid_month)
        out.append({'year': period.year, 'month': period.month, 'return': clean(value), 'partial': bool(partial)})
    return out


def by_month(monthly):
    """Average return and share of positive months for each calendar month (full months only)."""
    out = []
    for month in range(1, 13):
        values = [m['return'] for m in monthly if m['month'] == month and not m['partial'] and m['return'] is not None]
        if values:
            out.append({'month': month, 'average': clean(sum(values) / len(values)),
                        'positive': clean(sum(v > 0 for v in values) / len(values)), 'years': len(values)})
    return out


def ticker_data(symbol, history, start, end, is_benchmark=False, benchmark_returns=None, benchmark_total=None,
                weekly_bars=False):
    """TickerData (see docs/json-api.md) from daily bars that include history before start.

    Statistics always use daily data; with weekly_bars the chart series are sampled weekly.
    """
    close_all = history['Close']
    sma50 = close_all.rolling(50).mean()
    sma200 = close_all.rolling(200).mean()
    rolling_vol = close_all.pct_change().rolling(30).std(ddof=1) * math.sqrt(TRADING_DAYS)

    bars = in_range(history, start, end)
    close = bars['Close']
    idx = bars.index
    rets = daily_returns(close)
    n = len(rets)

    total = close.iloc[-1] / close.iloc[0] - 1 if len(close) else None
    depth, peak, trough, recovery = max_drawdown(close) if len(close) else (None, None, None, None)
    has_benchmark = benchmark_returns is not None

    summary = {
        'start_date': day(idx[0]) if len(idx) else None,
        'end_date': day(idx[-1]) if len(idx) else None,
        'start_price': clean(close.iloc[0], 4) if len(close) else None,
        'end_price': clean(close.iloc[-1], 4) if len(close) else None,
        'total_return': clean(total),
        'annual_return': clean(annual_return(total, n)),
        'annual_volatility': clean(annual_volatility(rets)),
        'sharpe': clean(sharpe(rets)),
        'max_drawdown': clean(depth),
        'max_drawdown_peak': day(peak),
        'max_drawdown_trough': day(trough),
        'max_drawdown_recovery': day(recovery),
        'best_day': {'date': day(rets.idxmax()), 'return': clean(rets.max())} if n else None,
        'worst_day': {'date': day(rets.idxmin()), 'return': clean(rets.min())} if n else None,
        'high': {'date': day(close.idxmax()), 'price': clean(close.max(), 4)} if len(close) else None,
        'low': {'date': day(close.idxmin()), 'price': clean(close.min(), 4)} if len(close) else None,
        'positive_days': clean((rets > 0).mean()) if n else None,
        'avg_volume': int(round(bars['Volume'].mean())) if len(bars) else None,
        'trading_days': int(len(bars)),
        'beta': (1.0 if is_benchmark else clean(beta(rets, benchmark_returns))) if has_benchmark else None,
        'excess_return': (clean(total - benchmark_total) if total is not None and benchmark_total is not None else None)
                         if has_benchmark else None,
    }

    monthly = monthly_returns(close, history.index, end)
    chart = weekly(bars) if weekly_bars else bars
    cidx = chart.index
    return {
        'symbol': symbol,
        'is_benchmark': is_benchmark,
        'prices': {
            'date': days(cidx),
            'open': clean_list(chart['Open'], 4),
            'high': clean_list(chart['High'], 4),
            'low': clean_list(chart['Low'], 4),
            'close': clean_list(chart['Close'], 4),
            'volume': [int(v) for v in chart['Volume']],
            'sma50': clean_list(sma50.reindex(cidx), 4),
            'sma200': clean_list(sma200.reindex(cidx), 4),
        },
        'summary': summary,
        'returns': return_stats(rets),
        'risk': {  # aligned with prices.date
            'rolling_volatility': clean_list(rolling_vol.reindex(cidx)),
            'drawdown': clean_list(drawdown(close).reindex(cidx)),
        },
        'seasonality': {'monthly': monthly, 'by_month': by_month(monthly)},
    }


def compare(closes, returns, summaries):
    """The compare section, from dicts keyed by symbol: in-range closes as charted (daily or weekly),
    daily returns, and summaries."""
    symbols = list(closes)
    frame = pd.DataFrame({s: closes[s] for s in symbols}).sort_index()
    cumulative = {s: clean_list(frame[s] / closes[s].iloc[0] - 1) for s in symbols}

    joined = pd.DataFrame({s: returns[s] for s in symbols}).dropna()
    if len(joined) >= 3:
        corr = joined.corr()
        matrix = [[clean(corr.loc[a, b]) for b in symbols] for a in symbols]
    else:
        matrix = [[None for _ in symbols] for _ in symbols]

    return {
        'cumulative_return': {'date': days(frame.index), 'values': cumulative},
        'correlation': {'symbols': symbols, 'matrix': matrix},
        'risk_return': [{'symbol': s, 'annual_return': summaries[s]['annual_return'],
                         'annual_volatility': summaries[s]['annual_volatility'], 'sharpe': summaries[s]['sharpe']}
                        for s in symbols],
    }
