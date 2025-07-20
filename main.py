# kl_weekly_dashboard.py

import streamlit as st
st.set_page_config(page_title="KL Weekly Dashboard", page_icon="📊", layout="wide")

import pandas as pd
import plotly.graph_objects as go
from kl_core import get_enriched_price_data, get_latest_cot_change, calculate_kl_zone

COT_FUTURES_MAPPING = {
    "GOLD - COMMODITY EXCHANGE INC.": "GC=F",
    "EURO FX - CHICAGO MERCANTILE EXCHANGE": "6E=F",
    "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE": "6A=F",
    "BITCOIN - CHICAGO MERCANTILE EXCHANGE": "BTC-USD",
    "SILVER - COMMODITY EXCHANGE INC.": "SI=F",
}

def filter_to_wednesday_tuesday_from_latest(df):
    if df.empty or 'datetime' not in df.columns:
        return df
    latest_date = df['datetime'].max().date()
    days_since_wednesday = (latest_date.weekday() - 2) % 7
    last_wednesday = latest_date - pd.Timedelta(days=days_since_wednesday)
    prev_wednesday = last_wednesday - pd.Timedelta(days=7)
    prev_tuesday = prev_wednesday + pd.Timedelta(days=6)
    mask = (df['datetime'].dt.date >= prev_wednesday) & (df['datetime'].dt.date <= prev_tuesday)
    return df[mask]

def create_price_chart_with_kl(df, kl_zone=None, title="Price Chart"):
    fig = go.Figure()
    open_col = 'Open' if 'Open' in df.columns else 'open' if 'open' in df.columns else None
    high_col = 'High' if 'High' in df.columns else 'high' if 'high' in df.columns else None
    low_col = 'Low' if 'Low' in df.columns else 'low' if 'low' in df.columns else None
    close_col = 'Close' if 'Close' in df.columns else 'close' if 'close' in df.columns else None
    if not all([open_col, high_col, low_col, close_col]):
        st.error(f"Missing required OHLC columns. Available columns: {list(df.columns)}")
        return fig
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
    # Add KL zone as horizontal lines if provided
    if kl_zone:
        price = kl_zone.get('price')
        kl_type = kl_zone.get('kl_type', 'KL')
        if kl_type == 'long':
            color = 'green'
        elif kl_type == 'short':
            color = 'red'
        else:
            color = 'blue'
        # If KL zone has a range, draw both lines
        if 'kl_low' in kl_zone and 'kl_high' in kl_zone:
            fig.add_hline(y=kl_zone['kl_low'], line_dash="dash", line_color=color, annotation_text=f"{kl_type} KL Low")
            fig.add_hline(y=kl_zone['kl_high'], line_dash="dash", line_color=color, annotation_text=f"{kl_type} KL High")
        elif price is not None:
            fig.add_hline(y=price, line_dash="dash", line_color=color, annotation_text=f"{kl_type} KL")
    fig.update_layout(
        title=title,
        xaxis_title='Date',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        height=400,
        showlegend=True
    )
    return fig

def create_rvol_chart(df, title="RVol Chart"):
    fig = go.Figure()
    if 'rvol' in df.columns:
        fig.add_trace(go.Bar(
            x=df['datetime'],
            y=df['rvol'],
            name='RVol',
            marker_color='blue',
            opacity=0.7
        ))
        fig.add_hline(y=1.0, line_dash="dash", line_color="red", annotation_text="RVol = 1.0")
    fig.update_layout(
        title=title,
        xaxis_title='Date',
        yaxis_title='RVol',
        height=300,
        showlegend=True
    )
    return fig

def main():
    # st.cache_data.clear()  # REMOVE
    # st.cache_resource.clear()  # REMOVE
    # st.write("Debug: main() executed")  # Optional for debugging

    st.title("KL Weekly Dashboard")

    asset = st.selectbox("Select Asset", list(COT_FUTURES_MAPPING.keys()), index=0)
    symbol = COT_FUTURES_MAPPING[asset]

    price_data = get_enriched_price_data(symbol, period="90d", interval="1h")
    cot_net_change = get_latest_cot_change(asset)
    if price_data.empty:
        st.error("No price data available.")
        return

    weekly_price_data = filter_to_wednesday_tuesday_from_latest(price_data)

    st.subheader(f"{asset} ({symbol}) - Weekly Price Chart (1H)")
    # Prepare dropdown for candle selection
    date_label_to_dt = {dt.strftime('%A, %Y-%m-%d %H:%M'): dt for dt in weekly_price_data['datetime']}
    available_dates = list(date_label_to_dt.keys())
    selected_label = st.selectbox(
        "Select candle date/time for KL calculation:",
        available_dates,
        index=len(available_dates)-1 if available_dates else 0,
        key='kl-candle-select'
    )
    selected_dt = date_label_to_dt[selected_label]
    match_idx = weekly_price_data[weekly_price_data['datetime'] == selected_dt].index
    selected_idx = match_idx[0] if len(match_idx) > 0 else None

    kl_zone = None
    if selected_idx is not None:
        kl_zone = calculate_kl_zone(selected_idx, weekly_price_data, cot_net_change)

    price_fig = create_price_chart_with_kl(weekly_price_data, kl_zone, f"{asset} - Weekly Price")
    st.plotly_chart(price_fig, use_container_width=True, key='price-chart')

    st.subheader("Weekly RVol Chart (1H)")
    rvol_fig = create_rvol_chart(weekly_price_data, f"{asset} - Weekly RVol")
    st.plotly_chart(rvol_fig, use_container_width=True, key='rvol-chart')

    if kl_zone:
        st.success(f"KL Entry: DateTime={kl_zone['datetime']}, Price={kl_zone['price']}, Type={kl_zone['kl_type']}")
        st.write("KL Zone Details:", kl_zone)

if __name__ == "__main__":
    main()