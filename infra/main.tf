locals { prefix = "${terraform.workspace}-aegisvolt" }

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
}

module "dynamodb" {
  source                     = "./modules/dynamodb"
  prefix                     = local.prefix
  enable_deletion_protection = var.enable_dynamodb_deletion_protection
}

module "observability" {
  source             = "./modules/observability"
  prefix             = local.prefix
  log_retention_days = var.cloudwatch_log_retention_days
}

module "api_gateway" {
  source = "./modules/api_gateway"
  prefix = local.prefix
}

module "eks_ecr" {
  source              = "./modules/eks_ecr"
  prefix              = local.prefix
  cluster_name        = "${local.prefix}-${var.cluster_name}"
  private_subnet_ids  = module.network.private_subnet_ids
  vpc_id              = module.network.vpc_id
  vpc_cidr            = module.network.vpc_cidr
  desired_size        = var.node_desired_size
  min_size            = var.node_min_size
  max_size            = var.node_max_size
  instance_types      = var.node_instance_types
  dynamodb_table_arns = module.dynamodb.table_arns
  log_group_arns      = module.observability.log_group_arns
}
