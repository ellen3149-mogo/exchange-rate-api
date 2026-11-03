variable "project_id" {
  description = "GCP 專案 ID"
  type        = string
}

variable "region" {
  description = "部署區域；asia-east1 位於台灣彰化，延遲最低"
  type        = string
  default     = "asia-east1"
}

variable "service_name" {
  description = "Cloud Run 服務名稱（同時用於 Artifact Registry 與 Service Account 命名）"
  type        = string
  default     = "exchange-rate-api"
}

variable "github_repository" {
  description = "允許部署的 GitHub repository，格式 owner/repo"
  type        = string
}

variable "min_instances" {
  type    = number
  default = 0
}

variable "max_instances" {
  type    = number
  default = 5
}

variable "allow_public_access" {
  description = "是否開放未驗證呼叫"
  type        = bool
  default     = true
}

variable "bootstrap_image" {
  description = "首次建立服務時使用的映像，之後由 CI/CD 更新"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}
