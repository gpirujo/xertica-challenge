variable "project_id" {
  description = "GCP project ID where all resources will be created"
  type        = string
}

variable "region" {
  description = "Default GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
  default     = "dev"
}

variable "app_name" {
  description = "Application name used as prefix for resource naming"
  type        = string
  default     = "compliance-agent"
}

variable "cloud_run_min_instances" {
  description = "Minimum number of Cloud Run instances (0 = scale to zero)"
  type        = number
  default     = 0
}

variable "cloud_run_max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 10
}

variable "cloud_run_cpu" {
  description = "CPU allocation per Cloud Run instance"
  type        = string
  default     = "1"
}

variable "cloud_run_memory" {
  description = "Memory allocation per Cloud Run instance"
  type        = string
  default     = "2Gi"
}

variable "db_tier" {
  description = "Cloud SQL instance tier (machine type)"
  type        = string
  default     = "db-f1-micro"
}

variable "db_name" {
  description = "Name of the PostgreSQL database to create"
  type        = string
  default     = "compliance"
}

variable "gcs_bucket_suffix" {
  description = "Unique suffix appended to the GCS bucket name to guarantee global uniqueness"
  type        = string
}

variable "gce_zone" {
  description = "GCP zone for GCE instances (Elasticsearch and FalkorDB). Must be within var.region."
  type        = string
  default     = "us-central1-a"
}
