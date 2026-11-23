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

output "graphql_api_id" {
  description = "ID of the private GraphQL REST API."
  value       = module.api_gateway.api_id
}

output "graphql_api_endpoint" {
  description = "Private GraphQL invocation URL after enable_graphql_integration is true; otherwise null."
  value       = module.api_gateway.api_endpoint
}

output "eks_cluster_security_group_id" {
  description = "EKS-managed cluster security group."
  value       = module.eks_ecr.cluster_security_group_id
}

output "load_balancer_controller_role_arn" {
  description = "Pod Identity role for kube-system/aws-load-balancer-controller."
  value       = module.eks_ecr.load_balancer_controller_role_arn
}

output "mirror_repository_urls" {
  description = "Private ECR mirrors for third-party images (no NAT egress)."
  value       = module.eks_ecr.mirror_repository_urls
}

output "vpc_id" {
  description = "Environment VPC ID."
  value       = module.network.vpc_id
}

output "access_host_instance_id" {
  description = "Session Manager access host instance ID, or null when disabled."
  value       = try(module.access_host[0].instance_id, null)
}

output "github_plan_role_arn" {
  description = "OIDC role for PR terraform plan (null when github_repository is empty)."
  value       = try(module.github_actions_cicd[0].plan_role_arn, null)
}

output "github_deploy_role_arn" {
  description = "OIDC role for the post-merge deploy of this workspace."
  value       = try(module.github_actions_cicd[0].deploy_role_arn, null)
}

output "service_log_group_names" {
  description = "Per-environment, per-service CloudWatch log groups."
  value       = module.observability.service_log_group_names
}
