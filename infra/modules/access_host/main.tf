# Private operator access host for a VPC without VPN/NAT.
# Reached only through AWS Systems Manager Session Manager (no public IP, no
# inbound rules, no SSH key). Used to port-forward to the private EKS API and
# the internal ALBs so the private architecture is never exposed publicly.

variable "prefix" { type = string }
variable "vpc_id" { type = string }
variable "vpc_cidr" { type = string }
variable "subnet_id" { type = string }
variable "cluster_security_group_id" { type = string }

variable "instance_type" {
  type    = string
  default = "t3.micro"
}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_iam_role" "host" {
  name = "${var.prefix}-ssm-access-host"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.host.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "host" {
  name = "${var.prefix}-ssm-access-host"
  role = aws_iam_role.host.name
}

resource "aws_security_group" "host" {
  name        = "${var.prefix}-ssm-access-host"
  description = "Session Manager access host: no inbound, egress to VPC only."
  vpc_id      = var.vpc_id

  egress {
    description = "HTTPS/HTTP to VPC endpoints, EKS API and internal ALBs"
    from_port   = 80
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = { Name = "${var.prefix}-ssm-access-host" }
}

resource "aws_vpc_security_group_ingress_rule" "eks_api_from_host" {
  security_group_id            = var.cluster_security_group_id
  referenced_security_group_id = aws_security_group.host.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  description                  = "Private EKS API from the SSM access host"
}

resource "aws_instance" "host" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.host.id]
  iam_instance_profile        = aws_iam_instance_profile.host.name
  associate_public_ip_address = false

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  root_block_device {
    volume_size           = 8
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  lifecycle { ignore_changes = [ami] }

  tags = { Name = "${var.prefix}-ssm-access-host" }

  depends_on = [aws_iam_role_policy_attachment.ssm_core]
}

output "instance_id" {
  value = aws_instance.host.id
}

output "security_group_id" {
  value = aws_security_group.host.id
}
