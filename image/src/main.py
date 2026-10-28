import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend: renders to PNG only, faster import
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import re
import yfinance as yahooFinance
import html as html_lib
import traceback

# Lambda's filesystem is read-only except /tmp; keep yfinance's timezone cache there
# so warm invocations reuse it.
yahooFinance.set_tz_cache_location('/tmp/py-yfinance')


class InputError(Exception):
    """A problem with the request that the user can fix; the message is shown to them."""


def error_response(message):
    # Same envelope and HTML document shape as the charts, so the website shows the
    # message in its response box. Single-quoted attribute: the body is JSON-encoded.
    body = "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'><title>Error</title></head>" \
           "<body><div class='eda-error' role='alert'>{}</div></body></html>".format(html_lib.escape(message))
    return {'statusCode': 200, 'body': body, 'headers': {'Content-Type': 'text/html'}}


def handler(event, context):
    try:
        return analyze(event)
    except InputError as e:
        return error_response(str(e))
    except Exception:
        traceback.print_exc()  # full detail goes to CloudWatch Logs
        return error_response("Something went wrong while building the charts. Please try again, or try a different date range.")


def analyze(event):

    # gets in variables from event
    start_date = str(event.get('start_date') or '').strip()
    end_date = str(event.get('end_date') or '').strip()
    # trims, uppercases, drops empty entries and duplicates (keeps input order)
    symbol = list(dict.fromkeys(s.strip().upper() for s in str(event.get('symbol') or '').split(',') if s.strip()))

    if not start_date or not end_date or not symbol:
        raise InputError("Please enter a start date, an end date and at least one ticker.")

    # separates the year, month, and day for both the start and end dates
    pattern = r'[/-]'
    try:
        startyear,startmonth,startday = [int(part) for part in re.split(pattern, start_date)]
        endyear,endmonth,endday = [int(part) for part in re.split(pattern, end_date)]
        startDate = datetime.datetime(startyear, startmonth, startday)
        endDate = datetime.datetime(endyear, endmonth, endday)
    except ValueError:
        raise InputError("Dates must be in YYYY-MM-DD format.")

    if startDate >= endDate:
        raise InputError("The start date must be before the end date.")

    def get_data(symbols, start, end):

        df_list = []
        for current_symbol in symbols:
            stock_ticker = yahooFinance.Ticker(current_symbol.upper()) # get stock ticker
            df = stock_ticker.history(start=start, end=end) # get data from yahoo

            # gets all the timestamps, converts them to date types, puts them in a list
            ts_list = []
            for i in range(0,len(df)):
                ts_list.append(df.index[i].date())
                
            df = df.assign(date = ts_list) # create a new column 'date' with the new date types
            df['symbol'] = current_symbol # create new column 'symbol' containing the ticker symbol

            df_list.append(df) # add dataframe to list

        return df_list

    df_list = get_data(symbol, startDate, endDate)
    missing = [s for s, d in zip(symbol, df_list) if d.empty]
    if missing:
        raise InputError("No data found for {} between {} and {}. Check the ticker symbol and the date range.".format(
            ', '.join(missing), startDate.date(), endDate.date()))

    df = pd.concat(df_list) # concat all data together from method

    # Rename columns
    df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume', 'trade_count': 'Trade_count', 'vwap': 'Vwap', 'date': 'Date', 'symbol': 'Symbol',}, inplace=True)
    
    # No outlier filter on Close: market closes are real data. (An IQR cut over
    # all tickers combined dropped run-ups and whole high-priced tickers.)

    # Charts use real prices. (Standardizing them made the axes read as z-scores
    # while labeled as prices; the correlation heatmap is unaffected by scaling.)

    if len(symbol) == 1: # USED FOR SINGLE-STOCK ANALYSIS

        # Line chart of closing stock price over time
        plt.figure(figsize=(10, 6))
        sns.lineplot(x='Date', y='Close', data=df)
        plt.title('Closing Stock Price Over Time')
        plt.xlabel('Date')
        plt.ylabel('Closing Stock Price')
        # Save figure as png
        img_data = io.BytesIO()
        plt.savefig(img_data, format='png')
        plt.close()  # free the figure; warm Lambdas reuse this process
        # encodes message
        encodedsub = base64.b64encode(img_data.getvalue()).decode('utf-8')
        encoded = "<img src=\'data:image/png;base64,{}\' alt=\'Closing Stock Price Over Time\'>".format(encodedsub)

        if startyear != endyear:
            # Box plot of Closing Stock Prices by Year'
            df['Year'] = [x.year for x in df['Date']]
            plt.figure(figsize=(10, 6))
            sns.boxplot(x='Year', y='Close', data=df)
            plt.title('Closing Stock Prices by Year')
            plt.xlabel('Year')
            plt.ylabel('Closing Stock Price')
            # Save figure as png
            img_data2 = io.BytesIO()
            plt.savefig(img_data2, format='png')
            plt.close()  # free the figure; warm Lambdas reuse this process
            # encodes message
            encoded2sub = base64.b64encode(img_data2.getvalue()).decode('utf-8')
            encoded2 = "<img src=\'data:image/png;base64,{}\' alt=\'Closing Stock Prices by Year\'>".format(encoded2sub)
        else:
            encoded2 = "<br>"

        # Create a heatmap of the correlation between stock prices
        corr = df[['Open', 'High', 'Low', 'Close']].corr()
        plt.figure(figsize=(8,8))
        sns.heatmap(corr, annot=True, cmap='coolwarm')
        plt.title('Correlation Between Stock Prices')
        # Save figure as png
        img_data3 = io.BytesIO()
        plt.savefig(img_data3, format='png')
        plt.close()  # free the figure; warm Lambdas reuse this process
        # encodes message
        encoded3sub = base64.b64encode(img_data3.getvalue()).decode('utf-8')
        encoded3 = "<img src=\'data:image/png;base64,{}\' alt=\'Correlation Between Stock Prices\'>".format(encoded3sub)

        # Distribution of Closing Stock Price
        plt.figure(figsize=(10, 6))
        sns.histplot(df['Close'], kde=True)
        plt.title('Distribution of Closing Stock Price')
        plt.xlabel('Closing Stock Price')
        plt.ylabel('Frequency')
        # Save figure as png
        img_data4 = io.BytesIO()
        plt.savefig(img_data4, format='png')
        plt.close()  # free the figure; warm Lambdas reuse this process
        # encodes message
        encoded4sub = base64.b64encode(img_data4.getvalue()).decode('utf-8')
        encoded4 = "<img src=\'data:image/png;base64,{}\' alt=\'Distribution of Closing Stock Price\'>".format(encoded4sub)

        # Create a histogram of the daily returns
        plt.figure(figsize=(12,6))
        sns.histplot(df['Close'].pct_change().dropna(), bins=100, kde=True)
        plt.title('Daily Returns')
        plt.xlabel('Daily Return')
        plt.ylabel('Frequency')
        # Save figure as png
        img_data5 = io.BytesIO()
        plt.savefig(img_data5, format='png')
        plt.close()  # free the figure; warm Lambdas reuse this process
        # encodes message
        encoded5sub = base64.b64encode(img_data5.getvalue()).decode('utf-8')
        encoded5 = "<img src=\'data:image/png;base64,{}\' alt=\'Daily Returns\'>".format(encoded5sub)

        html = """ <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>My Basic HTML Page</title>
    </head>
    <body>{}{}{}{}{}</body>
    </html>
        """.format(encoded,encoded3,encoded4,encoded5,encoded2)
        
        return {
            'statusCode': 200,
            'body': html,
            'headers':{
                'Content-Type': 'text/html'
            }
        }
    else: # USED FOR MULTI-STOCK ANALYSIS

        # Line chart of closing stock price for multiple companies over time
        companies = symbol
        plt.figure(figsize=(10, 6))
        for company in companies:
            company_df = df[df['Symbol']==company]
            sns.lineplot(x='Date', y='Close', data=company_df, label=company)
        plt.title('Closing Stock Price of Multiple Companies Over Time')
        plt.xlabel('Date')
        plt.ylabel('Closing Stock Price')
        # Save figure as png
        img_data7 = io.BytesIO()
        plt.savefig(img_data7, format='png')
        plt.close()  # free the figure; warm Lambdas reuse this process
        # encodes message
        encoded7sub = base64.b64encode(img_data7.getvalue()).decode('utf-8')
        encoded7 = "<img src=\'data:image/png;base64,{}\' alt=\'Closing Stock Price of Multiple Companies Over Time\'>".format(encoded7sub)

        html = """ <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>My Basic HTML Page</title>
    </head>
    <body>{}</body>
    </html>
        """.format(encoded7)
        
        return {
            'statusCode': 200,
            'body': html,
            'headers':{
                'Content-Type': 'text/html'
            }
        }
