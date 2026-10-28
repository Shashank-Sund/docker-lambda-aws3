"""The dashboard's response: chart data and statistics as JSON (docs/json-api.md)."""
from concurrent.futures import ThreadPoolExecutor
import json
import traceback

import pandas as pd

import fetch
from fetch import InputError
import metrics

BENCHMARK = 'SPY'
MAX_TICKERS = 10
MAX_YEARS = 20


def respond(status, body):
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(body, allow_nan=False, separators=(',', ':')),
    }


def handle(event):
    try:
        return respond(200, build(event))
    except InputError as e:
        return respond(400, {'error': str(e)})
    except Exception:
        traceback.print_exc()  # full detail goes to CloudWatch Logs
        return respond(500, {'error': "Something went wrong while analyzing the data. Please try again, or try a different date range."})


def _download(symbol, start, end):
    """Bars from (start - lookback) to end, so moving averages are valid from start."""
    return metrics.daily_bars(fetch.get_history(symbol, start - pd.Timedelta(days=metrics.LOOKBACK_DAYS), end))


def _benchmark(start, end):
    """SPY bars, or None if Yahoo has nothing; the dashboard still works without a benchmark."""
    try:
        bars = _download(BENCHMARK, start, end)
    except Exception:
        traceback.print_exc()
        return None
    return bars if not metrics.in_range(bars, start, end).empty else None


def build(event):
    start, end, symbols = fetch.parse_request(event)
    if len(symbols) > MAX_TICKERS:
        raise InputError("Enter at most {} tickers.".format(MAX_TICKERS))
    if end > start + pd.DateOffset(years=MAX_YEARS):
        raise InputError("The date range can be at most {} years.".format(MAX_YEARS))

    # One Yahoo request per ticker, run in parallel; SPY is fetched once even if entered.
    with ThreadPoolExecutor(max_workers=6) as pool:
        bench_job = None if BENCHMARK in symbols else pool.submit(_benchmark, start, end)
        histories = list(pool.map(lambda s: _download(s, start, end), symbols))
        bench_bars = histories[symbols.index(BENCHMARK)] if BENCHMARK in symbols else bench_job.result()

    in_range = [metrics.in_range(h, start, end) for h in histories]
    fetch.require_data(symbols, in_range, start, end)

    bench_returns = bench_total = None
    if bench_bars is not None:
        bench_close = metrics.in_range(bench_bars, start, end)['Close']
        bench_returns = metrics.daily_returns(bench_close)
        bench_total = bench_close.iloc[-1] / bench_close.iloc[0] - 1

    weekly = metrics.use_weekly(start, end)

    def data(symbol, history, is_benchmark=False):
        return metrics.ticker_data(symbol, history, start, end, is_benchmark=is_benchmark,
                                   benchmark_returns=bench_returns, benchmark_total=bench_total, weekly_bars=weekly)

    series = {s: data(s, h) for s, h in zip(symbols, histories)}
    if bench_bars is not None and BENCHMARK not in symbols:
        series[BENCHMARK] = data(BENCHMARK, bench_bars, is_benchmark=True)

    bars_by_symbol = dict(zip(symbols, in_range))
    if BENCHMARK in series and BENCHMARK not in symbols:
        bars_by_symbol[BENCHMARK] = metrics.in_range(bench_bars, start, end)
    closes = {s: b['Close'] for s, b in bars_by_symbol.items()}
    returns = {s: metrics.daily_returns(c) for s, c in closes.items()}  # daily, for correlation
    charted = {s: metrics.chart_close(c, weekly) for s, c in closes.items()}

    return {
        'version': 1,
        'start_date': start.strftime('%Y-%m-%d'),
        'end_date': end.strftime('%Y-%m-%d'),
        'tickers': symbols,
        'interval': '1wk' if weekly else '1d',
        'benchmark_symbol': BENCHMARK,
        'risk_free_rate': metrics.RISK_FREE_RATE,
        'trading_days_per_year': metrics.TRADING_DAYS,
        'series': series,
        'benchmark': BENCHMARK if bench_bars is not None else None,
        'compare': metrics.compare(charted, returns, {s: d['summary'] for s, d in series.items()}),
    }
