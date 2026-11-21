variable "prefix" { type = string }
resource "aws_cloudwatch_log_group" "app" {
  name              = "/aegisvolt/${var.prefix}"
  retention_in_days = 14
}
resource "aws_sns_topic" "alerts" { name = "${var.prefix}-alerts" }
