# =============================================================================
# Exchange Rate API - GCP 基礎設施（Infrastructure as Code）
#
# 建立的資源：
#   1. 啟用必要的 GCP API
#   2. Artifact Registry：存放 Docker 映像檔
#   3. Cloud Run 執行用 Service Account（最小權限）
#   4. Cloud Run 服務（自動擴展 0 ~ N）
#   5. GitHub Actions 用的 Workload Identity Federation（免金鑰部署）
# =============================================================================

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # 正式環境建議把 state 存在 GCS，多人協作時才不會互相覆蓋：
  # backend "gcs" {
  #   bucket = "your-tfstate-bucket"
  #   prefix = "exchange-rate-api"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  image_repo = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
}

# ---------- 1. 啟用 API ----------
resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# ---------- 2. Artifact Registry ----------
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = var.service_name
  format        = "DOCKER"
  description   = "Docker images for ${var.service_name}"

  # 只保留最近 10 個版本，控制儲存成本
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "2592000s" # 30 天
    }
  }

  depends_on = [google_project_service.services]
}

# ---------- 3. 執行用 Service Account ----------
# 此服務只需呼叫外部 API，不需要任何 GCP 權限 → 不授予任何角色（最小權限原則）
resource "google_service_account" "runtime" {
  account_id   = "${var.service_name}-run"
  display_name = "Cloud Run runtime SA for ${var.service_name}"
}

# ---------- 4. Cloud Run 服務 ----------
resource "google_cloud_run_v2_service" "api" {
  name                = var.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account                  = google_service_account.runtime.email
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = var.min_instances # 0 = 沒流量時不收費
      max_instance_count = var.max_instances # 上限避免流量暴增造成費用失控
    }

    containers {
      # 首次建立先用 Google 範例映像；之後由 CI/CD 部署實際版本
      image = var.bootstrap_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true # 只在處理請求時計費 CPU
      }

      env {
        name  = "ENVIRONMENT"
        value = "production"
      }
      env {
        name  = "CACHE_TTL_SECONDS"
        value = "600"
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 0
        period_seconds        = 3
        failure_threshold     = 10
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
        period_seconds = 30
      }
    }
  }

  lifecycle {
    # 映像版本由 CI/CD 管理，避免 terraform apply 把服務還原成舊映像
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  depends_on = [google_project_service.services]
}

# 公開 API：允許未驗證呼叫。若為內部服務，移除此資源並改用 IAM / API Gateway 驗證
resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.allow_public_access ? 1 : 0
  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------- 5. GitHub Actions：Workload Identity Federation ----------
# GitHub 以 OIDC token 換取短效 GCP 憑證，不需在 GitHub 存放任何 Service Account 金鑰
resource "google_service_account" "deployer" {
  account_id   = "${var.service_name}-deploy"
  display_name = "GitHub Actions deployer for ${var.service_name}"
}

resource "google_project_iam_member" "deployer_roles" {
  for_each = toset([
    "roles/run.developer",
    "roles/artifactregistry.writer",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# 部署時需要以 runtime SA 身分啟動 Cloud Run → 只授權這一個 SA
resource "google_service_account_iam_member" "deployer_act_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions"
  depends_on                = [google_project_service.services]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  # 只信任指定的 GitHub repository，其他 repo 即使拿到 token 也無法使用
  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_wif" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}
