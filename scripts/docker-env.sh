#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

IMAGE_NAME="${IMAGE_NAME:-shecc-dev:stable}"
CONTAINER_NAME="${CONTAINER_NAME:-shecc-dev}"
DEFAULT_TEST_CMD="make distclean && make config ARCH=arm && make && make check-stage0 && make check-stage2"

image_exists() {
    docker image inspect "$IMAGE_NAME" >/dev/null 2>&1
}

container_exists() {
    docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1
}

build_image() {
    docker build -f "$REPO_ROOT/Dockerfile.dev" -t "$IMAGE_NAME" "$REPO_ROOT"
}

create_container() {
    docker create \
        --name "$CONTAINER_NAME" \
        -v "$REPO_ROOT":"$REPO_ROOT" \
        -w "$REPO_ROOT" \
        "$IMAGE_NAME" \
        sleep infinity >/dev/null
}

ensure_image() {
    if ! image_exists; then
        build_image
    fi
}

ensure_container() {
    ensure_image

    if ! container_exists; then
        create_container
    fi

    local current_image
    current_image="$(docker inspect -f '{{.Config.Image}}' "$CONTAINER_NAME")"
    if [[ "$current_image" != "$IMAGE_NAME" ]]; then
        docker rm -f "$CONTAINER_NAME" >/dev/null
        create_container
    fi

    local running
    running="$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")"
    if [[ "$running" != "true" ]]; then
        docker start "$CONTAINER_NAME" >/dev/null
    fi
}

run_exec() {
    if [[ "$#" -eq 0 ]]; then
        echo "Missing command for exec." >&2
        exit 1
    fi
    ensure_container
    docker exec "$CONTAINER_NAME" bash -lc "$*"
}

run_shell() {
    ensure_container
    docker exec -it "$CONTAINER_NAME" bash
}

show_status() {
    echo "IMAGE_NAME=$IMAGE_NAME"
    if image_exists; then
        docker image inspect -f 'image={{.Id}} created={{.Created}}' "$IMAGE_NAME"
    else
        echo "image=missing"
    fi

    echo "CONTAINER_NAME=$CONTAINER_NAME"
    if container_exists; then
        docker inspect -f 'state={{.State.Status}} image={{.Config.Image}}' "$CONTAINER_NAME"
    else
        echo "container=missing"
    fi
}

rebuild() {
    build_image
    if container_exists; then
        docker rm -f "$CONTAINER_NAME" >/dev/null
    fi
    create_container
    docker start "$CONTAINER_NAME" >/dev/null
}

stop_container() {
    if container_exists; then
        local running
        running="$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")"
        if [[ "$running" == "true" ]]; then
            docker stop "$CONTAINER_NAME" >/dev/null
        fi
    fi
}

remove_container() {
    if container_exists; then
        docker rm -f "$CONTAINER_NAME" >/dev/null
    fi
}

usage() {
    cat <<'EOF'
Usage: scripts/docker-env.sh <command> [args...]

Commands:
  up                 Ensure stable image and reusable container exist and are running
  shell              Open interactive shell in the reusable container
  exec <cmd...>      Run command in the reusable container
  test               Run default shecc build + stage0/stage2 checks in container
  rebuild            Rebuild image and recreate container
  stop               Stop container (keep it for reuse)
  down               Remove container
  status             Show image/container status
EOF
}

COMMAND="${1:-}"
case "$COMMAND" in
    up)
        ensure_container
        show_status
        ;;
    shell)
        run_shell
        ;;
    exec)
        shift
        run_exec "$@"
        ;;
    test)
        run_exec "$DEFAULT_TEST_CMD"
        ;;
    rebuild)
        rebuild
        show_status
        ;;
    stop)
        stop_container
        show_status
        ;;
    down)
        remove_container
        show_status
        ;;
    status)
        show_status
        ;;
    *)
        usage
        exit 1
        ;;
esac
