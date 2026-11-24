#!/usr/bin/env bash
# ==============================================================================
# run_network_lander_docker.sh
#
# Interactive or parameterized script to build and run network-specific landers
# inside Docker on Linux servers.
#
# Usage:
#   ./run_network_lander_docker.sh             (prompts interactively for network)
#   ./run_network_lander_docker.sh facebook    (runs facebook lander directly)
#   ./run_network_lander_docker.sh instagram   (runs instagram lander directly)
# ==============================================================================

set -e

# Available networks configured in config.yaml
AVAILABLE_NETWORKS=("facebook" "instagram" "youtube" "google" "gdn" "native" "linkedin" "reddit" "quora" "pinterest" "chatgpt")

# 1. Obtain network name
NETWORK_INPUT="$1"

if [ -z "$NETWORK_INPUT" ]; then
    echo "============================================================================"
    echo "                 POWERADSPY DOCKER LANDER LAUNCHER"
    echo "============================================================================"
    echo "Available networks:"
    echo "  1) facebook"
    echo "  2) instagram (or 'insta')"
    echo "  3) youtube   (or 'yt')"
    echo "  4) google"
    echo "  5) gdn"
    echo "  6) native"
    echo "  7) linkedin"
    echo "  8) reddit"
    echo "  9) quora"
    echo " 10) pinterest (or 'pin')"
    echo " 11) chatgpt"
    echo "============================================================================"
    read -rp "Enter the network name to run: " NETWORK_INPUT
fi

# Trim & lowercase
NETWORK=$(echo "$NETWORK_INPUT" | tr '[:upper:]' '[:lower:]' | xargs)

# Map common aliases
case "$NETWORK" in
    fb)    NETWORK="facebook" ;;
    insta) NETWORK="instagram" ;;
    yt)    NETWORK="youtube" ;;
    pin)   NETWORK="pinterest" ;;
esac

# Validate network exists in supported list
VALID=0
for net in "${AVAILABLE_NETWORKS[@]}"; do
    if [ "$net" = "$NETWORK" ]; then
        VALID=1
        break
    fi
done

if [ $VALID -eq 0 ]; then
    echo "[ERROR] Unknown network: '$NETWORK_INPUT'."
    echo "Supported networks are: ${AVAILABLE_NETWORKS[*]}"
    exit 1
fi

# Define exact image and container naming convention requested by user:
IMAGE_NAME="${NETWORK}_lander_image"
CONTAINER_NAME="${NETWORK}_lander_container"

echo ""
echo "============================================================================"
echo " Target Network   : $NETWORK"
echo " Docker Image     : $IMAGE_NAME"
echo " Docker Container : $CONTAINER_NAME"
echo "============================================================================"
echo ""

# Ensure .env exists for credentials
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "[WARNING] .env file not found. Creating a template from .env.example..."
        cp .env.example .env
        echo "[ACTION REQUIRED] Please edit .env with your BRIGHT_DATA_CUSTOMER and BRIGHT_DATA_PASSWORD before running."
    else
        echo "[WARNING] .env file not found in $(pwd)."
    fi
fi

# Ensure local directories exist for volume mounting
mkdir -p logs er_logs images zip getApi_data

# 2. Build Docker Image
echo ">>> Building Docker image: $IMAGE_NAME ..."
docker build -t "$IMAGE_NAME" .

# 3. Check and clean up existing container if already running or stopped
if [ "$(docker ps -aq -f name=^/${CONTAINER_NAME}$)" ]; then
    echo ">>> Stopping and removing existing container: $CONTAINER_NAME ..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
fi

# 4. Run Docker Container
echo ">>> Starting Docker container: $CONTAINER_NAME ..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  --shm-size=2g \
  --env-file .env \
  -e NETWORK="$NETWORK" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/er_logs:/app/er_logs" \
  -v "$(pwd)/images:/app/images" \
  "$IMAGE_NAME"

echo ""
echo "============================================================================"
echo " [SUCCESS] $CONTAINER_NAME is running in background!"
echo "============================================================================"
echo " Handy management commands:"
echo "   View live logs    : docker logs -f $CONTAINER_NAME"
echo "   Check status      : docker ps -f name=$CONTAINER_NAME"
echo "   Stop lander       : docker stop $CONTAINER_NAME"
echo "   Inspect container : docker exec -it $CONTAINER_NAME bash"
echo "============================================================================"
