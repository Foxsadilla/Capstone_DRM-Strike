#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$HOME/Documents/Capstone_DRM-Strike"

echo "> Navigating to docker directory and resetting containers..."
cd "$PROJECT_DIR/docker"
docker compose down -v
docker compose up -d --build

echo "> Initializing ACME issuer keys..."
cd "$PROJECT_DIR"
docker exec acme-issuer /opt/acme/bin/acme-issuer init-root
docker exec acme-issuer /opt/acme/bin/acme-issuer init-update-keys

echo "> Provisioning devices..."
./provision.sh trust
./provision.sh server    SERVER-1
./provision.sh console   CONSOLE-X1
./provision.sh cartridge CART-A1

echo "> Running Phase 0 validations..."
cd "$PROJECT_DIR/docker"
./phase0-validations.sh

echo "Finished!"

