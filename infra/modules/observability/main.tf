variable "prefix" {
  type = string
}

variable "log_retention_days" {
  type = number
}

variable "cluster_name" {
  type = string
}

variable "environment_name" {
  type = string
}

locals {
  application_services = toset([
    "gateway",
    "station-reservation",
    "billing-wallet",
    "energy-dispatch",
  ])
}

resource "aws_cloudwatch_log_group" "app" {
  for_each          = local.application_services
  name              = "/aegisvolt/${var.environment_name}/${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = var.log_retention_days
}

resource "aws_sns_topic" "alerts" {
  name = "${var.prefix}-alerts"
}

output "log_group_arns" {
  value = merge(
    { for name, group in aws_cloudwatch_log_group.app : name => "${group.arn}:*" },
    { cluster = "${aws_cloudwatch_log_group.cluster.arn}:*" },
  )
}
