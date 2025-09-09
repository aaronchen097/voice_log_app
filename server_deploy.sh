#!/bin/bash
# Voice Log App Deployment Script
# Usage: ./server_deploy.sh <tar-file> [--skip-health-check]

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="voice-log-app"
CONTAINER_NAME="voice-log-app"
HEALTH_CHECK_PORT="31130"
HEALTH_CHECK_TIMEOUT=60
SKIP_HEALTH_CHECK=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-health-check)
      SKIP_HEALTH_CHECK=true
      shift
      ;;
    -*)
      echo -e "${RED}Unknown option $1${NC}"
      exit 1
      ;;
    *)
      TAR_FILE="$1"
      shift
      ;;
  esac
done

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    if ! docker version >/dev/null 2>&1; then
        print_error "Docker is not running or not accessible"
        exit 1
    fi
}

# Function to check if docker-compose.yml exists
check_compose_file() {
    if [ ! -f "docker-compose.yml" ]; then
        print_error "docker-compose.yml not found in current directory"
        exit 1
    fi
}

# Function to wait for service health
wait_for_health() {
    local timeout=$1
    local port=$2
    local count=0
    
    print_status "Waiting for service to be healthy on port $port..."
    
    while [ $count -lt $timeout ]; do
        if curl -f -s "http://localhost:$port/health" >/dev/null 2>&1 || \
           curl -f -s "http://localhost:$port/" >/dev/null 2>&1; then
            print_success "Service is responding on port $port"
            return 0
        fi
        
        sleep 2
        count=$((count + 2))
        echo -n "."
    done
    
    echo
    print_warning "Service health check timed out after ${timeout}s"
    return 1
}

# Function to backup current deployment
backup_current() {
    if docker ps -q -f name=$CONTAINER_NAME >/dev/null 2>&1; then
        print_status "Creating backup of current deployment..."
        local backup_name="${IMAGE_NAME}-backup-$(date +%Y%m%d-%H%M%S)"
        docker commit $CONTAINER_NAME $backup_name || true
        print_success "Backup created: $backup_name"
    fi
}

# Function to rollback deployment
rollback_deployment() {
    print_error "Deployment failed, attempting rollback..."
    
    # Stop current containers
    docker compose down --remove-orphans || true
    
    # Find latest backup
    local backup_image=$(docker images --format "table {{.Repository}}:{{.Tag}}" | grep "${IMAGE_NAME}-backup" | head -n1)
    
    if [ -n "$backup_image" ]; then
        print_status "Rolling back to: $backup_image"
        docker tag "$backup_image" "${IMAGE_NAME}:latest"
        docker compose up -d
        print_warning "Rollback completed"
    else
        print_error "No backup found for rollback"
    fi
}

# Main deployment function
main() {
    echo -e "${GREEN}=== Voice Log App Deployment Script ===${NC}"
    echo -e "${BLUE}Timestamp: $(date)${NC}"
    echo -e "${BLUE}TAR File: ${TAR_FILE}${NC}"
    echo
    
    # Validation
    if [ -z "$TAR_FILE" ]; then
        print_error "Usage: $0 <tar-file> [--skip-health-check]"
        exit 1
    fi
    
    if [ ! -f "$TAR_FILE" ]; then
        print_error "TAR file not found: $TAR_FILE"
        exit 1
    fi
    
    # Pre-deployment checks
    check_docker
    check_compose_file
    
    # Create backup
    backup_current
    
    # Load new image
    print_status "Loading Docker image from ${TAR_FILE}..."
    if ! docker load -i "${TAR_FILE}"; then
        print_error "Failed to load Docker image"
        exit 1
    fi
    
    # Extract version from tar file name
    VERSION=$(echo "${TAR_FILE}" | sed -E "s/.*${IMAGE_NAME}-(.*)\.tar$/\1/")
    if [ "$VERSION" = "$TAR_FILE" ]; then
        VERSION="latest"
        print_warning "Could not extract version from filename, using 'latest'"
    fi
    
    print_success "Loaded image version: $VERSION"
    
    # Tag the loaded image as latest
    docker tag "${IMAGE_NAME}:${VERSION}" "${IMAGE_NAME}:latest"
    
    # Stop and remove old containers
    print_status "Stopping and removing old containers..."
    (docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME) || true
    docker compose down --remove-orphans
    
    # Start new containers
    print_status "Starting new containers..."
    if ! docker compose up -d; then
        rollback_deployment
        exit 1
    fi
    
    # Health check
    if [ "$SKIP_HEALTH_CHECK" = false ]; then
        if ! wait_for_health $HEALTH_CHECK_TIMEOUT $HEALTH_CHECK_PORT; then
            print_error "Health check failed"
            rollback_deployment
            exit 1
        fi
    fi
    
    # Final status
    echo
    print_success "=== Deployment Complete ==="
    print_status "Image: ${IMAGE_NAME}:${VERSION}"
    print_status "Container: $CONTAINER_NAME"
    print_status "Port: $HEALTH_CHECK_PORT"
    echo
    print_status "Useful commands:"
    echo "  docker ps                    # Check container status"
    echo "  docker compose logs -f       # View logs"
    echo "  docker compose down          # Stop services"
    echo "  curl http://localhost:$HEALTH_CHECK_PORT/  # Test service"
}

# Set trap for cleanup on script exit
trap 'if [ $? -ne 0 ]; then print_error "Deployment script failed"; fi' EXIT

# Run main function
main "$@"