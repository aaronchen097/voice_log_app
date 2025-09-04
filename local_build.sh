#!/bin/bash
set -e

# Default version
VERSION="latest"

# Check if a version is provided
if [ -n "$1" ]; then
  VERSION=$1
fi

IMAGE_NAME="voice-log-app"
TAR_NAME="${IMAGE_NAME}-${VERSION}.tar"

echo "Building Docker image ${IMAGE_NAME}:${VERSION}..."
docker build -t ${IMAGE_NAME}:${VERSION} .

echo "Saving image to ${TAR_NAME}..."
docker save -o ${TAR_NAME} ${IMAGE_NAME}:${VERSION}

echo "Build and packaging complete."
echo "To deploy, transfer ${TAR_NAME} to your server and run the deployment script."