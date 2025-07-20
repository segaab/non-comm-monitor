import os
import pandas as pd
from datetime import datetime, timedelta
from yahooquery import Ticker
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ROLLING_WINDOW = 20  # Example window for avg_volume/rvol

def calculate_net_position_ratio(long, short):
    """Calculates the ratio (Long - Short) / (Long + Short), handling division by zero."""
    total_positions = long + short
    if total_positions == 0:
        return 0.0
    ratio = (long - short) / total_positions
    return ratio

# COT Asset to Futures Ticker mapping
COT_FUTURES_MAPPING = {
    "GOLD - COMMODITY EXCHANGE INC.": "GC=F",
    "EURO FX - CHICAGO MERCANTILE EXCHANGE": "6E=F",
    "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE": "6A=F",
    "BITCOIN - CHICAGO MERCANTILE EXCHANGE": "BTC-USD",
    "MICRO BITCOIN - CHICAGO MERCANTILE EXCHANGE": "MBT=F",
    "MICRO ETHER - CHICAGO MERCANTILE EXCHANGE": "ETH-USD",
    "SILVER - COMMODITY EXCHANGE INC.": "SI=F",
    "WTI FINANCIAL CRUDE OIL - NEW YORK MERCANTILE EXCHANGE": "CL=F",
    "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE": "6J=F",
    "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE": "6C=F",
    "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE": "6B=F",
    "U.S. DOLLAR INDEX - ICE FUTURES U.S.": "DX-Y.NYB",
    "NEW ZEALAND DOLLAR - CHICAGO MERCANTILE EXCHANGE": "6N=F",
    "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE": "6S=F",
    "DOW JONES U.S. REAL ESTATE IDX - CHICAGO BOARD OF TRADE": "^DJI",
    "E-MINI S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE": "ES=F",
    "NASDAQ-100 STOCK INDEX (MINI) - CHICAGO MERCANTILE EXCHANGE": "NQ=F",
    "NIKKEI STOCK AVERAGE - CHICAGO MERCANTILE EXCHANGE": "^N225",
    "SPDR S&P 500 ETF TRUST": "SPY"
}

def process_hist_df(hist):
    if isinstance(hist, pd.DataFrame) and not hist.empty:
        if isinstance(hist.index, pd.MultiIndex):
            hist = hist.reset_index()
        hist = hist.rename(columns={"symbol": "ticker"})
        # Add price column as 'close'
        if 'close' in hist.columns:
            hist['price'] = hist['close']
        elif 'Close' in hist.columns:
            hist['price'] = hist['Close']
        # Ensure 'volume' and 'date' columns exist
        if 'Volume' in hist.columns:
            hist = hist.rename(columns={'Volume': 'volume'})
        if 'Date' in hist.columns:
            hist = hist.rename(columns={'Date': 'date'})
        if 'Datetime' in hist.columns:
            hist = hist.rename(columns={'Datetime': 'date'})
        hist = hist.dropna(subset=["volume", "date"])
        hist = hist[hist["volume"] > 0]
        hist["datetime"] = pd.to_datetime(hist["date"], errors="coerce", utc=True)
        hist = hist.dropna(subset=["datetime"])
        hist = hist.sort_values("datetime")
        # Convert to GMT+3
        hist["datetime_gmt3"] = hist["datetime"] + timedelta(hours=3)
        hist["datetime_gmt3"] = hist["datetime_gmt3"].dt.strftime("%Y-%m-%dT%H:%M:%S+03:00")
        # Calculate avg_volume and rvol
        hist["avg_volume"] = hist["volume"].rolling(ROLLING_WINDOW).mean()
        hist["rvol"] = hist["volume"] / hist["avg_volume"]
        return hist
    else:
        return pd.DataFrame()

# Process each asset
for cot_asset_name, futures_ticker in COT_FUTURES_MAPPING.items():
    print(f"\n{'='*80}")
    print(f"Processing: {cot_asset_name} ({futures_ticker})")
    print(f"{'='*80}")
    
    # --- Futures Price and Volume Data ---
    try:
        t_fut = Ticker(futures_ticker, timeout=60)
        fut_hist = t_fut.history(period="90d", interval="1h")
        fut_hist = process_hist_df(fut_hist)
        print(f'\n--- {cot_asset_name} Futures Price and Volume (last quarter, 1H, processed) ---')
        print(fut_hist)
    except Exception as e:
        print(f"Error fetching {cot_asset_name} futures data: {e}")

    # --- COT Data ---
    base_url = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

    try:
        today = datetime.utcnow().date()
        
        # Determine the current quarter's start and end dates
        current_month = today.month
        if current_month <= 3:  # Q1: January, February, March
            quarter_start = datetime(today.year, 1, 1).date()
            quarter_end = datetime(today.year, 3, 31).date()
        elif current_month <= 6:  # Q2: April, May, June
            quarter_start = datetime(today.year, 4, 1).date()
            quarter_end = datetime(today.year, 6, 30).date()
        elif current_month <= 9:  # Q3: July, August, September
            quarter_start = datetime(today.year, 7, 1).date()
            quarter_end = datetime(today.year, 9, 30).date()
        else:  # Q4: October, November, December
            quarter_start = datetime(today.year, 10, 1).date()
            quarter_end = datetime(today.year, 12, 31).date()

        # Add one report before the quarter starts for net change calculation
        pre_quarter_start = quarter_start - timedelta(days=7)

        # Construct WHERE clause using BETWEEN for efficiency (including pre-quarter report)
        where_clause = (
            f"market_and_exchange_names = '{cot_asset_name}' AND "
            f"report_date_as_yyyy_mm_dd BETWEEN '{pre_quarter_start}' AND '{quarter_end}'"
        )

        params = {
            "$where": where_clause,
            "$select": "market_and_exchange_names,report_date_as_yyyy_mm_dd,noncomm_positions_long_all,noncomm_positions_short_all",
            "$order": "report_date_as_yyyy_mm_dd ASC"
        }

        # Fetch data
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        cot_data = response.json()
        
        # Convert to DataFrame
        cot_df = pd.DataFrame.from_records(cot_data)

        # Calculate net position ratios and changes
        if not cot_df.empty and len(cot_df) >= 2:
            # Convert to numeric, handling any non-numeric values
            cot_df['noncomm_positions_long_all'] = pd.to_numeric(cot_df['noncomm_positions_long_all'], errors='coerce')
            cot_df['noncomm_positions_short_all'] = pd.to_numeric(cot_df['noncomm_positions_short_all'], errors='coerce')
            
            # Calculate net position ratio for each record
            cot_df['net_position_ratio'] = cot_df.apply(
                lambda row: calculate_net_position_ratio(
                    row['noncomm_positions_long_all'], 
                    row['noncomm_positions_short_all']
                ), axis=1
            )
            
            # Sort by date to ensure proper order
            cot_df = cot_df.sort_values('report_date_as_yyyy_mm_dd')
            
            # Get latest and previous ratios
            latest_ratio = cot_df['net_position_ratio'].iloc[-1]
            previous_ratio = cot_df['net_position_ratio'].iloc[-2]
            net_ratio_change = latest_ratio - previous_ratio
            
            print(f'\n--- COT Non-Commercial Positions for {cot_asset_name} (Current Quarter: {quarter_start} to {quarter_end}) ---')
            print(f'COT records: {len(cot_df)}')
            print(f'Latest Net Position Ratio: {latest_ratio:.4f}')
            print(f'Previous Net Position Ratio: {previous_ratio:.4f}')
            print(f'Net Ratio Change: {net_ratio_change:.4f}')
            print(cot_df)
        else:
            print(f'\n--- COT Non-Commercial Positions for {cot_asset_name} (Current Quarter: {quarter_start} to {quarter_end}) ---')
            print(f'COT records: {len(cot_df)}')
            print('Insufficient data for net position change calculation')
            print(cot_df)
        
    except Exception as e:
        print(f"Error fetching COT data for {cot_asset_name}: {e}\nIf this is a name resolution error, please check your internet connection.") 