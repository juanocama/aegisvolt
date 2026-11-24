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

resource "aws_cloudwatch_log_group" "application" {
  name              = "/aws/containerinsights/${var.cluster_name}/application"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "dataplane" {
  name              = "/aws/containerinsights/${var.cluster_name}/dataplane"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "host" {
  name              = "/aws/containerinsights/${var.cluster_name}/host"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = var.log_retention_days
}

resource "aws_sns_topic" "alerts" {
  name = "${var.prefix}-alerts"
}

variable "region" {
  type = string
}

locals {
  aegisvolt_log_sources = toset(["gateway", "station-reservation", "billing-wallet", "energy-dispatch", "frontend", "gateway-canary", "other"])
  metric_namespace      = "AegisVolt/${var.environment_name}"
}

# Spec 2.5: per-environment, per-service structured logs. Fluent Bit (EKS
# add-on, see eks_ecr) routes pods by their `app` label; it never creates
# groups, so every destination is declared here with retention.
resource "aws_cloudwatch_log_group" "service" {
  for_each          = local.aegisvolt_log_sources
  name              = "/aegisvolt/${var.environment_name}/${each.key}"
  retention_in_days = var.log_retention_days
}

# Created by the CloudWatch agent when Container Insights is on; declared so
# it has retention and is removed by terraform destroy.
resource "aws_cloudwatch_log_group" "performance" {
  name              = "/aws/containerinsights/${var.cluster_name}/performance"
  retention_in_days = var.log_retention_days
}

# Request logs (common/observability.py) are merged under log_processed.
resource "aws_cloudwatch_log_metric_filter" "http_5xx" {
  for_each       = toset(["gateway", "gateway-canary", "station-reservation", "billing-wallet", "energy-dispatch"])
  name           = "${var.prefix}-${each.key}-http-5xx"
  log_group_name = aws_cloudwatch_log_group.service[each.key].name
  pattern        = "{ $.log_processed.status_code >= 500 }"
  metric_transformation {
    name          = "Http5xx"
    namespace     = local.metric_namespace
    value         = "1"
    default_value = "0"
    unit          = "Count"
  }
}

resource "aws_cloudwatch_log_metric_filter" "requests" {
  for_each       = toset(["gateway", "gateway-canary"])
  name           = "${var.prefix}-${each.key}-requests"
  log_group_name = aws_cloudwatch_log_group.service[each.key].name
  pattern        = "{ $.log_processed.status_code >= 100 }"
  metric_transformation {
    name      = "Requests-${each.key}"
    namespace = local.metric_namespace
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_log_metric_filter" "canary_5xx" {
  name           = "${var.prefix}-gateway-canary-5xx"
  log_group_name = aws_cloudwatch_log_group.service["gateway-canary"].name
  pattern        = "{ $.log_processed.status_code >= 500 }"
  metric_transformation {
    name          = "Http5xx-gateway-canary"
    namespace     = local.metric_namespace
    value         = "1"
    default_value = "0"
    unit          = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "http_5xx" {
  alarm_name          = "${var.prefix}-http-5xx"
  alarm_description   = "Any 5xx response logged by AegisVolt services in ${var.environment_name}."
  namespace           = local.metric_namespace
  metric_name         = "Http5xx"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  depends_on          = [aws_cloudwatch_log_metric_filter.http_5xx]
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.prefix}-overview"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title   = "HTTP 5xx (${var.environment_name})"
          region  = var.region
          stat    = "Sum"
          period  = 60
          metrics = [[local.metric_namespace, "Http5xx"], [local.metric_namespace, "Http5xx-gateway-canary"]]
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title   = "Gateway requests: stable vs canary"
          region  = var.region
          stat    = "Sum"
          period  = 60
          metrics = [[local.metric_namespace, "Requests-gateway"], [local.metric_namespace, "Requests-gateway-canary"]]
        }
      },
      {
        type = "log", x = 0, y = 6, width = 24, height = 8
        properties = {
          title  = "SAGA requests by correlation_id"
          region = var.region
          query  = "SOURCE '/aegisvolt/${var.environment_name}/gateway' | fields @timestamp, log_processed.correlation_id, log_processed.method, log_processed.path, log_processed.status_code, log_processed.duration_ms | filter ispresent(log_processed.correlation_id) | sort @timestamp desc | limit 50"
          view   = "table"
        }
      },
    ]
  })
}

output "service_log_group_names" {
  value = { for name, group in aws_cloudwatch_log_group.service : name => group.name }
}

output "alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}
