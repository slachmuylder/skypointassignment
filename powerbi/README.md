# Power BI

Not built as part of this pass — Power BI Desktop isn't available in this
environment (Mac, no Windows VM set up), and the plan was for this to be
done separately in Power BI Desktop rather than attempted here.

This folder is the placeholder for the `.pbix` deliverable so the repo
structure matches the assessment's expected layout. When built, it should:

- Connect to the Gold layer (`pipeline/data/gold/*.parquet` — Power BI can
  import Parquet directly, or go through the DuckDB ODBC driver against the
  same files).
- Use `sql/README.md` as the reference for grain and conformed dimensions
  (in particular, `dim_date` is role-played across every fact table's date
  columns — see the "Conformed dimensions" section there).
- Implement the two RLS roles (Regional Director, Community Executive
  Director) against `dim_community.region` / `dim_community.community_id`,
  matching the same scoping rules already enforced server-side in `/api`
  (see `api/scope.py`).
