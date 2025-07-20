import pandas as pd
from dashboard import fetch_price_data, fetch_cot_data, calculate_kl_zone

def get_enriched_price_data(symbol, period="90d", interval="1h"):
    """Fetch price data, ensure GMT+3, calculate avg_volume and rvol."""
    price_data = fetch_price_data(symbol, period=period, interval=interval)
    price_data = price_data.copy()
    # Ensure datetime is GMT+3
    if price_data['datetime'].dt.tz is None or str(price_data['datetime'].dt.tz) != 'Etc/GMT-3':
        price_data['datetime'] = price_data['datetime'].dt.tz_convert('Etc/GMT-3')
    # Calculate avg_volume and rvol if not present
    if 'avg_volume' not in price_data.columns:
        price_data['avg_volume'] = price_data['Volume'].rolling(window=20).mean()
    if 'rvol' not in price_data.columns:
        price_data['rvol'] = price_data['Volume'] / price_data['avg_volume']
        price_data['rvol'] = price_data['rvol'].fillna(1.0)
    return price_data

def get_latest_cot_change(asset_name):
    """Fetch COT data and return the latest net change."""
    cot_data = fetch_cot_data(asset_name)
    if not cot_data.empty and len(cot_data) >= 2:
        return cot_data['net_position_ratio'].iloc[-1] - cot_data['net_position_ratio'].iloc[-2]
    else:
        return None

def find_candle_by_label(df, entry_label, tz_offset='+03:00'):
    """Find the index of the candle matching the dropdown label and timezone offset."""
    entry_time_str = entry_label.split(', ', 1)[1] + ':00' + tz_offset
    df = df.copy()
    df['datetime_str'] = df['datetime'].astype(str)
    if entry_time_str not in df['datetime_str'].values:
        raise ValueError(f"Entry time '{entry_time_str}' not found in price data!\nAvailable datetimes: {df['datetime_str'].unique()}")
    return df[df['datetime_str'] == entry_time_str].index[0]

def save_kl_zone_to_db(kl_zone, symbol, asset, timeframe, kl_client):
    """Save KL zone to the database using the Supabase client."""
    from supabase_client import format_kl_zone_for_db
    db_data = format_kl_zone_for_db(kl_zone, symbol, asset, timeframe)
    return kl_client.insert_kl_zone(db_data)


def add_kl_entry(symbol, asset, entry_label, timeframe, kl_client):
    """
    Find the correct candle, generate the KL zone, and save it to the database.
    Returns the KL zone dict if successful.
    """
    try:
        price_data = get_enriched_price_data(symbol)
        idx = find_candle_by_label(price_data, entry_label)
        cot_change = get_latest_cot_change(asset)
        kl_zone = calculate_kl_zone(idx, price_data, cot_change)
        if kl_zone is None:
            raise ValueError("KL zone calculation returned None")
        save_kl_zone_to_db(kl_zone, symbol, asset, timeframe, kl_client)
        return kl_zone
    except Exception as e:
        raise RuntimeError(f"Failed to add KL entry: {e}")

# Re-export for convenience
__all__ = [
    'fetch_price_data',
    'fetch_cot_data',
    'calculate_kl_zone',
    'get_enriched_price_data',
    'get_latest_cot_change',
    'find_candle_by_label',
] 