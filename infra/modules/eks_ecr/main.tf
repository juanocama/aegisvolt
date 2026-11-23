variable "prefix" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "vpc_id" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "desired_size" {
  type = number
}

variable "min_size" {
  type = number
}

variable "max_size" {
  type = number
}

variable "instance_types" {
  type = list(string)
}

variable "dynamodb_table_arns" {
  type = map(string)
}

variable "environment_name" {
  type        = string
  description = "Environment name used in ECR repository naming."
}

variable "admin_principal_arns" {
  type        = list(string)
  description = "Validated IAM principal ARNs with EKS cluster administrator access."
  default     = []
}

resource "aws_ecr_repository" "service" {
  for_each             = toset(["gateway", "station-reservation", "billing-wallet", "energy-dispatch", "frontend"])
  name                 = "aegisvolt/${var.environment_name}/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.ecr_force_delete
  image_scanning_configuration { scan_on_push = true }
}

variable "ecr_force_delete" {
  description = "Allow terraform destroy to delete ECR repositories that still contain images (temporary environments only)."
  type        = bool
  default     = false
}

resource "aws_iam_role" "eks_cluster" {
  name = "${var.prefix}-eks-cluster"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "eks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}
resource "aws_iam_role_policy_attachment" "eks_cluster" {
  role       = aws_iam_role.eks_cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role" "eks_nodes" {
  name = "${var.prefix}-eks-node"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_node_worker" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_node_cni" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "eks_node_ecr" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.37"
  access_config {
    authentication_mode = "API_AND_CONFIG_MAP"
  }
  vpc_config {
    subnet_ids              = var.private_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = false
  }
  enabled_cluster_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler",
  ]
  depends_on = [aws_iam_role_policy_attachment.eks_cluster]
}

resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.prefix}-workers"
  node_role_arn   = aws_iam_role.eks_nodes.arn
  subnet_ids      = var.private_subnet_ids
  instance_types  = var.instance_types

  scaling_config {
    desired_size = var.desired_size
    min_size     = var.min_size
    max_size     = var.max_size
  }

  update_config {
    max_unavailable = 1
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_node_worker,
    aws_iam_role_policy_attachment.eks_node_cni,
    aws_iam_role_policy_attachment.eks_node_ecr,
  ]
}

resource "aws_eks_addon" "coredns" {
  cluster_name  = aws_eks_cluster.main.name
  addon_name    = "coredns"
  addon_version = var.addon_versions["coredns"]

  depends_on = [aws_eks_node_group.main]
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name  = aws_eks_cluster.main.name
  addon_name    = "kube-proxy"
  addon_version = var.addon_versions["kube_proxy"]
}

resource "aws_eks_addon" "vpc_cni" {
  cluster_name  = aws_eks_cluster.main.name
  addon_name    = "vpc-cni"
  addon_version = var.addon_versions["vpc_cni"]
}

resource "aws_eks_addon" "pod_identity_agent" {
  cluster_name  = aws_eks_cluster.main.name
  addon_name    = "eks-pod-identity-agent"
  addon_version = var.addon_versions["pod_identity_agent"]
  depends_on    = [aws_eks_node_group.main]
}

resource "aws_iam_role" "cloudwatch_observability" {
  name = "${var.prefix}-cloudwatch-observability"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "cloudwatch_observability" {
  role       = aws_iam_role.cloudwatch_observability.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_eks_addon" "cloudwatch_observability" {
  cluster_name  = aws_eks_cluster.main.name
  addon_name    = "amazon-cloudwatch-observability"
  addon_version = var.addon_versions["cloudwatch_observability"]
  configuration_values = jsonencode({
    # With every metrics pipeline disabled the agent has no config and
    # crash-loops (observed on v8.0.1 in dev, 2026-11-23). Basic (not
    # enhanced) Container Insights keeps node/pod metrics at minimal cost.
    containerInsights = { enabled = true }
    agent = {
      config = {
        logs = {
          metrics_collected = {
            kubernetes = { enhanced_container_insights = false }
          }
        }
      }
    }
    applicationSignals    = { enabled = false }
    otlp                  = { enabled = false }
    otelPrometheusMonitor = { enabled = false }
    containerLogs         = { enabled = true }
  })
  pod_identity_association {
    role_arn        = aws_iam_role.cloudwatch_observability.arn
    service_account = "cloudwatch-agent"
  }
  depends_on = [
    aws_eks_addon.pod_identity_agent,
    aws_iam_role_policy_attachment.cloudwatch_observability,
  ]
}

resource "aws_eks_access_entry" "admin" {
  for_each          = toset(var.admin_principal_arns)
  cluster_name      = aws_eks_cluster.main.name
  principal_arn     = each.key
  kubernetes_groups = []
  type              = "STANDARD"
}

resource "aws_eks_access_policy_association" "admin" {
  for_each = aws_eks_access_entry.admin

  cluster_name  = aws_eks_cluster.main.name
  principal_arn = each.value.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}

data "tls_certificate" "eks" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "eks" {
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
}

locals {
  oidc_provider_arn = aws_iam_openid_connect_provider.eks.arn
  oidc_provider_url = replace(aws_iam_openid_connect_provider.eks.url, "https://", "")

  workload_tables = {
    station-reservation = "stations"
    billing-wallet      = "wallets"
    energy-dispatch     = "dispatch"
    gateway             = "sagas"
  }

  workload_dynamodb_actions = {
    station-reservation = ["dynamodb:DescribeTable", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"]
    billing-wallet      = ["dynamodb:DescribeTable", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:TransactWriteItems"]
    energy-dispatch     = ["dynamodb:DescribeTable", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Scan", "dynamodb:TransactWriteItems"]
    gateway             = ["dynamodb:DescribeTable", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Scan"]
  }
}

resource "aws_iam_role" "workload" {
  for_each = local.workload_tables
  name     = "${var.prefix}-${each.key}-irsa"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = local.oidc_provider_arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_provider_url}:aud" = "sts.amazonaws.com"
          "${local.oidc_provider_url}:sub" = "system:serviceaccount:aegisvolt:${each.key}"
        }
      }
    }]
  })
}

resource "aws_iam_policy" "workload" {
  for_each = local.workload_tables
  name     = "${var.prefix}-${each.key}-dynamodb"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ServiceTableDataAccess"
        Effect   = "Allow"
        Action   = local.workload_dynamodb_actions[each.key]
        Resource = var.dynamodb_table_arns[each.value]
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "workload" {
  for_each   = aws_iam_policy.workload
  role       = aws_iam_role.workload[each.key].name
  policy_arn = each.value.arn
}

# AWS Load Balancer Controller: dedicated least-privilege role bound through EKS
# Pod Identity to kube-system/aws-load-balancer-controller only. The policy is
# the unmodified upstream iam_policy.json for chart/app v3.6.3, downloaded from
# kubernetes-sigs/aws-load-balancer-controller (Apache-2.0) on 2026-11-23.
resource "aws_iam_role" "load_balancer_controller" {
  name = "${var.prefix}-aws-load-balancer-controller"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
        ArnEquals = {
          "aws:SourceArn" = aws_eks_cluster.main.arn
        }
      }
    }]
  })
}

data "aws_caller_identity" "current" {}

resource "aws_iam_policy" "load_balancer_controller" {
  name   = "${var.prefix}-aws-load-balancer-controller"
  policy = file("${path.module}/policies/lbc_iam_policy_v3.6.3.json")
}

resource "aws_iam_role_policy_attachment" "load_balancer_controller" {
  role       = aws_iam_role.load_balancer_controller.name
  policy_arn = aws_iam_policy.load_balancer_controller.arn
}

resource "aws_eks_pod_identity_association" "load_balancer_controller" {
  cluster_name    = aws_eks_cluster.main.name
  namespace       = "kube-system"
  service_account = "aws-load-balancer-controller"
  role_arn        = aws_iam_role.load_balancer_controller.arn
  depends_on      = [aws_eks_addon.pod_identity_agent]
}

# Private clusters without NAT cannot pull from public.ecr.aws; the controller
# image is mirrored here by digest before the Helm install.
resource "aws_ecr_repository" "mirror" {
  for_each             = toset(["aws-load-balancer-controller"])
  name                 = "aegisvolt/${var.environment_name}/mirror/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.ecr_force_delete
  image_scanning_configuration { scan_on_push = true }
}

output "cluster_security_group_id" {
  value = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
}

output "load_balancer_controller_role_arn" {
  value = aws_iam_role.load_balancer_controller.arn
}

output "mirror_repository_urls" {
  value = { for name, repository in aws_ecr_repository.mirror : name => repository.repository_url }
}

output "cluster_name" {
  value = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.main.endpoint
}

output "oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.eks.arn
}

output "workload_role_arns" {
  value = { for name, role in aws_iam_role.workload : name => role.arn }
}

output "ecr_repository_urls" {
  value = { for name, repository in aws_ecr_repository.service : name => repository.repository_url }
}

variable "addon_versions" {
  description = "Pinned EKS add-on versions (from aws eks describe-addon-versions for the cluster Kubernetes version)."
  type = object({
    coredns                  = string
    kube_proxy               = string
    vpc_cni                  = string
    pod_identity_agent       = string
    cloudwatch_observability = string
  })
}
