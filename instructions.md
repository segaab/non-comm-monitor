1. **Main Page:**

   * Displays a **weekly price chart built out of 1H chart** of the selected symbol.(Allows user to highlight non-comm activities)
   * Shows **weekly COT analytics** table(e.g., non-commercial longs vs shorts, net positions, and changes).

2. **Subpage (Quarterly KL View):**

   * Displays a **quarterly price chart** Divide the year to a 4 quarter.
   * Highlights **automatically calculated KLs**, based on user **identified non-commercial activity** (using marking on the Main page weekly price chart) and **market structure (swing highs/lows + ATR)**.
   * The goal is to visualize macro market positioning and liquidity zones.

---

# **Updated Development Roadmap**

---

## **Phase 1 – Dashboard Architecture**

**Goals:**

* Create the main structure with **multi-page Streamlit navigation**.
* Define two main pages:

  1. **Weekly Macro View** (price + COT).
  2. **Quarterly KL View** (price + liquidity zones).

**Tasks:**

* Set up `streamlit_multipage` or use Streamlit’s built-in `st.sidebar` for page navigation.
* Add a symbol selector (e.g., dropdown for `EURUSD`, `GOLD`, `SPX500`, etc.).
* Fetch and cache hourly price data for the last quarter.
    - Fetch user highlighted KLs from Supabase database 
* Fetch and cache COT data.

---

## **Phase 2 – Main Page (Weekly Price + COT Analytics)**

**Goals:**

* Create a **weeks worth of hourly candlestick chart**.
* Plot **COT analytics** below the chart (e.g., bar chart of non-commercial longs/shorts, or a net-position in percentage).
* Allow the user to highlight a candlestick used for calculating the liquidity KL

**Tasks:**

1. **Weekly Price Chart:**

   * Use Yahoo Finance or other APIs for weekly OHLCV.
   * Plot using Plotly (candlestick).

2. **Weekly COT Chart:**

   * Pull weekly COT data (non-commercials).
   * Display as:

     * **Histogram:** Current Longs vs Shorts.
     * **Line Chart:** Net positions.

---

## **Phase 3 – Subpage (Quarterly KL View)**

**Goals:**

* Display **quarterly price chart**.
* Auto-calculate **KLs** (key liquidity zones) using:

  * ATR-based range expansion.
  * Swing highs/lows.
  * Non-commercial activity spikes (from COT data).

**Tasks:**

1. **Quarterly Price Chart:**

   * Resample price data to 3-month intervals.
   * Plot candles with user selected KLs.

2. **KL Calculation:**

   * Identify areas where **non-commercial net position changes** exceed a threshold.
   * For each candle selected by user, compute ATR and draw a liquidity zone around the swing high/low.

3. **Visual Overlay:**

   * Highlight KLs on the chart with shaded bands or horizontal rectangles.
   * Optionally annotate with “Heavy Non-Commercial Entry Detected”.

---

## **Phase 4 – Database Integration**

* Store **selected symbol**, **identified KLs**, and **COT-derived zones** for later review.
* Table structure:

  * `symbol`, `kl_start`, `kl_end`, `atr_value`, `non_com_delta`, `zone_high`, `zone_low`.

---

## **Phase 5 – Macro Market Structure Dashboard**

* Add a **summary panel** (top of dashboard):

  * Weekly trend direction.
  * Last non-commercial spike date.
  * Current KL zones for reference.

---
