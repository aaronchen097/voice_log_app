#!/bin/bash
set -e

# Check if a tar file is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <tar-file>"
  exit 1
fi

TAR_FILE=$1
IMAGE_NAME="voice-log-app"

echo "Loading Docker image from ${TAR_FILE}..."
docker load -i ${TAR_FILE}

# Extract version from tar file name (e.g., voice-log-app-v1.0.1.tar -> v1.0.1)
VERSION=$(echo "${TAR_FILE}" | sed -E "s/voice-log-app-(.*).tar/\1/")

# Tag the loaded image as latest
docker tag ${IMAGE_NAME}:${VERSION} ${IMAGE_NAME}:latest

echo "Stopping and removing old containers..."
# Forcefully stop and remove the container by its known name to ensure the port is free.
(docker stop voice-log-app && docker rm voice-log-app) || true

# Now, bring down the compose environment to clean up networks etc.
docker compose down --remove-orphans

echo "Starting new containers..."
docker compose up -d

echo "Deployment complete."
echo "Run 'docker ps' to check the container status."
echo "Run 'docker compose logs -f' to view logs."