"""Score one customer online: what an application does before it calls the lapse model's endpoint (Chapter 13).

    python tools/score_customer.py --project pw-ebook --customer 15098

1. Reads the customer's latest row from the data team's feature table, customer_activity.
2. Finds the model the endpoint serves and reads, from that model's own files, the order of its features
   (features.json) and the medians it was trained with (training_stats.json).
3. Fills an empty value with the training median, exactly as batch scoring does. The endpoint does not fill it:
   send it an empty value and it answers HTTP 503 "Prediction failed".
4. Calls the endpoint over REST and prints the answer, with the version that gave it.

Needs: pip install google-cloud-aiplatform google-cloud-bigquery google-cloud-storage, and
`gcloud auth application-default login`.
"""

import argparse
import json

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import aiplatform, bigquery, storage


def model_files(project: str, model_resource: str) -> tuple[list, dict]:
    """features.json and the training medians of the model version the endpoint serves."""
    uri = aiplatform.Model(model_resource).uri.rstrip("/")
    bucket, prefix = uri[len("gs://"):].split("/", 1)
    files = storage.Client(project=project).bucket(bucket)
    features = json.loads(files.blob(f"{prefix}/features.json").download_as_text())
    medians = json.loads(files.blob(f"{prefix}/training_stats.json").download_as_text())["medians"]
    return features, medians


def latest_features(project: str, dataset: str, customer: str) -> dict:
    query = f"""
        SELECT * FROM `{project}.{dataset}.customer_activity`
        WHERE customer_id = @customer
        ORDER BY feature_timestamp DESC LIMIT 1"""
    job = bigquery.Client(project=project).query(query, job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("customer", "STRING", customer)]))
    rows = [dict(r) for r in job.result()]
    if not rows:
        raise SystemExit(f"customer {customer} has no row in customer_activity")
    return rows[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", default="europe-west2")
    parser.add_argument("--dataset", default="pw_retail")
    parser.add_argument("--endpoint", default="lapse-risk-endpoint", help="the endpoint's display name")
    parser.add_argument("--customer", required=True)
    args = parser.parse_args()

    aiplatform.init(project=args.project, location=args.region)
    found = aiplatform.Endpoint.list(filter=f'display_name="{args.endpoint}"')
    if not found or not found[0].list_models():
        raise SystemExit(f"{args.endpoint} serves no model: run `pipewright deploy-model` first")
    endpoint = found[0]
    serving = max(endpoint.list_models(), key=lambda d: endpoint.traffic_split.get(d.id, 0))
    features, medians = model_files(args.project, f"{serving.model}@{serving.model_version_id}")

    row = latest_features(args.project, args.dataset, args.customer)
    instance, filled = [], []
    for name in features:
        value = row.get(name)
        if value is None:                       # empty, as for a customer with one order: the training median
            value = medians[name]
            filled.append(name)
        instance.append(float(value))
    print(f"customer {args.customer}, features as of {row['feature_timestamp']:%Y-%m-%d}:")
    for name, value in zip(features, instance):
        print(f"  {name:<25} {value:>10}{'  (empty: the training median)' if name in filled else ''}")

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    url = f"https://{args.region}-aiplatform.googleapis.com/v1/{endpoint.resource_name}:predict"
    answer = AuthorizedSession(credentials).post(url, json={"instances": [instance]})
    answer.raise_for_status()
    body = answer.json()
    probability = body["predictions"][0]
    print(f"return probability {probability:.3f}, lapse risk {1 - probability:.3f} "
          f"(model version {body['modelVersionId']})")


if __name__ == "__main__":
    main()
