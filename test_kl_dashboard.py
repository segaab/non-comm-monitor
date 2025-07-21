import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from kl_entry_utils import fetch_quarter_data, calculate_kl_for_label, insert_kl_to_supabase
from kl_data_utils import filter_to_wednesday_tuesday_from_latest, calculate_cot_net_change
from kl_overlay_utils import fetch_kl_zones, add_kl_overlay
import logging

# --- UI: Asset selection ---
COT_FUTURES_MAPPING = {
    "GOLD - COMMODITY EXCHANGE INC.": "GC=F",
    "EURO FX - CHICAGO MERCANTILE EXCHANGE": "6E=F",
    "SILVER - COMMODITY EXCHANGE INC.": "SI=F",
    "E-MINI S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE": "ES=F",
}

st.set_page_config(page_title="KL Test Dashboard", layout="wide")
st.title("KL Test Dashboard")

selected_asset = st.selectbox("Select Asset", list(COT_FUTURES_MAPPING.keys()), index=0)
selected_symbol = COT_FUTURES_MAPPING[selected_asset]

# --- Fetch data ---
price_data, cot_data = fetch_quarter_data(selected_symbol, selected_asset, price_interval='1h')
# Debug: Show fetched price and COT data
st.subheader("[DEBUG] Fetched Price Data (head)")
st.dataframe(price_data.head(), use_container_width=True)
st.subheader("[DEBUG] Fetched COT Data (head)")
st.dataframe(cot_data.head(), use_container_width=True)
# Convert all datetimes to GMT+3
if not price_data.empty and 'datetime' in price_data.columns:
    price_data['datetime'] = price_data['datetime'].dt.tz_convert('Etc/GMT-3')
weekly_price_data = filter_to_wednesday_tuesday_from_latest(price_data)
# Fetch all KLs for the selected symbol (futures ticker)
all_kl_zones_raw = fetch_kl_zones(selected_symbol, period='weekly')
# Only keep required fields for each KL entry
kl_zones = [
    {
        'zone_high': kl.get('zone_high'),
        'zone_low': kl.get('zone_low'),
        'time_period': kl.get('time_period'),
        'candle_label': kl.get('candle_label'),
    }
    for kl in all_kl_zones_raw
]

# --- KL Entry UI ---
st.header("KL Calculation and Entry")
if not weekly_price_data.empty:
    # Dropdown for candle label
    date_label_to_dt = {dt.strftime('%A, %Y-%m-%d %H:%M'): dt for dt in weekly_price_data['datetime']}
    available_dates = list(date_label_to_dt.keys())
    st.write(f"[DEBUG] Available candle labels: {available_dates}")
    st.write(f"[DEBUG] Label to datetime mapping: {date_label_to_dt}")
    selected_label = st.selectbox("Select candle for KL calculation:", available_dates, index=len(available_dates)-1)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Add KL Entry"):
            try:
                st.write(f"[DEBUG] Selected label: {selected_label}")
                kl_zone = calculate_kl_for_label(weekly_price_data, cot_data, selected_label)
                st.write(f"[DEBUG] KL zone: {kl_zone}")
                if kl_zone is None:
                    st.error("KL calculation failed: No KL zone returned.")
                else:
                    result = insert_kl_to_supabase(kl_zone, selected_symbol, selected_asset, selected_label)
                    st.write(f"[DEBUG] Insert result: {result}")
                    if result and result.get('action') in ('inserted', 'updated'):
                        st.success(f"KL {result['action']}! {selected_label}")
                    elif result:
                        st.error(f"KL entry failed: {result.get('error')}")
                    else:
                        st.error("KL entry failed: No result returned from insert function.")
            except Exception as e:
                st.error(f"KL calculation/entry error: {e}")
                st.write(f"[DEBUG] Exception: {e}")
    with col2:
        if st.button("Refresh KLs"):
            st.experimental_rerun()

# --- Price Chart with KL Overlay ---
st.header("Price Chart (Wednesday-Tuesday)")
if not weekly_price_data.empty:
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=weekly_price_data['datetime'],
        open=weekly_price_data['Open'],
        high=weekly_price_data['High'],
        low=weekly_price_data['Low'],
        close=weekly_price_data['Close'],
        name='OHLC'))
    fig = add_kl_overlay(fig, kl_zones, weekly_price_data)
    fig.update_layout(title="Price Chart", height=500)
    st.plotly_chart(fig, use_container_width=True)

# --- RVol Chart ---
st.header("RVol Chart (Wednesday-Tuesday)")
if not weekly_price_data.empty and 'rvol' in weekly_price_data.columns:
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=weekly_price_data['datetime'],
        y=weekly_price_data['rvol'],
        name='RVol',
        marker_color='blue',
        opacity=0.7
    ))
    fig2.add_hline(y=1.0, line_dash="dash", line_color="red", annotation_text="RVol = 1.0")
    fig2.update_layout(title="RVol Chart", height=300)
    st.plotly_chart(fig2, use_container_width=True)

# --- KL Table ---
st.header("Current KL Zones (from DB)")
if kl_zones:
    kl_df = pd.DataFrame(kl_zones)
    st.dataframe(kl_df, use_container_width=True)
else:
    st.info("No KL zones found in database.") 