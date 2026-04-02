#!/usr/bin/env python3
# Trading Signal Generator
# Generates buy/sell signals using RSI, Bollinger Bands, ADX, Volume Spike
# Exports results to Excel. Edit TICKERS list to add your stocks.
# Install: pip install yfinance pandas pandas-ta openpyxl
# Run:     python trading_signals.py 

import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
from pathlib import Path
import sys


# ============================================================
# CONFIGURATION - EDIT THESE VALUES
# ============================================================

# Your tickers (add as many as you want)
TICKERS = ["MU", "EXOD", "DNB.OL"]

# Number of days to show in output
ANALYSIS_DAYS = 10

# History to download (extra days needed for indicator warmup)
LOOKBACK_DAYS = 120

# RSI settings
RSI_PERIOD = 14
RSI_BUY_THRESHOLD = 50
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# Bollinger Bands settings
BB_PERIOD = 20
BB_STD = 2.0

# ADX settings
ADX_PERIOD = 14

# Volume Spike settings
VOLUME_MA_PERIOD = 20
VOLUME_SPIKE_MULTIPLIER = 1.5

# Output filename
OUTPUT_FILENAME = "trading_signals.xlsx"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def download_data(ticker, days):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    try:
        df = yf.download(
            ticker,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            print(f"  WARNING: No data for {ticker}")
            return pd.DataFrame()
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"  ERROR downloading {ticker}: {e}")
        return pd.DataFrame()


def calculate_indicators(df):
    # RSI
    df["RSI"] = ta.rsi(df["Close"], length=RSI_PERIOD)

    # Bollinger Bands
    bb = ta.bbands(df["Close"], length=BB_PERIOD, std=BB_STD)
    if bb is not None and not bb.empty:
        df["BB_Upper"] = bb.iloc[:, 2]   # BBU
        df["BB_Middle"] = bb.iloc[:, 1]  # BBM
        df["BB_Lower"] = bb.iloc[:, 0]   # BBL
    else:
        df["BB_Upper"] = float("nan")
        df["BB_Middle"] = float("nan")
        df["BB_Lower"] = float("nan")

    # ADX
    adx = ta.adx(df["High"], df["Low"], df["Close"], length=ADX_PERIOD)
    if adx is not None and not adx.empty:
        df["ADX"] = adx.iloc[:, 0]
    else:
        df["ADX"] = float("nan")

    # Volume Moving Average and Spike detection
    df["Volume_MA"] = df["Volume"].rolling(window=VOLUME_MA_PERIOD).mean()
    df["Volume_Spike"] = df["Volume"] > (df["Volume_MA"] * VOLUME_SPIKE_MULTIPLIER)

    # Bollinger Band breakouts
    df["Close>Upper"] = df["Close"] > df["BB_Upper"]
    df["Close<Lower"] = df["Close"] < df["BB_Lower"]

    return df


def generate_signals(df):
    df["Signal"] = "No Signal"
    df.loc[df["RSI"] > RSI_BUY_THRESHOLD, "Signal"] = "Buy"
    df.loc[df["RSI"] < RSI_OVERSOLD, "Signal"] = "Sell"
    df["Overbought"] = df["RSI"] > RSI_OVERBOUGHT
    return df


def format_output(df, ticker, days):
    df_out = df.tail(days).copy()
    df_out.insert(0, "Ticker", ticker)
    df_out["Date"] = df_out.index.strftime("%Y-%m-%d")

    cols = [
        "Ticker", "Date", "Signal", "Close", "RSI",
        "ADX", "Volume_Spike", "Close>Upper", "Close<Lower",
        "BB_Upper", "BB_Middle", "BB_Lower",
        "Volume", "Volume_MA", "Overbought",
    ]

    available = [c for c in cols if c in df_out.columns]
    return df_out[available].reset_index(drop=True)


# ============================================================
# MAIN PROGRAM
# ============================================================

def main():
    print("=" * 60)
    print("  TRADING SIGNAL GENERATOR")
    print("=" * 60)
    print(f"  Tickers:  {', '.join(TICKERS)}")
    print(f"  Period:   Last {ANALYSIS_DAYS} trading days")
    print(f"  Date:     {datetime.today().strftime('%Y-%m-%d')}")
    print("=" * 60)
    print()

    all_results = []

    for ticker in TICKERS:
        print(f"Analyzing {ticker}...")

        # 1. Download data
        df = download_data(ticker, LOOKBACK_DAYS)
        if df.empty:
            continue

        # 2. Calculate indicators
        df = calculate_indicators(df)

        # 3. Generate signals
        df = generate_signals(df)

        # 4. Format output
        result = format_output(df, ticker, ANALYSIS_DAYS)
        all_results.append(result)

        # 5. Print last signal to terminal
        last = result.iloc[-1]
        sig = last["Signal"]
        emoji = "BUY" if sig == "Buy" else "SELL" if sig == "Sell" else "---"
        print(f"  [{emoji}] {ticker}: {sig} | Close: ${last['Close']:.2f} | RSI: {last['RSI']:.1f}")
        print()

    if not all_results:
        print("ERROR: No data retrieved. Check internet and tickers.")
        sys.exit(1)

    # 6. Combine all results
    combined = pd.concat(all_results, ignore_index=True)

    # 7. Export to Excel
    output_path = Path(OUTPUT_FILENAME)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        # Main sheet with all signals
        combined.to_excel(writer, sheet_name="Signals", index=False)

        # Summary sheet (latest day per ticker)
        summary_rows = []
        for ticker in TICKERS:
            ticker_data = combined[combined["Ticker"] == ticker]
            if not ticker_data.empty:
                summary_rows.append(ticker_data.iloc[-1])
        if summary_rows:
            summary = pd.DataFrame(summary_rows)
            summary.to_excel(writer, sheet_name="Summary", index=False)

    print("=" * 60)
    print(f"  Results exported to: {output_path.absolute()}")
    print("  Open the file in Excel for full overview")
    print("=" * 60)


if __name__ == "__main__":
    main()
