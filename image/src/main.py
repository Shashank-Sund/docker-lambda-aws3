import numpy as np
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
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

def handler(event, context):

    # gets in variables from event
    start_date = event['start_date']
    end_date = event['end_date']
    symbol = event['symbol']
    
    # converts date inputs to integers
    startyear,startmonth,startday = int(start_date.split('-')[0]), int(start_date.split('-')[1]), int(start_date.split('-')[2])
    endyear,endmonth,endday = int(end_date.split('-')[0]), int(end_date.split('-')[1]), int(end_date.split('-')[2])

    # No keys required for crypto data, connect to Alpaca client
    client = CryptoHistoricalDataClient()
    
    # Creating request object
    request_params = CryptoBarsRequest(
                            symbol_or_symbols=symbol,
                            timeframe=TimeFrame.Day,
                            start=datetime.datetime(startyear, startmonth, startday),
                            end=datetime.datetime(endyear, endmonth, endday)
                            )
    
    # API request to get data
    btc_bars = client.get_crypto_bars(request_params, feed = 'us')
    # Convert to dataframe
    df = btc_bars.df
    
    # gets all the timestamps, converts them to date types, puts them in a list
    ts_list = []
    for i in range(0,len(df)):
        ts_list.append(df.index[i][1].date())
    
    # create a new column with the new date types
    df = df.assign(date = ts_list)
    df['date'] = pd.to_datetime(df['date'])
    
    # create a collumn for the ticker
    symbol = df.index[0][0]
    df['symbol'] = symbol
    
    # Rename columns
    df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume', 'trade_count': 'Trade_count', 'vwap': 'Vwap', 'date': 'Date', 'symbol': 'Symbol',}, inplace=True)
    
    # Handle outliers
    q1 = df['Close'].quantile(0.25)
    q3 = df['Close'].quantile(0.75)
    iqr = q3 - q1
    upper_bound = q3 + 1.5 * iqr
    df = df[df['Close'] <= upper_bound]
    
    # # fits data using scaler
    # scaler = StandardScaler()
    # df[['Open', 'High', 'Low', 'Close', 'Volume']] = scaler.fit_transform(df[['Open', 'High', 'Low', 'Close', 'Volume']] 
    print(df)

    # Initialize s3 resource
    # s3 = boto3.resource('s3')
    # bucket = s3.Bucket("dockerlambdaoutputs3")

    # initialize list for images
    list_of_images_encoded = []

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
    encoded = base64.b64encode(img_data.getvalue()).decode('utf-8')

    # Send data to s3 code
    # img_data.seek(0)
    # s3_object_key = "{}_to_{}/Closing_Stock_Price_Over_Time.png".format(start_date, end_date) 
    # bucket.put_object(Body=img_data, ContentType='image/png', Key=s3_object_key)

    # Box plot of Closing Stock Prices by Year'
    df['Year'] = df['Date'].dt.year
    sns.boxplot(x='Year', y='Close', data=df)
    plt.title('Closing Stock Prices by Year')
    plt.xlabel('Year')
    plt.ylabel('Closing Stock Price')
    # Save figure as png
    img_data2 = io.BytesIO()
    plt.savefig(img_data2, format='png')
    # encodes message
    encoded2 = base64.b64encode(img_data2.getvalue()).decode('utf-8')

    # Create a heatmap of the correlation between stock prices
    corr = df[['Open', 'High', 'Low', 'Close']].corr()
    plt.figure(figsize=(8,8))
    sns.heatmap(corr, annot=True, cmap='coolwarm')
    plt.title('Correlation Between Stock Prices')
    # Save figure as png
    img_data3 = io.BytesIO()
    plt.savefig(img_data3, format='png')
    # encodes message
    encoded3 = base64.b64encode(img_data3.getvalue()).decode('utf-8')

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
    encoded4 = base64.b64encode(img_data4.getvalue()).decode('utf-8')

    # Create a histogram of the daily returns
    plt.figure(figsize=(12,6))
    sns.histplot(df['Close'].pct_change().dropna(), bins=100, kde=True)
    plt.title('BTC Daily Returns')
    plt.xlabel('Daily Return')
    plt.ylabel('Frequency')
    # Save figure as png
    img_data5 = io.BytesIO()
    plt.savefig(img_data5, format='png')
    # encodes message
    encoded5 = base64.b64encode(img_data5.getvalue()).decode('utf-8')

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
    <img src=\'data:image/png;base64,{}\'>
    <br>
    <br>
    <img src=\'data:image/png;base64,{}\'>
    <br>
    <br>
    <img src=\'data:image/png;base64,{}\'>
    <br>
    <br>
    <img src=\'data:image/png;base64,{}\'>
    <br>
    <br>
    <img src=\'data:image/png;base64,{}\'>
    <br>
    <br>
</body>
</html>
    """.format(encoded,encoded2,encoded3,encoded4,encoded5)
    
    return {
        'statusCode': 200,
        'body': html,
        'headers':{
            'Content-Type': 'text/html'
        }
    }