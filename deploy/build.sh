#!/usr/bin/env bash
# Build the PRODUCTION image (whole stack + school_suite) by hand. CI does the same
# on every push to main (.github/workflows/ci.yml, job "image"), after the tests pass.
# Run from a checkout of https://github.com/frappe/frappe_docker at FRAPPE_DOCKER_REF
# (deploy/versions.env); the Containerfile lives there.
#
# Uses images/custom/Containerfile: it builds from python:<PYTHON_VERSION> and uses
# FRAPPE_BRANCH only for the Frappe source, so a release tag works (the layered one
# also uses it as the frappe/build base-image tag, which isn't published per release).
# apps.json goes in as a BuildKit secret; the Containerfile ignores a build-arg.
#
#   cd frappe_docker && git checkout <FRAPPE_DOCKER_REF>
#   /path/to/school_suite/deploy/build.sh
#
# Every build is tagged twice: <name>:v16 (moves to the newest build) and
# <name>:v16-<school_suite commit> (never moves, so you can roll back to it).
# school_suite is fetched from the git URL in apps.json, so push first.
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=versions.env
source "$SELF_DIR/versions.env"

APPS_JSON="${APPS_JSON:-$SELF_DIR/apps.json}"
IMAGE_NAME="${IMAGE_NAME:-school-erp}"
SHA="$(git -C "$SELF_DIR" rev-parse --short HEAD)"

if [ "$(git rev-parse HEAD 2>/dev/null)" != "$FRAPPE_DOCKER_REF" ]; then
  echo "WARNING: this frappe_docker checkout is not at FRAPPE_DOCKER_REF ($FRAPPE_DOCKER_REF)." >&2
fi

DOCKER_BUILDKIT=1 docker build \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH="$FRAPPE_BRANCH" \
  --build-arg=PYTHON_VERSION="$PYTHON_VERSION" \
  --build-arg=NODE_VERSION="$NODE_VERSION" \
  --secret=id=apps_json,src="$APPS_JSON" \
  --tag="$IMAGE_NAME:v16" \
  --tag="$IMAGE_NAME:v16-$SHA" \
  --file=images/custom/Containerfile .

echo "Built $IMAGE_NAME:v16 and $IMAGE_NAME:v16-$SHA"
echo "Smoke test:  docker run --rm $IMAGE_NAME:v16-$SHA bench version"
