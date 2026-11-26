# Refresh the mirror from a machine that can reach openplatform.byd.com.
#
# GitHub-hosted runners cannot: their TCP connection to the BYD host never
# completes (the platform sits behind a China-only CDN/WAF), so the crawl has to
# run somewhere with China-side connectivity, then push the result to GitHub.
#
#   pwsh -File scripts/refresh.ps1 -Out docs
#
# Typical run on a Ryzen box with a decent link: ~5 minutes for the full fetch.

param(
    [string]$Out = "docs",
    [int]$MaxAssetMb = 60,
    [int]$MaxVideoMb = 60,
    [int]$BudgetMb = 650,
    [switch]$SkipMedia,
    [switch]$SkipCapture
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here

function Find-Python {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "C:\byd\python\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe"
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "python.exe not found; install Python 3.10+ first"
}

$python = Find-Python
Write-Host "python: $python"

$crawlArgs = @("$here/crawl.py", "--out", "$root/$Out",
    "--max-asset-mb", $MaxAssetMb, "--max-video-mb", $MaxVideoMb, "--budget-mb", $BudgetMb)
if ($SkipMedia) { $crawlArgs += "--no-assets" }

Write-Host "== 1/3 crawl documentation + API + media =="
& $python @crawlArgs

if (-not $SkipCapture) {
    Write-Host "== 2/3 capture rendered competition pages =="
    & $python "$here/capture_contest.py" "$root/$Out"
}

Write-Host "== 3/3 build home / contest / downloads / search / API bundle =="
& $python "$here/extras.py" "$root/$Out"

$size = (Get-ChildItem "$root/$Out" -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("done: {0:N1} MB in {1}" -f $size, "$root/$Out")
Write-Host "next: git add -A && git commit -m 'chore(mirror): refresh' && git push"
