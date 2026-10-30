#!/usr/bin/env bash
# Build a pinned PRODUCTION image containing the whole stack + school_suite.
# Run from a checkout of https://github.com/frappe/frappe_docker (the Containerfile
# lives there). Versions are pinned to match the verified local pilot (v16).
#
#   cd frappe_docker
#   APPS_JSON=/path/to/school_suite/deploy/apps.json ./build.sh
#
# NOTE: school_suite must be reachable by the builder. Either push it to the
# git URL in apps.json, or bake it in as a private repo with a build secret.
set -euo pipefail

APPS_JSON="${APPS_JSON:-./apps.json}"
IMAGE_TAG="${IMAGE_TAG:-school-erp:v16}"

# Pins verified in the local pilot (frappe/bench:latest shipped these):
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-16}"
PYTHON_VERSION="${PYTHON_VERSION:-3.14.10}"
NODE_VERSION="${NODE_VERSION:-24.22.2}"

export APPS_JSON_BASE64="$(base64 < "$APPS_JSON" | tr -d '\n')"

docker build \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH="$FRAPPE_BRANCH" \
  --build-arg=PYTHON_VERSION="$PYTHON_VERSION" \
  --build-arg=NODE_VERSION="$NODE_VERSION" \
  --build-arg=APPS_JSON_BASE64="$APPS_JSON_BASE64" \
  --tag="$IMAGE_TAG" \
  --file=images/layered/Containerfile .

echo "Built $IMAGE_TAG"
echo "Smoke test:  docker run --rm $IMAGE_TAG bench version"
