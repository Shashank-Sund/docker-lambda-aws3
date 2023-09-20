import numpy as np
import datetime
import pandas as pd
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import json
import boto3
import io
import base64
import re
import yfinance as yahooFinance

def handler(event, context):

    # gets in variables from event
    start_date = event['start_date']
    end_date = event['end_date']
    symbol = event['symbol'].split(',')

    # separates the year, month, and day for both the start and end dates
    pattern = r'[/-]'
    startyear,startmonth,startday = int(re.split(pattern, start_date)[0]), int(re.split(pattern, start_date)[1]), int(re.split(pattern, start_date)[2])
    endyear,endmonth,endday = int(re.split(pattern, end_date)[0]), int(re.split(pattern, end_date)[1]), int(re.split(pattern, end_date)[2])

    startDate = datetime.datetime(startyear, startmonth, startday) # startDate , as per our convenience we can modify
    endDate = datetime.datetime(endyear, endmonth, endday) # endDate , as per our convenience we can modify

    def get_data(symbols, start, end):

        df_list = []
        for current_symbol in symbols:
            stock_ticker = yahooFinance.Ticker(current_symbol) # get stock ticker
            df = stock_ticker.history(start=start, end=end) # get data from yahoo

            # gets all the timestamps, converts them to date types, puts them in a list
            ts_list = []
            for i in range(0,len(df)):
                ts_list.append(df.index[i].date())
                
            df = df.assign(date = ts_list) # create a new column 'date' with the new date types
            df['symbol'] = current_symbol # create new column 'symbol' containing the ticker symbol

            df_list.append(df) # add dataframe to list

        return df_list

    df = pd.concat(get_data(symbol, startDate, endDate)) # concat all data together from method
    
    # Rename columns
    df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume', 'trade_count': 'Trade_count', 'vwap': 'Vwap', 'date': 'Date', 'symbol': 'Symbol',}, inplace=True)
    
    # Handle outliers
    q1 = df['Close'].quantile(0.25)
    q3 = df['Close'].quantile(0.75)
    iqr = q3 - q1
    upper_bound = q3 + 1.5 * iqr
    df = df[df['Close'] <= upper_bound]
    
    # # fits data using scaler
    scaler = StandardScaler()
    df[['Open', 'High', 'Low', 'Close', 'Volume']] = scaler.fit_transform(df[['Open', 'High', 'Low', 'Close', 'Volume']]) 

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
        # encodes message
        encodedsub = base64.b64encode(img_data.getvalue()).decode('utf-8')
        encoded = "<img src=\'data:image/png;base64,{}\'>".format(encodedsub)

        if startyear != endyear:
            # Box plot of Closing Stock Prices by Year'
            df['Year'] = [x.year for x in df['Date']]
            sns.boxplot(x='Year', y='Close', data=df)
            plt.title('Closing Stock Prices by Year')
            plt.xlabel('Year')
            plt.ylabel('Closing Stock Price')
            # Save figure as png
            img_data2 = io.BytesIO()
            plt.savefig(img_data2, format='png')
            # encodes message
            encoded2sub = base64.b64encode(img_data2.getvalue()).decode('utf-8')
            encoded2 = "<img src=\'data:image/png;base64,{}\'>".format(encoded2sub)
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
        # encodes message
        encoded3sub = base64.b64encode(img_data3.getvalue()).decode('utf-8')
        encoded3 = "<img src=\'data:image/png;base64,{}\'>".format(encoded3sub)

        # Distribution of Closing Stock Price
        plt.figure(figsize=(10, 6))
        sns.histplot(df['Close'], kde=True)
        plt.title('Distribution of Closing Stock Price')
        plt.xlabel('Closing Stock Price')
        plt.ylabel('Frequency')
        # Save figure as png
        img_data4 = io.BytesIO()
        plt.savefig(img_data4, format='png')
        # encodes message
        encoded4sub = base64.b64encode(img_data4.getvalue()).decode('utf-8')
        encoded4 = "<img src=\'data:image/png;base64,{}\'>".format(encoded4sub)

        # Create a histogram of the daily returns
        plt.figure(figsize=(12,6))
        sns.histplot(df['Close'].pct_change().dropna(), bins=100, kde=True)
        plt.title('Daily Returns')
        plt.xlabel('Daily Return')
        plt.ylabel('Frequency')
        # Save figure as png
        img_data5 = io.BytesIO()
        plt.savefig(img_data5, format='png')
        # encodes message
        encoded5sub = base64.b64encode(img_data5.getvalue()).decode('utf-8')
        encoded5 = "<img src=\'data:image/png;base64,{}\'>".format(encoded5sub)

        html = """ <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>My Basic HTML Page</title>
    </head>
    <body>
        <br>
        <br>
        {}
        <br>
        <br>
        {}
        <br>
        <br>
        {}
        <br>
        <br>
        {}
        <br>
        <br>
        {}
        <br>
        <br>
    </body>
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
        # encodes message
        encoded7sub = base64.b64encode(img_data7.getvalue()).decode('utf-8')
        encoded7 = "<img src=\'data:image/png;base64,{}\'>".format(encoded7sub)

        html = """ <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>My Basic HTML Page</title>
    </head>
    <body>
        <br>
        <br>
        {}
    </body>
    </html>
        """.format(encoded7)
        
        return {
            'statusCode': 200,
            'body': html,
            'headers':{
                'Content-Type': 'text/html'
            }
        }
