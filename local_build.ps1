# PowerShell script for building and packaging the Docker image

# Default version
param (
    [string]$Version = "latest"
)

$imageName = "voice-log-app"
$tarName = "${imageName}-${Version}.tar"

Write-Host "Building Docker image ${imageName}:${Version}..."
docker build -t "${imageName}:${Version}" .

Write-Host "Saving image to ${tarName}..."
docker save -o $tarName "${imageName}:${Version}"

Write-Host "Build and packaging complete."
Write-Host "To deploy, transfer ${tarName} to your server and run the deployment script."