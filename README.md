# Investment Tracker Flask App

A simple Flask app to track the performance of investments against the SPY index. Upload investment data, and the app will handle missing prices, calculate returns, and visualize performance with interactive graphs.

## Features

- Upload feature for investment data.
- Automatic price fetching for missing entries via Yahoo Finance.
- Return calculations and SPY comparison.
- Interactive graphs for performance analysis.

## Installation

```bash
git clone https://github.com/s1lven/TradeAnalyser
cd TradeAnalyser
python3 -m venv venv
source venv/bin/activate  # On Windows use venv\Scripts\activate
pip install flask pandas yfinance plotly
python app.py
```
## Screenshots

![alt text](https://i.imgur.com/BgwqS0w.png "Upload Menu")
![alt text](https://i.imgur.com/hdKqlua.png "Trade Analyser")


