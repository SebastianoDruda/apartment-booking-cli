# Apartment Booking System

[![Checkpoints 01–05](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/checkpoints-01-05.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/checkpoints-01-05.yml)
[![Tests](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/tests.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/tests.yml)
[![Coverage](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/coverage.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/coverage.yml)
[![Load test](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/load-test.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/load-test.yml)
[![Website](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/website.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/website.yml)
[![Playwright](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/playwright.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/playwright.yml)
[![Checkpoint 07](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/microservices.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/microservices.yml)
[![Checkpoint 08](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/checkpoint-08-system.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/checkpoint-08-system.yml)

Apartment Booking is a compact, fully tested booking system built step by step for
the course *Continuous Integration and Delivery*. Guests search, book, change and
cancel stays; hosts publish, reprice and remove apartments. The same domain rules
run behind a terminal client, a Flask REST API, the Dimora web client and, in the
last two releases, a set of microservices connected through RabbitMQ.

Every release of the project lives in its own folder under [`releases/`](releases/)
and runs on its own, with its own code, tests, Docker files and documentation. Any
of them can be started, tested or shown exactly as it was delivered.

## Releases

| | Folder | What it adds | Runs as |
| --- | --- | --- | --- |
| 01 | [`checkpoint-01-terminal-app`](releases/checkpoint-01-terminal-app/README.md) | Terminal booking application with SQLite persistence | `cli` |
| 02 | [`checkpoint-02-docker-compose`](releases/checkpoint-02-docker-compose/README.md) | Docker Compose, persistent storage and reliability fixes | `cli`, `docker` |
| 03 | [`checkpoint-03-rest-api`](releases/checkpoint-03-rest-api/README.md) | Flask REST API, OpenAPI contract and API explorer | `cli`, `api`, `docker` |
| 04 | [`checkpoint-04-github-actions`](releases/checkpoint-04-github-actions/README.md) | GitHub Actions: tests on three systems, coverage, Locust load test | `cli`, `api`, `docker` |
| 05 | [`checkpoint-05-gitlab-ci`](releases/checkpoint-05-gitlab-ci/README.md) | GitLab CI on a self-managed runner | `cli`, `api`, `docker` |
| 06 | [`checkpoint-06-dimora-web`](releases/checkpoint-06-dimora-web/README.md) | Dimora, a multilingual web client for guests and hosts; Playwright tests | `cli`, `api`, `web`, `docker` |
| 07 | [`checkpoint-07-cqrs-microservices`](releases/checkpoint-07-cqrs-microservices/README.md) | Event-driven CQRS microservices: RabbitMQ, PostgreSQL, MongoDB, nginx (9 containers) | `stack`, `cli` |
| 08 | [`checkpoint-08-microservices`](releases/checkpoint-08-microservices/README.md) | Microservices without a read model, one pipeline per team, restarts without errors (6 containers) | `stack`, `cli` |

Checkpoints 01–05 are kept exactly as they were tagged. Checkpoint 06 includes the
fixes made to the monolith after its tag (the Playwright suite and full CLI parity
of the web client). Every release also has a `test` mode.

## Running a release

[`run.py`](run.py) starts any release in any of the ways it supports. It only needs
Python 3.10 or newer; it changes into the release folder and runs the command its
README gives.

```bash
python3 run.py                     # list every release and its modes
python3 run.py 01 cli              # the original terminal application
python3 run.py 06 web              # REST API + Dimora on http://127.0.0.1:8080
python3 run.py 07 stack            # the CQRS stack in Docker, on http://127.0.0.1:8080
python3 run.py 08 stack --replicas 2
python3 run.py 08 down
python3 run.py 03 test             # the test suite of checkpoint 03
```

| Mode | Needs |
| --- | --- |
| `cli`, `test` of 01–02 | Python only |
| `api`, `web`, `test` of 03–06 | Flask: `pip install -r releases/checkpoint-06-dimora-web/requirements/web.txt` |
| `docker`, `stack`, `smoke` | Docker Desktop, or Docker Engine with Compose v2 |
| `test`, `contract` of 07–08 | the services' packages: `pip install -r releases/checkpoint-08-microservices/microservices/requirements.txt` |

Each release keeps its own data: the local SQLite file in its folder, or its own
Docker volumes. Releases 06, 07 and 08 all use port 8080, so run one of them at a
time, or pass `--port` to `stack`. Every command can also be run by hand from the
release folder, as its README describes.

## Repository layout

```text
apartment-booking-cli/
├── releases/                       # one folder per release, each runnable on its own
│   ├── checkpoint-01-terminal-app/
│   ├── …
│   └── checkpoint-08-microservices/
├── docs/
│   └── devops.md                   # teams, CODEOWNERS, pipelines and images
├── ci/gitlab/                      # GitLab pipeline summary (runner scripts stay local)
├── .github/
│   ├── CODEOWNERS                  # who reviews which folder
│   └── workflows/                  # one or more GitHub Actions workflows per release
├── .gitlab-ci.yml                  # GitLab pipeline for every release
└── run.py                          # launcher: python3 run.py <release> <mode>
```

Only files that tools require at the root stay there: the pipelines (GitHub and
GitLab read them from fixed locations), `CODEOWNERS`, this README and the launcher.

## Continuous integration

Every workflow watches only the folder of its release, so a change runs only the
checks it can affect.

| Workflow | Release | What it checks |
| --- | --- | --- |
| `Checkpoints 01–05` | 01–05 | each release's own tests; Docker images and smoke tests from 02 on |
| `Checkpoint 06 · Tests` | 06 | Python 3.10 and 3.14 on Linux, macOS and Windows; Docker CLI and HTTP smoke tests |
| `Checkpoint 06 · Code coverage` | 06 | at least 85 % branch coverage |
| `Checkpoint 06 · API load test` | 06 | Locust booking journey: ≤ 1 % errors, ≤ 500 ms average, ≤ 1,000 ms p95 |
| `Checkpoint 06 · Website` | 06 | the web client's modules, JavaScript and dev-server tests |
| `Checkpoint 06 · Playwright` | 06 | guest and host journeys in Chromium, desktop and mobile |
| `Checkpoint 07 · CQRS microservices` | 07 | unit tests, the Docker stack with failure scenarios, Playwright through the gateway |
| `Checkpoint 08 · apartment service` | 08 | the apartment team's tests, contract side, lint and image |
| `Checkpoint 08 · reservation service` | 08 | the reservation team's tests, contract side, lint and image |
| `Checkpoint 08 · system` | 08 | every test in the image, the stack with failure scenarios, Playwright; stress test on demand |

### GitLab CI and the self-managed runner

The project is also hosted in the private university GitLab project
[`gitlab-ci-docker-lab`](https://gitlab.inf.unibz.it/Sebastiano.Druda/gitlab-ci-docker-lab).
GitHub remains the primary repository; GitLab receives the same commits by merging
GitHub `main`, so both contain identical files. The pipeline in `.gitlab-ci.yml`
runs only on a dedicated, project-scoped runner, because shared runners are disabled
for the project.

```text
GitLab project -> tagged job -> GitLab Runner container -> Docker Desktop
                                                       -> isolated ARM64 job container
```

The runner runs in the `gitlab-runner` Docker container on an Apple Silicon Mac and
uses the Docker executor. It accepts only jobs tagged `local`, `docker` and `arm64`,
processes one job at a time and limits each job container to 2 CPUs and 2 GB of
memory. It never uses privileged mode or Docker-in-Docker, and job images are pinned
by digest.

| Stage | Job | Purpose |
| --- | --- | --- |
| validate | `lint` | Ruff correctness rules (04–08) and bytecode compilation of every release |
| test | `checkpoints-01-05` | each of the first five releases' own tests |
| test | `unit-tests:python3.10`, `unit-tests:python3.14` | checkpoint 06; branch coverage, Cobertura and HTML reports on 3.14 |
| test | `checkpoint-07-unit-tests` | unit tests of the CQRS edition |
| test | `checkpoint-08:apartment-service`, `checkpoint-08:reservation-service` | one job per team, run only when its paths change |
| test | `checkpoint-08:all-tests` | every unit and contract test of checkpoint 08 |
| performance | `load-test` | Locust booking journey against checkpoint 06 inside the job |
| report | `pipeline-summary` | Markdown summary of tests, coverage and load results |

Because job containers are unprivileged, GitLab does not build Docker images; the
Docker builds and Compose stacks run on GitHub Actions.

The runner is managed with local scripts in `ci/gitlab/`, which are git-ignored and
not part of the repository. They require Docker Desktop and `glab` authenticated
against `gitlab.inf.unibz.it` with the `api` scope. Credentials stay in the macOS
Keychain and in `~/.gitlab-runner/config.toml`, never in the repository.

```bash
./ci/gitlab/setup-runner.sh                         # register if needed, start the container
./ci/gitlab/verify-runner.sh                        # check container, executor and registration
UNINSTALL_CONFIRM=yes ./ci/gitlab/remove-runner.sh  # unregister and remove the container
```

If jobs remain pending, start Docker Desktop and run `./ci/gitlab/verify-runner.sh`;
`docker logs --tail 100 gitlab-runner` shows the runner log.

## Teams and ownership

Checkpoint 08 is organised so that separate teams could own its parts inside this
one repository: an apartment team, a reservation team, a platform team, a frontend
team and a domain team, each with its own folders, tests, image and pipeline, and
an event contract that both service teams review.
[`.github/CODEOWNERS`](.github/CODEOWNERS) maps every folder to its owner, and with
branch protection a pull request needs an approval from the owner of every area it
touches. The whole model is described in [docs/devops.md](docs/devops.md).

## Release history

| Release | Focus |
| --- | --- |
| [Checkpoint 08](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-08) | Microservices without a read model, one folder per release, team pipelines and CODEOWNERS |
| [Checkpoint 07](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-07) | Event-driven edition: CQRS microservices, RabbitMQ, nginx gateway |
| [Checkpoint 06](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-06) | Dimora web client for guests and hosts in Italian, English and German |
| [Checkpoint 05](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-05) | GitLab CI with a self-managed Docker executor runner |
| [Checkpoint 04](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-04) | GitHub Actions pipeline with coverage and Locust load testing |
| [Checkpoint 03](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-03) | Flask REST API, OpenAPI contract and interactive API documentation |
| [Checkpoint 02](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-02) | Docker Compose, persistent storage and reliability fixes |
| [Checkpoint 01](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-01) | Terminal booking application with SQLite persistence |

## Authors and licensing

Created by **Sebastiano Druda, Tom Springer and Jacob Wieser**. No license file is
currently included; contact the authors before reuse or redistribution.
