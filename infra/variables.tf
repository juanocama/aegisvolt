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
