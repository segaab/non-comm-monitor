import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase_client import get_kl_client, format_kl_zone_for_db
from dashboard import calculate_kl_zone

# Generate mock price data (1h candles for 10 days)
now = pd.Timestamp.now(tz='Etc/GMT-3')
dates = pd.date_range(now - timedelta(days=10), periods=240, freq='H', tz='Etc/GMT-3')
data = {
    'datetime': dates,
    'Open': np.random.uniform(1900, 2000, size=len(dates)),
    'High': np.random.uniform(2000, 2100, size=len(dates)),
    'Low': np.random.uniform(1800, 1900, size=len(dates)),
    'Close': np.random.uniform(1900, 2000, size=len(dates)),
    'Volume': np.random.randint(100, 1000, size=len(dates)),
}
df = pd.DataFrame(data)

# Calculate ATR for the DataFrame (needed by calculate_kl_zone)
df['ATR'] = df['High'] - df['Low']

# Pick a random candle as the KL entry point
clicked_point = np.random.randint(10, len(df)-10)

# Mock COT net change
cot_net_change = 0.25

# Calculate KL zone
kl_zone = calculate_kl_zone(clicked_point, df, cot_net_change)
print("Calculated KL zone:", kl_zone)

# Insert into Supabase
try:
    kl_client = get_kl_client()
    selected_symbol = 'GC=F'
    selected_asset = 'GOLD - COMMODITY EXCHANGE INC.'
    db_data = format_kl_zone_for_db(kl_zone, selected_symbol, selected_asset, 'weekly')
    db_result = kl_client.insert_kl_zone(db_data)
    print("DB Insert Result:", db_result)
except Exception as e:
    print("Error inserting KL zone into Supabase:", e) 