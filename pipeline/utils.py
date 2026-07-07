"""Small shared helpers used across bronze/silver/gold stages."""
import hashlib
import re

import pandas as pd

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_mixed_date(series: pd.Series) -> pd.Series:
    """Parse a date column that mixes YYYY-MM-DD and MM/DD/YYYY (a confirmed
    anomaly in pcc_residents dob/admit_date/discharge_date). Returns
    normalized ISO date strings (or NaT-safe None)."""
    parsed = pd.to_datetime(series, format="mixed", errors="coerce")
    return parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), None)


def row_hash(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    """Stable hash of the given columns per row, used as a dedup / idempotency key."""

    def _hash(row) -> str:
        payload = "|".join("" if pd.isna(v) else str(v) for v in row)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return df[columns].apply(_hash, axis=1)
