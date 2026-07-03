# Build the Vite frontend from the local AlignX/web-frontend repo and copy it to AlignX/static

$repoRoot = Split-Path $PSScriptRoot -Parent
$portfolioDir = Join-Path $repoRoot "web-frontend"
$staticDir = Join-Path $repoRoot "static"

Write-Host "Building Vite frontend in $portfolioDir..." -ForegroundColor Cyan
Push-Location $portfolioDir
npm run build
Pop-Location

Write-Host "Re-creating static directory at $staticDir..." -ForegroundColor Cyan
if (Test-Path $staticDir) {
    Remove-Item -Recurse -Force $staticDir
}
New-Item -ItemType Directory -Path $staticDir -Force

Write-Host "Copying build output from $portfolioDir\dist to $staticDir..." -ForegroundColor Cyan
Copy-Item -Path "$portfolioDir\dist\*" -Destination $staticDir -Recurse -Force

Write-Host "Vite frontend built and deployed to static/ successfully!" -ForegroundColor Green
