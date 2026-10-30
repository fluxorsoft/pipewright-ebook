"""The data team's jobs, run by hand: load the transactions, then run SQL files from data-team/sql/.

    python tools/data_team.py --project <project> load
    python tools/data_team.py --project <project> sql customer_activity_backfill.sql lapse_risk_entities.sql
    python tools/data_team.py --project <project> sql customer_activity_month.sql --as-of "2011-12-01 00:00:00"

Uses google-cloud-bigquery, which `pip install "pipewright-mlops[gcp]"` installs, and your gcloud credentials. The
tables go to the dataset the SQL names (pw_retail, the retail tenant's dataset in the book's environment).
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[1] / "data-team"

parser = argparse.ArgumentParser()
parser.add_argument("--project", required=True)
parser.add_argument("--location", default="europe-west2")
parser.add_argument("--dataset", default="pw_retail")
sub = parser.add_subparsers(dest="cmd", required=True)
sub.add_parser("load")
run = sub.add_parser("sql")
run.add_argument("files", nargs="+")
run.add_argument("--as-of", help="the @as_of parameter, a UTC timestamp")
args = parser.parse_args()
client = bigquery.Client(project=args.project, location=args.location)

if args.cmd == "load":
    schema = client.schema_from_json(str(ROOT / "schemas" / "transactions.json"))
    table = f"{args.project}.{args.dataset}.retail_transactions"
    config = bigquery.LoadJobConfig(source_format=bigquery.SourceFormat.CSV, skip_leading_rows=1, schema=schema,
                                    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    with open(ROOT / "data" / "transactions.csv", "rb") as f:
        client.load_table_from_file(f, table, job_config=config).result()
    print(f"{table}: {client.get_table(table).num_rows:,} rows")
else:
    params = []
    if args.as_of:
        as_of = datetime.fromisoformat(args.as_of).replace(tzinfo=timezone.utc)
        params.append(bigquery.ScalarQueryParameter("as_of", "TIMESTAMP", as_of))
    for name in args.files:
        sql = (ROOT / "sql" / name).read_text(encoding="utf-8")
        job = client.query(sql, job_config=bigquery.QueryJobConfig(
            query_parameters=params, default_dataset=f"{args.project}.{args.dataset}"))
        try:
            job.result()
        except Exception as e:                       # an ASSERT that fails, a missing table: say which file
            reason = (getattr(e, "errors", None) or [{}])[0].get("message") or str(e)
            sys.exit(f"{name}: {reason}")
        steps = list(client.list_jobs(parent_job=job.job_id)) if job.statement_type == "SCRIPT" else [job]
        changed = sum(s.num_dml_affected_rows or 0 for s in steps if s.statement_type in ("INSERT", "MERGE"))
        made = [s.destination.table_id for s in steps if s.statement_type == "CREATE_TABLE_AS_SELECT"]
        what = f"created {', '.join(made)}" if made else f"{changed:,} rows added"
        print(f"{name}: {what}, {job.total_bytes_processed or 0:,} bytes processed")
