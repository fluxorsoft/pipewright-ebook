#!/usr/bin/env bash
# Chapter 16: let GitHub Actions in one repository act as a CI service account in each environment's project, with
# Workload Identity Federation (no keys). Run once, as a project owner, after reading it. Safe to re-run: "already
# exists" errors are expected the second time.
#
#   REPO=your-org/your-repo TEST_PROJECT=your-test-project PROD_PROJECT=your-prod-project bash platform/github-ci.sh
#
# What the CI account may do comes from the starter's `operators` list, not from here: add
# "serviceAccount:pw-github-ci@<project>.iam.gserviceaccount.com" to operators in each environment's terraform.tfvars,
# then plan, review and apply.
set -u
: "${REPO:?set REPO=org/repo}" "${TEST_PROJECT:?set TEST_PROJECT}" "${PROD_PROJECT:?set PROD_PROJECT}"

for PJ in "$TEST_PROJECT" "$PROD_PROJECT"; do
  NUM=$(gcloud projects describe "$PJ" --format="value(projectNumber)")
  SA="pw-github-ci@${PJ}.iam.gserviceaccount.com"
  echo "== $PJ ($NUM)"

  # 1. The token exchange APIs.
  gcloud services enable iamcredentials.googleapis.com sts.googleapis.com --project "$PJ"

  # 2. A pool, and a GitHub provider that accepts tokens from this one repository only.
  gcloud iam workload-identity-pools create github --location=global --display-name="GitHub Actions" --project "$PJ"
  gcloud iam workload-identity-pools providers create-oidc github-repo --location=global \
    --workload-identity-pool=github --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.environment=assertion.environment" \
    --attribute-condition="assertion.repository=='${REPO}'" --project "$PJ"

  # 3. The CI service account, and the repository's workflows allowed to act as it.
  gcloud iam service-accounts create pw-github-ci --display-name="Pipewright CI (GitHub Actions, ${REPO})" --project "$PJ"
  gcloud iam service-accounts add-iam-policy-binding "$SA" --role=roles/iam.workloadIdentityUser \
    --member="principalSet://iam.googleapis.com/projects/${NUM}/locations/global/workloadIdentityPools/github/attribute.repository/${REPO}" \
    --project "$PJ"

  echo "GitHub environment variables for ${PJ}:"
  echo "  GCP_WIF_PROVIDER=projects/${NUM}/locations/global/workloadIdentityPools/github/providers/github-repo"
  echo "  PIPEWRIGHT_SERVICE_ACCOUNT=${SA}"
done

# 4. Promotion copies from test, so production's CI account reads test's images, artifacts and models.
PROD_SA="serviceAccount:pw-github-ci@${PROD_PROJECT}.iam.gserviceaccount.com"
gcloud projects add-iam-policy-binding "$TEST_PROJECT" --member="$PROD_SA" --role=roles/artifactregistry.reader --condition=None
gcloud projects add-iam-policy-binding "$TEST_PROJECT" --member="$PROD_SA" --role=roles/aiplatform.viewer --condition=None
gcloud storage buckets add-iam-policy-binding "gs://${TEST_PROJECT}-pw-artifacts" --member="$PROD_SA" \
  --role=roles/storage.objectViewer --condition=None
