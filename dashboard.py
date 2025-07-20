import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import requests
from yahooquery import Ticker
import os
from dotenv import load_dotenv
from supabase_client import get_kl_client, format_kl_zone_for_db
import logging
from inspect import getframeinfo, stack
import datetime

# def debug(input):
#     if "debug_string" not in st.session_state:
#         st.session_state["debug_string"] = "<b>Debug window ☝️</b>"
#     now = datetime.datetime.now()
#     st.session_state["debug_string"] = (
#         "<div style='border-bottom: dotted; border-width: thin;border-color: #cccccc;'>"
#         + str(now.hour)
#         + ":"
#         + str(now.minute)
#         + ":"
#         + str(now.second)
#         + " Debug.print["
#         + str(getframeinfo(stack()[1][0]).lineno)
#         + "] "
#         + str(input)
#         + "</div>"
#         + st.session_state["debug_string"]
#     )

# def local_css(file_name):
#     with open(file_name) as f:
#         st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Load environment variables
load_dotenv()

# Initialize Supabase client
try:
    kl_client = get_kl_client()
    SUPABASE_AVAILABLE = True
except Exception as e:
    st.warning(f"Supabase not configured: {e}")
    SUPABASE_AVAILABLE = False

# Set up logging for KL entry actions
logging.basicConfig(
    filename='kl_entry.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

# Page configuration
st.set_page_config(
    page_title="Non-Commercial Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load debug CSS
# local_css("debug.css")

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

# Helper functions
@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_price_data(symbol, period="90d", interval="1h"):
    """Fetch price data using yahooquery"""
    try:
        t = Ticker(symbol, timeout=60)
        hist = t.history(period=period, interval=interval)
        
        if isinstance(hist, pd.DataFrame) and not hist.empty:
            # Reset index if it's a MultiIndex
            if isinstance(hist.index, pd.MultiIndex):
                hist = hist.reset_index()
            
            # Ensure we have the correct column names
            column_mapping = {
                'open': 'Open',
                'high': 'High', 
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume',
                'adjclose': 'Adj Close'
            }
            
            # Rename columns to standard format
            for old_col, new_col in column_mapping.items():
                if old_col in hist.columns:
                    hist = hist.rename(columns={old_col: new_col})
            
            # Add price column as 'close'
            if 'Close' in hist.columns:
                hist['price'] = hist['Close']
            elif 'close' in hist.columns:
                hist['price'] = hist['close']
            
            # Ensure volume column exists
            if 'Volume' not in hist.columns and 'volume' in hist.columns:
                hist = hist.rename(columns={'volume': 'Volume'})
            
            # Handle date column
            if 'Date' in hist.columns:
                hist = hist.rename(columns={'Date': 'date'})
            elif 'Datetime' in hist.columns:
                hist = hist.rename(columns={'Datetime': 'date'})
            elif 'date' not in hist.columns and 'datetime' in hist.columns:
                hist = hist.rename(columns={'datetime': 'date'})
            
            # Process datetime
            hist["datetime"] = pd.to_datetime(hist["date"], errors="coerce", utc=True)
            # Convert to GMT+3
            hist["datetime"] = hist["datetime"].dt.tz_convert('Etc/GMT-3')
            hist = hist.dropna(subset=["datetime"])
            hist = hist.sort_values("datetime")
            
            # Filter for valid volume data
            if 'Volume' in hist.columns:
                hist = hist.dropna(subset=["Volume"])
                hist = hist[hist["Volume"] > 0]
                
                # Calculate RVol (Relative Volume)
                hist["avg_volume"] = hist["Volume"].rolling(window=20).mean()
                hist["rvol"] = hist["Volume"] / hist["avg_volume"]
                hist["rvol"] = hist["rvol"].fillna(1.0)  # Fill NaN with 1.0
            
            return hist
        else:
            st.error(f"No data returned for symbol {symbol}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error fetching price data for {symbol}: {e}")
        return pd.DataFrame()

def create_price_rvol_chart(df, title="Price and RVol Chart"):
    """Create a combined price and RVol chart using Plotly"""
    # Create subplots: price chart on top, RVol on bottom
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(f'{title} - Price', f'{title} - RVol'),
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3]
    )
    
    # Handle different column name variations from yahooquery
    open_col = 'Open' if 'Open' in df.columns else 'open' if 'open' in df.columns else None
    high_col = 'High' if 'High' in df.columns else 'high' if 'high' in df.columns else None
    low_col = 'Low' if 'Low' in df.columns else 'low' if 'low' in df.columns else None
    close_col = 'Close' if 'Close' in df.columns else 'close' if 'close' in df.columns else None
    
    # Check if we have all required columns
    if not all([open_col, high_col, low_col, close_col]):
        st.error(f"Missing required OHLC columns. Available columns: {list(df.columns)}")
        return fig
    
    # Add candlestick chart to first subplot
    fig.add_trace(go.Candlestick(
        x=df['datetime'],
        open=df[open_col],
        high=df[high_col],
        low=df[low_col],
        close=df[close_col],
        name='OHLC'
    ), row=1, col=1)
    
    # Add RVol chart to second subplot
    if 'rvol' in df.columns:
        fig.add_trace(go.Bar(
            x=df['datetime'],
            y=df['rvol'],
            name='RVol',
            marker_color='blue',
            opacity=0.7
        ), row=2, col=1)
        
        # Add RVol = 1.0 reference line
        fig.add_hline(y=1.0, line_dash="dash", line_color="red", 
                     annotation_text="RVol = 1.0", row=2, col=1)
    
    fig.update_layout(
        title=title,
        xaxis_title='Date',
        height=800,
        showlegend=True
    )
    
    # Update y-axis labels
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="RVol", row=2, col=1)
    
    return fig

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_cot_data(cot_asset_name):
    """Fetch COT data for the specified asset - last week only"""
    try:
        today = datetime.datetime.utcnow().date()
        
        # Calculate last week's Tuesday (COT reports are usually on Tuesday)
        days_since_tuesday = (today.weekday() - 1) % 7
        this_tuesday = today - timedelta(days=days_since_tuesday)
        last_tuesday = this_tuesday - timedelta(days=7)
        
        # Add one report before last week for net change calculation
        pre_week_start = last_tuesday - timedelta(days=7)

        base_url = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
        where_clause = (
            f"market_and_exchange_names = '{cot_asset_name}' AND "
            f"report_date_as_yyyy_mm_dd BETWEEN '{pre_week_start}' AND '{this_tuesday}'"
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
        
        # Calculate net position ratios and changes
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
            
        return cot_df
    except Exception as e:
        st.error(f"Error fetching COT data: {e}")
        return pd.DataFrame()

def calculate_net_position_ratio(long, short):
    """Calculates the ratio (Long - Short) / (Long + Short), handling division by zero."""
    total_positions = long + short
    if total_positions == 0:
        return 0.0
    ratio = (long - short) / total_positions
    return ratio

def create_candlestick_chart(df, title="Price Chart"):
    """Create a candlestick chart using Plotly"""
    fig = go.Figure()
    # Handle different column name variations from yahooquery
    open_col = 'Open' if 'Open' in df.columns else 'open' if 'open' in df.columns else None
    high_col = 'High' if 'High' in df.columns else 'high' if 'high' in df.columns else None
    low_col = 'Low' if 'Low' in df.columns else 'low' if 'low' in df.columns else None
    close_col = 'Close' if 'Close' in df.columns else 'close' if 'close' in df.columns else None
    # Check if we have all required columns
    if not all([open_col, high_col, low_col, close_col]):
        st.error(f"Missing required OHLC columns. Available columns: {list(df.columns)}")
        st.write("DataFrame head:")
        st.dataframe(df.head())
        return fig
    # Add weekday name to hover text
    hover_text = df['datetime'].dt.strftime('%A, %Y-%m-%d %H:%M')
    fig.add_trace(go.Candlestick(
        x=df['datetime'],
        open=df[open_col],
        high=df[high_col],
        low=df[low_col],
        close=df[close_col],
        name='OHLC',
        hovertext=hover_text,
        hoverinfo="text"
    ))
    fig.update_layout(
        title=title,
        xaxis_title='Date',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        height=600
    )
    return fig

def create_rvol_chart(df, title="RVol Chart"):
    """Create an RVol-only chart using Plotly"""
    fig = go.Figure()
    if 'rvol' in df.columns:
        fig.add_trace(go.Bar(
            x=df['datetime'],
            y=df['rvol'],
            name='RVol',
            marker_color='blue',
            opacity=0.7
        ))
        # Add RVol = 1.0 reference line
        fig.add_hline(y=1.0, line_dash="dash", line_color="red", annotation_text="RVol = 1.0")
    fig.update_layout(
        title=title,
        xaxis_title='Date',
        yaxis_title='RVol',
        height=400,
        showlegend=True
    )
    return fig

def calculate_atr(df, period=14):
    """Calculate Average True Range"""
    high = df['High']
    low = df['Low']
    close = df['Close'].shift(1)
    
    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def identify_swing_points(df, window=5):
    """Identify swing highs and lows"""
    swing_highs = []
    swing_lows = []
    
    for i in range(window, len(df) - window):
        # Check for swing high
        if all(df['High'].iloc[i] >= df['High'].iloc[i-window:i]) and \
           all(df['High'].iloc[i] >= df['High'].iloc[i+1:i+window+1]):
            swing_highs.append(i)
        
        # Check for swing low
        if all(df['Low'].iloc[i] <= df['Low'].iloc[i-window:i]) and \
           all(df['Low'].iloc[i] <= df['Low'].iloc[i+1:i+window+1]):
            swing_lows.append(i)
    
    return swing_highs, swing_lows

def create_price_rvol_kl_chart(df, title="Price, RVol and KL Chart", kl_zones=None):
    """Create a combined price, RVol and KL zones chart using Plotly"""
    # Create subplots: price chart on top, RVol on bottom
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(f'{title} - Price', f'{title} - RVol'),
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3]
    )
    
    # Handle different column name variations from yahooquery
    open_col = 'Open' if 'Open' in df.columns else 'open' if 'open' in df.columns else None
    high_col = 'High' if 'High' in df.columns else 'high' if 'high' in df.columns else None
    low_col = 'Low' if 'Low' in df.columns else 'low' if 'low' in df.columns else None
    close_col = 'Close' if 'Close' in df.columns else 'close' if 'close' in df.columns else None
    
    # Check if we have all required columns
    if not all([open_col, high_col, low_col, close_col]):
        st.error(f"Missing required OHLC columns. Available columns: {list(df.columns)}")
        return fig
    
    # Add weekday name to hover text
    hover_text = df['datetime'].dt.strftime('%A, %Y-%m-%d %H:%M')
    # Add candlestick chart to first subplot
    fig.add_trace(go.Candlestick(
        x=df['datetime'],
        open=df[open_col],
        high=df[high_col],
        low=df[low_col],
        close=df[close_col],
        name='OHLC',
        hovertext=hover_text,
        hoverinfo="text"
    ), row=1, col=1)
    
    # Add KL zones if provided
    if kl_zones:
        for i, kl in enumerate(kl_zones):
            # Add KL zone as horizontal rectangle
            fig.add_shape(
                type="rect",
                x0=df['datetime'].min(),
                x1=df['datetime'].max(),
                y0=kl['zone_low'],
                y1=kl['zone_high'],
                fillcolor="rgba(255, 0, 0, 0.2)",
                line=dict(color="red", width=2),
                row=1, col=1
            )
            
            # Add annotation for KL zone
            fig.add_annotation(
                x=kl['datetime'],
                y=kl['zone_high'],
                text=f"KL {i+1}: {kl['kl_type']}<br>Net Change: {kl['cot_net_change']:.4f}",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor="red",
                row=1, col=1
            )
    
    # Add RVol chart to second subplot
    if 'rvol' in df.columns:
        fig.add_trace(go.Bar(
            x=df['datetime'],
            y=df['rvol'],
            name='RVol',
            marker_color='blue',
            opacity=0.7
        ), row=2, col=1)
        
        # Add RVol = 1.0 reference line
        fig.add_hline(y=1.0, line_dash="dash", line_color="red", 
                     annotation_text="RVol = 1.0", row=2, col=1)
    
    fig.update_layout(
        title=title,
        xaxis_title='Date',
        height=800,
        showlegend=True
    )
    
    # Update y-axis labels
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="RVol", row=2, col=1)
    
    return fig

def filter_to_wednesday_tuesday(df):
    """Filter DataFrame to only include data from the previous Wednesday to the following Tuesday (the week before the current one)."""
    if df.empty or 'datetime' not in df.columns:
        return df
    today = datetime.datetime.utcnow().date()
    # Find the most recent Wednesday
    days_since_wednesday = (today.weekday() - 2) % 7
    last_wednesday = today - timedelta(days=days_since_wednesday)
    # Move back one week
    prev_wednesday = last_wednesday - timedelta(days=7)
    prev_tuesday = prev_wednesday + timedelta(days=6)
    mask = (df['datetime'].dt.date >= prev_wednesday) & (df['datetime'].dt.date <= prev_tuesday)
    return df[mask]

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

def create_price_chart(df, title="Price Chart"):
    """Create a candlestick price chart using Plotly"""
    fig = go.Figure()
    open_col = 'Open' if 'Open' in df.columns else 'open' if 'open' in df.columns else None
    high_col = 'High' if 'High' in df.columns else 'high' if 'high' in df.columns else None
    low_col = 'Low' if 'Low' in df.columns else 'low' if 'low' in df.columns else None
    close_col = 'Close' if 'Close' in df.columns else 'close' if 'close' in df.columns else None
    if not all([open_col, high_col, low_col, close_col]):
        st.error(f"Missing required OHLC columns. Available columns: {list(df.columns)}")
        return fig
    # Add weekday name to hover text
    hover_text = df['datetime'].dt.strftime('%A, %Y-%m-%d %H:%M')
    fig.add_trace(go.Candlestick(
        x=df['datetime'],
        open=df[open_col],
        high=df[high_col],
        low=df[low_col],
        close=df[close_col],
        name='OHLC',
        hovertext=hover_text,
        hoverinfo="text"
    ))
    fig.update_layout(
        title=title,
        xaxis_title='Date',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        height=400,
        showlegend=True
    )
    return fig

def add_kl_lines_to_fig(fig, kl_zones, df, row=1, col=1):
    """Add horizontal lines for each KL zone to the given Plotly figure."""
    for kl in kl_zones:
        # Draw zone_high
        fig.add_hline(y=kl['zone_high'], line_dash="dash", line_color="red", annotation_text=f"KL High", row=row, col=col)
        # Draw zone_low
        fig.add_hline(y=kl['zone_low'], line_dash="dash", line_color="blue", annotation_text=f"KL Low", row=row, col=col)
    return fig

# --- KL Core Logic (inlined from kl_core.py) ---

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

def calculate_kl_zone(clicked_point, df, cot_net_change, atr_multiplier=2.0):
    """Calculate Key Liquidity zone based on clicked point and COT net change"""
    if clicked_point >= len(df):
        return None
    point_data = df.iloc[clicked_point]
    # Calculate ATR for the full DataFrame
    high = df['High']
    low = df['Low']
    close = df['Close'].shift(1)
    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean().iloc[clicked_point]
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

# Sidebar navigation
st.sidebar.title("📊 Non-Commercial Dashboard")

# Symbol selector
selected_asset = st.sidebar.selectbox(
    "Select Asset",
    list(COT_FUTURES_MAPPING.keys()),
    index=0
)

selected_symbol = COT_FUTURES_MAPPING[selected_asset]

# Page navigation
page = st.sidebar.radio(
    "Navigation",
    ["Weekly Macro View", "Quarterly KL View"]
)

# Initialize session state for KL zones
if 'kl_zones' not in st.session_state:
    st.session_state.kl_zones = []

# Load KL zones from database if available
if SUPABASE_AVAILABLE and 'db_loaded' not in st.session_state:
    try:
        db_zones = kl_client.get_kl_zones_for_symbol(selected_symbol, 'weekly')
        st.session_state.kl_zones = []
        if db_zones:
            # Convert database format to local format
            for db_zone in db_zones:
                local_zone = {
                    'clicked_point': db_zone['clicked_point_index'],
                    'datetime': pd.to_datetime(db_zone['clicked_datetime']),
                    'price': db_zone['clicked_price'],
                    'zone_high': db_zone['zone_high'],
                    'zone_low': db_zone['zone_low'],
                    'atr': db_zone['atr_value'],
                    'cot_net_change': db_zone['cot_net_change'],
                    'kl_type': db_zone['kl_type'],
                    'zone_size': db_zone['zone_size'],
                    'db_id': db_zone['id']  # Store database ID for updates
                }
                st.session_state.kl_zones.append(local_zone)
        st.session_state.db_loaded = True
    except Exception as e:
        st.error(f"Error loading KL zones from database: {e}")

# Show KL feedback if present
if 'kl_feedback' in st.session_state:
    st.info(st.session_state.kl_feedback)
    del st.session_state.kl_feedback

# Main content
if page == "Weekly Macro View":
    st.title("📈 Weekly Macro View")
    st.subheader(f"{selected_asset} ({selected_symbol})")
    
    # Database status indicator
    if SUPABASE_AVAILABLE:
        st.sidebar.success("✅ Supabase Connected")
    else:
        st.sidebar.warning("⚠️ Supabase Not Available")
    
    # Fetch and enrich quarterly data (use for both views)
    price_data = get_enriched_price_data(selected_symbol, period="90d", interval="1h")
    cot_data = fetch_cot_data(selected_asset)  # still needed for table display, but use get_latest_cot_change for KL
    # Filter to previous Wednesday-Tuesday based on latest date in data
    weekly_price_data = filter_to_wednesday_tuesday_from_latest(price_data)
    
    if not weekly_price_data.empty:
        # Show the DataFrame for debugging
        st.subheader("Debug: Weekly Price Data Table")
        st.dataframe(weekly_price_data, use_container_width=True)
        
        # Get latest COT net change for KL calculation
        latest_cot_net_change = get_latest_cot_change(selected_asset)
        
        # Price chart
        st.subheader("Weekly Price Chart (1H)")
        price_fig = create_price_chart(weekly_price_data, f"{selected_asset} - Weekly Price")
        price_fig = add_kl_lines_to_fig(price_fig, st.session_state.kl_zones, weekly_price_data)
        st.plotly_chart(price_fig, use_container_width=True)
        
        # RVol chart
        st.subheader("Weekly RVol Chart (1H)")
        rvol_fig = create_rvol_chart(weekly_price_data, f"{selected_asset} - Weekly RVol")
        st.plotly_chart(rvol_fig, use_container_width=True)
        
        # KL Selection Interface
        st.subheader("🎯 Key Liquidity (KL) Selection")
        st.write("Click on a candle to mark non-commercial entry points for KL calculation")
        
        # Date picker for KL selection
        if not weekly_price_data.empty:
            # Map dropdown labels to full formatted strings with weekday name
            date_label_to_dt = {dt.strftime('%A, %Y-%m-%d %H:%M'): dt for dt in weekly_price_data['datetime']}
            available_dates = list(date_label_to_dt.keys())
            selected_label = st.selectbox(
                "Select candle date/time for KL calculation:",
                available_dates,
                index=len(available_dates)-1 if available_dates else 0
            )
            # Use the actual datetime object for matching
            selected_dt = date_label_to_dt[selected_label]
            match_idx = weekly_price_data[weekly_price_data['datetime'] == selected_dt].index
            if len(match_idx) == 0:
                st.error(f"No matching candle found for {selected_label} (datetime: {selected_dt})")
                selected_idx = None
            else:
                selected_idx = match_idx[0]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Add KL Zone") and selected_idx is not None:
                    # Calculate KL zone
                    kl_zone = calculate_kl_zone(selected_idx, weekly_price_data, latest_cot_net_change)
                    if kl_zone:
                        # Log KL entry
                        logging.info(
                            f"KL Entry Attempt | Symbol: {selected_symbol} | DateTime: {kl_zone['datetime']} | Price: {kl_zone['price']} | KL Type: {kl_zone['kl_type']} | User Action: Add KL Zone"
                        )
                        # Prepare detailed feedback
                        kl_vars = (
                            f"KL Entry Variables:\n"
                            f"  Clicked Point: {kl_zone['clicked_point']}\n"
                            f"  DateTime: {kl_zone['datetime']}\n"
                            f"  Price: {kl_zone['price']}\n"
                            f"  Zone High: {kl_zone['zone_high']}\n"
                            f"  Zone Low: {kl_zone['zone_low']}\n"
                            f"  ATR: {kl_zone['atr']}\n"
                            f"  COT Net Change: {kl_zone['cot_net_change']}\n"
                            f"  KL Type: {kl_zone['kl_type']}\n"
                            f"  Zone Size: {kl_zone['zone_size']}\n"
                        )
                        # Save to database if available
                        if SUPABASE_AVAILABLE:
                            try:
                                db_data = format_kl_zone_for_db(kl_zone, selected_symbol, selected_asset, 'weekly')
                                logging.info(f"DB Insert Data: {db_data}")
                                db_result = kl_client.insert_kl_zone(db_data)
                                logging.info(f"DB Insert Result: {db_result}")
                                if db_result:
                                    st.session_state.kl_feedback = f"KL Entry: Symbol={selected_symbol}, DateTime={kl_zone['datetime']}, Price={kl_zone['price']}, Type={kl_zone['kl_type']} (Saved to DB)\n{kl_vars}"
                                    # Reload all KLs from database
                                    db_zones = kl_client.get_kl_zones_for_symbol(selected_symbol, 'weekly')
                                    st.session_state.kl_zones = []
                                    if db_zones:
                                        for db_zone in db_zones:
                                            local_zone = {
                                                'clicked_point': db_zone['clicked_point_index'],
                                                'datetime': pd.to_datetime(db_zone['clicked_datetime']),
                                                'price': db_zone['clicked_price'],
                                                'zone_high': db_zone['zone_high'],
                                                'zone_low': db_zone['zone_low'],
                                                'atr': db_zone['atr_value'],
                                                'cot_net_change': db_zone['cot_net_change'],
                                                'kl_type': db_zone['kl_type'],
                                                'zone_size': db_zone['zone_size'],
                                                'db_id': db_zone['id']
                                            }
                                            st.session_state.kl_zones.append(local_zone)
                                else:
                                    st.session_state.kl_feedback = f"KL Entry: Symbol={selected_symbol}, DateTime={kl_zone['datetime']}, Price={kl_zone['price']}, Type={kl_zone['kl_type']} (DB Save Failed)\n{kl_vars}"
                            except Exception as e:
                                logging.error(f"Exception during DB insert: {e}")
                                st.session_state.kl_feedback = f"Error saving to database: {e}\n{kl_vars}"
                        else:
                            st.session_state.kl_zones.append(kl_zone)
                            st.session_state.kl_feedback = f"KL Entry: Symbol={selected_symbol}, DateTime={kl_zone['datetime']}, Price={kl_zone['price']}, Type={kl_zone['kl_type']} (Saved Locally)\n{kl_vars}"
                        st.rerun()
            with col2:
                if st.button("Debug KL Entry") and selected_idx is not None:
                    kl_zone = calculate_kl_zone(selected_idx, weekly_price_data, latest_cot_net_change)
                    if kl_zone:
                        # debug_vars = (
                        #     f"[DEBUG] KL Entry Variables:\n"
                        #     f"  Clicked Point: {kl_zone['clicked_point']}\n"
                        #     f"  DateTime: {kl_zone['datetime']}\n"
                        #     f"  Price: {kl_zone['price']}\n"
                        #     f"  Zone High: {kl_zone['zone_high']}\n"
                        #     f"  Zone Low: {kl_zone['zone_low']}\n"
                        #     f"  ATR: {kl_zone['atr']}\n"
                        #     f"  COT Net Change: {kl_zone['cot_net_change']}\n"
                        #     f"  KL Type: {kl_zone['kl_type']}\n"
                        #     f"  Zone Size: {kl_zone['zone_size']}\n"
                        # )
                        # debug(debug_vars)
                        pass # Commented out debug() call
            with col3:
                if st.button("Clear All KL Zones"):
                    # Clear from database if available
                    if SUPABASE_AVAILABLE:
                        try:
                            for zone in st.session_state.kl_zones:
                                if 'db_id' in zone:
                                    kl_client.delete_kl_zone(zone['db_id'])
                        except Exception as e:
                            st.error(f"Error clearing from database: {e}")
                    st.session_state.kl_zones = []
                    st.rerun()
        
        # Display current KL zones
        if st.session_state.kl_zones:
            st.subheader("Current KL Zones")
            
            # Create DataFrame for display
            kl_display_data = []
            for i, zone in enumerate(st.session_state.kl_zones):
                kl_display_data.append({
                    'KL #': i + 1,
                    'Type': zone['kl_type'],
                    'Price': f"{zone['price']:.2f}",
                    'Zone Low': f"{zone['zone_low']:.2f}",
                    'Zone High': f"{zone['zone_high']:.2f}",
                    'ATR': f"{zone['atr']:.2f}",
                    'COT Change': f"{zone['cot_net_change']:.4f}" if zone['cot_net_change'] else "N/A",
                    'Date': zone['datetime'].strftime('%Y-%m-%d %H:%M'),
                    'DB Status': "✅ Saved" if 'db_id' in zone else "⚠️ Local Only"
                })
            
            kl_df = pd.DataFrame(kl_display_data)
            st.dataframe(kl_df, use_container_width=True)
            
            # Individual zone management
            if st.session_state.kl_zones:
                st.subheader("Manage Individual KL Zones")
                zone_to_delete = st.selectbox(
                    "Select KL zone to delete:",
                    [f"KL {i+1}: {zone['kl_type']} at {zone['datetime'].strftime('%Y-%m-%d %H:%M')}" 
                     for i, zone in enumerate(st.session_state.kl_zones)]
                )
                
                if st.button("Delete Selected KL Zone"):
                    zone_index = int(zone_to_delete.split()[1].replace('#', '')) - 1
                    zone_to_remove = st.session_state.kl_zones[zone_index]
                    
                    # Delete from database if available
                    if SUPABASE_AVAILABLE and 'db_id' in zone_to_remove:
                        try:
                            kl_client.delete_kl_zone(zone_to_remove['db_id'])
                        except Exception as e:
                            st.error(f"Error deleting from database: {e}")
                    
                    # Remove from session state
                    st.session_state.kl_zones.pop(zone_index)
                    st.rerun()
        
        # COT Analytics
        if not cot_data.empty:
            st.subheader("COT Analytics (Last Week)")
            # Only display the latest net change as a percentage
            if len(cot_data) >= 2:
                latest_ratio = cot_data['net_position_ratio'].iloc[-1]
                previous_ratio = cot_data['net_position_ratio'].iloc[-2]
                net_change = (latest_ratio - previous_ratio) * 100
                st.metric("Latest Net Change (%)", f"{net_change:.2f}%")
            else:
                st.info("Not enough COT data to calculate net change.")
        else:
            st.warning("No COT data available for the selected asset.")
    else:
        st.error("Unable to fetch price data for the selected symbol.")

elif page == "Quarterly KL View":
    st.title("🎯 Quarterly KL View")
    st.subheader(f"{selected_asset} ({selected_symbol})")
    
    # Database status indicator
    if SUPABASE_AVAILABLE:
        st.sidebar.success("✅ Supabase Connected")
    else:
        st.sidebar.warning("⚠️ Supabase Not Available")
    
    # Fetch quarterly data
    price_data = get_enriched_price_data(selected_symbol, period="90d", interval="1h")
    cot_data = fetch_cot_data(selected_asset)
    
    if not price_data.empty:
        # Quarterly price and RVol chart
        st.subheader("Quarterly Price and RVol Chart")
        fig = create_price_rvol_kl_chart(price_data, f"{selected_asset} - Quarterly Price", st.session_state.kl_zones)
        fig = add_kl_lines_to_fig(fig, st.session_state.kl_zones, price_data)
        st.plotly_chart(fig, use_container_width=True)
        
        # KL Analysis
        st.subheader("Key Liquidity Zones (KL) Analysis")
        if st.session_state.kl_zones:
            st.success(f"Found {len(st.session_state.kl_zones)} KL zones for analysis")
            
            # KL Summary
            kl_df = pd.DataFrame(st.session_state.kl_zones)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total KL Zones", len(st.session_state.kl_zones))
            with col2:
                avg_zone_size = kl_df['zone_size'].mean()
                st.metric("Avg Zone Size", f"{avg_zone_size:.2f}")
            with col3:
                avg_cot_change = kl_df['cot_net_change'].mean()
                st.metric("Avg COT Change", f"{avg_cot_change:.4f}")
            
            # Database statistics if available
            if SUPABASE_AVAILABLE:
                try:
                    db_stats = kl_client.get_kl_zones_stats(selected_symbol, 'weekly')
                    if db_stats:
                        st.subheader("Database Statistics")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("DB Total Zones", db_stats['total_zones'])
                        with col2:
                            st.metric("Swing Highs", db_stats['swing_high_count'])
                        with col3:
                            st.metric("Swing Lows", db_stats['swing_low_count'])
                        with col4:
                            st.metric("General", db_stats['general_count'])
                except Exception as e:
                    st.error(f"Error fetching database stats: {e}")
        else:
            st.info("No KL zones defined. Go to Weekly Macro View to add KL zones.")
        
        # COT Summary
        if not cot_data.empty:
            st.subheader("COT Summary for Quarter")
            latest_cot = cot_data.iloc[-1] if len(cot_data) > 0 else None
            if latest_cot is not None:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Latest Longs", f"{latest_cot['noncomm_positions_long_all']:,.0f}")
                with col2:
                    st.metric("Latest Shorts", f"{latest_cot['noncomm_positions_short_all']:,.0f}")
                with col3:
                    st.metric("Net Ratio", f"{latest_cot['net_position_ratio']:.4f}")
    else:
        st.error("Unable to fetch quarterly price data for the selected symbol.")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**Data Sources:**")
st.sidebar.markdown("- Price: Yahoo Finance")
st.sidebar.markdown("- COT: CFTC Public Data")
if SUPABASE_AVAILABLE:
    st.sidebar.markdown("- Storage: Supabase")
else:
    st.sidebar.markdown("- Storage: Local Session") 

# Example debug usage (remove or comment out in production)
# debug("Dashboard loaded successfully.")

# Always display the debug window at the bottom if present
# if "debug_string" in st.session_state:
#     st.markdown(
#         f'<div class="debug">{ st.session_state["debug_string"]}</div>',
#         unsafe_allow_html=True,
#     ) 