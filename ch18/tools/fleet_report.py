"""The fleet report (Chapter 18): every use case in every environment, on one page, from the records Pipewright keeps.

    python tools/fleet_report.py --out fleet.html [--mask]

Reads, for each environment in environments/*.yaml: its manifest, each use case's live release pointer, its champion
(`pipewright lineage --json`), its training runs (<use case>_model_metrics), its scoring runs (<use case>_monitoring),
its pipeline jobs, the event log (<prefix>_evidence.events, Chapter 17) and what waits for a person
(`pipewright decisions pending --json`). Writes one self-contained HTML page with charts; nothing is changed.

--mask replaces email addresses with "..." (for screenshots and sharing). Needs the gcp extra of Pipewright and read
access to each environment (an operator has it).
"""

import argparse
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml
from google.cloud import aiplatform, bigquery, storage

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ("release.live", "release.promoted", "release.rolled_back", "model.approved", "model.deployed",
             "model.undeployed", "retrain.approved", "retrain.declined", "retrain.snoozed", "data.erased")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def gcs_json(client, uri: str) -> dict | None:
    bucket, path = uri[len("gs://"):].split("/", 1)
    blob = client.bucket(bucket).blob(path)
    return json.loads(blob.download_as_text()) if blob.exists() else None


def pipewright_json(*args) -> object | None:
    # The pipewright command installed next to this Python (the same virtual environment), else the one on PATH.
    here = Path(sys.executable).parent
    exe = next((str(here / n) for n in ("pipewright", "pipewright.exe") if (here / n).exists()),
               shutil.which("pipewright") or "pipewright")
    done = subprocess.run([exe, *args, "--json"], cwd=ROOT, capture_output=True, text=True)
    try:
        return json.loads(done.stdout) if done.returncode == 0 else None
    except ValueError:
        return None


def table_rows(bq, table: str, sql: str) -> list[dict]:
    try:
        bq.get_table(table)
    except Exception:  # noqa: BLE001 - a use case without that table has nothing to show
        return []
    return [dict(r) for r in bq.query(sql.format(table=table)).result()]


def collect() -> dict:
    usecases = sorted(p.parent.name for p in (ROOT / "usecases").glob("*/usecase.yaml"))
    # Reading an object needs no project; the client wants one anyway, before the manifest names it.
    envs, gcs = [], storage.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT") or "-")
    for path in sorted((ROOT / "environments").glob("*.yaml"), key=lambda p: (p.stem != "test", p.stem)):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))["spec"]
        manifest = gcs_json(gcs, spec["manifest"])
        project, region = manifest["project"], manifest["region"]
        dataset = next(iter(manifest["tenants"].values()))["bigquery_dataset"]
        bq = bigquery.Client(project=project, location=region)
        aiplatform.init(project=project, location=region)
        env = {"name": path.stem, "project": project, "usecases": {}, "events": [], "pending": [], "compute": {}}

        jobs = aiplatform.PipelineJob.list(order_by="create_time desc")
        for uc in usecases:
            pointer = gcs_json(gcs, f"gs://{manifest['artifacts_bucket']}/contracts/{uc}/current.json")
            lineage = pipewright_json("lineage", "--env", path.stem, "--usecase", uc)
            name = uc.replace("-", "_")
            env["usecases"][uc] = {
                "pointer": pointer,
                "champion": lineage,
                "training": table_rows(bq, f"{project}.{dataset}.{name}_model_metrics",
                                       "SELECT evaluated_at, primary_metric, primary_value, decision, run_id "
                                       "FROM `{table}` ORDER BY evaluated_at"),
                "scoring": table_rows(bq, f"{project}.{dataset}.{name}_monitoring",
                                      "SELECT monitored_at, source_uri, model_version_id, max_feature_psi, "
                                      "prediction_psi, alert FROM `{table}` ORDER BY monitored_at"),
            }
            hours = sum((j.gca_resource.end_time - j.gca_resource.start_time).total_seconds() / 3600
                        for j in jobs if j.display_name.startswith(f"{uc}-r")
                        and j.gca_resource.end_time and j.gca_resource.start_time)
            env["compute"][uc] = {"hours": hours, "runs": sum(1 for j in jobs if j.display_name.startswith(f"{uc}-r"))}

        evidence = next((d.dataset_id for d in bq.list_datasets() if d.dataset_id.endswith("_evidence")), None)
        if evidence:
            env["events"] = [dict(r) for r in bq.query(
                f"SELECT publish_time, JSON_VALUE(data, '$.event_type') AS event_type, "
                f"JSON_VALUE(data, '$.usecase') AS usecase, JSON_VALUE(data, '$.release') AS release, "
                f"TO_JSON_STRING(JSON_QUERY(data, '$.data')) AS detail "
                f"FROM `{project}.{evidence}.events` ORDER BY publish_time DESC LIMIT 500").result()]
        env["evidence"] = evidence
        env["pending"] = pipewright_json("decisions", "pending", "--env", path.stem) or []
        envs.append(env)
    return {"usecases": usecases, "envs": envs, "at": datetime.now(timezone.utc)}


# ------------------------------------------------------------------------------------------------ rendering --

def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def when(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.strftime("%d %b %H:%M")


def scale(lo, hi, a, b):
    span = (hi - lo) or 1
    return lambda v: a + (v - lo) / span * (b - a)


def ticks(lo, hi, n=4):
    step = (hi - lo) / n
    return [lo + i * step for i in range(n + 1)]


def chart_training(rows: list[dict], slot: int) -> str:
    """Primary metric of every training run, over time: filled when it became a model, hollow when refused."""
    if not rows:
        return '<p class="empty">No training runs recorded.</p>'
    W, H, L, R, T, B = 680, 260, 52, 16, 16, 36
    xs = list(range(len(rows)))                         # oldest first: runs come in bursts, days apart
    ys = [r["primary_value"] for r in rows]
    lo, hi = min(ys) - 0.002, max(ys) + 0.002
    x, y = scale(0, max(len(rows) - 1, 1), L + 8, W - R - 8), scale(lo, hi, H - B, T)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Training runs: {esc(rows[0]["primary_metric"])} '
           f'of {len(rows)} runs over time">']
    for t in ticks(lo, hi):
        out.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                   f'<text class="tick" x="{L - 6}" y="{y(t) + 4:.1f}" text-anchor="end">{t:.3f}</text>')
    for i, r in enumerate(rows):                        # a day label under the first run of each day
        if i == 0 or r["evaluated_at"].date() != rows[i - 1]["evaluated_at"].date():
            out.append(f'<line class="grid" x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{T}" y2="{H - B}"/>'
                       f'<text class="tick" x="{x(i):.1f}" y="{H - B + 18}" text-anchor="middle">'
                       f'{r["evaluated_at"]:%d %b}</text>')
    for r, xv, yv in zip(rows, xs, ys):
        kept = r["decision"] == "approve"
        tip = (f'{r["evaluated_at"]:%d %b %H:%M} · {r["primary_metric"]} {yv:.4f} · '
               f'{"kept" if kept else "refused"} · run {r["run_id"]}')
        out.append(f'<circle class="pt s{slot} {"kept" if kept else "refused"}" cx="{x(xv):.1f}" cy="{y(yv):.1f}" '
                   f'r="5" data-tip="{esc(tip)}"/>')
    out.append("</svg>")
    return "".join(out)


def chart_drift(rows: list[dict], slot: int, threshold: float = 0.2) -> str:
    """The largest feature PSI of every scoring run, oldest first, against the drift threshold."""
    rows = [r for r in rows if r["max_feature_psi"] is not None]
    if not rows:
        return '<p class="empty">No scoring runs with drift measured.</p>'
    W, H, L, R, T, B = 680, 240, 52, 16, 16, 36
    step = 0.05                                         # round ticks: 0.05, 0.10, ...
    hi = math.ceil(max(max(r["max_feature_psi"] for r in rows), threshold) * 1.1 / step) * step
    x, y = scale(0, max(len(rows) - 1, 1), L + 8, W - R - 8), scale(0, hi, H - B, T)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Drift: largest feature PSI of {len(rows)} '
           f'scoring runs">']
    for t in [i * step for i in range(round(hi / step) + 1)]:
        out.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                   f'<text class="tick" x="{L - 6}" y="{y(t) + 4:.1f}" text-anchor="end">{t:.2f}</text>')
    out.append(f'<line class="threshold" x1="{L}" x2="{W - R}" y1="{y(threshold):.1f}" y2="{y(threshold):.1f}"/>'
               f'<text class="tick" x="{W - R}" y="{y(threshold) - 6:.1f}" text-anchor="end">threshold {threshold}'
               f'</text>')
    path = " ".join(f'{"M" if i == 0 else "L"}{x(i):.1f},{y(r["max_feature_psi"]):.1f}' for i, r in enumerate(rows))
    out.append(f'<path class="line s{slot}" d="{path}"/>')
    for i, r in enumerate(rows):
        batch = r["source_uri"].rsplit(".", 1)[-1]
        tip = (f'{when(r["monitored_at"])} · {batch} · v{r["model_version_id"]} · PSI {r["max_feature_psi"]:.3f}'
               f'{" · alert" if r["alert"] else ""}')
        out.append(f'<circle class="pt s{slot} kept" cx="{x(i):.1f}" cy="{y(r["max_feature_psi"]):.1f}" r="4.5" '
                   f'data-tip="{esc(tip)}"/>')
    out.append(f'<text class="tick" x="{L + 8}" y="{H - B + 18}">oldest</text>'
               f'<text class="tick" x="{W - R - 8}" y="{H - B + 18}" text-anchor="end">newest</text></svg>')
    return "".join(out)


def chart_compute(env: dict, usecases: list[str], top: float) -> str:
    """Pipeline hours per use case in one environment: one bar each, the use case's own colour."""
    W, ROW, L, R = 330, 30, 128, 56
    H = ROW * len(usecases) + 10
    x = scale(0, top or 1, L, W - R)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Pipeline hours per use case in {env["name"]}">']
    for i, uc in enumerate(usecases):
        c = env["compute"].get(uc, {"hours": 0, "runs": 0})
        yv = 6 + i * ROW
        width = max(x(c["hours"]) - L, 0)
        tip = f'{uc} in {env["name"]}: {c["hours"]:.1f} h over {c["runs"]} runs'
        out.append(f'<text class="label" x="{L - 8}" y="{yv + 15}" text-anchor="end">{esc(uc)}</text>'
                   f'<rect class="bar s{i + 1}" x="{L}" y="{yv + 4}" width="{width:.1f}" height="16" rx="4" '
                   f'data-tip="{esc(tip)}"/>'
                   f'<text class="value" x="{L + width + 6:.1f}" y="{yv + 16}">{c["hours"]:.1f} h</text>')
    out.append("</svg>")
    return "".join(out)


def mask(text: str, on: bool) -> str:
    return EMAIL.sub("...", text) if on else text


def render(data: dict, masked: bool) -> str:
    usecases, envs = data["usecases"], data["envs"]
    slot = {uc: i + 1 for i, uc in enumerate(usecases)}
    prod = envs[-1]
    in_prod = sum(1 for uc in usecases if (prod["usecases"][uc]["champion"] or {}).get("version"))
    decisions = [e for env in envs for e in env["events"] if e["event_type"] in DECISIONS]
    pending = sum(len(env["pending"]) for env in envs)

    tiles = [("use cases", len(usecases)), ("environments", len(envs)), (f"models in {prod['name']}", in_prod),
             ("decisions kept", len(decisions)), ("waiting for a person", pending)]
    parts = ['<section class="tiles">'] + [f'<div class="tile"><b>{v}</b><span>{esc(k)}</span></div>'
                                          for k, v in tiles] + ["</section>"]

    # The fleet grid: what is live where, and its champion.
    head = "".join(f"<th>{esc(e['name'])}</th>" for e in envs)
    parts.append(f'<h2>What is live, where</h2><table class="grid-table"><thead><tr><th>use case</th>{head}</tr>'
                 "</thead><tbody>")
    for uc in usecases:
        cells = []
        for env in envs:
            u = env["usecases"][uc]
            p, c = u["pointer"] or {}, u["champion"] or {}
            ev = ((c.get("lineage") or {}).get("evaluation")) or {}
            release = (f'release <code>{esc(p.get("release_id"))}</code><br><small>{when(p.get("updated_at"))} by '
                       f'{esc(mask(p.get("updated_by") or "", masked))}</small>') if p else "<small>no release</small>"
            model = (f'<br>v{esc(c.get("version"))} {esc(ev.get("primary_metric") or "")} '
                     f'{ev.get("value") if ev.get("value") is not None else ""}'
                     f'{" · from " + esc((c.get("labels") or {}).get("promoted-from")) if (c.get("labels") or {}).get("promoted-from") else ""}'
                     ) if c.get("version") else "<br><small>no model</small>"
            first = (envs[0]["usecases"][uc]["pointer"] or {}).get("release_id")
            if env is not envs[0] and p and first and p.get("release_id") != first:
                model += f'<br><small class="behind">differs from {esc(envs[0]["name"])} ({esc(first)})</small>'
            cells.append(f"<td>{release}{model}</td>")
        parts.append(f'<tr><th><span class="key s{slot[uc]}"></span>{esc(uc)}</th>{"".join(cells)}</tr>')
    parts.append("</tbody></table>")

    # Charts: training history and drift for each use case that has them, compute per environment.
    for env in envs:
        for uc in usecases:
            u = env["usecases"][uc]
            if len(u["training"]) >= 3:
                kept = sum(1 for r in u["training"] if r["decision"] == "approve")
                parts.append(f'<h2>Training runs: {esc(uc)} in {esc(env["name"])}</h2><p class="caption">'
                             f'{len(u["training"])} runs; {kept} became a model (filled), {len(u["training"]) - kept}'
                             f' were refused by the gates (hollow). Hover for each run.</p>'
                             + chart_training(u["training"], slot[uc]))
    for env in envs:
        for uc in usecases:
            u = env["usecases"][uc]
            if sum(1 for r in u["scoring"] if r["max_feature_psi"] is not None) >= 3:
                alerts = sum(1 for r in u["scoring"] if r["alert"])
                parts.append(f'<h2>Drift: {esc(uc)} in {esc(env["name"])}</h2><p class="caption">The largest feature '
                             f'PSI of each scoring run; {alerts} of {len(u["scoring"])} runs alerted.</p>'
                             + chart_drift(u["scoring"], slot[uc]))
    top = max((c["hours"] for env in envs for c in env["compute"].values()), default=1)
    parts.append('<h2>Compute: pipeline hours</h2><p class="caption">Every pipeline run of each use case, start to end. '
                 'A first measure of cost; Cloud Billing export, filtered by the pipewright-usecase label, gives the '
                 'money.</p><div class="multiples">')
    for env in envs:
        parts.append(f'<div><h3>{esc(env["name"])}</h3>{chart_compute(env, usecases, top)}</div>')
    parts.append("</div>")

    # The decision log and what waits.
    parts.append('<h2>Decisions</h2><table class="log"><thead><tr><th>when</th><th>where</th><th>use case</th>'
                 '<th>decision</th><th>by</th><th>how approved</th></tr></thead><tbody>')
    rows = sorted(((e, env["name"]) for env in envs for e in env["events"] if e["event_type"] in DECISIONS),
                  key=lambda t: t[0]["publish_time"], reverse=True)
    for e, name in rows[:40]:
        d = json.loads(e["detail"] or "{}")
        a = d.get("approval") or {}
        how = (f'GitHub, {esc(a.get("actor"))}, <a href="{esc(a.get("run_url"))}">run</a>' if a.get("via") == "github"
               else "outside CI" if a.get("via") else "")
        what = {"model.approved": f'v{d.get("version")} champion', "release.live": f'release {e.get("release")}',
                "release.rolled_back": f'rolled back to {e.get("release")}', "data.erased":
                f'{sum((d.get("rows") or {}).values())} rows erased'}.get(e["event_type"], e["event_type"])
        parts.append(f'<tr><td>{when(e["publish_time"])}</td><td>{esc(name)}</td><td>{esc(e["usecase"])}</td>'
                     f'<td>{esc(what)}</td><td>{esc(mask(d.get("by") or "", masked))}</td><td>{how}</td></tr>')
    if not rows:
        parts.append('<tr><td colspan="6">No decisions in the event log yet (Chapter 17: is anything subscribed '
                     'to the events topic?)</td></tr>')
    parts.append("</tbody></table>")
    missing = [env["name"] for env in envs if not env["evidence"]]
    if missing:
        parts.append(f'<p class="caption">No event log in {esc(", ".join(missing))}: decisions there were not kept.</p>')
    parts.append(f'<h2>Waiting for a person</h2><p class="caption">{pending or "Nothing"} pending '
                 f'(`pipewright decisions pending`).</p>')

    body = "\n".join(parts)
    return PAGE.replace("{{BODY}}", body).replace("{{AT}}", data["at"].strftime("%d %B %Y %H:%M UTC"))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fleet report</title>
<style>
:root { color-scheme: light; --surface:#fcfcfb; --raised:#ffffff; --ink:#0b0b0b; --ink-2:#52514e; --rule:#e4e3df;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --threshold:#d03b3b; }
@media (prefers-color-scheme: dark) { :root:where(:not([data-theme="light"])) { color-scheme: dark; --surface:#1a1a19;
  --raised:#232322; --ink:#f0efec; --ink-2:#c3c2b7; --rule:#3a3a37; --s1:#3987e5; --s2:#d95926; --s3:#199e70; } }
:root[data-theme="dark"] { color-scheme: dark; --surface:#1a1a19; --raised:#232322; --ink:#f0efec; --ink-2:#c3c2b7;
  --rule:#3a3a37; --s1:#3987e5; --s2:#d95926; --s3:#199e70; }
body { margin:0; background:var(--surface); color:var(--ink); font:15px/1.5 system-ui, sans-serif; }
main { max-width:980px; margin:0 auto; padding:24px 16px 48px; }
h1 { font-size:24px; margin:0 0 4px; } h2 { font-size:17px; margin:32px 0 6px; } h3 { font-size:14px; margin:8px 0; }
.caption, small, .empty { color:var(--ink-2); } .caption { margin:0 0 8px; font-size:13px; }
.tiles { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:12px; margin-top:20px; }
.tile { background:var(--raised); border:1px solid var(--rule); border-radius:10px; padding:12px 14px; }
.tile b { display:block; font-size:28px; } .tile span { color:var(--ink-2); font-size:13px; }
table { width:100%; border-collapse:collapse; font-size:13px; background:var(--raised); }
th, td { text-align:left; vertical-align:top; padding:8px; border-bottom:1px solid var(--rule); }
thead th { color:var(--ink-2); font-weight:600; } code { font-size:12px; }
.key { display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:6px; }
.key.s1, .bar.s1 { background:var(--s1); fill:var(--s1); } .key.s2, .bar.s2 { background:var(--s2); fill:var(--s2); }
.key.s3, .bar.s3 { background:var(--s3); fill:var(--s3); }
svg { width:100%; height:auto; overflow:visible; }
.grid { stroke:var(--rule); stroke-width:1; } .tick, .label, .value { fill:var(--ink-2); font-size:11px; }
.label { fill:var(--ink); font-size:12px; } .threshold { stroke:var(--threshold); stroke-width:1.5; stroke-dasharray:6 4; }
.line { fill:none; stroke-width:2; } .line.s1 { stroke:var(--s1); } .line.s2 { stroke:var(--s2); } .line.s3 { stroke:var(--s3); }
.pt { stroke:var(--surface); stroke-width:2; } .pt.s1 { fill:var(--s1); } .pt.s2 { fill:var(--s2); } .pt.s3 { fill:var(--s3); }
.pt.refused { fill:var(--surface); stroke-width:2; } .pt.refused.s1 { stroke:var(--s1); } .pt.refused.s2 { stroke:var(--s2); }
.pt.refused.s3 { stroke:var(--s3); } [data-tip] { cursor:default; } [data-tip]:hover { opacity:.8; }
.multiples { display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:16px; }
.multiples > div { background:var(--raised); border:1px solid var(--rule); border-radius:10px; padding:8px 12px; }
#tip { position:fixed; pointer-events:none; background:var(--ink); color:var(--surface); font-size:12px;
  padding:4px 8px; border-radius:6px; display:none; max-width:320px; }
.table-wrap { overflow-x:auto; } .behind { color:var(--ink); font-weight:600; }
</style></head>
<body><main>
<h1>Fleet report</h1><p class="caption">Every use case in every environment, from the records Pipewright keeps.
Generated {{AT}} by tools/fleet_report.py. Read only.</p>
{{BODY}}
</main><div id="tip"></div>
<script>
const tip = document.getElementById("tip");
document.addEventListener("mousemove", (e) => {
  const t = e.target.closest && e.target.closest("[data-tip]");
  if (!t) { tip.style.display = "none"; return; }
  tip.textContent = t.getAttribute("data-tip"); tip.style.display = "block";
  tip.style.left = Math.min(e.clientX + 12, innerWidth - 330) + "px"; tip.style.top = (e.clientY + 14) + "px";
});
</script></body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="fleet.html")
    parser.add_argument("--mask", action="store_true", help="replace email addresses with ...")
    args = parser.parse_args()
    data = collect()
    Path(args.out).write_text(render(data, args.mask), encoding="utf-8")
    print(f"wrote {args.out}: {len(data['usecases'])} use cases in {len(data['envs'])} environments")


if __name__ == "__main__":
    main()
