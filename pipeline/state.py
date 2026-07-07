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
    """Load the state file that stores file name
    and hash of each file that has been processed."""
    if not STATE_FILE.exists():
        return {}
    df = pd.read_parquet(STATE_FILE)
    #returns a hash for future comparison
    return dict(zip(df["file_name"], df["file_hash"]))


def save_state(state: dict[str, str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [{"file_name": k, "file_hash": v} for k, v in state.items()]
    ).to_parquet(STATE_FILE, index=False)


def filter_new_or_changed(
    files_by_table: dict[str, list[Path]], state: dict[str, str]
) -> tuple[dict[str, list[Path]], dict[str, str], dict[str, dict[str, list[str]]]]:
    """Returns (files that need reprocessing, updated full state dict,
    per-table breakdown of *why* each file needs reprocessing).

    "Needs reprocessing" covers two different situations that are worth
    distinguishing even though both are handled identically by Bronze:
    a brand-new filename never seen before, vs. a previously-ingested
    filename whose content has since changed (e.g. a source system
    re-delivering a corrected export under the same name) -- the latter is a
    retroactive revision of data that may have already been reported on, and
    is surfaced as a distinct anomaly rather than folded silently into
    "processed some files this run".
    """
    to_process: dict[str, list[Path]] = {}
    new_state = dict(state)
    file_status: dict[str, dict[str, list[str]]] = {}
    for table, paths in files_by_table.items():
        changed = []
        new_files: list[str] = []
        updated_files: list[str] = []
        for path in paths:
            h = _file_hash(path)
            key = f"{table}/{path.name}"
            if key not in state:
                changed.append(path)
                new_files.append(path.name)
                new_state[key] = h
            elif state[key] != h:
                changed.append(path)
                updated_files.append(path.name)
                new_state[key] = h
        to_process[table] = changed
        file_status[table] = {"new": new_files, "updated": updated_files}
    return to_process, new_state, file_status
