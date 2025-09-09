# PowerShell script for building and packaging the Docker image
# Usage: .\local_build.ps1 [-Version <version>] [-Clean]

param (
    [string]$Version = "latest",
    [switch]$Clean = $false
)

$imageName = "voice-log-app"
$tarName = "${imageName}-${Version}.tar"

# Function to check if Docker is running
function Test-DockerRunning {
    try {
        docker version | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

# Function to clean up old images
function Remove-OldImages {
    Write-Host "Cleaning up old images..." -ForegroundColor Yellow
    try {
        # Remove dangling images
        $danglingImages = docker images -f "dangling=true" -q
        if ($danglingImages) {
            docker rmi $danglingImages
        }
        
        # Remove old versions of our image (keep latest and current version)
        $oldImages = docker images $imageName --format "table {{.Tag}}" | Where-Object { $_ -ne "TAG" -and $_ -ne "latest" -and $_ -ne $Version }
        foreach ($tag in $oldImages) {
            docker rmi "${imageName}:${tag}" -f
        }
    }
    catch {
        Write-Warning "Failed to clean up some old images: $_"
    }
}

# Main build process
Write-Host "=== Voice Log App Docker Build Script ===" -ForegroundColor Green
Write-Host "Version: $Version" -ForegroundColor Cyan
Write-Host "Clean: $Clean" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
if (-not (Test-DockerRunning)) {
    Write-Error "Docker is not running. Please start Docker and try again."
    exit 1
}

# Clean up if requested
if ($Clean) {
    Remove-OldImages
}

# Remove existing tar file if it exists
if (Test-Path $tarName) {
    Write-Host "Removing existing tar file: $tarName" -ForegroundColor Yellow
    Remove-Item $tarName -Force
}

Write-Host "Building Docker image ${imageName}:${Version}..." -ForegroundColor Green
try {
    docker build -t "${imageName}:${Version}" . --no-cache
    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed with exit code $LASTEXITCODE"
    }
}
catch {
    Write-Error "Failed to build Docker image: $_"
    exit 1
}

Write-Host "Saving image to ${tarName}..." -ForegroundColor Green
try {
    docker save -o $tarName "${imageName}:${Version}"
    if ($LASTEXITCODE -ne 0) {
        throw "Docker save failed with exit code $LASTEXITCODE"
    }
}
catch {
    Write-Error "Failed to save Docker image: $_"
    exit 1
}

# Get file size
$fileSize = (Get-Item $tarName).Length / 1MB

Write-Host "" -ForegroundColor Green
Write-Host "=== Build Complete ===" -ForegroundColor Green
Write-Host "Image: ${imageName}:${Version}" -ForegroundColor Cyan
Write-Host "Package: $tarName (${fileSize:F2} MB)" -ForegroundColor Cyan
Write-Host "" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Transfer $tarName to your server" -ForegroundColor White
Write-Host "2. Run: ./server_deploy.sh $tarName" -ForegroundColor White
Write-Host "3. Check deployment: docker ps" -ForegroundColor White