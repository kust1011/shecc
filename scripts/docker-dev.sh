#!/usr/bin/env bash

set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-shecc-dev:local}"
WORKSPACE="${PWD}"

docker build -f Dockerfile.dev -t "$IMAGE_NAME" .
docker run --rm -it \
    -v "$WORKSPACE":"$WORKSPACE" \
    -w "$WORKSPACE" \
    "$IMAGE_NAME" \
    bash
