# Build the Vite frontend from the voidomin repo and copy it to AlignX/static

$portfolioDir = "C:\Users\ASUS\Documents\personal\voidomin\portfolio"
$staticDir = "C:\Users\ASUS\Documents\personal\AlignX\static"

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
