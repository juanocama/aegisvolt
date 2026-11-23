variable "prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "availability_zone_count" {
  type = number
}

variable "enable_nat_gateway" {
  type = bool
}

variable "nat_gateway_per_availability_zone" {
  type = bool
}

variable "interface_endpoint_az_count" {
  description = "Number of private subnets (AZs) that receive interface endpoint ENIs. Endpoints are billed per AZ-hour."
  type        = number
}

variable "enable_ssm_endpoints" {
  description = "Create ssm/ssmmessages/ec2messages endpoints for the private Session Manager access host."
  type        = bool
  default     = false
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "${var.prefix}-vpc" }
}

resource "aws_subnet" "public" {
  count                   = var.availability_zone_count
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.prefix}-public-${count.index}", "kubernetes.io/role/elb" = "1" }
}

resource "aws_subnet" "private" {
  count                   = var.availability_zone_count
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + var.availability_zone_count)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.prefix}-private-${count.index}", "kubernetes.io/role/internal-elb" = "1" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.prefix}-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${var.prefix}-public" }
}

resource "aws_route_table_association" "public" {
  count          = var.availability_zone_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

locals {
  nat_gateway_count = var.enable_nat_gateway ? (var.nat_gateway_per_availability_zone ? var.availability_zone_count : 1) : 0
}

resource "aws_eip" "nat" {
  count  = local.nat_gateway_count
  domain = "vpc"
  tags   = { Name = "${var.prefix}-nat-${count.index}" }
}

resource "aws_nat_gateway" "main" {
  count         = local.nat_gateway_count
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = { Name = "${var.prefix}-nat-${count.index}" }

  depends_on = [aws_internet_gateway.main]
}

resource "aws_route_table" "private" {
  count  = var.availability_zone_count
  vpc_id = aws_vpc.main.id

  dynamic "route" {
    for_each = var.enable_nat_gateway ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = aws_nat_gateway.main[var.nat_gateway_per_availability_zone ? count.index : 0].id
    }
  }

  tags = { Name = "${var.prefix}-private-${count.index}" }
}

resource "aws_route_table_association" "private" {
  count          = var.availability_zone_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_security_group" "vpc_endpoints" {
  name        = "${var.prefix}-vpc-endpoints"
  description = "Allow HTTPS from private VPC resources"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.prefix}-vpc-endpoints" }
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat([aws_route_table.public.id], aws_route_table.private[*].id)
  tags              = { Name = "${var.prefix}-s3" }
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat([aws_route_table.public.id], aws_route_table.private[*].id)
  tags              = { Name = "${var.prefix}-dynamodb" }
}

locals {
  interface_endpoints = toset([
    "ec2",
    "elasticloadbalancing", # AWS Load Balancer Controller ALB/target-group reconciliation
    "monitoring",           # CloudWatch PutMetricData (Prefect audit, agent metrics)
    "ecr.api",
    "ecr.dkr",
    "logs",
    "sts",
    "execute-api",
    "eks-auth",
  ])
  ssm_endpoints           = var.enable_ssm_endpoints ? toset(["ssm", "ssmmessages", "ec2messages"]) : toset([])
  endpoint_az_count       = min(var.interface_endpoint_az_count, var.availability_zone_count)
  endpoint_subnet_ids     = slice(aws_subnet.private[*].id, 0, local.endpoint_az_count)
  all_interface_endpoints = setunion(local.interface_endpoints, local.ssm_endpoints)
}

resource "aws_vpc_endpoint" "interface" {
  for_each            = local.all_interface_endpoints
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.endpoint_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  tags                = { Name = "${var.prefix}-${replace(each.key, ".", "-")}" }
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "vpc_cidr" {
  value = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "execute_api_vpc_endpoint_id" {
  value = aws_vpc_endpoint.interface["execute-api"].id
}
