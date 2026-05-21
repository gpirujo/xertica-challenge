output "cloud_run_url" {
  description = "Public URL of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.api.uri
}

output "artifact_registry_url" {
  description = "Full Artifact Registry path for docker push (append :<tag>)"
  value       = "us-central1-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}/${var.app_name}"
}

output "db_instance_connection_name" {
  description = "Cloud SQL connection name used by Cloud SQL Auth Proxy"
  value       = google_sql_database_instance.postgres.connection_name
}

output "gcs_bucket_name" {
  description = "Name of the GCS bucket used for document storage"
  value       = google_storage_bucket.documents.name
}

output "service_account_email" {
  description = "Email of the service account used by the Cloud Run service"
  value       = google_service_account.compliance_agent_sa.email
}

output "elasticsearch_internal_ip" {
  description = "Internal VPC IP of the Elasticsearch GCE instance"
  value       = google_compute_instance.elasticsearch.network_interface[0].network_ip
}

output "falkordb_internal_ip" {
  description = "Internal VPC IP of the FalkorDB GCE instance"
  value       = google_compute_instance.falkordb.network_interface[0].network_ip
}
