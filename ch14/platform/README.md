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
