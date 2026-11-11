#!/usr/bin/env bash
# Check that the dedicated runner container is running, unprivileged and accepted by GitLab.
set -euo pipefail

RUNNER_NAME="${RUNNER_NAME:-sebastiano-mac-docker-arm64}"
RUNNER_CONTAINER="${RUNNER_CONTAINER:-gitlab-runner}"
RUNNER_CONFIG_DIR="${RUNNER_CONFIG_DIR:-$HOME/.gitlab-runner}"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

docker info >/dev/null 2>&1 || fail "Docker Engine is unavailable. Start Docker Desktop."
runner_config="$RUNNER_CONFIG_DIR/config.toml"
[[ -f "$runner_config" ]] || fail "Runner configuration not found at $runner_config."
grep -Fq "name = \"$RUNNER_NAME\"" "$runner_config" || fail "Runner $RUNNER_NAME is not registered."
grep -Fq 'executor = "docker"' "$runner_config" || fail "The runner does not use the Docker executor."
if grep -Fq 'privileged = true' "$runner_config"; then
  fail "Privileged job containers must remain disabled."
fi

[[ "$(docker inspect --format '{{.State.Running}}' "$RUNNER_CONTAINER" 2>/dev/null || true)" == "true" ]] \
  || fail "Runner container $RUNNER_CONTAINER is not running. Start it with ci/gitlab/setup-runner.sh."
[[ "$(docker inspect --format '{{.HostConfig.Privileged}}' "$RUNNER_CONTAINER")" == "false" ]] \
  || fail "The runner container must not be privileged."

docker exec "$RUNNER_CONTAINER" gitlab-runner verify --name "$RUNNER_NAME"
printf 'Runner verified: %s is running in container %s with an unprivileged Docker executor.\n' \
  "$RUNNER_NAME" "$RUNNER_CONTAINER"
