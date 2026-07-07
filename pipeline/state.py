"""Incremental-load bookkeeping: which raw CSVs have already been ingested.

A file is re-ingested only if it's new or its content hash changed since the
last run, so re-running the pipeline on an unchanged dataset is a no-op at
the Bronze stage, and adding a new monthly CSV only processes that one file.
"""
import hashlib
from pathlib import Path

import pandas as pd

from pipeline.config import STATE_FILE


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_state() -> dict[str, str]:
    if not STATE_FILE.exists():
        return {}
    df = pd.read_parquet(STATE_FILE)
    return dict(zip(df["file_name"], df["file_hash"]))


def save_state(state: dict[str, str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [{"file_name": k, "file_hash": v} for k, v in state.items()]
    ).to_parquet(STATE_FILE, index=False)


def filter_new_or_changed(
    files_by_table: dict[str, list[Path]], state: dict[str, str]
) -> tuple[dict[str, list[Path]], dict[str, str]]:
    """Returns (files that need reprocessing, updated full state dict)."""
    to_process: dict[str, list[Path]] = {}
    new_state = dict(state)
    for table, paths in files_by_table.items():
        changed = []
        for path in paths:
            h = _file_hash(path)
            key = f"{table}/{path.name}"
            if state.get(key) != h:
                changed.append(path)
                new_state[key] = h
        to_process[table] = changed
    return to_process, new_state
