/**
 * The event log (book, chapter 17): every Pipewright lifecycle event, as published on the events topic, kept in
 * BigQuery. Without a subscription Pub/Sub discards what is published, so promotions, approvals, deployments and
 * retrain decisions would leave no record. Ported from Pipewright Enterprise's observability module, without CMEK.
 */

resource "google_bigquery_dataset" "evidence" {
  dataset_id                 = "${replace(local.p, "-", "_")}_evidence"
  location                   = var.region
  description                = "Pipewright evidence: every lifecycle event, as published (append-only by design)"
  delete_contents_on_destroy = var.force_destroy
  labels                     = local.labels
}

resource "google_bigquery_table" "events" {
  dataset_id          = google_bigquery_dataset.evidence.dataset_id
  table_id            = "events"
  description         = "Every Pipewright lifecycle event, as published (one row per message)"
  deletion_protection = !var.force_destroy
  labels              = local.labels

  time_partitioning {
    type  = "DAY"
    field = "publish_time"
  }

  schema = jsonencode([
    { name = "subscription_name", type = "STRING", mode = "NULLABLE" },
    { name = "message_id", type = "STRING", mode = "NULLABLE" },
    { name = "publish_time", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "attributes", type = "JSON", mode = "NULLABLE" },
    { name = "data", type = "JSON", mode = "NULLABLE" },
  ])
}

# Pub/Sub writes into the table as its service agent.
resource "google_bigquery_table_iam_member" "events_writer" {
  for_each = toset(["roles/bigquery.dataEditor", "roles/bigquery.metadataViewer"])

  dataset_id = google_bigquery_dataset.evidence.dataset_id
  table_id   = google_bigquery_table.events.table_id
  role       = each.value
  member     = "serviceAccount:${local.pubsub_agent}"
}

resource "google_pubsub_subscription" "events_to_bigquery" {
  name   = "${local.p}-events-to-bigquery"
  topic  = google_pubsub_topic.this["events"].id
  labels = local.labels

  bigquery_config {
    table          = "${var.project_id}.${google_bigquery_dataset.evidence.dataset_id}.${google_bigquery_table.events.table_id}"
    write_metadata = true
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [google_bigquery_table_iam_member.events_writer]
}

# Operators read the evidence; nobody but Pub/Sub writes it.
resource "google_bigquery_dataset_iam_member" "evidence_readers" {
  for_each = toset(var.operators)

  dataset_id = google_bigquery_dataset.evidence.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = each.value
}
