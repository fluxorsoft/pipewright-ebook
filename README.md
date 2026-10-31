# retailer-mlops

The MLOps repository of the UK online gift retailer in *Governed MLOps on Google Cloud*, for Pipewright 1.2.0. Each folder is the whole repository as it stands at the end of one chapter, ready to run: open the folder of
the chapter you are reading and follow its **Try it** section there. Comparing two folders shows exactly what a
chapter changed, for example `diff -r ch04 ch05`.

| Folder | At the end of | What it adds |
|---|---|---|
| `ch02/` | Chapter 2. One use case, one YAML file | the lapse-risk use case, the test environment, the overrides |
| `ch03/` | Chapter 3. Data contracts and quality gates | the data contract, the raw table, the good file and the bad Monday (`tools/make_snapshots.py`) |
| `ch04/` | Chapter 4. Features without leakage | the data team's tables and SQL (`data-team/`), features read point in time, the leakage demo |
| `ch05/` | Chapter 5. Reproducible runs | the label from purchase events, per-run snapshots, every setting in one file (`reference/`) |
| `ch06/` | Chapter 6. Synthetic data for MLOps | a synthetic copy of the training rows, gated for sharing |
| `ch07/` | Chapter 7. Pipelines that release like software | `tests.command` with an import check (`tests/check_imports.py`), the renamed helper fixed |
| `ch08/` | Chapter 8. Models for SQL teams | `customer-segments` (k-means) and `demand-forecast` (ARIMA_PLUS) in BigQuery ML: YAML and SQL only |
| `ch09/` | Chapter 9. Training at scale | `train-model` sized in configuration, eight tuning trials, and the same trials on a Ray cluster per step (`training_pipeline_ray.py`) |
| `ch10/` | Chapter 10. Evaluation gates | gates on AUC and calibration, the champion, slices and fairness by country, with the reviewed fairness decision written in `usecase.yaml` |
| `ch11/` | Chapter 11. Features that earn their place | the candidate measurement (`tools/candidate_features.py`) and the customer's rhythm, `avg_days_between_orders`, in the feature table and the use case |
| `ch12/` | Chapter 12. Promotion between environments | `environments/prod.yaml` (promotion only from test) and lapse-risk's production overrides |
| `ch13/` | Chapter 13. Serving, canaries and A/B tests | the weekly scoring pipeline and its tables, `model.serving` with a canary, online features from the feature group `customer_activity`, `tools/score_customer.py` and the platform's `online_features.tf` |
| `ch14/` | Chapter 14. Monitoring drift and performance | drift, prediction drift and email alerts on, the monthly backtest views, entity cut-offs from December 2010, `scored_for` on every score and `sql/performance.sql`; serving back to request mode |
| `ch15/` | Chapter 15. Retraining with a human in the loop | the weekly scoring schedule and the `retraining` policy: drift opens a case, `ml-leads` decides, escalation, cooldown and snooze |
| `ch16/` | Chapter 16. CI/CD and approvals in GitHub | `.github/`: PR checks, release to test on merge, a promote workflow for production, operate; the CI constraints file; `platform/github-ci.sh` (Workload Identity Federation) |
| `ch17/` | Chapter 17. Lineage: every model's full story | rows sorted by the contract key before training (exact replays), `data_protection.erasure`, `platform/evidence.tf` (the event log) |
| `ch18/` | Chapter 18. Evidence, audit and running a fleet | `tools/fleet_report.py`: one HTML page with charts for every use case in every environment (live releases, champions, training runs, drift, compute, decisions) |
| `ch19/` | Chapter 19. From endpoint to app | `app/`: the checkout offer service (FastAPI): the weekly score, a fresh score from the request-mode endpoint, the business rule `OFFER_AT`, a one-page front end and a `Dockerfile`; `FEATURES=online` asks by customer ID alone, from the online store (Pipewright 1.2.0) |

Every folder is a Pipewright repository root: run `pipewright` commands from inside it. The chapters were first
built with Pipewright 1.1.0 and run unchanged on 1.2.0; where 1.2.0 changed something a chapter met, the book says so
in a note marked **Since Pipewright 1.2.0**.

```bash
pip install "pipewright-mlops[gcp]==1.2.0"
cd ch06
pipewright validate --env test
pipewright doctor --env test
```

To use your own Google Cloud project instead of the book's, build an environment with the open-source
[pipewright-starter](https://github.com/fluxorsoft/pipewright-starter) and replace `environments/test.yaml` in the
folder with the environment file it prints.

Data: Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository.
https://doi.org/10.24432/C5CG6D (CC BY 4.0).
