# JSON response (`"format": "json"`)

The Lambda returns chart data instead of PNG charts when the request asks for it.
Requests without `format` get the original HTML page, unchanged.

## Request

```json
{"start_date": "2025-01-02", "end_date": "2025-06-30", "symbol": "AAPL,MSFT", "format": "json"}
```

- `start_date`, `end_date`: `YYYY-MM-DD` (slashes also accepted). `end_date` is exclusive, as in yfinance.
- `symbol`: comma-separated tickers; trimmed, uppercased, duplicates dropped. At most 10, not counting SPY.
- The range can be at most 20 years.

## Envelope

API Gateway (non-proxy integration) passes the Lambda result through, so the HTTP body is:

```json
{"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": "<JSON string>"}
```

Parse the envelope, then `JSON.parse(envelope.body)`. `statusCode` is 400 for input
errors and 500 for unexpected failures; the HTTP status itself is always 200.

## Error body

```json
{"error": "No data found for QXZQZ between 2025-01-02 and 2025-06-30. Check the ticker symbol and the date range."}
```

The message is written for the user and can be shown as is.

## Success body

```jsonc
{
  "version": 1,
  "start_date": "2025-01-02",          // as requested
  "end_date": "2025-06-30",
  "tickers": ["AAPL", "MSFT"],         // normalized, in input order
  "interval": "1d",                    // "1wk" when the range is over 5 years: chart series are weekly bars
                                       // (statistics are always computed from daily data)
  "benchmark_symbol": "SPY",
  "risk_free_rate": 0.0,               // used for Sharpe
  "trading_days_per_year": 252,

  "series": {                          // one entry per ticker, plus SPY (always present
    "AAPL": { ...TickerData },         // unless Yahoo failed for SPY; then benchmark is null)
    "SPY":  { ...TickerData }
  },
  "benchmark": "SPY",                  // key into series, or null if SPY could not be fetched

  "compare": {
    "cumulative_return": {             // close / first close in range - 1, on the union of bar dates (per interval)
      "date": ["2025-01-02", ...],
      "values": {"AAPL": [0.0, 0.0123, ...], "MSFT": [...], "SPY": [...]}   // null where a ticker has no bar
    },
    "correlation": {                   // Pearson correlation of daily returns, dates aligned (inner join)
      "symbols": ["AAPL", "MSFT", "SPY"],
      "matrix": [[1.0, 0.61, 0.72], [0.61, 1.0, 0.80], [0.72, 0.80, 1.0]]
    },
    "risk_return": [                   // one point per symbol including SPY
      {"symbol": "AAPL", "annual_return": 0.18, "annual_volatility": 0.27, "sharpe": 0.67}
    ]
  }
}
```

If the user enters SPY, it appears once in `series` and in `tickers`; `benchmark` is still `"SPY"`.

### TickerData

```jsonc
{
  "symbol": "AAPL",
  "is_benchmark": false,               // true only when SPY was added as the benchmark, not entered by the user

  "prices": {                          // columnar; one element per bar in [start_date, end_date): each trading
                                       // day, or with interval "1wk" each week, dated by its last trading day
                                       // (open = first, high = max, low = min, close = last, volume = sum)
    "date":   ["2025-01-02", ...],
    "open":   [243.26, ...],           // split- and dividend-adjusted (yfinance default)
    "high":   [...],
    "low":    [...],
    "close":  [...],
    "volume": [55740700, ...],         // integers
    "sma50":  [231.5, ...],            // 50 / 200 trading-day simple moving averages of close.
    "sma200": [210.1, ...]             // Computed with ~400 days of history before start_date, so they are
  },                                   // valid from the first day. null only when the ticker has less history.

  "summary": {
    "start_date": "2025-01-02", "end_date": "2025-06-27",   // first and last trading day returned
    "start_price": 243.26, "end_price": 201.08,             // closes
    "total_return": -0.1734,           // end_price / start_price - 1
    "annual_return": -0.31,            // (1 + total_return) ^ (252 / n_returns) - 1   (CAGR)
    "annual_volatility": 0.37,         // stdev(daily returns, ddof=1) * sqrt(252)
    "sharpe": -0.62,                   // (mean daily return * 252 - risk_free_rate) / annual_volatility
    "max_drawdown": -0.3036,           // most negative close / running peak - 1
    "max_drawdown_peak": "2025-01-02", // date of the peak before the worst trough
    "max_drawdown_trough": "2025-04-08",
    "max_drawdown_recovery": null,     // first date the close got back to the peak; null if it has not
    "best_day":  {"date": "2025-04-09", "return": 0.1533},
    "worst_day": {"date": "2025-04-03", "return": -0.0925},
    "high": {"date": "2025-01-02", "price": 243.26},      // highest / lowest close in range
    "low":  {"date": "2025-04-08", "price": 172.19},
    "positive_days": 0.48,             // share of daily returns > 0
    "avg_volume": 61234567,
    "trading_days": 122,               // number of price rows
    "beta": 1.21,                      // cov(r, r_SPY) / var(r_SPY) on aligned dates; 1.0 for SPY; null if no benchmark
    "excess_return": -0.21             // total_return - SPY total_return; 0.0 for SPY; null if no benchmark
  },

  "returns": {                         // statistics of daily returns close_t / close_{t-1} - 1 inside the range
                                       // (the first trading day has no return); always daily
    "histogram": {"edges": [-0.09, ...], "counts": [1, ...]},   // 40 bins: len(edges) = len(counts) + 1
    "mean": 0.0012, "median": 0.0008, "std": 0.023,
    "skew": 0.41,                      // sample skewness
    "kurtosis": 6.2,                   // excess kurtosis (normal = 0)
    "var_95": -0.034                   // 5th percentile daily return (historical value at risk)
  },

  "risk": {                            // aligned index for index with prices.date
    "rolling_volatility": [0.21, ...], // 30 trading-day stdev of daily returns * sqrt(252), using prior history
    "drawdown": [0.0, -0.01, ...]      // close / running daily peak (within range) - 1
  },

  "seasonality": {
    "monthly": [                       // month-end close / previous month-end close - 1;
      {"year": 2025, "month": 1, "return": 0.031, "partial": true},   // the first month is measured from the
      ...                                                              // first close in range, the last month to the
    ],                                                                 // last close; both are flagged partial when
    "by_month": [                                                      // the range starts or ends mid-month
      {"month": 1, "average": 0.012, "positive": 0.6, "years": 5}     // average over the years in range, share positive
    ]
  }
}
```

### Numbers

- Returns and ratios are fractions (0.0123 = 1.23%), rounded to 6 decimals; prices to 4.
- Any value that cannot be computed (too few days, flat prices) is `null`, never NaN. This includes the
  `best_day`, `worst_day`, `high` and `low` objects, which are `null` when there are no returns or prices.
- `seasonality.by_month` only counts full months, so a range shorter than a full calendar month has none.
- Statistics need at least 2 daily returns; with fewer they are `null`.

### Size

Ten tickers plus SPY over 20 years (weekly bars) is about 1.5 MB, well under Lambda's 6 MB
response limit; daily bars for 20 years would be about 8.7 MB, which is why long ranges are weekly.
