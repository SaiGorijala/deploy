#!/usr/bin/env bash
set -euo pipefail

# Usage:
# sudo ./deploy.sh [REPO_DIR] [GIT_URL]
# Examples:
# sudo ./deploy.sh /home/ubuntu/deploy
# sudo ./deploy.sh /opt/deploy https://github.com/SaiGorijala/deploy.git

REPO_DIR="${1:-/home/ubuntu/deploy}"
GIT_URL="${2:-}"

echo "Deploy script started. Target dir: ${REPO_DIR}"

# Ensure running as root (installing packages requires root)
if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run with sudo or as root. Exiting." >&2
  exit 1
fi

# Install Docker Engine and Docker Compose plugin if missing
if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker Engine and Compose plugin..."
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg lsb-release
  mkdir -p /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
else
  echo "Docker already installed"
fi

# Ensure git is available
if ! command -v git >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y git
fi

# Clone or update repository if a GIT_URL is provided
if [ -n "${GIT_URL}" ]; then
  if [ -d "${REPO_DIR}/.git" ]; then
    echo "Updating repository in ${REPO_DIR}"
    # If there are local changes, stash them to allow pull --rebase to succeed
    STASHED=0
    if [ -n "$(git -C "${REPO_DIR}" status --porcelain)" ]; then
      echo "Local changes detected in ${REPO_DIR}, stashing before pull..."
      git -C "${REPO_DIR}" stash push -u -m "autostash-$(date +%s)" >/dev/null && STASHED=1 || STASHED=0
    fi

    if ! git -C "${REPO_DIR}" pull --rebase; then
      echo "git pull --rebase failed. Attempting a normal pull..."
      git -C "${REPO_DIR}" pull || true
    fi

    # Try to pop the stash if we stashed earlier
    if [ "${STASHED}" -eq 1 ]; then
      echo "Restoring stashed changes..."
      if ! git -C "${REPO_DIR}" stash pop; then
        echo "Warning: stash pop reported conflicts or failed. Stash still available in the repo."
      fi
    fi
  else
    echo "Cloning ${GIT_URL} into ${REPO_DIR}"
    rm -rf "${REPO_DIR}"
    git clone "${GIT_URL}" "${REPO_DIR}"
  fi
fi

# Verify directory exists
if [ ! -d "${REPO_DIR}" ]; then
  echo "Directory ${REPO_DIR} does not exist. Exiting." >&2
  exit 1
fi

cd "${REPO_DIR}"

# Build and start containers
echo "Building and starting services (no-cache build for the api)..."
docker compose build --no-cache devops-api || docker compose build devops-api

docker compose up -d --remove-orphans

# Wait for the API health endpoint
echo "Waiting for API health endpoint..."
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "API is healthy"
    break
  fi
  echo "  waiting... ($i)"
  sleep 2
done

# Show status
echo "Docker containers status:"
docker compose ps

echo "Deploy finished. Check services with 'docker compose logs -f' or visit SonarQube at http://SERVER_IP:9000 and API at http://SERVER_IP:8000"
