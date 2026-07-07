"""Single entrypoint for the full Bronze -> Silver -> Gold pipeline.

Usage:
    python -m pipeline.run
"""
import datetime as dt
import json
import time

import pandas as pd

from pipeline.bronze import discover_source_files, read_bronze_table, run_bronze
from pipeline.config import LOG_DIR, SILVER_DIR, data_window
from pipeline.gold import (
    build_dim_community,
    build_dim_date,
    build_dim_employee,
    build_dim_resident,
    build_dim_resident_care_level_scd2,
    build_dim_unit,
    build_fact_acuity_snapshot,
    build_fact_incident,
    build_fact_labor,
    build_fact_lease,
    build_fact_resident_day,
    build_fact_review,
    build_fact_lead,
    write_gold_table,
)
from pipeline.silver import CLEANERS
from pipeline.state import filter_new_or_changed, load_state, save_state


def run() -> dict:
    start = time.time()
    log: dict = {
        "run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "bronze": {},
        "silver": {},
        "gold": {},
        "anomalies": [],
    }

    # ---- Bronze ----
    all_files = discover_source_files()
    #get the files and hash that currently exist
    state = load_state()
    #determine files to be processed
    to_process, new_state, file_status = filter_new_or_changed(all_files, state)
    #overwrite files that need to be updated
    files_needing_work = {t: p for t, p in to_process.items() if p}
    log["bronze"] = run_bronze(files_needing_work)
    for table, paths in to_process.items():
        log["bronze"].setdefault(table, {"files_processed": 0, "rows_in": 0})
        log["bronze"][table]["files_skipped_unchanged"] = len(all_files[table]) - len(paths)
        log["bronze"][table]["files_new"] = file_status[table]["new"]
        log["bronze"][table]["files_updated_content"] = file_status[table]["updated"]
        if file_status[table]["updated"]:
            # A previously-ingested filename came back with different content --
            # a retroactive revision of data that may have already been reported
            # on, not just a new month landing. Flagged distinctly rather than
            # silently folded into "processed some files this run".
            log["anomalies"].append(
                {
                    "table": table,
                    "reason": "source_file_content_revised",
                    "rows_affected": len(file_status[table]["updated"]),
                    "severity": "high",
                    "action": "raise_to_client",
                }
            )
    save_state(new_state)

    # ---- Silver ----
    silver_tables: dict[str, pd.DataFrame] = {}
    for table, cleaner in CLEANERS.items():
        bronze_df = read_bronze_table(table)
        rows_in = len(bronze_df)
        clean_df, rejects = cleaner(bronze_df)
        silver_tables[table] = clean_df

        SILVER_DIR.mkdir(parents=True, exist_ok=True)
        clean_df.to_parquet(SILVER_DIR / f"{table}.parquet", index=False)
        if not rejects.empty:
            (SILVER_DIR / "rejects").mkdir(parents=True, exist_ok=True)
            rejects.to_parquet(SILVER_DIR / "rejects" / f"{table}.parquet", index=False)
            for reason, count in rejects["reject_reason"].value_counts().items():
                log["anomalies"].append(
                    {
                        "table": table,
                        "reason": reason,
                        "rows_affected": int(count),
                        "severity": "high" if reason == "unresolvable_hourly_rate" else "medium",
                        "action": "quarantine",
                    }
                )

        log["silver"][table] = {
            "rows_in": rows_in,
            "rows_out": len(clean_df),
            # rows_dropped: removed from the dataset entirely (structural problems,
            # e.g. unknown_community_id). rows_flagged: total rows with an anomaly
            # noted in rejects/, which can be larger than rows_dropped since some
            # anomalies (bad acuity_score, future-dated discharge) are handled by
            # nulling just the offending field rather than dropping the resident --
            # see pipeline/silver.py::clean_pcc_residents.
            "rows_dropped": rows_in - len(clean_df),
            "rows_flagged": len(rejects),
        }

    # ---- Gold ----
    care_level_scd = build_dim_resident_care_level_scd2(
        silver_tables["pcc_residents"], silver_tables["pcc_care_history"]
    )
    gold_tables = {
        "dim_community": build_dim_community(),
        "dim_resident": build_dim_resident(silver_tables["pcc_residents"], care_level_scd),
        "dim_resident_care_level": care_level_scd,
        "dim_unit": build_dim_unit(silver_tables["yardi_units"]),
        "dim_employee": build_dim_employee(silver_tables["adp_shifts"]),
        "dim_date": build_dim_date(*data_window()),
        "fact_resident_day": build_fact_resident_day(silver_tables["pcc_residents"], care_level_scd),
        "fact_acuity_snapshot": build_fact_acuity_snapshot(silver_tables["pcc_residents"]),
        "fact_lease": build_fact_lease(silver_tables["yardi_leases"]),
        "fact_labor": build_fact_labor(silver_tables["adp_shifts"]),
        "fact_incident": build_fact_incident(silver_tables["pcc_incidents"]),
        "fact_review": build_fact_review(silver_tables["gbp_reviews"]),
        "fact_lead": build_fact_lead(silver_tables["hubspot_leads"]),
    }
    for name, df in gold_tables.items():
        n = write_gold_table(df, name)
        log["gold"][name] = {"rows_out": n}

    log["duration_seconds"] = round(time.time() - start, 2)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "latest_run.json", "w") as f:
        json.dump(log, f, indent=2, default=str)
    _write_markdown_log(log)
    return log


def _write_markdown_log(log: dict) -> None:
    lines = [
        "# Pipeline Run Report",
        "",
        f"Run at: {log['run_at']} UTC  ",
        f"Duration: {log['duration_seconds']}s",
        "",
        "## Bronze (incremental ingestion)",
        "",
        "| Table | New files | Revised files (content changed) | Skipped (unchanged) | Rows ingested |",
        "|---|---|---|---|---|",
    ]
    for table, stats in log["bronze"].items():
        lines.append(
            f"| {table} | {len(stats.get('files_new', []))} | {len(stats.get('files_updated_content', []))} "
            f"| {stats.get('files_skipped_unchanged', 0)} | {stats.get('rows_in', 0)} |"
        )

    lines += ["", "## Silver (cleaning)", "", "| Table | Rows in | Rows out | Rows dropped | Rows flagged |", "|---|---|---|---|---|"]
    for table, stats in log["silver"].items():
        lines.append(f"| {table} | {stats['rows_in']} | {stats['rows_out']} | {stats['rows_dropped']} | {stats['rows_flagged']} |")

    lines += ["", "## Gold (mart tables)", "", "| Table | Rows |", "|---|---|"]
    for table, stats in log["gold"].items():
        lines.append(f"| {table} | {stats['rows_out']} |")

    lines += ["", "## Anomalies detected this run", ""]
    if log["anomalies"]:
        lines.append("| Table | Reason | Rows affected | Severity | Action |")
        lines.append("|---|---|---|---|---|")
        for a in log["anomalies"]:
            lines.append(f"| {a['table']} | {a['reason']} | {a['rows_affected']} | {a['severity']} | {a['action']} |")
    else:
        lines.append("No anomalies detected this run.")

    (LOG_DIR / "latest_run.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    result = run()
    print(json.dumps({k: v for k, v in result.items() if k != "anomalies"}, indent=2, default=str))
    print(f"\n{len(result['anomalies'])} anomaly type(s) detected this run — see pipeline/logs/latest_run.md")
