# retailer-mlops

The MLOps repository of the UK online gift retailer in *Governed MLOps on Google Cloud*, built with Pipewright
1.1.0. Each folder is the whole repository as it stands at the end of one chapter, ready to run: open the folder of
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

Every folder is a Pipewright repository root: run `pipewright` commands from inside it.

```bash
pip install "pipewright-mlops[gcp]==1.1.0"
cd ch06
pipewright validate --env test
pipewright doctor --env test
```

To use your own Google Cloud project instead of the book's, build an environment with the open-source
[pipewright-starter](https://github.com/fluxorsoft/pipewright-starter) and replace `environments/test.yaml` in the
folder with the environment file it prints.

Data: Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository.
https://doi.org/10.24432/C5CG6D (CC BY 4.0).
