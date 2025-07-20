# Non-Commercial Dashboard

A Streamlit dashboard for analyzing non-commercial trading positions and market structure across multiple assets.

## Features

- **Weekly Macro View**: Displays weekly price charts with COT analytics
- **Quarterly KL View**: Shows quarterly price charts with Key Liquidity zones analysis
- **Multi-Asset Support**: 19 different assets including Gold, Silver, Forex, Crypto, and Indices
- **Real-time Data**: Fetches live price data and COT reports
- **Interactive Charts**: Plotly-based candlestick charts and COT analytics

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file (optional, for future Supabase integration):
```bash
# .env
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_key
```

## Usage

Run the dashboard:
```bash
streamlit run dashboard.py
```

The dashboard will open in your browser at `http://localhost:8501`

## Navigation

### Weekly Macro View
- Select an asset from the sidebar dropdown
- View weekly price chart (1H candlesticks)
- Analyze COT data with interactive charts
- See non-commercial longs vs shorts and net position ratios

### Quarterly KL View
- View quarterly price charts
- Analyze Key Liquidity zones (KL) analysis
- Review COT summary metrics for the quarter

## Data Sources

- **Price Data**: Yahoo Finance via yahooquery
- **COT Data**: CFTC Public Reporting API
- **Assets**: 19 major futures and spot markets

## Supported Assets

- Gold, Silver, Oil
- Major Forex pairs (EUR, AUD, JPY, CAD, GBP, NZD, CHF)
- Cryptocurrencies (Bitcoin, Ether)
- Major Indices (S&P 500, NASDAQ, Nikkei, Dow Jones)
- Dollar Index and SPY ETF

## Development Roadmap

- [x] Phase 1: Dashboard Architecture
- [x] Phase 2: Weekly Macro View
- [ ] Phase 3: Quarterly KL View (KL calculation)
- [ ] Phase 4: Database Integration (Supabase)
- [ ] Phase 5: Macro Market Structure Dashboard

## Contributing

Feel free to submit issues and enhancement requests! 