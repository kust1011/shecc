#!/usr/bin/env bash

set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-shecc-dev:local}"
WORKSPACE="${PWD}"

docker build -f Dockerfile.dev -t "$IMAGE_NAME" .
docker run --rm \
    -v "$WORKSPACE":"$WORKSPACE" \
    -w "$WORKSPACE" \
    "$IMAGE_NAME" \
    bash -lc "make distclean && make config ARCH=arm && make && make check-stage0 && make check-stage2"
