import pytest

import legacy_html
import main

from conftest import images, invoke


def test_single_ticker_within_one_year_returns_four_charts(fake_yahoo):
    response = invoke("2025-01-02", "2025-06-30", "AAPL")
    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "text/html"
    assert len(images(response)) == 4


def test_single_ticker_across_years_adds_yearly_box_plot(fake_yahoo):
    response = invoke("2023-01-03", "2025-06-30", "AAPL")
    assert len(images(response)) == 5


def test_multiple_tickers_return_one_comparison_chart(fake_yahoo):
    response = invoke("2025-01-02", "2025-06-30", "AAPL,MSFT")
    assert len(images(response)) == 1
    assert fake_yahoo.calls == ["AAPL", "MSFT"]


def test_dates_accept_slashes(fake_yahoo):
    response = invoke("2025/01/02", "2025/06/30", "AAPL")
    assert len(images(response)) == 4


@pytest.mark.live
def test_live_yahoo_returns_charts():
    """Root cause of the 'An error occurred while sending the request.' bug: yfinance 0.2.28 got no data."""
    response = invoke("2025-01-02", "2025-06-30", "AAPL")
    assert len(images(response)) == 4


def test_price_charts_show_real_prices_not_standardized_values(fake_yahoo, charts):
    invoke("2025-01-02", "2025-06-30", "AAPL")  # fake AAPL closes run from about 100 to 300
    closing = next(c for c in charts if "Closing Stock Price Over Time" in c["titles"])
    y = closing["fig"].axes[0].lines[0].get_ydata()
    assert 90 < min(y) and max(y) < 330

    distribution = next(c for c in charts if "Distribution of Closing Stock Price" in c["titles"])
    lo, hi = distribution["fig"].axes[0].get_xlim()
    assert lo > 50 and hi < 400


def test_daily_returns_are_real_percentage_changes(fake_yahoo, charts):
    invoke("2025-01-02", "2025-06-30", "AAPL")  # fake data moves about 1 percent a day
    returns = next(c for c in charts if "Daily Returns" in c["titles"])
    lo, hi = returns["fig"].axes[0].get_xlim()
    assert -0.2 < lo < 0 < hi < 0.2


def test_comparison_keeps_high_priced_tickers(fake_yahoo, charts):
    # BRK-A trades around 400,000 to 600,000, the others under 400, so BRK-A is
    # only a fifth of the rows and sits far above the combined upper quartile.
    invoke("2025-01-02", "2025-06-30", "AAPL,MSFT,GOOG,NVDA,BRK-A")
    points = {line.get_label(): len(line.get_ydata()) for line in charts[0]["fig"].axes[0].lines}
    for ticker in ["AAPL", "MSFT", "GOOG", "NVDA", "BRK-A"]:
        assert points.get(ticker, 0) > 100, f"{ticker} has no plotted prices"


def test_single_ticker_keeps_a_sharp_run_up(fake_yahoo, charts, monkeypatch):
    # A stock that triples in the final weeks: those closes are real data, not outliers.
    original = fake_yahoo.history

    def run_up(self, start, end):
        df = original(self, start, end)
        df.loc[df.index[-15:], "Close"] *= 3
        return df

    monkeypatch.setattr(fake_yahoo, "history", run_up)
    invoke("2025-01-02", "2025-06-30", "AAPL")
    closing = next(c for c in charts if "Closing Stock Price Over Time" in c["titles"])
    assert max(closing["fig"].axes[0].lines[0].get_ydata()) > 700


def test_yearly_box_plot_is_drawn_on_its_own_figure(fake_yahoo, charts):
    invoke("2023-01-03", "2025-06-30", "AAPL")
    box = next(c for c in charts if "Closing Stock Prices by Year" in c["titles"])
    closing = next(c for c in charts if "Closing Stock Price Over Time" in c["titles"])
    assert box["fig"] is not closing["fig"]
    # The box plot axes should hold only box plot artists, not the daily price line.
    assert all(len(line.get_xdata()) < 100 for line in box["fig"].axes[0].lines)


@pytest.mark.parametrize("symbol", ["AAPL", "AAPL,MSFT"])
def test_figures_are_closed_after_each_request(fake_yahoo, symbol):
    # A warm Lambda reuses the process, so open figures pile up across requests.
    legacy_html.plt.close("all")
    for _ in range(3):
        invoke("2023-01-03", "2025-06-30", symbol)
    assert legacy_html.plt.get_fignums() == []


def test_tickers_are_trimmed_and_uppercased(fake_yahoo, charts):
    response = invoke("2025-01-02", "2025-06-30", " aapl , msft ")
    assert fake_yahoo.calls == ["AAPL", "MSFT"]
    assert len(images(response)) == 1
    labels = {line.get_label() for line in charts[0]["fig"].axes[0].lines if len(line.get_ydata())}
    assert {"AAPL", "MSFT"} <= labels


@pytest.mark.parametrize("symbol", ["AAPL,", "AAPL,aapl", ",AAPL, "])
def test_trailing_commas_and_duplicates_still_mean_one_ticker(fake_yahoo, symbol):
    response = invoke("2025-01-02", "2025-06-30", symbol)
    assert fake_yahoo.calls == ["AAPL"]
    assert len(images(response)) == 4  # single-ticker analysis, not a one-line comparison


def error_text(response):
    import re
    match = re.search(r"<div class='eda-error' role='alert'>(.*?)</div>", response["body"])
    return match.group(1) if match else None


@pytest.mark.parametrize(
    "start, end, symbol, message",
    [
        ("", "2025-06-30", "AAPL", "Please enter a start date, an end date and at least one ticker."),
        ("2025-01-02", "2025-06-30", " , ", "Please enter a start date, an end date and at least one ticker."),
        ("01-02-2025x", "2025-06-30", "AAPL", "Dates must be in YYYY-MM-DD format."),
        ("2025-02-30", "2025-06-30", "AAPL", "Dates must be in YYYY-MM-DD format."),
        ("2025-06-30", "2025-01-02", "AAPL", "The start date must be before the end date."),
        ("2025-01-02", "2025-01-02", "AAPL", "The start date must be before the end date."),
    ],
)
def test_bad_input_returns_a_readable_message(fake_yahoo, start, end, symbol, message):
    response = invoke(start, end, symbol)
    assert response["statusCode"] == 200
    assert error_text(response) == message
    assert images(response) == []


def test_missing_fields_return_a_readable_message(fake_yahoo):
    response = main.handler({}, None)
    assert error_text(response) == "Please enter a start date, an end date and at least one ticker."


def test_unknown_ticker_names_the_ticker(fake_yahoo):
    response = invoke("2025-01-02", "2025-06-30", "AAPL,ZZZZ")
    assert error_text(response) == (
        "No data found for ZZZZ between 2025-01-02 and 2025-06-30. Check the ticker symbol and the date range."
    )


def test_user_input_is_html_escaped(fake_yahoo):
    # The old website inserts the response with innerHTML, so the message must not carry markup.
    response = invoke("2025-01-02", "2025-06-30", "<IMG SRC=X ONERROR=ALERT(1)>")
    assert "<IMG" not in response["body"]
    assert "&lt;IMG SRC=X ONERROR=ALERT(1)&gt;" in error_text(response)


@pytest.mark.parametrize("end", ["2025-01-03", "2025-01-06"])
def test_very_short_ranges_never_crash(fake_yahoo, end):
    # One or two trading days: either charts or a readable message, never a Lambda error.
    response = invoke("2025-01-02", end, "AAPL")
    assert images(response) or error_text(response)


def test_unexpected_failures_return_a_generic_message(fake_yahoo, monkeypatch):
    def boom(self, start, end):
        raise ConnectionError("network down")

    monkeypatch.setattr(fake_yahoo, "history", boom)
    response = invoke("2025-01-02", "2025-06-30", "AAPL")
    assert error_text(response).startswith("Something went wrong while building the charts.")


def test_each_chart_carries_its_title_as_alt_text(fake_yahoo):
    import re

    single = invoke("2023-01-03", "2025-06-30", "AAPL")["body"]
    assert re.findall(r"alt='([^']*)'", single) == [
        "Closing Stock Price Over Time",
        "Correlation Between Stock Prices",
        "Distribution of Closing Stock Price",
        "Daily Returns",
        "Closing Stock Prices by Year",
    ]
    multi = invoke("2025-01-02", "2025-06-30", "AAPL,MSFT")["body"]
    assert re.findall(r"alt='([^']*)'", multi) == ["Closing Stock Price of Multiple Companies Over Time"]
