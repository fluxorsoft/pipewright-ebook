# retailer-mlops

The MLOps repository of the UK online gift retailer in *Governed MLOps on Google Cloud*, built with Pipewright
1.1.0, as it stands at the end of **Chapter 19. From endpoint to app**. Run every command from inside this folder. The other
chapters are in the folders beside this one.

```
environments/test.yaml     the test environment (the platform team's manifest, on Google Cloud)
environments/prod.yaml     production, promoted to only from test (Chapter 12)
usecases/lapse-risk/       the lapse model: which customers will not buy again within 90 days
usecases/customer-segments/  customer segments in BigQuery ML (Chapter 8)
usecases/demand-forecast/    weekly demand forecast in BigQuery ML (Chapter 8)
reference/                 lapse-risk with every setting and its default, in one file (tools/all_settings.py)
platform/                  what the 1.1.0 starter does not create yet: the online store (13), CI's identity (16), the event log (17)
.github/                   GitHub Actions: PR checks, release to test, promote to production, operate (Chapter 16)
app/                       the checkout offer service (Chapter 19): `uvicorn app.main:app`
```

Start from Chapter 1 to build it yourself. To use your own Google Cloud project instead of the book's, build an
environment with the open-source [pipewright-starter](https://github.com/fluxorsoft/pipewright-starter) and replace
`environments/test.yaml` with the environment file it prints.

```bash
pip install "pipewright-mlops[gcp]==1.1.0"
pipewright validate --env test
pipewright doctor --env test
```

Data: Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository.
https://doi.org/10.24432/C5CG6D (CC BY 4.0).
