# retailer-mlops

The MLOps repository of the UK online gift retailer in *Governed MLOps on Google Cloud*, built with Pipewright
1.1.0. Each chapter's **Try it** section changes this repository; its state after each chapter is what readers get
for that chapter.

```
environments/test.yaml     the test environment (the platform team's manifest, on Google Cloud)
usecases/lapse-risk/       the lapse model: which customers will not buy again within 90 days
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
