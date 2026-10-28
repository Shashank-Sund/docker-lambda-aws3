import os
import re
import sys

import numpy as np
import pandas as pd
import pytest

# main.py sits in image/src in the repo and in /var/task (next to tests/) in the test image.
HERE = os.path.dirname(os.path.abspath(__file__))
for path in (os.path.join(HERE, "..", "src"), os.path.join(HERE, "..")):
    sys.path.insert(0, os.path.abspath(path))

import main  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls the real Yahoo Finance API (run with -m live)")


def make_history(start, end, first_close=100.0, last_close=300.0):
    """Daily bars shaped like yfinance 1.x output: tz-aware index plus Dividends and Stock Splits."""
    index = pd.bdate_range(start=start, end=end, inclusive="left", tz="America/New_York", name="Date")
    rng = np.random.default_rng(7)
    close = np.linspace(first_close, last_close, len(index)) * (1 + rng.normal(0, 0.01, len(index)))
    return pd.DataFrame(
        {
            "Open": close * 0.995,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": rng.integers(1_000_000, 5_000_000, len(index)),
            "Dividends": 0.0,
            "Stock Splits": 0.0,
        },
        index=index,
    )


class FakeTicker:
    """Stands in for yfinance.Ticker. Known symbols get data; anything else returns an empty frame."""

    prices = {
        "AAPL": (100.0, 300.0),
        "MSFT": (200.0, 400.0),
        "GOOG": (150.0, 200.0),
        "NVDA": (100.0, 150.0),
        "BRK-A": (400000.0, 600000.0),
    }
    calls = []

    def __init__(self, symbol):
        self.symbol = symbol
        FakeTicker.calls.append(symbol)

    def history(self, start, end):
        if self.symbol not in self.prices:
            return make_history(start, end).iloc[0:0]  # no rows, same columns (what yfinance returns)
        first, last = self.prices[self.symbol]
        return make_history(start, end, first, last)


@pytest.fixture
def fake_yahoo(monkeypatch):
    FakeTicker.calls = []
    monkeypatch.setattr(main.yahooFinance, "Ticker", FakeTicker)
    return FakeTicker


@pytest.fixture
def charts(monkeypatch):
    """Records the axes titles and plotted y values of every figure the handler saves."""
    saved = []
    original_savefig = main.plt.savefig

    def recording_savefig(*args, **kwargs):
        fig = main.plt.gcf()
        saved.append({"titles": [ax.get_title() for ax in fig.axes], "fig": fig})
        return original_savefig(*args, **kwargs)

    monkeypatch.setattr(main.plt, "savefig", recording_savefig)
    return saved


def invoke(start_date, end_date, symbol):
    return main.handler({"start_date": start_date, "end_date": end_date, "symbol": symbol}, None)


def images(response):
    return re.findall(r"<img src='data:image/png;base64,[A-Za-z0-9+/=]+'", response["body"])
