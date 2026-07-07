"""Validation framework: run after each pipeline execution, produces a
report the COO could read before approving a refresh.

Usage:
    python -m validation.run
"""
import datetime as dt
import json

from pipeline.config import LOG_DIR, REPO_ROOT
from validation.checks import run_all_checks

REPORT_MD = REPO_ROOT / "validation" / "latest_report.md"
REPORT_JSON = REPO_ROOT / "validation" / "latest_report.json"


def load_pipeline_log() -> dict:
    log_path = LOG_DIR / "latest_run.json"
    if not log_path.exists():
        raise SystemExit("No pipeline run found. Run `python -m pipeline.run` first.")
    return json.loads(log_path.read_text())


def run() -> dict:
    pipeline_log = load_pipeline_log()
    checks = run_all_checks(pipeline_log["bronze"], pipeline_log["silver"])

    failures = [c for c in checks if c["status"] == "fail"]
    report = {
        "generated_at": dt.datetime.utcnow().isoformat(),
        "pipeline_run_at": pipeline_log["run_at"],
        "checks_run": len(checks),
        "checks_passed": len(checks) - len(failures),
        "checks_failed": len(failures),
        "checks": checks,
        "pipeline_anomalies": pipeline_log["anomalies"],
    }

    REPORT_JSON.write_text(json.dumps(report, indent=2, default=str))
    _write_markdown(report)
    return report


def _write_markdown(report: dict) -> None:
    lines = [
        "# Pinewood Data Validation Report",
        "",
        f"Generated: {report['generated_at']} UTC  ",
        f"Based on pipeline run: {report['pipeline_run_at']} UTC",
        "",
        f"**{report['checks_passed']}/{report['checks_run']} checks passed.**",
        "",
    ]

    if report["checks_failed"] == 0:
        lines.append("No failing checks this run. Safe to approve this refresh.")
    else:
        lines.append("⚠️ Failing checks below need review before approving this refresh.")

    lines += ["", "## Checks", "", "| Check | Status | Severity | Recommended action | Detail |", "|---|---|---|---|---|"]
    for c in report["checks"]:
        detail = json.dumps(c["detail"], default=str)
        if len(detail) > 120:
            detail = detail[:117] + "..."
        lines.append(f"| {c['check']} | {c['status'].upper()} | {c['severity']} | {c['action']} | `{detail}` |")

    lines += ["", "## Anomalies detected during ingestion (from the pipeline run log)", ""]
    if report["pipeline_anomalies"]:
        lines.append("| Table | Reason | Rows affected | Severity | Action |")
        lines.append("|---|---|---|---|---|")
        for a in report["pipeline_anomalies"]:
            lines.append(f"| {a['table']} | {a['reason']} | {a['rows_affected']} | {a['severity']} | {a['action']} |")
    else:
        lines.append("None.")

    REPORT_MD.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    result = run()
    print(f"{result['checks_passed']}/{result['checks_run']} checks passed.")
    if result["checks_failed"]:
        print(f"{result['checks_failed']} FAILED — see validation/latest_report.md")
