output "service_url" {
  description = "Cloud Run 服務網址"
  value       = google_cloud_run_v2_service.api.uri
}

output "artifact_registry_repo" {
  description = "Docker 映像檔路徑前綴"
  value       = local.image_repo
}

output "workload_identity_provider" {
  description = "填入 GitHub Variables：GCP_WIF_PROVIDER"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  description = "填入 GitHub Variables：GCP_DEPLOY_SA"
  value       = google_service_account.deployer.email
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}
