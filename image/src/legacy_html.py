"""The original response: an HTML page of matplotlib PNG charts, used by the 2023 website."""
import base64
import html as html_lib
import io

import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend: renders to PNG only, faster import
import matplotlib.pyplot as plt
import seaborn as sns


def error_response(message):
    # Same envelope and HTML document shape as the charts, so the website shows the
    # message in its response box. Single-quoted attribute: the body is JSON-encoded.
    body = "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'><title>Error</title></head>" \
           "<body><div class='eda-error' role='alert'>{}</div></body></html>".format(html_lib.escape(message))
    return {'statusCode': 200, 'body': body, 'headers': {'Content-Type': 'text/html'}}


def _save_png(alt):
    """Saves the current figure as an <img> tag and closes it (warm Lambdas reuse this process)."""
    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    plt.close()
    encoded = base64.b64encode(img_data.getvalue()).decode('utf-8')
    return "<img src=\'data:image/png;base64,{}\' alt=\'{}\'>".format(encoded, alt)


def _page(body):
    html = """ <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>My Basic HTML Page</title>
    </head>
    <body>{}</body>
    </html>
        """.format(body)
    return {
        'statusCode': 200,
        'body': html,
        'headers': {
            'Content-Type': 'text/html'
        }
    }


def render(symbols, frames, start, end):
    df = pd.concat(frames)  # concat all data together
    df.rename(columns={'date': 'Date', 'symbol': 'Symbol'}, inplace=True)

    # No outlier filter on Close: market closes are real data. (An IQR cut over
    # all tickers combined dropped run-ups and whole high-priced tickers.)

    # Charts use real prices. (Standardizing them made the axes read as z-scores
    # while labeled as prices; the correlation heatmap is unaffected by scaling.)

    if len(symbols) == 1:  # USED FOR SINGLE-STOCK ANALYSIS

        # Line chart of closing stock price over time
        plt.figure(figsize=(10, 6))
        sns.lineplot(x='Date', y='Close', data=df)
        plt.title('Closing Stock Price Over Time')
        plt.xlabel('Date')
        plt.ylabel('Closing Stock Price')
        encoded = _save_png('Closing Stock Price Over Time')

        if start.year != end.year:
            # Box plot of Closing Stock Prices by Year
            df['Year'] = [x.year for x in df['Date']]
            plt.figure(figsize=(10, 6))
            sns.boxplot(x='Year', y='Close', data=df)
            plt.title('Closing Stock Prices by Year')
            plt.xlabel('Year')
            plt.ylabel('Closing Stock Price')
            encoded2 = _save_png('Closing Stock Prices by Year')
        else:
            encoded2 = "<br>"

        # Create a heatmap of the correlation between stock prices
        corr = df[['Open', 'High', 'Low', 'Close']].corr()
        plt.figure(figsize=(8, 8))
        sns.heatmap(corr, annot=True, cmap='coolwarm')
        plt.title('Correlation Between Stock Prices')
        encoded3 = _save_png('Correlation Between Stock Prices')

        # Distribution of Closing Stock Price
        plt.figure(figsize=(10, 6))
        sns.histplot(df['Close'], kde=True)
        plt.title('Distribution of Closing Stock Price')
        plt.xlabel('Closing Stock Price')
        plt.ylabel('Frequency')
        encoded4 = _save_png('Distribution of Closing Stock Price')

        # Create a histogram of the daily returns
        plt.figure(figsize=(12, 6))
        sns.histplot(df['Close'].pct_change().dropna(), bins=100, kde=True)
        plt.title('Daily Returns')
        plt.xlabel('Daily Return')
        plt.ylabel('Frequency')
        encoded5 = _save_png('Daily Returns')

        return _page(encoded + encoded3 + encoded4 + encoded5 + encoded2)

    else:  # USED FOR MULTI-STOCK ANALYSIS

        # Line chart of closing stock price for multiple companies over time
        plt.figure(figsize=(10, 6))
        for company in symbols:
            company_df = df[df['Symbol'] == company]
            sns.lineplot(x='Date', y='Close', data=company_df, label=company)
        plt.title('Closing Stock Price of Multiple Companies Over Time')
        plt.xlabel('Date')
        plt.ylabel('Closing Stock Price')
        encoded7 = _save_png('Closing Stock Price of Multiple Companies Over Time')

        return _page(encoded7)
