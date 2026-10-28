"""Each metric is checked against a hand-worked answer or an independent numpy calculation."""
import json
import math

import numpy as np
import pandas as pd
import pytest

import metrics

SQRT252 = math.sqrt(252)


def bars(closes, start="2025-01-02", volume=1000):
    index = pd.bdate_range(start=start, periods=len(closes), name="date")
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({"Open": closes, "High": closes * 1.01, "Low": closes * 0.99, "Close": closes,
                         "Volume": volume}, index=index)


def random_walk(n, seed=1, start="2023-01-02", drift=0.0005, vol=0.02):
    rng = np.random.default_rng(seed)
    return bars(100 * np.cumprod(1 + rng.normal(drift, vol, n)), start=start)


def data_for(frame, start=None, end=None, **kwargs):
    start = start or frame.index[0]
    end = end or frame.index[-1] + pd.Timedelta(days=1)
    return metrics.ticker_data("TEST", frame, start, end, **kwargs)


# ---------- hand-worked example: 100, 110, 99, 121 ----------

@pytest.fixture
def small():
    return data_for(bars([100, 110, 99, 121]))


def test_daily_returns_and_total_return(small):
    assert small["returns"]["value"] == [0.1, -0.1, pytest.approx(0.222222, abs=1e-6)]
    assert small["returns"]["date"] == small["prices"]["date"][1:]
    assert small["summary"]["total_return"] == pytest.approx(0.21)


def test_drawdown_peak_trough_and_recovery(small):
    s = small["summary"]
    assert small["risk"]["drawdown"] == [0.0, 0.0, pytest.approx(-0.1), 0.0]
    assert s["max_drawdown"] == pytest.approx(-0.1)
    dates = small["prices"]["date"]
    assert (s["max_drawdown_peak"], s["max_drawdown_trough"], s["max_drawdown_recovery"]) == (dates[1], dates[2], dates[3])


def test_best_worst_high_low_and_positive_days(small):
    s, dates = small["summary"], small["prices"]["date"]
    assert s["best_day"] == {"date": dates[3], "return": pytest.approx(0.222222, abs=1e-6)}
    assert s["worst_day"] == {"date": dates[2], "return": pytest.approx(-0.1)}
    assert s["high"] == {"date": dates[3], "price": 121.0}
    assert s["low"] == {"date": dates[2], "price": 99.0}
    assert s["positive_days"] == pytest.approx(2 / 3, abs=1e-6)
    assert (s["start_price"], s["end_price"], s["trading_days"]) == (100.0, 121.0, 4)


def test_annual_return_compounds_over_252_trading_days(small):
    assert small["summary"]["annual_return"] == pytest.approx(1.21 ** (252 / 3) - 1, rel=1e-6)


def test_volatility_and_sharpe_with_zero_risk_free_rate(small):
    r = np.array([0.1, -0.1, 0.22222222])
    vol = np.std(r, ddof=1) * SQRT252
    assert small["summary"]["annual_volatility"] == pytest.approx(vol, rel=1e-5)
    assert small["summary"]["sharpe"] == pytest.approx(r.mean() * 252 / vol, rel=1e-5)


def test_drawdown_that_never_recovers():
    s = data_for(bars([100, 80, 90]))["summary"]
    assert s["max_drawdown"] == pytest.approx(-0.2)
    assert s["max_drawdown_recovery"] is None


def test_rising_prices_have_no_drawdown():
    s = data_for(bars([100, 101, 102, 103]))["summary"]
    assert s["max_drawdown"] == 0.0
    assert s["max_drawdown_peak"] is None and s["max_drawdown_trough"] is None


# ---------- independent numpy calculations on a random walk ----------

def test_distribution_statistics_match_numpy():
    frame = random_walk(300)
    d = data_for(frame)
    r = frame["Close"].to_numpy()
    r = r[1:] / r[:-1] - 1
    n, mean, sd = len(r), r.mean(), r.std(ddof=1)
    m2, m3, m4 = ((r - mean) ** 2).mean(), ((r - mean) ** 3).mean(), ((r - mean) ** 4).mean()
    g1 = m3 / m2 ** 1.5
    skew = g1 * math.sqrt(n * (n - 1)) / (n - 2)
    g2 = m4 / m2 ** 2 - 3
    kurt = (n - 1) / ((n - 2) * (n - 3)) * ((n + 1) * g2 + 6)
    ret = d["returns"]
    assert ret["mean"] == pytest.approx(mean, abs=1e-6)
    assert ret["median"] == pytest.approx(np.median(r), abs=1e-6)
    assert ret["std"] == pytest.approx(sd, abs=1e-6)
    assert ret["skew"] == pytest.approx(skew, abs=1e-5)
    assert ret["kurtosis"] == pytest.approx(kurt, abs=1e-5)
    assert ret["var_95"] == pytest.approx(np.percentile(r, 5), abs=1e-6)


def test_histogram_has_40_bins_covering_every_return():
    d = data_for(random_walk(300))
    h = d["returns"]["histogram"]
    assert len(h["counts"]) == 40 and len(h["edges"]) == 41
    assert sum(h["counts"]) == len(d["returns"]["value"])
    assert h["edges"][0] <= min(d["returns"]["value"]) and h["edges"][-1] >= max(d["returns"]["value"])


def test_moving_averages_use_history_before_start():
    frame = random_walk(500)
    start = frame.index[300]
    d = data_for(frame, start=start)
    close = frame["Close"].to_numpy()
    assert d["prices"]["date"][0] == start.strftime("%Y-%m-%d")
    assert d["prices"]["sma200"][0] == pytest.approx(close[101:301].mean(), abs=1e-4)
    assert d["prices"]["sma50"][0] == pytest.approx(close[251:301].mean(), abs=1e-4)
    assert None not in d["prices"]["sma200"]


def test_moving_average_is_null_without_enough_history():
    d = data_for(random_walk(120))
    assert d["prices"]["sma200"][0] is None and d["prices"]["sma200"][-1] is None
    assert d["prices"]["sma50"][48] is None and d["prices"]["sma50"][49] is not None


def test_rolling_volatility_is_30_day_annualized_stdev():
    frame = random_walk(200)
    d = data_for(frame, start=frame.index[100])
    close = frame["Close"].to_numpy()
    r = close[1:] / close[:-1] - 1  # r[i] is the return into day i+1
    expected = np.std(r[70:100], ddof=1) * SQRT252  # 30 returns ending on day 100
    assert d["risk"]["rolling_volatility"][0] == pytest.approx(expected, abs=1e-6)


def test_beta_against_benchmark():
    bench = random_walk(250, seed=3)
    rb = bench["Close"].pct_change()
    stock_close = 50 * np.cumprod(1 + np.nan_to_num(2 * rb.to_numpy()))  # exactly twice the benchmark's moves
    stock = bars(stock_close, start=bench.index[0].strftime("%Y-%m-%d"))
    b = data_for(bench, is_benchmark=True, benchmark_returns=rb.iloc[1:], benchmark_total=0.1)
    s = data_for(stock, benchmark_returns=rb.iloc[1:], benchmark_total=b["summary"]["total_return"])
    assert s["summary"]["beta"] == pytest.approx(2.0, abs=1e-6)
    assert b["summary"]["beta"] == 1.0
    assert s["summary"]["excess_return"] == pytest.approx(s["summary"]["total_return"] - b["summary"]["total_return"], abs=1e-6)


def test_no_benchmark_means_null_beta():
    s = data_for(random_walk(50))["summary"]
    assert s["beta"] is None and s["excess_return"] is None


# ---------- seasonality ----------

def test_monthly_returns_from_month_end_closes():
    index = pd.bdate_range("2025-01-01", "2025-03-31", name="date")
    frame = bars(np.linspace(100, 160, len(index)), start="2025-01-01")
    d = data_for(frame, start="2025-01-01", end="2025-04-01")
    close = frame["Close"]
    jan, feb, mar = close["2025-01"].iloc[-1], close["2025-02"].iloc[-1], close["2025-03"].iloc[-1]
    monthly = d["seasonality"]["monthly"]
    assert [(m["year"], m["month"]) for m in monthly] == [(2025, 1), (2025, 2), (2025, 3)]
    assert monthly[0]["return"] == pytest.approx(jan / close.iloc[0] - 1, abs=1e-6)
    assert monthly[1]["return"] == pytest.approx(feb / jan - 1, abs=1e-6)
    assert monthly[2]["return"] == pytest.approx(mar / feb - 1, abs=1e-6)
    assert [m["partial"] for m in monthly] == [False, False, False]


def test_partial_months_at_both_ends():
    frame = bars(np.linspace(100, 160, 80), start="2024-12-02")
    d = data_for(frame, start="2025-01-15", end="2025-03-15")
    assert [m["partial"] for m in d["seasonality"]["monthly"]] == [True, False, True]


def test_by_month_averages_full_months_only():
    frame = random_walk(800, start="2022-01-03")
    d = data_for(frame, start="2022-01-03", end="2025-01-01")
    jan = [m["return"] for m in d["seasonality"]["monthly"] if m["month"] == 1]
    row = next(r for r in d["seasonality"]["by_month"] if r["month"] == 1)
    assert row["years"] == len(jan)
    assert row["average"] == pytest.approx(sum(jan) / len(jan), abs=1e-6)
    assert row["positive"] == pytest.approx(sum(v > 0 for v in jan) / len(jan), abs=1e-6)


# ---------- compare ----------

def test_compare_cumulative_return_correlation_and_risk_return():
    a = random_walk(100, seed=1)
    ra = a["Close"].pct_change()
    b = bars(100 * np.cumprod(1 - np.nan_to_num(ra.to_numpy())), start=a.index[0].strftime("%Y-%m-%d"))  # mirror moves
    da, db = data_for(a), data_for(b)
    closes = {"A": a["Close"], "B": b["Close"].iloc[5:]}  # B starts later: nulls on the union of dates
    returns = {"A": ra.iloc[1:], "B": b["Close"].pct_change().iloc[1:]}
    out = metrics.compare(closes, returns, {"A": da["summary"], "B": db["summary"]})
    cum = out["cumulative_return"]
    assert cum["values"]["A"][0] == 0.0 and cum["values"]["B"][:5] == [None] * 5 and cum["values"]["B"][5] == 0.0
    assert cum["values"]["A"][-1] == pytest.approx(a["Close"].iloc[-1] / a["Close"].iloc[0] - 1, abs=1e-6)
    assert out["correlation"]["symbols"] == ["A", "B"]
    assert out["correlation"]["matrix"][0][1] == pytest.approx(-1.0, abs=1e-6)
    assert out["risk_return"][0] == {"symbol": "A", "annual_return": da["summary"]["annual_return"],
                                     "annual_volatility": da["summary"]["annual_volatility"], "sharpe": da["summary"]["sharpe"]}


# ---------- edge cases ----------

@pytest.mark.parametrize("closes", [[100.0], [100.0, 101.0], [100.0, 100.0, 100.0]])
def test_tiny_or_flat_ranges_give_nulls_not_nan(closes):
    d = data_for(bars(closes))
    json.dumps(d, allow_nan=False)  # raises on NaN or infinity
    if len(closes) < 3:
        assert d["summary"]["annual_volatility"] is None and d["returns"]["skew"] is None
    else:
        assert d["summary"]["sharpe"] is None  # zero volatility


def test_volumes_are_integers_and_prices_rounded():
    d = data_for(bars([100.123456, 101.987654], volume=1234))
    assert d["prices"]["close"] == [100.1235, 101.9877]
    assert d["prices"]["volume"] == [1234, 1234] and isinstance(d["summary"]["avg_volume"], int)
