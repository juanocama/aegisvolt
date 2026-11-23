region       = "us-east-1"
cluster_name = "aegisvolt"
# Underlying IAM role of the Identity Center AdministratorAccess permission set
# (verified with iam list-roles on 2026-11-23). Not the STS assumed-role ARN.
eks_admin_principal_arns = [
  "arn:aws:iam::065656773005:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_AdministratorAccess_a0fe7335cef42aa4",
]

# Temporary low-cost dev demonstration (2026-11-23): no NAT, one node,
# interface endpoints in one AZ, SSM access host instead of a paid VPN.
enable_nat_gateway                  = false
node_desired_size                   = 1
node_min_size                       = 1
node_max_size                       = 1
node_instance_types                 = ["t3.medium"]
interface_endpoint_az_count         = 1
enable_access_host                  = true
ecr_force_delete                    = true
cloudwatch_log_retention_days       = 1
enable_dynamodb_deletion_protection = false
github_repository                   = "juanocama/aegisvolt"
state_bucket                        = "aegisvolt-tfstate-065656773005-us-east-1"
github_oidc_subject_repository      = "juanocama@140413471/aegisvolt@1468028506"
