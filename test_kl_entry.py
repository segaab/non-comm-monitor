import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase_client import get_kl_client, format_kl_zone_for_db
from kl_core import get_enriched_price_data, get_latest_cot_change, calculate_kl_zone, add_kl_entry

COT_FUTURES_MAPPING = {
    "GOLD - COMMODITY EXCHANGE INC.": "GC=F",
    "EURO FX - CHICAGO MERCANTILE EXCHANGE": "6E=F",
    "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE": "6A=F",
    "BITCOIN - CHICAGO MERCANTILE EXCHANGE": "BTC-USD",
    "SILVER - COMMODITY EXCHANGE INC.": "SI=F",
}

def create_price_chart(df, title="Price Chart"):
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

def main():
    st.write("Debug: main() executed")
    st.title("KL Entry Dashboard")
    asset = st.selectbox("Select Asset", list(COT_FUTURES_MAPPING.keys()), index=0, key='asset-select')
    symbol = COT_FUTURES_MAPPING[asset]

    price_data = get_enriched_price_data(symbol, period="90d", interval="1h")
    cot_net_change = get_latest_cot_change(asset)
    if price_data.empty:
        st.error("No price data available.")
        return

    weekly_price_data = filter_to_wednesday_tuesday_from_latest(price_data)

    st.subheader(f"{asset} ({symbol}) - Weekly Price Chart (1H)")
    price_fig = create_price_chart(weekly_price_data, f"{asset} - Weekly Price")
    st.plotly_chart(price_fig, use_container_width=True, key='price-chart')

    st.subheader("Weekly RVol Chart (1H)")
    rvol_fig = create_rvol_chart(weekly_price_data, f"{asset} - Weekly RVol")
    st.plotly_chart(rvol_fig, use_container_width=True, key='rvol-chart')

    st.subheader("🎯 Key Liquidity (KL) Selection")
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

    if st.button("Add KL Zone", key=f'add-kl-zone-{selected_label}'):
        try:
            kl_client = get_kl_client()
            kl_zone = add_kl_entry(symbol, asset, selected_label, 'weekly', kl_client)
            st.success(f"KL Entry: DateTime={kl_zone['datetime']}, Price={kl_zone['price']}, Type={kl_zone['kl_type']}")
            st.write("KL Zone Details:", kl_zone)
            st.rerun()
        except RuntimeError as e:
            st.error(str(e))

    st.subheader("Latest COT Net Change")
    if cot_net_change is not None:
        st.metric("Latest Net Change", f"{cot_net_change:.4f}")
    else:
        st.info("Not enough COT data to calculate net change.")

if __name__ == "__main__":
    main() 