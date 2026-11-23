# DevOps: one repository, several teams

The project is a **monorepo**: every release, every service, the web client and the
pipelines live in one Git repository. Checkpoint 08 is built so that separate teams
could own its parts without slowing each other down. This page explains how the
repository, the reviews, the pipelines and the images are organised for that.

A monorepo fits this project: one pull request can change an API and the client
that uses it in the same commit, every release can be compared side by side, and
there is one place to look. The alternative, one repository per service, gives each
team full autonomy but turns every change across services into several pull
requests and lets versions drift apart.

## Teams and what they own

| Team | Owns in checkpoint 08 | Pipeline that tests it |
| --- | --- | --- |
| Apartment team | `microservices/dimora/apartment/`, its tests, the producer side of the contract | `Checkpoint 08 · apartment service` |
| Reservation team | `microservices/dimora/reservation/`, its tests, the consumer side of the contract | `Checkpoint 08 · reservation service` |
| Platform team | `dimora/common/`, `dimora/tools/`, the gateway, Compose, Dockerfile, system tests | `Checkpoint 08 · system` |
| Frontend team | `website-studio/` (Dimora), `dimora/cli/` | `Checkpoint 08 · system` (end-to-end suite) |
| Domain team | `apartment_booking/`: the shared validation rules | both service pipelines |
| DevOps team | `.github/`, `.gitlab-ci.yml`, `ci/`, `run.py` | every pipeline |
| Tech leads | everything else, including the frozen releases 01–07 and the docs | — |

The event contract (`microservices/contracts/`) belongs to both the apartment and
the reservation team: changing it needs both to agree.

## Reviews: CODEOWNERS and branch protection

[`.github/CODEOWNERS`](../.github/CODEOWNERS) maps every folder to its owner.
GitHub reads it top to bottom and the **last matching line wins**, so the catch-all
`*` comes first and the most specific paths last.

The file only takes effect together with branch protection on `main`
(Settings → Branches → `main`):

1. **Require a pull request before merging.**
2. **Require review from Code Owners.**
3. **Require status checks to pass:** the pipelines below.

GitHub then requests a review from the owners of every area a pull request touches,
and keeps the merge button locked until each of them approves:

- A change inside `dimora/apartment/` needs the apartment team only.
- A change to an event in `contracts/` needs both service teams.
- A change that adds an API field and uses it in Dimora needs the service team and
  the frontend team, and lands in one commit, so the API and its client never
  disagree.
- A change to `.github/` or `compose.yaml` needs the DevOps or platform team.

The repository belongs to a personal account, where GitHub teams do not exist, so
every line currently names `@SebastianoDruda` and the intended team as a comment.
In an organisation, each owner becomes a team such as `@dimora/apartment-team`.

## Pipelines

Every pipeline watches only the paths it tests, so a change runs the checks that
matter for it and nothing else.

| Release | GitHub Actions workflow | Runs when … changes |
| --- | --- | --- |
| 01–05 | `Checkpoints 01–05` | any of the five folders: tests and Docker smoke tests of each |
| 06 | `Checkpoint 06 · Tests`, `· Code coverage`, `· API load test`, `· Website`, `· Playwright` | `releases/checkpoint-06-dimora-web/` |
| 07 | `Checkpoint 07 · CQRS microservices` | `releases/checkpoint-07-cqrs-microservices/` |
| 08 | `Checkpoint 08 · apartment service` | the apartment service, shared code, contract or domain package |
| 08 | `Checkpoint 08 · reservation service` | the reservation service, shared code, contract or domain package |
| 08 | `Checkpoint 08 · system` | anything in `releases/checkpoint-08-microservices/` |

The two service workflows call one reusable workflow
(`checkpoint-08-service.yml`) with the service's name. It runs that service's unit
tests, the shared code's tests, the service's side of the event contract, lint, and
builds the service's own image. The system workflow runs every test inside the
image, the whole Docker stack with its failure scenarios, and the Dimora end-to-end
suite through the gateway. The stress test runs on demand: Actions →
`Checkpoint 08 · system` → Run workflow → *stress*.

GitLab runs the same idea on the self-managed runner (see the repository README):
`checkpoint-08:apartment-service` and `checkpoint-08:reservation-service` run only
when their paths change, and `checkpoint-08:all-tests` always checks the whole
release.

## Images and deployment

Each service of checkpoint 08 has its own image, built from its own Dockerfile
target and holding only its package plus the shared code:

| Image | Target | Contains |
| --- | --- | --- |
| `dimora-microservices-apartment` | `apartment-service` | `dimora/common`, `dimora/apartment`, `apartment_booking` |
| `dimora-microservices-reservation` | `reservation-service` | `dimora/common`, `dimora/reservation`, `apartment_booking` |
| `dimora-microservices-gateway` | gateway Dockerfile | nginx configuration and the Dimora client |
| `dimora-microservices-tools` | `tools` | everything: CLI, importer, republish |

A team can therefore ship a new version of its service without rebuilding the
other one. Running two replicas of a service (`--scale`) lets it restart, or roll
out a new image, without a failed request: the gateway moves traffic to the other
replica while the stopping one finishes its requests.

## Changing a shared contract

The services never call each other or share a database; the event contract is the
only coupling between the apartment and reservation teams:

1. Add fields only; never rename or remove one, or change its type.
2. Update the example in `contracts/events/` in the same pull request as the
   producer. Both teams review it, and both teams' contract tests run.
3. A change that cannot be additive becomes a new event type (for example
   `apartment.added.v2`), published next to the old one until the consumer has moved.
