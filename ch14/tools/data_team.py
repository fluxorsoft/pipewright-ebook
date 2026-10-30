"""The data team's jobs, run by hand: load the transactions, then run SQL files from data-team/sql/.

    python tools/data_team.py --project <project> load
    python tools/data_team.py --project <project> sql customer_activity_backfill.sql lapse_risk_entities.sql
    python tools/data_team.py --project <project> sql customer_activity_month.sql --as-of "2011-12-01 00:00:00"
    python tools/data_team.py --project <project> sql customer_purchases.sql --loaded-until "2011-12-10 00:00:00"
    python tools/data_team.py --project <project> sql usecases/lapse-risk/sql/synthetic_source.sql
    python tools/data_team.py --project <project> feature-group customer_activity

Uses google-cloud-bigquery, which `pip install "pipewright-mlops[gcp]"` installs, and your gcloud credentials. The
tables go to the dataset the SQL names (pw_retail, the retail tenant's dataset in the book's environment).

feature-group registers a feature table in Agent Platform's Feature Store, as data-team/feature_groups.json
describes it: a feature group over the table and one feature per column (Chapter 13). Safe to repeat: what exists is
left as it is.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import google.auth
from google.auth.transport.requests import AuthorizedSession
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
run.add_argument("--loaded-until", help="the @loaded_until parameter, a UTC timestamp")
group = sub.add_parser("feature-group")
group.add_argument("names", nargs="+", help="feature groups in data-team/feature_groups.json")
args = parser.parse_args()
client = bigquery.Client(project=args.project, location=args.location)


def register(name: str, spec: dict) -> None:
    """The feature group and its features, created when missing (each create is a long-running operation)."""
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    http = AuthorizedSession(credentials)
    api = f"https://{args.location}-aiplatform.googleapis.com/v1/projects/{args.project}/locations/{args.location}"

    def wait(answer):
        answer.raise_for_status()
        operation = answer.json()
        while not operation.get("done"):
            time.sleep(5)
            operation = http.get(f"https://{args.location}-aiplatform.googleapis.com/v1/{operation['name']}").json()
        if "error" in operation:
            sys.exit(f"{name}: {operation['error'].get('message')}")

    if http.get(f"{api}/featureGroups/{name}").status_code == 404:
        wait(http.post(f"{api}/featureGroups", params={"featureGroupId": name}, json={
            "description": spec["description"],
            "bigQuery": {"bigQuerySource": {"inputUri": f"bq://{args.project}.{args.dataset}.{spec['table']}"},
                         "entityIdColumns": spec["entity"]}}))
        print(f"feature group {name}: created over {args.dataset}.{spec['table']}")
    else:
        print(f"feature group {name}: exists")
    have = {f["name"].rsplit("/", 1)[-1]
            for f in http.get(f"{api}/featureGroups/{name}/features").json().get("features", [])}
    for feature, description in spec["features"].items():
        if feature not in have:
            wait(http.post(f"{api}/featureGroups/{name}/features", params={"featureId": feature},
                           json={"description": description}))
    print(f"  {len(spec['features'])} features: {', '.join(spec['features'])}")


if args.cmd == "feature-group":
    groups = json.loads((ROOT / "feature_groups.json").read_text(encoding="utf-8"))
    for name in args.names:
        register(name, groups[name])
elif args.cmd == "load":
    schema = client.schema_from_json(str(ROOT / "schemas" / "transactions.json"))
    table = f"{args.project}.{args.dataset}.retail_transactions"
    config = bigquery.LoadJobConfig(source_format=bigquery.SourceFormat.CSV, skip_leading_rows=1, schema=schema,
                                    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    with open(ROOT / "data" / "transactions.csv", "rb") as f:
        client.load_table_from_file(f, table, job_config=config).result()
    print(f"{table}: {client.get_table(table).num_rows:,} rows")
else:
    params = [bigquery.ScalarQueryParameter(name, "TIMESTAMP",
                                            datetime.fromisoformat(value).replace(tzinfo=timezone.utc))
              for name, value in (("as_of", args.as_of), ("loaded_until", args.loaded_until)) if value]
    for name in args.files:
        path = ROOT / "sql" / name if "/" not in name else ROOT.parent / name   # a path: a use case's own SQL
        sql = path.read_text(encoding="utf-8")
        job = client.query(sql, job_config=bigquery.QueryJobConfig(
            query_parameters=params, default_dataset=f"{args.project}.{args.dataset}"))
        try:
            job.result()
        except Exception as e:                       # an ASSERT that fails, a missing table: say which file
            reason = (getattr(e, "errors", None) or [{}])[0].get("message") or str(e)
            sys.exit(f"{name}: {reason}")
        steps = list(client.list_jobs(parent_job=job.job_id)) if job.statement_type == "SCRIPT" else [job]
        changed = sum(s.num_dml_affected_rows or 0 for s in steps if s.statement_type in ("INSERT", "MERGE"))
        made = [s.destination.table_id if s.destination else "a view" for s in steps
                if s.statement_type in ("CREATE_TABLE_AS_SELECT", "CREATE_VIEW")]
        what = f"created {', '.join(made)}" if made else f"{changed:,} rows added"
        print(f"{name}: {what}, {job.total_bytes_processed or 0:,} bytes processed")
