param([string]$Namespace="aegisvolt",[string]$Deployment="gateway-canary",[int]$Retries=12)
$ok = $true
for ($i = 0; $i -lt $Retries; $i++) {
  kubectl -n $Namespace rollout status deployment/$Deployment --timeout=20s
  if ($LASTEXITCODE -ne 0) { $ok = $false; break }
  $restarts = kubectl -n $Namespace get pods -l track=canary -o jsonpath="{range .items[*]}{.status.containerStatuses[*].restartCount}{'\n'}{end}"
  if (($restarts | Measure-Object).Count -gt 0 -and ($restarts | Where-Object { [int]$_ -gt 2 }).Count -gt 0) { $ok = $false; break }
  Start-Sleep -Seconds 5
}
if (-not $ok) { Write-Error "Canary failed health/restart checks"; exit 1 }
Write-Host "Canary health and restart checks passed"
