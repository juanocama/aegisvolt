variable "prefix" {
  type = string
}

resource "aws_apigatewayv2_api" "gateway" {
  name          = "${var.prefix}-graphql"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.gateway.id
  name        = "$default"
  auto_deploy = true
}

output "api_id" {
  description = "ID of the GraphQL HTTP API shell."
  value       = aws_apigatewayv2_api.gateway.id
}

output "api_endpoint" {
  description = "Regional endpoint exposed before routes and integrations are configured."
  value       = aws_apigatewayv2_api.gateway.api_endpoint
}

# No route or integration is declared. A private- or public-backend URI,
# VPC link, load balancer and DNS decision is not yet available in the
# inspected Kubernetes source. This resource is a valid HTTP API shell only.
