variable "project_id" {
  type        = string
  description = "Existing GCP project with billing enabled."
}

variable "region" {
  type    = string
  default = "southamerica-east1"
}

variable "environment" {
  type = string

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "state_bucket_name" {
  type        = string
  description = "Globally unique GCS bucket used for Terraform remote state."
}

variable "github_repository" {
  type    = string
  default = "faabio3131/f-m-tecnologia-campaia"
}
