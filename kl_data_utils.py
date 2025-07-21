import pandas as pd
from datetime import timedelta

def filter_to_wednesday_tuesday_from_latest(df):
    """Filter DataFrame to only include data from the previous Wednesday to the following Tuesday, calculated from the latest date in the DataFrame."""
    if df.empty or 'datetime' not in df.columns:
        return df
    latest_date = df['datetime'].max().date()
    days_since_wednesday = (latest_date.weekday() - 2) % 7
    last_wednesday = latest_date - timedelta(days=days_since_wednesday)
    prev_wednesday = last_wednesday - timedelta(days=7)
    prev_tuesday = prev_wednesday + timedelta(days=6)
    mask = (df['datetime'].dt.date >= prev_wednesday) & (df['datetime'].dt.date <= prev_tuesday)
    return df[mask]

def calculate_cot_net_change(cot_df):
    """Calculate the latest COT net position change from a COT DataFrame."""
    if cot_df is not None and not cot_df.empty and len(cot_df) >= 2:
        return cot_df['net_position_ratio'].iloc[-1] - cot_df['net_position_ratio'].iloc[-2]
    return None 