output "eks_cluster_name" {
  description = "Name of the provisioned EKS cluster."
  value       = module.eks_ecr.cluster_name
}

output "eks_cluster_endpoint" {
  description = "Private EKS API endpoint."
  value       = module.eks_ecr.cluster_endpoint
}

output "eks_oidc_provider_arn" {
  description = "OIDC provider ARN used by workload IAM roles."
  value       = module.eks_ecr.oidc_provider_arn
}

output "eks_workload_role_arns" {
  description = "IRSA role ARN for each application workload."
  value       = module.eks_ecr.workload_role_arns
}

output "ecr_repository_urls" {
  description = "ECR repository URLs for application workloads."
  value       = module.eks_ecr.ecr_repository_urls
}

output "dynamodb_table_names" {
  description = "Environment-specific DynamoDB table names."
  value       = module.dynamodb.table_names
}

output "github_actions_ecr_role_arns" {
  description = "Optional GitHub Actions OIDC role ARNs for this Terraform workspace."
  value       = try(module.github_actions_ecr[0].role_arns, {})
}
