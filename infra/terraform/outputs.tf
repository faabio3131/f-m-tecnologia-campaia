output "artifact_repository" {
  value = google_artifact_registry_repository.containers.name
}

output "artifact_registry_host" {
  value = "${var.region}-docker.pkg.dev"
}

output "cloud_sql_instance_name" {
  value = google_sql_database_instance.postgres.name
}

output "cloud_sql_private_ip" {
  value = google_sql_database_instance.postgres.private_ip_address
}

output "database_url_secret_name" {
  value = google_secret_manager_secret.platform["database-url"].secret_id
}

output "kms_key_name" {
  value = google_kms_crypto_key.tenant_credentials.id
}

output "assets_bucket_name" {
  value = google_storage_bucket.assets.name
}

output "pubsub_topic_name" {
  value = google_pubsub_topic.domain_events.name
}

output "vpc_network_name" {
  value = google_compute_network.runtime.name
}

output "direct_vpc_subnet_name" {
  value = google_compute_subnetwork.direct_vpc.name
}

output "backend_service_account_email" {
  value = google_service_account.backend.email
}

output "web_service_account_email" {
  value = google_service_account.web.email
}
