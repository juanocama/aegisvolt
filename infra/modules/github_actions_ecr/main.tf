variable "prefix" {
  type = string
}

variable "environment_name" {
  type = string
}

variable "github_repository" {
  type = string
}

variable "region" {
  type = string
}

data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}

# This deliberately looks up, rather than creates, the account-level GitHub
# provider. Reconcile/import an existing provider before enabling these roles.
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

locals {
  image_names = ["gateway", "station-reservation", "billing-wallet", "energy-dispatch"]
  repository_arns = {
    for name in local.image_names : name => "arn:${data.aws_partition.current.partition}:ecr:${var.region}:${data.aws_caller_identity.current.account_id}:repository/aegisvolt/${var.environment_name}/${name}"
  }
  oidc_host = "token.actions.githubusercontent.com"
  promotion_source_environment = {
    test = "dev"
    prod = "test"
  }
  promotion_source_arns = var.environment_name == "dev" ? [] : [
    for name in local.image_names : "arn:${data.aws_partition.current.partition}:ecr:${var.region}:${data.aws_caller_identity.current.account_id}:repository/aegisvolt/${local.promotion_source_environment[var.environment_name]}/${name}"
  ]
}

resource "aws_iam_role" "publisher" {
  count = var.environment_name == "dev" ? 1 : 0
  name  = "${var.prefix}-github-ecr-publisher"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = data.aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_host}:aud" = "sts.amazonaws.com"
          "${local.oidc_host}:sub" = "repo:${var.github_repository}:environment:ecr-publish-${var.environment_name}"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "publisher" {
  count = var.environment_name == "dev" ? 1 : 0
  name  = "${var.prefix}-github-ecr-push-four-images"
  role  = aws_iam_role.publisher[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrLogin"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "PushOnlyAegisVoltWorkloadRepositories"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:DescribeImages",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart",
        ]
        Resource = values(local.repository_arns)
      },
    ]
  })
}

resource "aws_iam_role" "promoter" {
  count = var.environment_name == "dev" ? 0 : 1
  name  = "${var.prefix}-github-ecr-promoter"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = data.aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_host}:aud" = "sts.amazonaws.com"
          "${local.oidc_host}:sub" = "repo:${var.github_repository}:environment:ecr-promote-${var.environment_name}"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "promoter" {
  count = var.environment_name == "dev" ? 0 : 1
  name  = "${var.prefix}-github-ecr-promote-four-images"
  role  = aws_iam_role.promoter[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrLogin"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "ReadPreviousEnvironmentImages"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:DescribeImages",
          "ecr:GetDownloadUrlForLayer",
        ]
        Resource = local.promotion_source_arns
      },
      {
        Sid    = "WriteOnlyTargetEnvironmentImages"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:DescribeImages",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart",
        ]
        Resource = values(local.repository_arns)
      },
    ]
  })
}

output "role_arns" {
  value = merge(
    var.environment_name == "dev" ? { publisher = aws_iam_role.publisher[0].arn } : {},
    var.environment_name == "dev" ? {} : { promoter = aws_iam_role.promoter[0].arn },
  )
}
