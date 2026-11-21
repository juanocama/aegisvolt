variable "prefix" { type = string }
resource "aws_apigatewayv2_api" "gateway" {
  name          = "${var.prefix}-graphql"
  protocol_type = "HTTP"
}
