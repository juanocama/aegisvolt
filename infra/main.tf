locals {
  prefix       = "${terraform.workspace}-aegisvolt"
  table_prefix = "aegisvolt-${terraform.workspace}"
  cluster_name = "${terraform.workspace}-${var.cluster_name}"
}

resource "terraform_data" "workspace_guard" {
  lifecycle {
    precondition {
      condition     = contains(["dev", "test", "prod"], terraform.workspace)
      error_message = "Terraform workspace must be one of: dev, test, or prod."
    }
    precondition {
      condition     = var.node_min_size <= var.node_desired_size && var.node_desired_size <= var.node_max_size
      error_message = "EKS node sizing must satisfy node_min_size <= node_desired_size <= node_max_size."
    }
  }
}

module "network" {
  source                            = "./modules/network"
  prefix                            = local.prefix
  region                            = var.region
  vpc_cidr                          = var.vpc_cidr
  availability_zone_count           = var.availability_zone_count
  enable_nat_gateway                = var.enable_nat_gateway
  nat_gateway_per_availability_zone = var.nat_gateway_per_availability_zone
  interface_endpoint_az_count       = var.interface_endpoint_az_count
  enable_ssm_endpoints              = var.enable_access_host
}

module "dynamodb" {
  source                     = "./modules/dynamodb"
  prefix                     = local.table_prefix
  enable_deletion_protection = var.enable_dynamodb_deletion_protection
  initial_feature_flags      = var.initial_feature_flags[terraform.workspace]
}

module "observability" {
  source             = "./modules/observability"
  prefix             = local.prefix
  environment_name   = terraform.workspace
  cluster_name       = local.cluster_name
  log_retention_days = var.cloudwatch_log_retention_days
  region             = var.region
}

module "api_gateway" {
  source                      = "./modules/api_gateway"
  prefix                      = local.prefix
  vpc_id                      = module.network.vpc_id
  vpc_cidr                    = module.network.vpc_cidr
  private_subnet_ids          = module.network.private_subnet_ids
  execute_api_vpc_endpoint_id = module.network.execute_api_vpc_endpoint_id
  enable_graphql_integration  = var.enable_graphql_integration
  gateway_alb_arn             = var.gateway_alb_arn
  gateway_alb_dns_name        = var.gateway_alb_dns_name
}

module "eks_ecr" {
  source               = "./modules/eks_ecr"
  prefix               = local.prefix
  environment_name     = terraform.workspace
  cluster_name         = local.cluster_name
  admin_principal_arns = var.eks_admin_principal_arns
  private_subnet_ids   = module.network.private_subnet_ids
  vpc_id               = module.network.vpc_id
  vpc_cidr             = module.network.vpc_cidr
  desired_size         = var.node_desired_size
  min_size             = var.node_min_size
  max_size             = var.node_max_size
  instance_types       = var.node_instance_types
  dynamodb_table_arns  = module.dynamodb.table_arns
  addon_versions       = var.eks_addon_versions
  ecr_force_delete     = var.ecr_force_delete
  depends_on           = [module.observability]
}

module "github_actions_ecr" {
  count  = var.github_repository == "" ? 0 : 1
  source = "./modules/github_actions_ecr"

  prefix            = local.prefix
  environment_name  = terraform.workspace
  github_repository = var.github_repository
  region            = var.region
}

module "access_host" {
  count  = var.enable_access_host ? 1 : 0
  source = "./modules/access_host"

  prefix                    = local.prefix
  vpc_id                    = module.network.vpc_id
  vpc_cidr                  = module.network.vpc_cidr
  subnet_id                 = module.network.private_subnet_ids[0]
  cluster_security_group_id = module.eks_ecr.cluster_security_group_id
}

module "github_actions_cicd" {
  count  = var.github_repository == "" ? 0 : 1
  source = "./modules/github_actions_cicd"

  prefix            = local.prefix
  environment_name  = terraform.workspace
  github_repository = var.github_repository
  state_bucket      = var.state_bucket
}

# The deploy role needs kubectl access to apply manifests and run the canary.
resource "aws_eks_access_entry" "github_deploy" {
  count         = var.github_repository == "" ? 0 : 1
  cluster_name  = module.eks_ecr.cluster_name
  principal_arn = module.github_actions_cicd[0].deploy_role_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "github_deploy" {
  count         = var.github_repository == "" ? 0 : 1
  cluster_name  = module.eks_ecr.cluster_name
  principal_arn = aws_eks_access_entry.github_deploy[0].principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  access_scope {
    type = "cluster"
  }
}
