from flask import Flask, render_template, request
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import plotly.graph_objs as go
import plotly
import json

app = Flask(__name__)

# Updated order of columns
columns = ['ID', 'Stock/ETF', 'Date Bought', '# of Shares', 'Price Bought', 'Date Sold', 'Price Sold', 'Return', 'SPY Return']

last_uploaded_data = None

@app.route('/')
def index():
    return render_template('index.html')

def process_data(df):
    df['Date Sold'].fillna(datetime.now(), inplace=True)
    for index, row in df.iterrows():
        if pd.isnull(row['Price Bought']) or pd.isnull(row['Price Sold']):
            stock_data = yf.download(row['Stock/ETF'], start=row['Date Bought'] - timedelta(days=1), end=row['Date Sold'] + timedelta(days=1))
            if pd.isnull(row['Price Bought']):
                price_bought = stock_data.iloc[0]['Close']
                df.at[index, 'Price Bought'] = price_bought
            if pd.isnull(row['Price Sold']):
                price_sold = stock_data.iloc[-1]['Close']
                df.at[index, 'Price Sold'] = price_sold

    df['Return'] = (((df['# of Shares'] * df['Price Sold']) - (df['# of Shares'] * df['Price Bought'])) / (df['# of Shares'] * df['Price Bought']) * 100).round(2)

    total_investment = (df['# of Shares'] * df['Price Bought']).sum()
    df['Weight'] = (df['# of Shares'] * df['Price Bought']) / total_investment
    df['Weighted Return'] = df['Return'] * df['Weight']
    overall_weighted_return = df['Weighted Return'].sum()

    etf_roi = f'{overall_weighted_return:.2f}%'

    # Keep existing individual SPY return calculations
    spy_returns = []
    for _, row in df.iterrows():
        spy_data_subset = yf.download('SPY', start=row['Date Bought'] - timedelta(days=1), end=row['Date Sold'] + timedelta(days=1), progress=False)
        if not spy_data_subset.empty:
            price_bought_spy = spy_data_subset.iloc[0]['Adj Close']
            price_sold_spy = spy_data_subset.iloc[-1]['Adj Close']
            spy_return = ((price_sold_spy - price_bought_spy) / price_bought_spy) * 100
            spy_returns.append(f'{spy_return:.2f}%')
        else:
            spy_returns.append('N/A')
    df['SPY Return'] = spy_returns

    # Calculate overall weighted SPY return (new implementation)
    weighted_spy_returns = []
    for index, row in df.iterrows():
        spy_data = yf.download('SPY', start=row['Date Bought'] - timedelta(days=1), end=row['Date Sold'] + timedelta(days=1), progress=False)
        if not spy_data.empty:
            price_bought_spy = spy_data.iloc[0]['Adj Close']
            price_sold_spy = spy_data.iloc[-1]['Adj Close']
            spy_return = ((price_sold_spy - price_bought_spy) / price_bought_spy) * 100
            weighted_spy_return = spy_return * row['Weight']
            weighted_spy_returns.append(weighted_spy_return)
        else:
            weighted_spy_returns.append(0)  # Adjust as needed

    overall_weighted_spy_return = sum(weighted_spy_returns)
    overall_spy_return_formatted = f'{overall_weighted_spy_return:.2f}%'

    # Your existing plotting code...
    fig = go.Figure()
    for _, row in df.iterrows():
        if not pd.isnull(row['Price Bought']) and not pd.isnull(row['Price Sold']):
            stock_data = yf.download(row['Stock/ETF'], start=row['Date Bought'], end=row['Date Sold'] + timedelta(days=1), progress=False)
            purchase_price = row['Price Bought']
            stock_data['Daily Return %'] = (stock_data['Adj Close'] - purchase_price) / purchase_price * 100
            if not stock_data['Daily Return %'].empty:
                first_day_return = stock_data['Daily Return %'].iloc[0]
                stock_data['Daily Return %'] -= first_day_return
            fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['Daily Return %'], mode='lines+markers', name=f"{row['Stock/ETF']} (ID: {row['ID']})"))

    fig.update_layout(title='Daily Return Percentage of Investments Over Time', xaxis_title='Date', yaxis_title='Daily Return %')
    graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return etf_roi, overall_spy_return_formatted, graph_json



def process_data2(df, etf_roi, overall_spy_return):
    df['Date Sold'].fillna(pd.to_datetime('now'), inplace=True)
    initial_total_investment = (df['# of Shares'] * df['Price Bought']).sum()

    df['Weight'] = (df['# of Shares'] * df['Price Bought']) / initial_total_investment

    last_date = df['Date Sold'].max()
    portfolio_dates = pd.date_range(df['Date Bought'].min(), last_date)

    portfolio_returns = pd.DataFrame(index=portfolio_dates, columns=['Daily Return']).fillna(0)

    # Calculate daily returns and weighted daily returns for each investment
    for _, row in df.iterrows():
        stock_data = yf.download(row['Stock/ETF'], start=row['Date Bought'] - timedelta(days=1), end=row['Date Sold'] + timedelta(days=1), progress=False)
        stock_data['Daily Return'] = stock_data['Adj Close'].pct_change()
        stock_data['Weighted Daily Return'] = stock_data['Daily Return'] * row['Weight']

        for date, value in stock_data['Weighted Daily Return'].items():
            if date in portfolio_returns.index:
                portfolio_returns.loc[date, 'Daily Return'] += value

    portfolio_returns['Cumulative Return'] = (1 + portfolio_returns['Daily Return']).cumprod() * 100

    # Adjust the last value of the portfolio cumulative return to match etf_roi
    etf_roi_value = float(etf_roi.strip('%')) + 100
    portfolio_returns.at[last_date, 'Cumulative Return'] = etf_roi_value

    spy_cumulative_returns = pd.DataFrame(index=portfolio_dates, columns=['SPY Cumulative Return']).fillna(1)  # Start with 1 for cumulative product

    for _, row in df.iterrows():
        spy_data = yf.download('SPY', start=row['Date Bought'] - timedelta(days=1), end=row['Date Sold'] + timedelta(days=1), progress=False)
        spy_data['Daily Return'] = spy_data['Adj Close'].pct_change()
        spy_data['Weighted Daily Return'] = spy_data['Daily Return'] * row['Weight']
        
        for date in spy_cumulative_returns.index:
            if date in spy_data.index:
                spy_cumulative_returns.loc[date] *= (1 + spy_data.at[date, 'Weighted Daily Return'])

    spy_cumulative_returns['SPY Cumulative Return'] = spy_cumulative_returns['SPY Cumulative Return'].cumprod() * 100

    # Adjust the last value of the SPY cumulative return to match overall_spy_return
    overall_spy_return_value = float(overall_spy_return.strip('%')) + 100
    spy_cumulative_returns.at[last_date, 'SPY Cumulative Return'] = overall_spy_return_value

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=portfolio_returns.index, y=portfolio_returns['Cumulative Return'], mode='lines+markers', name='Portfolio Cumulative Return'))
    fig.add_trace(go.Scatter(x=spy_cumulative_returns.index, y=spy_cumulative_returns['SPY Cumulative Return'], mode='lines+markers', name='SPY Cumulative Return'))

    fig.update_layout(title='Portfolio vs. SPY Cumulative Returns Over Time', xaxis_title='Date', yaxis_title='Cumulative Return (Normalized to 100)')

    graph2_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return graph2_json




@app.route('/upload', methods=['POST'])
def upload():
    global last_uploaded_data

    if 'file' not in request.files:
        return render_template('index.html', message='No file part')

    file = request.files['file']
    if file.filename == '':
        return render_template('index.html', message='No selected file')

    if file:
        try:
            df = pd.read_excel(file, header=None, names=columns[1:], skiprows=[0])
            df.insert(0, 'ID', range(1, 1 + len(df)))
            
            # Ensure 'Date Bought' and 'Date Sold' are treated as datetime objects
            df['Date Bought'] = pd.to_datetime(df['Date Bought'], format='%d.%m.%y', errors='coerce')
            df['Date Sold'] = pd.to_datetime(df['Date Sold'], format='%d.%m.%y', errors='coerce')

            # Fill missing 'Date Sold' with current date, ensuring it's a datetime object
            df['Date Sold'] = df['Date Sold'].fillna(pd.Timestamp(datetime.now()))

            last_uploaded_data = df.copy()

            etf_roi, overall_spy_return, graph_json = process_data(df)
            graph2_json = process_data2(df, etf_roi, overall_spy_return)

            display_columns = ['ID', 'Stock/ETF', 'Date Bought', '# of Shares', 'Price Bought', 'Date Sold', 'Price Sold', 'Return', 'SPY Return']
            display_df = df[display_columns].copy()

            # Format 'Date Bought' and 'Date Sold' for display, ensuring they're datetime-like before formatting
            display_df['Date Bought'] = display_df['Date Bought'].dt.strftime('%Y-%m-%d')
            display_df['Date Sold'] = display_df['Date Sold'].dt.strftime('%Y-%m-%d')

            # Format 'Return' and 'SPY Return' for display
            display_df['Return'] = display_df['Return'].apply(lambda x: "{}%".format(x))

            return render_template('display.html', tables=[display_df.to_html(classes='data', escape=False, index=False)], etf_roi=etf_roi, overall_spy_return=overall_spy_return, graph_json=graph_json, graph2_json=graph2_json)

        except Exception as e:
            return render_template('index.html', message=f'Error processing file: {e}')


@app.route('/lastviewed')
def last_viewed():
    if last_uploaded_data is not None:
        temp_df = last_uploaded_data.copy()
        etf_roi, overall_spy_return, graph_json = process_data(temp_df)
        graph2_json = process_data2(temp_df)

        # Explicitly select columns to display, excluding 'Weighted Return'
        display_columns = ['ID', 'Stock/ETF', 'Date Bought', '# of Shares', 'Price Bought', 'Date Sold', 'Price Sold', 'Return', 'SPY Return']
        display_df = temp_df[display_columns]
        display_df['Return'] = display_df['Return'].apply(lambda x: "{}%".format(x))

        table_html = display_df.to_html(classes='data', escape=False, index=False)
        return render_template('display.html', tables=[table_html], etf_roi=etf_roi, overall_spy_return=overall_spy_return, graph_json=graph_json, graph2_json=graph2_json)
    else:
        return render_template('index.html', message='No data uploaded yet')


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=80)