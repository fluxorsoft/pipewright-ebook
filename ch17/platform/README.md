# platform/: the online store the starter does not create yet (Chapter 13)

Pipewright 1.1.0's starter writes no online store, so Chapter 13 adds one to the starter by hand. Three changes, in
your copy of pipewright-starter:

1. Copy `online_features.tf` into the starter's folder.
2. In `variables.tf`, add to the tenant object, after `members`:

   ```hcl
       online_features = optional(object({
         nodes = optional(object({ min = number, max = number }), { min = 1, max = 1 })
         views = map(object({
           feature_groups = map(list(string))
           sync           = optional(string, "0 6 * * *")
         }))
       }))
   ```

3. In `manifest.tf`, name the store in the tenant's entry:

   ```hcl
       tenants = {
         for t, v in local.tenants : t => merge({
           runner_service_account = google_service_account.runner[t].email
           bigquery_dataset       = v.dataset
           landing_prefix         = v.landing_prefix
           online_serving         = v.online_serving
           }, v.online_features == null ? {} : {
           features = {
             online_store = "projects/${var.project_id}/locations/${var.region}/featureOnlineStores/${local.online_store_names[t]}"
           }
         })
       }
   ```

Then add the `online_features` block of section 13.7 to the tenant in `terraform.tfvars`, plan, review and apply.
Register the feature group first (`python tools/data_team.py --project <project> feature-group customer_activity`):
the view reads it.

The store is Bigtable: it is billed every hour it exists and cannot scale to zero. Take the block out of
`terraform.tfvars` and apply when you are done; the plan destroys the store, its view and its grant.

## github-ci.sh: an identity for CI (Chapter 16)

`github-ci.sh` creates, in each environment's project, a Workload Identity pool and a GitHub provider that trust one
repository, a `pw-github-ci` service account that repository's workflows may act as, and, in production, read access to
test's images, artifacts and models for promotion. Read it, then run it as a project owner with `REPO`, `TEST_PROJECT`
and `PROD_PROJECT` set. Then add the service account to `operators` in each environment's `terraform.tfvars`, plan,
review and apply, and put the two values it prints in the GitHub environments' variables.

The starter's operators also need three read-only roles for `pipewright doctor` (`roles/run.viewer`,
`roles/pubsub.viewer`, and `roles/storage.legacyBucketReader` on the artifacts and landing buckets) and
`roles/pubsub.publisher` on the events topic, so CI's releases reach the event log. Pipewright's next starter grants
them; for 1.1.0, add them to `identities.tf` as the book's environment did.

## evidence.tf: keep the event log (Chapter 17)

Pipewright publishes every lifecycle event, including every decision (promotions, approvals, deployments, rollbacks,
retrain decisions, erasures), to the environment's `events` topic. The 1.1.0 starter creates the topic but nothing
subscribes to it, and Pub/Sub discards what nobody subscribes to. Copy `evidence.tf` into the starter's folder, plan,
review and apply: it creates a `<prefix>_evidence` dataset, an append-only `events` table, a BigQuery subscription on
the topic, and read access for the operators. Events are kept from then on; earlier ones cannot be recovered.
