"""Small shared helpers used across bronze/silver/gold stages."""
import pandas as pd


def parse_mixed_date(series: pd.Series) -> pd.Series:
    """Parse a date column that mixes YYYY-MM-DD and MM/DD/YYYY (a confirmed
    anomaly in pcc_residents dob/admit_date/discharge_date). Returns
    normalized ISO date strings (or NaT-safe None)."""
    parsed = pd.to_datetime(series, format="mixed", errors="coerce")
    return parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), None)
