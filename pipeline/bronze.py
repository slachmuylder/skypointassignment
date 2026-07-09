"""Bronze layer: land raw CSVs as-is, one Parquet file per source CSV.
"""
import datetime as dt
from pathlib import Path
import pandas as pd
from pipeline.config import BRONZE_DIR, RAW_DATA_DIR, SOURCE_TABLES


def _bronze_path_for(table: str, csv_path: Path) -> Path:
    return BRONZE_DIR / table / f"{csv_path.stem}.parquet"


def load_one_file(table: str, csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype=str)
    df["_source_file"] = csv_path.name
    df["_ingested_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return df


def run_bronze(files_to_process: dict[str, list[Path]]) -> dict:
    """files_to_process: {table_name: [csv paths that are new/changed]}.
    Returns a per-table summary of rows written, for the run log."""
    summary = {}
    for table, paths in files_to_process.items():
        rows_in = 0
        for csv_path in paths:
            df = load_one_file(table, csv_path)
            out_path = _bronze_path_for(table, csv_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(out_path, index=False)
            rows_in += len(df)
        summary[table] = {"files_processed": len(paths), "rows_in": rows_in}
    return summary


def discover_source_files() -> dict[str, list[Path]]:
    """Files are stored with YYYY_MM in the filename. Returns a sorted dict
    of files available"""
    result = {}
    for table, pattern in SOURCE_TABLES.items():
        result[table] = sorted(RAW_DATA_DIR.glob(pattern))
    return result


def read_bronze_table(table: str) -> pd.DataFrame:
    """Read every Parquet file for a table back out of Bronze (used by Silver)."""
    paths = sorted((BRONZE_DIR / table).glob("*.parquet"))
    if not paths:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True, sort=False)
