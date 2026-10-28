import json
import os
import subprocess
import sys

import pytest

import main


def ask(start_date, end_date, symbol, **extra):
    return main.handler({"start_date": start_date, "end_date": end_date, "symbol": symbol, "format": "json", **extra}, None)


def body(response):
    return json.loads(response["body"])


def test_single_ticker_returns_json_with_spy_benchmark(fake_yahoo):
    response = ask("2025-01-02", "2025-06-30", "aapl")
    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "application/json"
    data = body(response)
    assert data["tickers"] == ["AAPL"]
    assert list(data["series"]) == ["AAPL", "SPY"]
    assert data["benchmark"] == "SPY"
    assert data["series"]["SPY"]["is_benchmark"] is True and data["series"]["AAPL"]["is_benchmark"] is False
    assert data["series"]["SPY"]["summary"]["beta"] == 1.0
    assert data["series"]["AAPL"]["summary"]["beta"] is not None
    assert data["compare"]["correlation"]["symbols"] == ["AAPL", "SPY"]
    assert "<img" not in response["body"]


def test_prices_cover_the_requested_range_only(fake_yahoo):
    data = body(ask("2025-01-02", "2025-06-30", "AAPL"))
    dates = data["series"]["AAPL"]["prices"]["date"]
    assert dates[0] == "2025-01-02" and dates[-1] < "2025-06-30"
    assert data["series"]["AAPL"]["summary"]["trading_days"] == len(dates)


def test_moving_averages_are_valid_from_the_first_day(fake_yahoo):
    prices = body(ask("2025-01-02", "2025-06-30", "AAPL"))["series"]["AAPL"]["prices"]
    assert prices["sma200"][0] is not None and prices["sma50"][0] is not None


def test_ranges_over_five_years_chart_weekly_bars(fake_yahoo):
    short = body(ask("2020-07-01", "2025-06-30", "AAPL"))
    long = body(ask("2015-01-02", "2025-06-30", "AAPL"))
    assert short["interval"] == "1d" and long["interval"] == "1wk"
    weekly = long["series"]["AAPL"]
    assert len(weekly["prices"]["date"]) < weekly["summary"]["trading_days"] / 4  # summary still counts days
    assert long["compare"]["cumulative_return"]["date"] == weekly["prices"]["date"]
    assert len(weekly["risk"]["drawdown"]) == len(weekly["prices"]["date"])


def test_multiple_tickers_keep_input_order(fake_yahoo):
    data = body(ask("2025-01-02", "2025-06-30", "MSFT, AAPL ,GOOG"))
    assert data["tickers"] == ["MSFT", "AAPL", "GOOG"]
    assert list(data["series"]) == ["MSFT", "AAPL", "GOOG", "SPY"]
    assert [p["symbol"] for p in data["compare"]["risk_return"]] == ["MSFT", "AAPL", "GOOG", "SPY"]
    assert set(data["compare"]["cumulative_return"]["values"]) == {"MSFT", "AAPL", "GOOG", "SPY"}


def test_entering_spy_does_not_duplicate_it(fake_yahoo):
    data = body(ask("2025-01-02", "2025-06-30", "AAPL,SPY"))
    assert list(data["series"]) == ["AAPL", "SPY"]
    assert data["series"]["SPY"]["is_benchmark"] is False
    assert data["benchmark"] == "SPY"
    assert fake_yahoo.calls.count("SPY") == 1


def test_missing_benchmark_still_returns_the_tickers(fake_yahoo, monkeypatch):
    monkeypatch.delitem(fake_yahoo.prices, "SPY")
    data = body(ask("2025-01-02", "2025-06-30", "AAPL"))
    assert data["benchmark"] is None
    assert list(data["series"]) == ["AAPL"]
    assert data["series"]["AAPL"]["summary"]["beta"] is None


@pytest.mark.parametrize(
    "start, end, symbol, message",
    [
        ("2025-01-02", "2025-06-30", "QXZQZ", "No data found for QXZQZ between 2025-01-02 and 2025-06-30."),
        ("2025-06-30", "2025-01-02", "AAPL", "The start date must be before the end date."),
        ("01-02-2025x", "2025-06-30", "AAPL", "Dates must be in YYYY-MM-DD format."),
        ("", "", "", "Please enter a start date, an end date and at least one ticker."),
        ("2025-01-02", "2025-06-30", ",".join("T%d" % i for i in range(11)), "Enter at most 10 tickers."),
        ("2000-01-03", "2025-06-30", "AAPL", "The date range can be at most 20 years."),
    ],
)
def test_input_errors_come_back_as_json(fake_yahoo, start, end, symbol, message):
    response = ask(start, end, symbol)
    assert response["statusCode"] == 400
    assert body(response)["error"].startswith(message)


def test_spy_does_not_count_toward_the_ticker_limit(fake_yahoo, monkeypatch):
    names = ["T%d" % i for i in range(10)]
    for n in names:
        monkeypatch.setitem(fake_yahoo.prices, n, (10.0, 20.0))
    data = body(ask("2025-01-02", "2025-06-30", ",".join(names + ["SPY"])))
    assert data["tickers"] == names + ["SPY"] and len(data["series"]) == 11


def test_exactly_twenty_years_is_allowed(fake_yahoo):
    assert ask("2005-06-30", "2025-06-30", "AAPL")["statusCode"] == 200


def test_unexpected_failures_return_a_generic_json_message(fake_yahoo, monkeypatch):
    def boom(self, start, end):
        raise ConnectionError("network down")

    monkeypatch.setattr(fake_yahoo, "history", boom)
    response = ask("2025-01-02", "2025-06-30", "AAPL")
    assert response["statusCode"] == 500
    assert body(response)["error"].startswith("Something went wrong")


def test_other_formats_still_get_the_html_page(fake_yahoo):
    response = main.handler({"start_date": "2025-01-02", "end_date": "2025-06-30", "symbol": "AAPL", "format": "png"}, None)
    assert response["headers"]["Content-Type"] == "text/html" and "<img" in response["body"]


def test_largest_request_fits_in_a_lambda_response(fake_yahoo):
    # The fake has 5 distinct tickers; with SPY that is 6 symbols over 20 years. Scale to 10 plus SPY.
    response = ask("2005-06-30", "2025-06-30", "AAPL,MSFT,GOOG,NVDA,BRK-A")
    count = len(body(response)["series"])
    per_symbol = len(json.dumps(response)) / count
    print("20 years: %.0f bytes per symbol, about %.1f MB for 10 tickers plus SPY" % (per_symbol, per_symbol * 11 / 1e6))
    assert count == 6
    assert per_symbol * 11 < 6_000_000  # Lambda's response limit is 6 MB


def test_json_requests_do_not_load_matplotlib():
    # A fresh interpreter without conftest (which imports the HTML module for its tests).
    script = (
        "import sys; sys.path.insert(0, %r)\n"
        "import pandas as pd, fetch, main\n"
        "class Fake:\n"
        "    def __init__(self, symbol): pass\n"
        "    def history(self, start, end):\n"
        "        i = pd.bdate_range(start, end, inclusive='left', tz='America/New_York')\n"
        "        return pd.DataFrame({'Open': 1.0, 'High': 1.0, 'Low': 1.0, 'Close': [100 + k for k in range(len(i))], 'Volume': 1}, index=i)\n"
        "fetch.yahooFinance.Ticker = Fake\n"
        "r = main.handler({'start_date': '2025-01-02', 'end_date': '2025-06-30', 'symbol': 'AAPL', 'format': 'json'}, None)\n"
        "assert r['statusCode'] == 200, r\n"
        "print('matplotlib' in sys.modules, 'seaborn' in sys.modules)\n"
    ) % os.path.dirname(main.__file__)
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True).stdout.split()
    assert out == ["False", "False"]


def test_yfinance_caches_are_created_before_parallel_fetches():
    # Without this, parallel fetches on a cold start raced to create the SQLite cache:
    # 2 of 6 cold starts failed with "database is locked" (one lost SPY, one returned 500).
    from yfinance import cache
    assert cache.get_tz_cache().initialised == 1
    assert cache.get_cookie_cache().initialised == 1


@pytest.mark.live
def test_live_yahoo_returns_json_for_several_tickers():
    response = ask("2025-01-02", "2025-06-30", "AAPL,MSFT,NVDA,GOOG,AMZN")
    data = body(response)
    assert response["statusCode"] == 200, data
    assert data["benchmark"] == "SPY" and len(data["series"]) == 6
    assert all(s["summary"]["trading_days"] > 100 for s in data["series"].values())
