from supabase_client import get_kl_client
import plotly.graph_objects as go

# 1. Fetch KL zones from Supabase for a given symbol and period
def fetch_kl_zones(symbol, period='weekly'):
    kl_client = get_kl_client()
    return kl_client.get_kl_zones_for_symbol(symbol, period)

# 2. Overlay KL zones on a Plotly figure (horizontal lines + rectangle highlight)
def add_kl_overlay(fig, kl_zones, price_data, row=1, col=1):
    for kl in kl_zones:
        # Draw horizontal lines
        fig.add_hline(y=kl['zone_high'], line_dash="dash", line_color="red", annotation_text="KL High", row=row, col=col)
        fig.add_hline(y=kl['zone_low'], line_dash="dash", line_color="blue", annotation_text="KL Low", row=row, col=col)
        # Draw rectangle between the lines
        fig.add_shape(
            type="rect",
            x0=price_data['datetime'].min(),
            x1=price_data['datetime'].max(),
            y0=kl['zone_low'],
            y1=kl['zone_high'],
            fillcolor="rgba(255, 0, 0, 0.1)",  # semi-transparent
            line=dict(width=0),
            row=row, col=col
        )
    return fig 