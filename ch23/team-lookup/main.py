"""The retailer's own lookup service (Chapter 23): a small store the ML team runs itself, behind Pipewright's lookup
gateway. It loads the newest generation of Pipewright's Parquet export of the online features, checks every file
against the manifest before it serves, keeps the last good generation in memory, and answers the gateway's
POST /lookup {"entity_ids": [...]} with {"features": {id: {name: value}}}. An ID it does not hold is left out: the
gateway answers that ID's caller with its own error.

Settings (environment variables): EXPORT (gs://<bucket>/online-export/<tenant>/<usecase>/), RELOAD_SECONDS (900).
It runs as an identity Pipewright grants read access to the export (model.serving.online_store.export.readers).
"""
import hashlib
import io
import json
import logging
import os
import threading
import time

import pyarrow.parquet as pq
from fastapi import FastAPI
from google.cloud import storage
from pydantic import BaseModel

EXPORT = os.environ["EXPORT"].rstrip("/") + "/"
RELOAD_SECONDS = int(os.environ.get("RELOAD_SECONDS", "900"))
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("team-lookup")
app = FastAPI()
gcs = storage.Client()
state = {"generation": None, "rows": {}, "loaded_at": None, "contract": None}


def newest_generation() -> str | None:
    bucket, _, prefix = EXPORT.removeprefix("gs://").partition("/")
    names = {b.name[len(prefix):].split("/", 1)[0] for b in gcs.list_blobs(bucket, prefix=prefix)}
    gens = sorted(n for n in names if n.startswith("g"))
    return gens[-1] if gens else None


def load(generation: str) -> None:
    """Check before you load, load beside, then swap: a generation that fails a check is never served."""
    bucket_name, _, prefix = EXPORT.removeprefix("gs://").partition("/")
    bucket = gcs.bucket(bucket_name)
    manifest = json.loads(bucket.blob(f"{prefix}{generation}/manifest.json").download_as_bytes())
    key, rows = manifest["entity_key"], {}
    for f in manifest["files"]:
        data = bucket.blob(f["name"], generation=int(f["generation"])).download_as_bytes()
        if hashlib.sha256(data).hexdigest() != f["sha256"]:
            raise ValueError(f"{f['name']}: SHA-256 differs from the manifest")
        for r in pq.read_table(io.BytesIO(data)).to_pylist():
            rows[str(r.pop(key))] = r
    if len(rows) != int(manifest["rows"]):
        raise ValueError(f"loaded {len(rows)} rows, the manifest says {manifest['rows']}")
    state.update(generation=generation, rows=rows, loaded_at=time.time(),
                 contract=(manifest.get("feature_contract") or {}).get("version"))     # the swap
    log.info(json.dumps({"severity": "INFO", "message": "loaded", "generation": generation, "rows": len(rows),
                         "feature_contract": state["contract"]}))


def refresh() -> None:
    try:
        newest = newest_generation()
        if newest and newest != state["generation"]:
            load(newest)
    except Exception as e:  # noqa: BLE001 - keep serving the last good generation
        log.warning(json.dumps({"severity": "WARNING", "message": f"not reloaded: {e}",
                                "serving": state["generation"]}))


def reloader() -> None:
    while True:
        time.sleep(RELOAD_SECONDS)
        refresh()


refresh()
threading.Thread(target=reloader, daemon=True).start()


class Lookup(BaseModel):
    entity_ids: list[str]


@app.post("/lookup")
def lookup(req: Lookup) -> dict:
    return {"features": {i: state["rows"][i] for i in req.entity_ids if i in state["rows"]}}


@app.get("/healthz")
def healthz() -> dict:
    return {"generation": state["generation"], "rows": len(state["rows"]), "feature_contract": state["contract"]}
