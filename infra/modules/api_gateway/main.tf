variable "prefix" { type = string }
variable "vpc_id" { type = string }
variable "vpc_cidr" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "execute_api_vpc_endpoint_id" { type = string }
variable "enable_graphql_integration" {
  description = "Enable after the AWS Load Balancer Controller has created the private GraphQL ALB and its ARN/DNS are supplied."
  type        = bool
  default     = false
}

variable "gateway_alb_arn" {
  description = "ARN of the internal ALB created by AWS Load Balancer Controller."
  type        = string
  validation {
    condition     = !var.enable_graphql_integration || can(regex("^arn:[^:]+:elasticloadbalancing:[^:]+:[0-9]{12}:loadbalancer/app/.+", var.gateway_alb_arn))
    error_message = "When enabling GraphQL integration, gateway_alb_arn must be an application load balancer ARN."
  }
}

variable "gateway_alb_dns_name" {
  description = "DNS name of that internal ALB, supplied after the controller creates it."
  type        = string
  validation {
    condition     = !var.enable_graphql_integration || (length(trimspace(var.gateway_alb_dns_name)) > 0 && !can(regex("^https?://", var.gateway_alb_dns_name)))
    error_message = "When enabling GraphQL integration, provide the ALB DNS name without a URL scheme."
  }
}

resource "aws_security_group" "vpc_link" {
  name        = "${var.prefix}-apigw-vpclink"
  description = "API Gateway VPC Link traffic to the private GraphQL ALB."
  vpc_id      = var.vpc_id
  egress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
}

resource "aws_apigatewayv2_vpc_link" "gateway" {
  count              = var.enable_graphql_integration ? 1 : 0
  name               = "${var.prefix}-graphql"
  subnet_ids         = var.private_subnet_ids
  security_group_ids = [aws_security_group.vpc_link.id]
}

resource "aws_api_gateway_rest_api" "gateway" {
  name                         = "${var.prefix}-graphql"
  description                  = "Private GraphQL API for VPC-connected clients."
  disable_execute_api_endpoint = false
  endpoint_configuration {
    types            = ["PRIVATE"]
    vpc_endpoint_ids = [var.execute_api_vpc_endpoint_id]
  }
}

# Separate policy resource so the Resource can be the concrete execution ARN
# (AWS rewrites "execute-api:/*" and Terraform would otherwise drift forever).
resource "aws_api_gateway_rest_api_policy" "gateway" {
  rest_api_id = aws_api_gateway_rest_api.gateway.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = "*"
      Action    = "execute-api:Invoke"
      Resource  = "${aws_api_gateway_rest_api.gateway.execution_arn}/*"
      Condition = { StringEquals = { "aws:SourceVpce" = var.execute_api_vpc_endpoint_id } }
    }]
  })
}

resource "aws_api_gateway_resource" "graphql" {
  rest_api_id = aws_api_gateway_rest_api.gateway.id
  parent_id   = aws_api_gateway_rest_api.gateway.root_resource_id
  path_part   = "graphql"
}

resource "aws_api_gateway_method" "graphql" {
  count         = var.enable_graphql_integration ? 1 : 0
  rest_api_id   = aws_api_gateway_rest_api.gateway.id
  resource_id   = aws_api_gateway_resource.graphql.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "graphql" {
  count                   = var.enable_graphql_integration ? 1 : 0
  rest_api_id             = aws_api_gateway_rest_api.gateway.id
  resource_id             = aws_api_gateway_resource.graphql.id
  http_method             = aws_api_gateway_method.graphql[0].http_method
  integration_http_method = "POST"
  type                    = "HTTP_PROXY"
  uri                     = "http://${var.gateway_alb_dns_name}/graphql"
  connection_type         = "VPC_LINK"
  connection_id           = aws_apigatewayv2_vpc_link.gateway[0].id
  integration_target      = var.gateway_alb_arn
}

resource "aws_api_gateway_deployment" "gateway" {
  count       = var.enable_graphql_integration ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.gateway.id
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.graphql.id,
      aws_api_gateway_method.graphql[0].id,
      aws_api_gateway_integration.graphql[0].id,
      var.gateway_alb_arn,
      var.gateway_alb_dns_name,
      aws_api_gateway_rest_api_policy.gateway.policy,
    ]))
  }
  lifecycle { create_before_destroy = true }
  depends_on = [aws_api_gateway_rest_api_policy.gateway]
}

resource "aws_api_gateway_stage" "gateway" {
  count         = var.enable_graphql_integration ? 1 : 0
  rest_api_id   = aws_api_gateway_rest_api.gateway.id
  deployment_id = aws_api_gateway_deployment.gateway[0].id
  stage_name    = terraform.workspace
}

data "aws_region" "current" {}

output "api_id" {
  description = "ID of the private GraphQL REST API."
  value       = aws_api_gateway_rest_api.gateway.id
}

output "api_endpoint" {
  description = "Private API Gateway invocation URL, reachable only through execute-api VPC endpoint."
  value       = var.enable_graphql_integration ? "https://${aws_api_gateway_rest_api.gateway.id}.execute-api.${data.aws_region.current.region}.amazonaws.com/${aws_api_gateway_stage.gateway[0].stage_name}/graphql" : null
}
