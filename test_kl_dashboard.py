import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from kl_entry_utils import fetch_quarter_data, calculate_kl_for_label, insert_kl_to_supabase
from kl_data_utils import filter_to_wednesday_tuesday_from_latest, calculate_cot_net_change
from kl_overlay_utils import fetch_kl_zones, add_kl_overlay
import logging
from supabase_client import get_kl_client


st.set_page_config(page_title="KL Test Dashboard", layout="wide")
st.title("KL Test Dashboard")

# --- UI: Asset selection ---
COT_FUTURES_MAPPING = {
    "GOLD - COMMODITY EXCHANGE INC.": "GC=F",
    "SILVER - COMMODITY EXCHANGE INC.": "SI=F",
    "PLATINUM - NEW YORK MERCANTILE EXCHANGE": "PL=F",
    "PALLADIUM - NEW YORK MERCANTILE EXCHANGE": "PA=F",
    "COPPER - COMMODITY EXCHANGE INC.": "HG=F",
    "CRUDE OIL - NEW YORK MERCANTILE EXCHANGE": "CL=F",
    "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE": "NG=F",
    "E-MINI S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE": "ES=F",
    "E-MINI NASDAQ 100 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE": "NQ=F",
    "E-MINI DOW JONES STOCK INDEX - CHICAGO BOARD OF TRADE": "YM=F",
    "EURO FX - CHICAGO MERCANTILE EXCHANGE": "6E=F",
    "BRITISH POUND STERLING - CHICAGO MERCANTILE EXCHANGE": "6B=F",
    "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE": "6J=F",
    "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE": "6A=F",
    "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE": "6C=F",
    "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE": "6S=F",
    "NEW ZEALAND DOLLAR - CHICAGO MERCANTILE EXCHANGE": "6N=F",
    "BITCOIN - CHICAGO MERCANTILE EXCHANGE": "BTC-USD",
    "ETHER - CHICAGO MERCANTILE EXCHANGE": "ETH-USD",
    "DOLLAR INDEX - ICE FUTURES U.S.": "DX-Y.NYB",
    "SPDR S&P 500 ETF TRUST": "SPY",
}

# Move asset selection to sidebar and make it more visible
with st.sidebar:
    st.header("Asset Selection")
    selected_asset = st.selectbox("Select Asset", list(COT_FUTURES_MAPPING.keys()), index=0)
    st.markdown("---")
    st.info("Use the sidebar to select the asset for analysis.")
selected_symbol = COT_FUTURES_MAPPING[selected_asset]

# --- Fetch data ---
price_data, cot_data = fetch_quarter_data(selected_symbol, selected_asset, price_interval='1h')
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

# --- Display latest net change in non-commercial positions ---
latest_cnet_change = None
if not cot_data.empty and 'net_position_ratio' in cot_data.columns:
    cot_net_changes = cot_data['net_position_ratio'].diff().dropna()
    if not cot_net_changes.empty:
        latest_cnet_change = cot_net_changes.iloc[-1]
if latest_cnet_change is not None:
    st.info(f"Latest net change in non-commercial positions: {latest_cnet_change:.4f}")
else:
    st.info("No COT net change data available.")

# --- Price Chart with KL Overlay ---
st.header("Price Chart (Wednesday-Tuesday)")
if not weekly_price_data.empty:
    fig = go.Figure()
    # Candlestick chart
    fig.add_trace(go.Candlestick(
        x=weekly_price_data['datetime'],
        open=weekly_price_data['Open'],
        high=weekly_price_data['High'],
        low=weekly_price_data['Low'],
        close=weekly_price_data['Close'],
        name='Price',
        increasing_line_color='green',
        decreasing_line_color='red',
        showlegend=True
    ))
    # Overlay KL zones
    fig = add_kl_overlay(fig, kl_zones, weekly_price_data)
    # Modern layout
    fig.update_layout(
        title={
            'text': f"{selected_asset} ({selected_symbol}) - Weekly Price (1H)",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 22}
        },
        xaxis_title='Date',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        height=500,
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Volume Chart ---
# Remove the RVol/Volume chart title
def show_volume_chart():
    if not weekly_price_data.empty and 'Volume' in weekly_price_data.columns:
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=weekly_price_data['datetime'],
            y=weekly_price_data['Volume'],
            name='Volume',
            marker_color='blue',
            opacity=0.7
        ))
        fig2.update_layout(height=300, yaxis_title='Volume')
        st.plotly_chart(fig2, use_container_width=True)
show_volume_chart()

# --- KL Entry UI ---
st.header("KL Calculation and Entry")
if not weekly_price_data.empty:
    # Move candle label dropdown to the bottom
    st.markdown("---")
    st.subheader("Select Candle for KL Calculation")
    date_label_to_dt = {dt.strftime('%A, %Y-%m-%d %H:%M'): dt for dt in weekly_price_data['datetime']}
    available_dates = list(date_label_to_dt.keys())
    selected_label = st.selectbox("Select candle for KL calculation:", available_dates, index=len(available_dates)-1)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Add KL Entry"):
            try:
                st.write(f"[DEBUG] Selected label: {selected_label}")
                # Convert label to pandas Timestamp with correct timezone
                date_label_to_dt = {dt.strftime('%A, %Y-%m-%d %H:%M'): dt for dt in weekly_price_data['datetime']}
                if selected_label in date_label_to_dt:
                    selected_dt = date_label_to_dt[selected_label]
                else:
                    # Fallback: try parsing
                    selected_dt = pd.to_datetime(selected_label)
                st.write(f"[DEBUG] Converted selected_label to datetime: {selected_dt}")
                st.write(f"[KL UI] Calling calculate_kl_for_label with label={selected_label}")
                kl_zone = calculate_kl_for_label(weekly_price_data, cot_data, selected_label)
                st.write(f"[KL UI] KL zone result: {kl_zone}")
                st.write(f"[DEBUG] KL zone: {kl_zone}")
                if kl_zone is None:
                    st.error("KL calculation failed: No KL zone returned.")
                else:
                    st.write(f"[KL UI] Calling insert_kl_to_supabase with kl_zone for label={selected_label}")
                    result = insert_kl_to_supabase(kl_zone, selected_symbol, selected_asset, selected_label)
                    st.write(f"[KL UI] Insert result: {result}")
                    st.write(f"[DEBUG] Insert result: {result}")
                    if result and result.get('action') in ('inserted', 'updated'):
                        st.success(f"KL {result['action']}! {selected_label}")
                        st.rerun()
                    elif result:
                        st.error(f"KL entry failed: {result.get('error')}")
                    else:
                        st.error("KL entry failed: No result returned from insert function.")
            except Exception as e:
                st.error(f"KL calculation/entry error: {e}")
                st.write(f"[DEBUG] Exception: {e}")
    with col2:
        if st.button("Refresh KLs"):
            st.rerun()

    # --- Remove KL Entry Dropdown and Button ---
    st.markdown("---")
    kl_client = get_kl_client()
    all_kl = kl_client.get_kl_zones_for_symbol(selected_symbol, time_period='weekly')
    kl_labels = [str(entry.get('candle_label')) for entry in all_kl]
    if kl_labels:
        kl_to_remove = st.selectbox("Select KL to remove (by candle):", kl_labels, key="remove-kl-dropdown")
        if st.button("Remove KL Entry"):
            entry_to_delete = None
            for entry in all_kl:
                if str(entry.get('candle_label')) == str(kl_to_remove):
                    entry_to_delete = entry
                    break
            if entry_to_delete:
                success = kl_client.delete_kl_zone(entry_to_delete['id'])
                if success:
                    st.success(f"KL entry for {selected_symbol} @ {kl_to_remove} deleted.")
                    st.rerun()
                else:
                    st.error("Failed to delete KL entry.")
            else:
                st.warning("No KL entry found for this symbol and candle.")
    else:
        st.info("No KL entries available for removal.")

# --- KL Table ---
# Move KL table to the bottom
st.header("Current KL Zones (from DB)")
if kl_zones:
    kl_df = pd.DataFrame(kl_zones)
    st.dataframe(kl_df, use_container_width=True)
else:
    st.info("No KL zones found in database.") 