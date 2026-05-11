
import pandas as pd
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from signalvortex.analytics.monetary.collector import compute_growth, get_latest_growth_rates

# Mock data: 14 months of data to calculate YoY (need 12 months lag)
dates = pd.date_range(start="2023-01-01", periods=14, freq="ME")
# Make values simple to verify: 
# Jan 2023: 100
# ...
# Jan 2024: 110 (YoY = 10%)
# Feb 2024: 112 (MoM from Jan: 2/110 approx 1.8%, YoY from Feb 2023: )
values = [100.0] * 14
values[12] = 110.0 # Jan 2024, vs Jan 2023 (100) -> 10% YoY
values[13] = 112.0 # Feb 2024

df = pd.DataFrame({
    "date": dates,
    "region": ["USA"] * 14,
    "aggregate": ["M2"] * 14,
    "value": values
})

print("Original DF tail:")
print(df.tail(3))

df_growth = compute_growth(df)
print("\nComputed Growth (tail):")
print(df_growth.tail(3))

latest = get_latest_growth_rates(df_growth)
print("\nLatest Rates:")
print(latest)
