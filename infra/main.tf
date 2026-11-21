locals { prefix = "${terraform.workspace}-aegisvolt" }

resource "terraform_data" "workspace_guard" {
  lifecycle {
    precondition {
      condition     = contains(["dev", "test", "prod"], terraform.workspace)
      error_message = "Terraform workspace must be one of: dev, test, or prod."
    }
  }
}

module "network" {
  source = "./modules/network"
  prefix = local.prefix
  region = var.region
}

module "dynamodb" {
  source = "./modules/dynamodb"
  prefix = local.prefix
}

module "observability" {
  source = "./modules/observability"
  prefix = local.prefix
}

module "api_gateway" {
  source = "./modules/api_gateway"
  prefix = local.prefix
}

module "eks_ecr" {
  source       = "./modules/eks_ecr"
  prefix       = local.prefix
  cluster_name = "${local.prefix}-${var.cluster_name}"
  subnet_ids   = module.network.subnet_ids
}
