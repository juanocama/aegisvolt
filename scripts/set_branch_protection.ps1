param([Parameter(Mandatory=$true)][string]$Owner,[Parameter(Mandatory=$true)][string]$Repo,[string]$Branch="main")
Write-Host "Configure branch protection in GitHub Settings -> Branches or gh api:"
Write-Host "gh api --method PUT repos/$Owner/$Repo/branches/$Branch/protection -f required_status_checks.strict=true -f enforce_admins=true -f required_pull_request_reviews.required_approving_review_count=1"
