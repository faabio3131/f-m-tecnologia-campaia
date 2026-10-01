locals {
  name = "campaia-${var.environment}"

  required_apis = toset([
    "artifactregistry.googleapis.com",
    "cloudkms.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "vpcaccess.googleapis.com",
  ])

  platform_secret_ids = toset([
    "database-url",
    "asaas-api-key",
    "asaas-webhook-token",
    "gemini-api-key",
  ])

  assets_bucket = coalesce(
    var.assets_bucket_name,
    "${var.project_id}-${var.environment}-campaia-assets"
  )
}

resource "google_project_service" "apis" {
  for_each = local.required_apis

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_project_iam_audit_config" "sensitive_data_access" {
  for_each = toset([
    "cloudkms.googleapis.com",
    "secretmanager.googleapis.com",
  ])

  project = var.project_id
  service = each.value

  audit_log_config {
    log_type = "DATA_READ"
  }

  audit_log_config {
    log_type = "DATA_WRITE"
  }

  depends_on = [google_project_service.apis]
}

resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = "campaia"
  description   = "CampaIA container images for ${var.environment}"
  format        = "DOCKER"

  depends_on = [google_project_service.apis]
}

resource "google_compute_network" "runtime" {
  name                    = "${local.name}-net"
  auto_create_subnetworks = false

  depends_on = [google_project_service.apis]
}

resource "google_compute_global_address" "private_services" {
  name          = "${local.name}-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.runtime.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.runtime.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]

  depends_on = [google_project_service.apis]
}

resource "google_vpc_access_connector" "serverless" {
  name          = "${local.name}-vpc"
  region        = var.region
  network       = google_compute_network.runtime.name
  ip_cidr_range = var.serverless_connector_cidr
  machine_type  = "e2-micro"
  min_instances = 2
  max_instances = 3

  depends_on = [google_project_service.apis]
}

resource "google_sql_database_instance" "postgres" {
  name                = "${local.name}-pg"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.db_deletion_protection

  settings {
    edition           = "ENTERPRISE"
    tier              = var.db_tier
    availability_type = var.environment == "production" ? "REGIONAL" : "ZONAL"
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "03:00"
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = var.environment == "production" ? 14 : 7
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.runtime.id
      enable_private_path_for_google_cloud_services = true
      ssl_mode                                      = "ENCRYPTED_ONLY"
    }
  }

  depends_on = [
    google_project_service.apis,
    google_service_networking_connection.private_services,
  ]
}

resource "google_sql_database" "campaia" {
  name     = "campaia"
  instance = google_sql_database_instance.postgres.name
}

resource "google_kms_key_ring" "vault" {
  name     = "${local.name}-vault"
  location = var.region

  depends_on = [google_project_service.apis]
}

resource "google_kms_crypto_key" "tenant_credentials" {
  name            = "tenant-credentials"
  key_ring        = google_kms_key_ring.vault.id
  rotation_period = "7776000s"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret" "platform" {
  for_each = local.platform_secret_ids

  secret_id = "${local.name}-${each.value}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket" "assets" {
  name                        = local.assets_bucket
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "domain_events" {
  name = "${local.name}-domain-events"

  message_retention_duration = "604800s"

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "backend" {
  account_id   = "campaia-${var.environment}-be"
  display_name = "CampaIA ${var.environment} backend runtime"
}

resource "google_service_account" "web" {
  account_id   = "campaia-${var.environment}-web"
  display_name = "CampaIA ${var.environment} web runtime"
}

resource "google_kms_crypto_key_iam_member" "backend_vault" {
  crypto_key_id = google_kms_crypto_key.tenant_credentials.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_secret_manager_secret_iam_member" "backend_secrets" {
  for_each = google_secret_manager_secret.platform

  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_storage_bucket_iam_member" "backend_assets" {
  bucket = google_storage_bucket.assets.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_pubsub_topic_iam_member" "backend_publish" {
  project = var.project_id
  topic   = google_pubsub_topic.domain_events.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_project_iam_member" "deployer_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${var.deployer_service_account_email}"
}

resource "google_project_iam_member" "deployer_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${var.deployer_service_account_email}"
}

resource "google_service_account_iam_member" "deployer_backend_user" {
  service_account_id = google_service_account.backend.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.deployer_service_account_email}"
}

resource "google_service_account_iam_member" "deployer_web_user" {
  service_account_id = google_service_account.web.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.deployer_service_account_email}"
}
