#!/usr/bin/env bash
# Unregister only the dedicated runner and remove its container.
# The runner image, the configuration directory and the GitLab project are kept.
set -euo pipefail

RUNNER_NAME="${RUNNER_NAME:-sebastiano-mac-docker-arm64}"
RUNNER_CONTAINER="${RUNNER_CONTAINER:-gitlab-runner}"

if [[ "${UNINSTALL_CONFIRM:-}" != "yes" ]]; then
  printf 'Refusing to unregister. Re-run with UNINSTALL_CONFIRM=yes after reviewing the target.\n' >&2
  exit 1
fi

docker exec "$RUNNER_CONTAINER" gitlab-runner unregister --name "$RUNNER_NAME"
docker stop "$RUNNER_CONTAINER" >/dev/null
docker rm "$RUNNER_CONTAINER" >/dev/null
printf 'Runner %s unregistered and container %s removed.\n' "$RUNNER_NAME" "$RUNNER_CONTAINER"
