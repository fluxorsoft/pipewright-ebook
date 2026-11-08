"""The checkout offer service (Chapter 19): should this customer see a "welcome back" offer at the checkout?

    uvicorn app.main:app --port 8080        (from the repository root, with Application Default Credentials)

Two ways to answer, and the page shows both:

  weekly   the customer's latest score from the weekly list (lapse_risk_scores, Chapter 13): one BigQuery lookup,
           no endpoint, as fresh as last Monday's run.
  fresh    the lapse model's endpoint, called over REST. Only when the endpoint is deployed. Two ways, FEATURES:
           request  the service reads the customer's features as of today from the data team's feature table and
                    prepares them exactly as training did: the served model's own feature order and training
                    medians (Chapter 13). The answer says which features were filled.
           online   the service sends the customer ID alone; the endpoint reads the features from the online store
                    and fills an empty one with its training median itself (model.serving.features online,
                    Pipewright 1.2). No BigQuery lookup, but the answer cannot say what was filled.

The offer rule is the business's, not the model's: offer when the lapse risk is at least OFFER_AT.

Settings (environment variables): PROJECT, REGION (europe-west2), DATASET (pw_retail), ENDPOINT (lapse-risk-endpoint),
OFFER_AT (0.6), FEATURES (request or online; it must match the served model's model.serving.features). The service's
identity needs to read the dataset, run BigQuery jobs, read the model's files and call the endpoint. It logs no
customer IDs.
"""

import json
import logging
import os
import time
from functools import lru_cache
from pathlib import Path

import google.auth
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from google.auth.transport.requests import AuthorizedSession
from google.cloud import aiplatform, bigquery, storage

PROJECT = os.environ["PROJECT"]
REGION = os.environ.get("REGION", "europe-west2")
DATASET = os.environ.get("DATASET", "pw_retail")
ENDPOINT = os.environ.get("ENDPOINT", "lapse-risk-endpoint")
OFFER_AT = float(os.environ.get("OFFER_AT", "0.6"))
FEATURES = os.environ.get("FEATURES", "request")
if FEATURES not in ("request", "online"):
    raise SystemExit(f"FEATURES is request or online, not {FEATURES!r}")
PAGE = (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("checkout-offer")
app = FastAPI(title="Checkout offer", docs_url=None, redoc_url=None)
bq = bigquery.Client(project=PROJECT, location=REGION)
aiplatform.init(project=PROJECT, location=REGION)


@lru_cache(maxsize=1)
def http() -> AuthorizedSession:
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return AuthorizedSession(credentials)


def served_model() -> dict | None:
    """The endpoint and what the model it serves needs: its feature order and training medians. Looked up per call,
    so a canary or a new version is seen at once; cheap next to the prediction."""
    found = aiplatform.Endpoint.list(filter=f'display_name="{ENDPOINT}"')
    if not found or not found[0].list_models():
        return None
    endpoint = found[0]
    deployed = max(endpoint.list_models(), key=lambda d: endpoint.traffic_split.get(d.id, 0))
    return {"endpoint": endpoint.resource_name, **model_files(f"{deployed.model}@{deployed.model_version_id}")}


@lru_cache(maxsize=8)
def model_files(model: str) -> dict:
    uri = aiplatform.Model(model).uri.rstrip("/")
    bucket, prefix = uri[len("gs://"):].split("/", 1)
    files = storage.Client(project=PROJECT).bucket(bucket)
    stats = json.loads(files.blob(f"{prefix}/training_stats.json").download_as_text())
    return {"features": json.loads(files.blob(f"{prefix}/features.json").download_as_text()),
            "medians": stats["medians"]}


def query_one(sql: str, customer: str) -> dict | None:
    job = bq.query(sql, job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("customer", "STRING", customer)]))
    rows = [dict(r) for r in job.result()]
    return rows[0] if rows else None


def weekly(customer: str) -> dict | None:
    # SELECT *: scored_for (the cut-off, Chapter 14) is there only once the release that writes it is live.
    row = query_one(f"""
        SELECT * FROM `{PROJECT}.{DATASET}.lapse_risk_scores`
        WHERE customer_id = @customer
        ORDER BY scored_at DESC LIMIT 1""", customer)
    if row is None:
        return None
    return {"lapse_risk": round(row["lapse_risk"], 3), "scored_for": str(row.get("scored_for") or ""),
            "model_version": row["model_version_id"], "scored_at": row["scored_at"].isoformat()}


def endpoint_name() -> str | None:
    """The online path needs only the endpoint, not the model's files: the model reads its own features."""
    found = aiplatform.Endpoint.list(filter=f'display_name="{ENDPOINT}"')
    return found[0].resource_name if found and found[0].list_models() else None


def fresh_online(customer: str) -> dict:
    endpoint = endpoint_name()
    if endpoint is None:
        return {"available": False, "why": f"{ENDPOINT} serves no model (it is deployed only when needed)"}
    started = time.perf_counter()
    answer = http().post(f"https://{REGION}-aiplatform.googleapis.com/v1/{endpoint}:predict",
                         json={"instances": [customer]}, timeout=10)
    millis = round((time.perf_counter() - started) * 1000)
    if answer.status_code != 200:
        log.warning("endpoint answered HTTP %s", answer.status_code)
        return {"available": False, "why": f"the endpoint answered HTTP {answer.status_code}"}
    body = answer.json()
    prediction = body["predictions"][0]
    if isinstance(prediction, dict):                    # an unknown customer: an error for this ID only
        return {"available": False, "why": prediction.get("error", "the endpoint had no answer")}
    return {"available": True, "lapse_risk": round(1 - prediction, 3), "model_version": body["modelVersionId"],
            "features_as_of": "the online store's last sync", "filled_with_median": None, "millis": millis}


def fresh(customer: str) -> dict:
    if FEATURES == "online":
        return fresh_online(customer)
    model = served_model()
    if model is None:
        return {"available": False, "why": f"{ENDPOINT} serves no model (it is deployed only when needed)"}
    row = query_one(f"""
        SELECT * FROM `{PROJECT}.{DATASET}.customer_activity`
        WHERE customer_id = @customer ORDER BY feature_timestamp DESC LIMIT 1""", customer)
    if row is None:
        return {"available": False, "why": "no features for this customer in customer_activity"}
    instance, filled = [], []
    for name in model["features"]:
        value = row.get(name)
        if value is None:                                  # empty, as for a one-order customer: as training did
            value = model["medians"][name]
            filled.append(name)
        instance.append(float(value))
    started = time.perf_counter()
    answer = http().post(f"https://{REGION}-aiplatform.googleapis.com/v1/{model['endpoint']}:predict",
                         json={"instances": [instance]}, timeout=10)
    millis = round((time.perf_counter() - started) * 1000)
    if answer.status_code != 200:
        log.warning("endpoint answered HTTP %s", answer.status_code)
        return {"available": False, "why": f"the endpoint answered HTTP {answer.status_code}"}
    body = answer.json()
    probability = body["predictions"][0]
    if not isinstance(probability, (int, float)):         # fail closed: an answer that is not a score is no score
        log.warning("endpoint answered no score")
        return {"available": False, "why": f"the endpoint answered no score: {str(probability)[:200]}"}
    return {"available": True, "lapse_risk": round(1 - probability, 3), "model_version": body["modelVersionId"],
            "features_as_of": f"{row['feature_timestamp']:%Y-%m-%d}", "filled_with_median": filled,
            "features": dict(zip(model["features"], instance)), "millis": millis}


@app.get("/", response_class=HTMLResponse)
def page() -> str:
    return PAGE.replace("{{OFFER_AT}}", f"{OFFER_AT:g}")


@app.get("/api/offer/{customer}")
def offer(customer: str, fresh_score: bool = False) -> dict:
    if not customer.isdigit() or len(customer) > 12:
        raise HTTPException(400, "a customer ID is digits only")
    w = weekly(customer)
    f = fresh(customer) if fresh_score else None
    risk = (f or {}).get("lapse_risk") if f and f.get("available") else (w or {}).get("lapse_risk")
    log.info("offer decided: weekly=%s fresh=%s", w is not None, bool(f and f.get("available")))
    return {"weekly": w, "fresh": f, "offer_at": OFFER_AT,
            "offer": risk is not None and risk >= OFFER_AT,
            "based_on": "fresh" if f and f.get("available") else "weekly" if w else None}


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
