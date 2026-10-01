variable "project_id" {
  description = "Dedicated GCP project for this CampaIA environment."
  type        = string
}

variable "environment" {
  description = "Cloud environment. Dev-local remains outside this Terraform stack."
  type        = string

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "region" {
  description = "Approved D-08 Google Cloud region."
  type        = string
  default     = "southamerica-east1"

  validation {
    condition     = var.region == "southamerica-east1"
    error_message = "D-08 fixes the CampaIA region to southamerica-east1."
  }
}

variable "deployer_service_account_email" {
  description = "GitHub OIDC deploy service account created by infra/bootstrap."
  type        = string
}

variable "db_tier" {
  description = "Cloud SQL machine tier; production sizing remains cost-governed."
  type        = string
  default     = "db-f1-micro"
}

variable "db_deletion_protection" {
  description = "Protect Cloud SQL from accidental Terraform destruction."
  type        = bool
  default     = true
}

variable "serverless_connector_cidr" {
  description = "Dedicated /28 used by Serverless VPC Access."
  type        = string
  default     = "10.8.0.0/28"
}

variable "assets_bucket_name" {
  description = "Optional globally unique assets bucket. Null uses project/environment derived name."
  type        = string
  default     = null
}
