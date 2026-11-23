region       = "us-east-1"
cluster_name = "aegisvolt"
# Same account as dev; separate workspace, state key, VPC, tables and flags.
eks_admin_principal_arns = [
  "arn:aws:iam::065656773005:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_AdministratorAccess_a0fe7335cef42aa4",
]
enable_nat_gateway             = false
enable_access_host             = true
github_repository              = "juanocama/aegisvolt"
state_bucket                   = "aegisvolt-tfstate-065656773005-us-east-1"
github_oidc_subject_repository = "juanocama@140413471/aegisvolt@1468028506"
