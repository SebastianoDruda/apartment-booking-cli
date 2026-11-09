#!/usr/bin/env bash
# Provision the project-scoped GitLab Runner as a Docker container on Apple Silicon.
# Idempotent: an existing registration or runner container is reused, never duplicated.
set -euo pipefail

GITLAB_HOST="${GITLAB_HOST:-gitlab.inf.unibz.it}"
PROJECT_PATH="${PROJECT_PATH:-Sebastiano.Druda/gitlab-ci-docker-lab}"
RUNNER_NAME="${RUNNER_NAME:-sebastiano-mac-docker-arm64}"
RUNNER_CONTAINER="${RUNNER_CONTAINER:-gitlab-runner}"
RUNNER_IMAGE="${RUNNER_IMAGE:-gitlab/gitlab-runner:v19.5.3}"
RUNNER_CONFIG_DIR="${RUNNER_CONFIG_DIR:-$HOME/.gitlab-runner}"
# Fallback image for jobs without an image; .gitlab-ci.yml pins its own images.
DEFAULT_JOB_IMAGE="python:3.14-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
json_field() { python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"; }

command -v docker >/dev/null || fail "Docker is not installed."
command -v glab >/dev/null || fail "glab is not installed."
command -v python3 >/dev/null || fail "python3 is required to read GitLab API responses."
docker info >/dev/null 2>&1 || fail "Docker Engine is not available. Start Docker Desktop."
[[ "$(uname -m)" == "arm64" ]] || fail "This setup expects Apple Silicon (arm64)."
glab auth status --hostname "$GITLAB_HOST" >/dev/null 2>&1 \
  || fail "Authenticate glab for $GITLAB_HOST with a token that has the api scope."

project_json="$(glab api --hostname "$GITLAB_HOST" "projects/${PROJECT_PATH//\//%2F}")" \
  || fail "Project $PROJECT_PATH does not exist or is not accessible."
project_id="$(printf '%s' "$project_json" | json_field id)"

# Jobs must run only on this dedicated runner, never on instance-wide shared runners.
glab api --hostname "$GITLAB_HOST" --method PUT "projects/$project_id" \
  --field 'builds_access_level=enabled' \
  --field 'shared_runners_enabled=false' >/dev/null

mkdir -p "$RUNNER_CONFIG_DIR"
runner_config="$RUNNER_CONFIG_DIR/config.toml"
if grep -Fq "name = \"$RUNNER_NAME\"" "$runner_config" 2>/dev/null; then
  printf 'Runner %s is already registered; keeping its registration.\n' "$RUNNER_NAME"
else
  runner_json="$(glab api --hostname "$GITLAB_HOST" --method POST user/runners \
    --field 'runner_type=project_type' \
    --field "project_id=$project_id" \
    --field "description=$RUNNER_NAME" \
    --field 'tag_list=["local","docker","arm64"]' \
    --field 'run_untagged=false' \
    --field 'locked=true' \
    --field 'maximum_timeout=1800')"
  # The token is passed through the environment so that it never appears in argv.
  CI_SERVER_TOKEN="$(printf '%s' "$runner_json" | json_field token)" \
    docker run --rm --env CI_SERVER_TOKEN \
    --volume "$RUNNER_CONFIG_DIR:/etc/gitlab-runner" \
    "$RUNNER_IMAGE" register --non-interactive \
    --url "https://$GITLAB_HOST" \
    --name "$RUNNER_NAME" \
    --executor docker \
    --docker-image "$DEFAULT_JOB_IMAGE" \
    --docker-privileged=false \
    --docker-cpus 2 \
    --docker-memory 2g \
    --docker-memory-swap 2g \
    --docker-pull-policy if-not-present \
    --limit 1 \
    --request-concurrency 1
fi
chmod 600 "$runner_config"

case "$(docker inspect --format '{{.State.Status}}' "$RUNNER_CONTAINER" 2>/dev/null || true)" in
  running)
    printf 'Runner container %s is already running.\n' "$RUNNER_CONTAINER"
    ;;
  "")
    docker run --detach --name "$RUNNER_CONTAINER" --restart unless-stopped \
      --volume "$RUNNER_CONFIG_DIR:/etc/gitlab-runner" \
      --volume /var/run/docker.sock:/var/run/docker.sock \
      "$RUNNER_IMAGE" >/dev/null
    printf 'Runner container %s started.\n' "$RUNNER_CONTAINER"
    ;;
  *)
    docker start "$RUNNER_CONTAINER" >/dev/null
    printf 'Runner container %s restarted.\n' "$RUNNER_CONTAINER"
    ;;
esac
# Restart the runner automatically with Docker Desktop; this does not interrupt it.
docker update --restart unless-stopped "$RUNNER_CONTAINER" >/dev/null

"$(dirname "$0")/verify-runner.sh"
