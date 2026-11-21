variable "region" {
  description = "AWS region for all environment resources."
  type        = string

  validation {
    condition     = length(trimspace(var.region)) > 0
    error_message = "The AWS region must be configured."
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
