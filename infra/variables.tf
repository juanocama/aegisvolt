variable "region" {
  description = "AWS region for all environment resources."
  type        = string

  validation {
    condition     = length(trimspace(var.region)) > 0 && !can(regex("CHANGE_ME", var.region))
    error_message = "The AWS region must be configured and must not contain CHANGE_ME."
  }
}

variable "cluster_name" {
  description = "Base name for the EKS cluster."
  type        = string
  default     = "aegisvolt"

  validation {
    condition     = length(trimspace(var.cluster_name)) > 0
    error_message = "The cluster name must not be empty."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the environment VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zone_count" {
  description = "Number of availability zones used for public and private subnets."
  type        = number
  default     = 2

  validation {
    condition     = var.availability_zone_count >= 2 && var.availability_zone_count <= 3
    error_message = "Use between 2 and 3 availability zones."
  }
}

variable "enable_nat_gateway" {
  description = "Create NAT gateways for private-subnet egress. This incurs hourly and data-processing costs."
  type        = bool
  default     = false
}

variable "nat_gateway_per_availability_zone" {
  description = "Create one NAT gateway per AZ instead of a single NAT gateway."
  type        = bool
  default     = false
}

variable "node_desired_size" {
  description = "Desired size of the EKS managed node group."
  type        = number
  default     = 1

  validation {
    condition     = var.node_desired_size >= 1
    error_message = "The desired node count must be at least 1."
  }
}

variable "node_min_size" {
  description = "Minimum size of the EKS managed node group."
  type        = number
  default     = 1

  validation {
    condition     = var.node_min_size >= 1
    error_message = "The minimum node count must be at least 1."
  }
}

variable "node_max_size" {
  description = "Maximum size of the EKS managed node group."
  type        = number
  default     = 3

  validation {
    condition     = var.node_max_size >= 1
    error_message = "The maximum node count must be at least 1."
  }
}

variable "node_instance_types" {
  description = "EC2 instance types used by the EKS managed node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "enable_dynamodb_deletion_protection" {
  description = "Enable DynamoDB deletion protection."
  type        = bool
  default     = false
}

variable "cloudwatch_log_retention_days" {
  description = "CloudWatch log retention for application and cluster logs."
  type        = number
  default     = 14
}

variable "github_repository" {
  description = "Exact GitHub owner/repository slug used by GitHub Actions OIDC; leave empty to omit CI roles until configured."
  type        = string
  default     = ""

  validation {
    condition     = var.github_repository == "" || can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must be empty or an exact owner/repository slug."
  }
}

variable "eks_admin_principal_arns" {
  description = "IAM principal ARNs granted the AmazonEKSClusterAdminPolicy access entry. At least one is required before cluster creation."
  type        = list(string)
  nullable    = false
  validation {
    condition     = length(var.eks_admin_principal_arns) > 0
    error_message = "Set at least one real IAM role or user ARN in the environment tfvars before creating EKS."
  }

  validation {
    condition = alltrue([
      for arn in var.eks_admin_principal_arns :
      can(regex("^arn:[^:]+:iam::[0-9]{12}:((role|user)/.+)$", arn))
    ])
    error_message = "eks_admin_principal_arns must contain valid IAM role or user ARN strings."
  }
}

variable "gateway_alb_arn" {
  description = "ARN of the internal GraphQL ALB created by AWS Load Balancer Controller."
  type        = string
  default     = ""
  validation {
    condition     = !var.enable_graphql_integration || can(regex("^arn:[^:]+:elasticloadbalancing:[^:]+:[0-9]{12}:loadbalancer/app/.+", var.gateway_alb_arn))
    error_message = "When enabling GraphQL integration, provide the actual internal ALB ARN after its Ingress is reconciled."
  }
}

variable "gateway_alb_dns_name" {
  description = "DNS name of the same internal GraphQL ALB."
  type        = string
  default     = ""
  validation {
    condition     = !var.enable_graphql_integration || (length(trimspace(var.gateway_alb_dns_name)) > 0 && !can(regex("^https?://", var.gateway_alb_dns_name)))
    error_message = "When enabling GraphQL integration, provide the actual ALB DNS name without a URL scheme."
  }
}

variable "enable_graphql_integration" {
  description = "Create the GraphQL route and VPC Link after the internal ALB has been provisioned by AWS Load Balancer Controller."
  type        = bool
  default     = false
}

variable "eks_addon_versions" {
  description = "EKS add-on versions pinned for Kubernetes 1.37. Defaults are the AWS-reported default versions from describe-addon-versions in us-east-1 on 2026-11-23."
  type = object({
    coredns                  = string
    kube_proxy               = string
    vpc_cni                  = string
    pod_identity_agent       = string
    cloudwatch_observability = string
  })
  default = {
    coredns                  = "v1.14.7-eksbuild.35"
    kube_proxy               = "v1.37.0-eksbuild.39"
    vpc_cni                  = "v1.22.4-eksbuild.14"
    pod_identity_agent       = "v1.4.1-eksbuild.3"
    cloudwatch_observability = "v8.0.1-eksbuild.1"
  }
}

variable "interface_endpoint_az_count" {
  description = "Number of AZs that receive interface VPC endpoint ENIs (billed per endpoint per AZ-hour). Use 1 for temporary dev, the AZ count for HA environments."
  type        = number
  default     = 2
  validation {
    condition     = var.interface_endpoint_az_count >= 1
    error_message = "At least one AZ must host the interface endpoints."
  }
}

variable "enable_access_host" {
  description = "Create the private Session Manager access host (no public IP) and its SSM endpoints for operating the private EKS API and internal ALBs without a VPN."
  type        = bool
  default     = false
}

variable "ecr_force_delete" {
  description = "Let terraform destroy delete non-empty ECR repositories. Only for temporary environments."
  type        = bool
  default     = false
}

variable "initial_feature_flags" {
  description = "Initial flag values per workspace (spec 2.2 example: surge pricing on in dev/test, off in prod). Runtime changes live in each environment's DynamoDB flags table."
  type        = map(map(bool))
  default = {
    dev  = { ENABLE_DYNAMIC_SURGE_PRICING = true, ENABLE_FAST_CHARGE_BOOST = false, SIMULATE_CHARGER_HARDWARE_FAULT = false }
    test = { ENABLE_DYNAMIC_SURGE_PRICING = true, ENABLE_FAST_CHARGE_BOOST = false, SIMULATE_CHARGER_HARDWARE_FAULT = false }
    prod = { ENABLE_DYNAMIC_SURGE_PRICING = false, ENABLE_FAST_CHARGE_BOOST = false, SIMULATE_CHARGER_HARDWARE_FAULT = false }
  }
  validation {
    condition = alltrue([
      for env in ["dev", "test", "prod"] :
      contains(keys(var.initial_feature_flags), env) &&
      toset(keys(var.initial_feature_flags[env])) == toset(["ENABLE_DYNAMIC_SURGE_PRICING", "ENABLE_FAST_CHARGE_BOOST", "SIMULATE_CHARGER_HARDWARE_FAULT"])
    ])
    error_message = "Each of dev/test/prod must define exactly the three official flags."
  }
}

variable "state_bucket" {
  description = "Terraform state bucket name (documented for the CI roles)."
  type        = string
  default     = ""
}

variable "github_oidc_subject_repository" {
  description = "Repository part of GitHub's OIDC sub claim (immutable format owner@ownerId/repo@repoId, as observed in CloudTrail). Empty uses github_repository."
  type        = string
  default     = ""
}
