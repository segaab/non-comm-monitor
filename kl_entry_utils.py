import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase_client import get_kl_client, format_kl_zone_for_db
import requests
from yahooquery import Ticker

def get_latest_calendar_quarter():
    """Return the start and end dates (inclusive) of the latest completed calendar quarter."""
    from datetime import datetime
    today = datetime.utcnow().date()
    year = today.year
    if today.month in [1, 2, 3]:
        # Q4 of previous year
        start = datetime(year-1, 10, 1).date()
        end = datetime(year-1, 12, 31).date()
    elif today.month in [4, 5, 6]:
        # Q1
        start = datetime(year, 1, 1).date()
        end = datetime(year, 3, 31).date()
    elif today.month in [7, 8, 9]:
        # Q2
        start = datetime(year, 4, 1).date()
        end = datetime(year, 6, 30).date()
    else:
        # Q3
        start = datetime(year, 7, 1).date()
        end = datetime(year, 9, 30).date()
    return start, end

def calculate_kl_zone(clicked_point, df, cot_net_change, atr_multiplier=2.0):
    """Calculate Key Liquidity zone based on clicked point and COT net change"""
    if clicked_point >= len(df):
        return None
    
    point_data = df.iloc[clicked_point]
    atr = calculate_atr(df).iloc[clicked_point]
    
    # Base zone size on ATR
    base_zone_size = atr * atr_multiplier
    
    # Adjust zone size based on COT net change (weight the KL)
    cot_weight = abs(cot_net_change) if cot_net_change is not None else 0.5
    zone_size = base_zone_size * (1 + cot_weight)
    
    # Determine if it's a swing high or low
    swing_highs, swing_lows = identify_swing_points(df)
    
    if clicked_point in swing_highs:
        # KL zone above swing high
        zone_high = point_data['High'] + zone_size
        zone_low = point_data['High'] - zone_size * 0.5
        kl_type = "Swing High"
    elif clicked_point in swing_lows:
        # KL zone below swing low
        zone_high = point_data['Low'] + zone_size * 0.5
        zone_low = point_data['Low'] - zone_size
        kl_type = "Swing Low"
    else:
        # General KL zone around the point
        zone_high = point_data['High'] + zone_size * 0.5
        zone_low = point_data['Low'] - zone_size * 0.5
        kl_type = "General"
    
    return {
        'clicked_point': clicked_point,
        'datetime': point_data['datetime'],
        'price': point_data['Close'],
        'zone_high': zone_high,
        'zone_low': zone_low,
        'atr': atr,
        'cot_net_change': cot_net_change,
        'kl_type': kl_type,
        'zone_size': zone_size
    }

def calculate_net_position_ratio(long, short):
    """Calculates the ratio (Long - Short) / (Long + Short), handling division by zero."""
    total_positions = long + short
    if total_positions == 0:
        return 0.0
    ratio = (long - short) / total_positions
    return ratio

def fetch_price_data(symbol, start_date=None, end_date=None, interval="1h"):
    """Fetch price data using yahooquery for a specific date range (calendar quarter)."""
    try:
        if start_date is None or end_date is None:
            start_date, end_date = get_latest_calendar_quarter()
        t = Ticker(symbol, timeout=60)
        hist = t.history(start=start_date, end=end_date, interval=interval)
        if isinstance(hist, pd.DataFrame) and not hist.empty:
            if isinstance(hist.index, pd.MultiIndex):
                hist = hist.reset_index()
            column_mapping = {
                'open': 'Open',
                'high': 'High', 
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume',
                'adjclose': 'Adj Close'
            }
            for old_col, new_col in column_mapping.items():
                if old_col in hist.columns:
                    hist = hist.rename(columns={old_col: new_col})
            if 'Close' in hist.columns:
                hist['price'] = hist['Close']
            elif 'close' in hist.columns:
                hist['price'] = hist['close']
            if 'Volume' not in hist.columns and 'volume' in hist.columns:
                hist = hist.rename(columns={'volume': 'Volume'})
            if 'Date' in hist.columns:
                hist = hist.rename(columns={'Date': 'date'})
            elif 'Datetime' in hist.columns:
                hist = hist.rename(columns={'Datetime': 'date'})
            elif 'date' not in hist.columns and 'datetime' in hist.columns:
                hist = hist.rename(columns={'datetime': 'date'})
            hist["datetime"] = pd.to_datetime(hist["date"], errors="coerce", utc=True)
            hist["datetime"] = hist["datetime"].dt.tz_convert('Etc/GMT-3')
            hist = hist.dropna(subset=["datetime"])
            hist = hist.sort_values("datetime")
            if 'Volume' in hist.columns:
                hist = hist.dropna(subset=["Volume"])
                hist = hist[hist["Volume"] > 0]
                hist["avg_volume"] = hist["Volume"].rolling(window=20).mean()
                hist["rvol"] = hist["Volume"] / hist["avg_volume"]
                hist["rvol"] = hist["rvol"].fillna(1.0)
            # Filter to the exact date range (in case API returns more)
            mask = (hist['datetime'].dt.date >= start_date) & (hist['datetime'].dt.date <= end_date)
            hist = hist[mask]
            return hist
        else:
            st.error(f"No data returned for symbol {symbol}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching price data for {symbol}: {e}")
        return pd.DataFrame()

def fetch_cot_data(cot_asset_name, start_date=None, end_date=None):
    """Fetch COT data for the specified asset and date range (calendar quarter)."""
    try:
        if start_date is None or end_date is None:
            start_date, end_date = get_latest_calendar_quarter()
        base_url = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
        where_clause = (
            f"market_and_exchange_names = '{cot_asset_name}' AND "
            f"report_date_as_yyyy_mm_dd BETWEEN '{start_date}' AND '{end_date}'"
        )
        params = {
            "$where": where_clause,
            "$select": "market_and_exchange_names,report_date_as_yyyy_mm_dd,noncomm_positions_long_all,noncomm_positions_short_all",
            "$order": "report_date_as_yyyy_mm_dd ASC"
        }
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        cot_data = response.json()
        cot_df = pd.DataFrame.from_records(cot_data)
        if not cot_df.empty and len(cot_df) >= 2:
            cot_df['noncomm_positions_long_all'] = pd.to_numeric(cot_df['noncomm_positions_long_all'], errors='coerce')
            cot_df['noncomm_positions_short_all'] = pd.to_numeric(cot_df['noncomm_positions_short_all'], errors='coerce')
            cot_df['net_position_ratio'] = cot_df.apply(
                lambda row: calculate_net_position_ratio(
                    row['noncomm_positions_long_all'], 
                    row['noncomm_positions_short_all']
                ), axis=1
            )
            cot_df = cot_df.sort_values('report_date_as_yyyy_mm_dd')
            # Filter to the exact date range
            cot_df = cot_df[(cot_df['report_date_as_yyyy_mm_dd'] >= str(start_date)) & (cot_df['report_date_as_yyyy_mm_dd'] <= str(end_date))]
        return cot_df
    except Exception as e:
        st.error(f"Error fetching COT data: {e}")
        return pd.DataFrame()


# 1. Fetch price (with rvol) and COT data for the latest quarter
def fetch_quarter_data(symbol, cot_asset_name, price_interval='1h'):
    price_data = fetch_price_data(symbol, interval=price_interval)
    cot_data = fetch_cot_data(cot_asset_name)
    return price_data, cot_data

# 2. Accept user-specified price datetime/candle label and calculate the KL range
def calculate_kl_for_label(price_data, cot_data, candle_label, atr_multiplier=2.0):
    # Map dropdown labels to datetime objects
    date_label_to_dt = {dt.strftime('%A, %Y-%m-%d %H:%M'): dt for dt in price_data['datetime']}
    print(f"[DEBUG] Available candle labels: {list(date_label_to_dt.keys())}")
    print(f"[DEBUG] Label to datetime mapping: {date_label_to_dt}")
    if candle_label not in date_label_to_dt:
        print(f"[DEBUG] Candle label '{candle_label}' not found in price data.")
        raise ValueError(f"Candle label '{candle_label}' not found in price data.")
    # Convert label back to pandas Timestamp (with tz)
    selected_dt = date_label_to_dt[candle_label]
    print(f"[DEBUG] Selected datetime: {selected_dt}")
    # Try direct match first
    match_idx = price_data[price_data['datetime'] == selected_dt].index
    # If no match, try tolerant string match (down to minute)
    if len(match_idx) == 0:
        selected_dt_str = selected_dt.strftime('%Y-%m-%d %H:%M')
        match_idx = price_data[price_data['datetime'].dt.strftime('%Y-%m-%d %H:%M') == selected_dt_str].index
    if len(match_idx) == 0:
        print(f"[DEBUG] No matching candle found for {candle_label} (datetime: {selected_dt})")
        raise ValueError(f"No matching candle found for {candle_label} (datetime: {selected_dt})")
    selected_idx = match_idx[0]
    print(f"[DEBUG] Matched DataFrame index: {selected_idx}")
    print(f"[DEBUG] Matched DataFrame row: {price_data.iloc[selected_idx].to_dict()}")
    # Use sum of abs of all COT net changes in the latest quarter
    cot_weight = 0.5
    if not cot_data.empty and len(cot_data) >= 2:
        cot_net_changes = cot_data['net_position_ratio'].diff().dropna()
        cot_weight = abs(cot_net_changes).sum()
    print(f"[DEBUG] Computed cot_weight (sum of abs net changes): {cot_weight}")
    kl_zone = calculate_kl_zone(selected_idx, price_data, cot_weight, atr_multiplier=atr_multiplier)
    print(f"[DEBUG] KL zone result: {kl_zone}")
    return kl_zone

# 3. Make an entry in the Supabase database, using candle_label as unique identifier
def insert_kl_to_supabase(kl_zone, symbol, cot_asset_name, candle_label, time_period='weekly', chart_interval='1h'):
    kl_client = get_kl_client()
    db_data = format_kl_zone_for_db(kl_zone, symbol, cot_asset_name, time_period)
    db_data['chart_interval'] = chart_interval
    db_data['candle_label'] = candle_label  # Add unique identifier
    # Check for duplicate (same symbol, period, candle_label)
    try:
        existing = kl_client.get_kl_zones_for_symbol(symbol, time_period)
        duplicate = None
        for entry in existing:
            if entry.get('candle_label') == candle_label:
                duplicate = entry
                break
        if duplicate:
            # Update existing entry
            try:
                db_result = kl_client.update_kl_zone(duplicate['id'], db_data)
                action = 'updated'
                return {'action': action, 'result': db_result}
            except Exception as e:
                return {'action': 'update_failed', 'error': str(e)}
        else:
            # Insert new entry
            try:
                db_result = kl_client.insert_kl_zone(db_data)
                action = 'inserted'
                return {'action': action, 'result': db_result}
            except Exception as e:
                return {'action': 'insert_failed', 'error': str(e)}
    except Exception as e:
        return {'action': 'db_error', 'error': str(e)}

# Note: The Supabase table schema should include a 'candle_label' (string, unique per symbol/period) field for uniqueness. 