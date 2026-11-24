# GitHub Actions OIDC roles for the PR plan gate and the post-merge deploy of
# one workspace. Requires the account-level GitHub OIDC provider (bootstrap
# once: see docs/CICD_PIPELINE.md). No long-lived AWS keys are stored in GitHub.

variable "prefix" { type = string }
variable "environment_name" { type = string }
variable "github_repository" { type = string }
variable "state_bucket" { type = string }

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

variable "github_oidc_subject_repository" {
  description = "Repository part of the GitHub OIDC sub claim. GitHub's immutable format is owner@ownerId/repo@repoId; empty uses owner/repo."
  type        = string
  default     = ""
}

locals {
  oidc_subject_repository = var.github_oidc_subject_repository != "" ? var.github_oidc_subject_repository : var.github_repository
  oidc_host               = "token.actions.githubusercontent.com"
}

# PR gate: `terraform plan` for the PR's target workspace. Read-only; plans run
# with -lock=false so no state write is needed.
resource "aws_iam_role" "plan" {
  name = "${var.prefix}-github-terraform-plan"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = data.aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_host}:aud" = "sts.amazonaws.com"
          "${local.oidc_host}:sub" = "repo:${local.oidc_subject_repository}:pull_request"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "plan_read_only" {
  role       = aws_iam_role.plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# Post-merge deploy: only a job bound to the GitHub Environment named after
# this workspace (dev/test/prod, branch-restricted in GitHub) can assume it.
# Terraform manages IAM, EKS, VPC and API Gateway, so the role is broad; its
# blast radius is limited by the OIDC subject and GitHub environment rules.
resource "aws_iam_role" "deploy" {
  name                 = "${var.prefix}-github-deploy"
  max_session_duration = 7200
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = data.aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_host}:aud" = "sts.amazonaws.com"
          "${local.oidc_host}:sub" = "repo:${local.oidc_subject_repository}:environment:${var.environment_name}"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "deploy_admin" {
  role       = aws_iam_role.deploy.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

output "plan_role_arn" {
  value = aws_iam_role.plan.arn
}

output "deploy_role_arn" {
  value = aws_iam_role.deploy.arn
}
