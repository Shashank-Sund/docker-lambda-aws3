import pytest

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
