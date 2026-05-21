terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  labels = {
    environment = var.environment
    app_name    = replace(var.app_name, "-", "_")
  }
}

# ─────────────────────────────────────────────
# GCS — Document storage
# ─────────────────────────────────────────────

resource "google_storage_bucket" "documents" {
  name     = "${var.app_name}-docs-${var.gcs_bucket_suffix}"
  location = "us-central1"
  labels   = local.labels

  # Uniform bucket-level access disables per-object ACLs — recommended for new buckets.
  uniform_bucket_level_access = true

  # force_destroy allows Terraform to delete a non-empty bucket.
  # Only enabled in dev so we never accidentally wipe production data.
  force_destroy = var.environment == "dev"
}

# ─────────────────────────────────────────────
# Cloud SQL — PostgreSQL with pgvector
# ─────────────────────────────────────────────

resource "google_sql_database_instance" "postgres" {
  name             = "${var.app_name}-pg"
  database_version = "POSTGRES_17"
  region           = "us-central1"

  # deletion_protection prevents accidental destruction via Terraform.
  # Disabled in dev to allow teardown; always enabled in higher environments.
  deletion_protection = var.environment != "dev"

  settings {
    tier = var.db_tier

    database_flags {
      # pgvector enables vector similarity search for RAG-based compliance queries.
      name  = "cloudsql.enable_pgvector"
      value = "on"
    }
  }

  user_labels = local.labels
}

resource "google_sql_database" "compliance" {
  name     = var.db_name
  instance = google_sql_database_instance.postgres.name
}

resource "random_password" "db_password" {
  length  = 32
  # Avoid special chars to prevent shell-escaping issues in DATABASE_URL.
  special = false
}

resource "google_sql_user" "app" {
  name     = "app"
  instance = google_sql_database_instance.postgres.name
  password = random_password.db_password.result
}

# ─────────────────────────────────────────────
# Artifact Registry — Docker image repository
# ─────────────────────────────────────────────

resource "google_artifact_registry_repository" "docker" {
  repository_id = var.app_name
  format        = "DOCKER"
  location      = "us-central1"
  labels        = local.labels
}

# ─────────────────────────────────────────────
# Service Account & IAM
# ─────────────────────────────────────────────

resource "google_service_account" "compliance_agent_sa" {
  account_id   = "${var.app_name}-sa"
  display_name = "Compliance Agent Service Account"
}

# Project-level bindings — least-privilege roles for BigQuery access.
resource "google_project_iam_member" "bq_data_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.compliance_agent_sa.email}"
}

resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.compliance_agent_sa.email}"
}

resource "google_project_iam_member" "cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.compliance_agent_sa.email}"
}

resource "google_project_iam_member" "run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.compliance_agent_sa.email}"
}

# Bucket-level binding — scoped to our bucket, not the whole project.
resource "google_storage_bucket_iam_member" "sa_object_viewer" {
  bucket = google_storage_bucket.documents.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.compliance_agent_sa.email}"
}

# ─────────────────────────────────────────────
# Cloud Run — API service
# ─────────────────────────────────────────────

resource "google_cloud_run_v2_service" "api" {
  name     = "${var.app_name}-api"
  location = "us-central1"
  labels   = local.labels

  template {
    service_account = google_service_account.compliance_agent_sa.email

    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.cloud_run_max_instances
    }

    containers {
      # Placeholder image replaced by CI/CD on every deploy.
      image = "gcr.io/cloudrun/hello"

      resources {
        limits = {
          cpu    = var.cloud_run_cpu
          memory = var.cloud_run_memory
        }
      }

      env {
        name  = "POSTGRES_HOST"
        # Cloud SQL unix socket path via the Cloud SQL Auth Proxy sidecar.
        value = "/cloudsql/${google_sql_database_instance.postgres.connection_name}"
      }
      env {
        name  = "POSTGRES_PORT"
        value = "5432"
      }
      env {
        name  = "POSTGRES_DB"
        value = var.db_name
      }
      env {
        name  = "POSTGRES_USER"
        value = google_sql_user.app.name
      }
      env {
        name  = "POSTGRES_PASSWORD"
        value = random_password.db_password.result
      }
      env {
        name  = "ELASTICSEARCH_HOST"
        value = google_compute_instance.elasticsearch.network_interface[0].network_ip
      }
      env {
        name  = "ELASTICSEARCH_PORT"
        value = "9200"
      }
      env {
        name  = "FALKORDB_HOST"
        value = google_compute_instance.falkordb.network_interface[0].network_ip
      }
      env {
        name  = "FALKORDB_PORT"
        value = "6379"
      }

      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.documents.name
      }

      env {
        name  = "ENV"
        value = var.environment
      }
    }
  }
}

# Make the Cloud Run service publicly invocable in dev only.
# In staging/production, invocation is restricted to the service account.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count    = var.environment == "dev" ? 1 : 0
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ─────────────────────────────────────────────
# GCE — Elasticsearch (Container-Optimized OS)
# ─────────────────────────────────────────────

resource "google_compute_instance" "elasticsearch" {
  name         = "${var.app_name}-elasticsearch"
  machine_type = "e2-medium"
  zone         = var.gce_zone
  labels       = local.labels

  boot_disk {
    initialize_params {
      image = "cos-cloud/cos-stable"
      size  = 20
      type  = "pd-ssd"
    }
  }

  network_interface {
    network = "default"
    # Sin access_config → sin IP pública. Cloud Run accede por VPC interna.
  }

  service_account {
    email  = google_service_account.compliance_agent_sa.email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  metadata = {
    # COS levanta el contenedor directamente sin instalar Docker.
    user-data = <<-EOT
      #cloud-config
      runcmd:
        - docker run -d --name elasticsearch --restart always
            -p 9200:9200
            -e "discovery.type=single-node"
            -e "xpack.security.enabled=false"
            -e "ES_JAVA_OPTS=-Xms512m -Xmx512m"
            docker.elastic.co/elasticsearch/elasticsearch:8.17.0
    EOT
  }
}

# ─────────────────────────────────────────────
# GCE — FalkorDB (Container-Optimized OS)
# ─────────────────────────────────────────────

resource "google_compute_instance" "falkordb" {
  name         = "${var.app_name}-falkordb"
  machine_type = "e2-medium"
  zone         = var.gce_zone
  labels       = local.labels

  boot_disk {
    initialize_params {
      image = "cos-cloud/cos-stable"
      size  = 20
      type  = "pd-ssd"
    }
  }

  network_interface {
    network = "default"
  }

  service_account {
    email  = google_service_account.compliance_agent_sa.email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  metadata = {
    user-data = <<-EOT
      #cloud-config
      runcmd:
        - docker run -d --name falkordb --restart always
            -p 6379:6379
            falkordb/falkordb:latest
    EOT
  }
}

# ─────────────────────────────────────────────
# Firewall — Internal VPC access (Cloud Run → GCE)
# ─────────────────────────────────────────────

resource "google_compute_firewall" "allow_internal_services" {
  name    = "${var.app_name}-allow-internal"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["9200", "6379"]
  }

  # Permite tráfico desde rangos internos RFC-1918 (Cloud Run → GCE).
  source_ranges = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
}
