# Apartment Booking System

[![Tests](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/tests.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/tests.yml)
[![Coverage](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/coverage.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/coverage.yml)
[![Load test](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/load-test.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/load-test.yml)

Apartment Booking is a compact, fully tested Python application developed to
demonstrate how one domain model can support different delivery interfaces without
duplicating business logic. Users can work through an interactive terminal client
or through a Flask REST API with a local browser-based request explorer.

Both interfaces delegate to the same application and persistence layer. Calendar
validation, apartment capacity, price handling, booking overlap detection and
transaction safety therefore behave consistently whether a request originates from
the CLI or HTTP. SQLite provides lightweight local persistence, while Docker Compose
offers a reproducible runtime with shared storage.

## Features

- Apartment catalogue management with capacity and nightly pricing.
- Booking creation, modification, cancellation and availability search.
- Calendar, capacity and overlap validation shared by the CLI and REST API.
- Persistent SQLite storage with transactional writes and Docker volumes.
- Interactive terminal completion and browser-based API exploration.
- Automated unit, integration, Docker, coverage and Locust load tests.
- Continuous integration on GitHub Actions and on a self-managed GitLab runner.

## Getting started

The recommended way to run the project is with Docker. It avoids local dependency
setup and creates a persistent volume shared by the CLI and web service. From the
repository root, build and start the API in the background:

```bash
docker compose up --build --detach --wait web
```

When the health check is ready, the following local endpoints are available:

- http://localhost:8000/docs — API explorer;
- http://localhost:8000/api/health — readiness check;
- http://localhost:8000/api/openapi.json — OpenAPI 3.1 contract.

The API explorer at `/docs` is the main entry point for inspecting and exercising
the HTTP interface. To use the terminal workflow against the same database, open a
second terminal and run:

```bash
docker compose run --rm booking
```

When finished, stop the web process without deleting stored bookings:

```bash
docker compose stop web
```

Both services use the `booking-data` Docker volume. The HTTP port is intentionally
published only on `127.0.0.1`; because this educational API has no authentication,
it should not be exposed to a public network. If port 8000 is already in use, set
`BOOKING_WEB_PORT` to another host port, for example
`BOOKING_WEB_PORT=8080 docker compose up --build --detach --wait web`.

## Using the application

### Command-line interface

The CLI begins with a role selection. An **Apartment Booker** can inspect and search
apartments, create bookings, review existing reservations, change dates or party
size, and cancel bookings. A **System Manager** maintains the apartment catalogue by
adding properties, changing nightly prices and removing apartments, while retaining
visibility over bookings.

Commands follow a consistent `resource action` format, such as `apartment search`,
`booking create` or `apartment update`. Enter `help` for role-specific guidance,
`role` to switch responsibility and `exit` to close the application.

| Role | Main commands |
| --- | --- |
| System Manager | `apartment add`, `apartment update`, `apartment remove`, `apartment view`, `booking view` |
| Apartment Booker | `apartment search`, `apartment view`, `booking create`, `booking change`, `booking cancel`, `booking view` |
| Both | `help`, `role`, `exit` |

Dates accept `YYYY-MM-DD`, `YYYY/MM/DD`, `DD/MM/YYYY` and `DD.MM.YYYY`.
Apartment names are matched case-insensitively.
Check-out must follow check-in, the selected apartment must fit the party, and two
bookings for the same apartment may not overlap.

### REST API

The HTTP interface models apartments and bookings as resources. `GET` and `POST`
requests to `/api/apartments` list and create apartments, while the resource-specific
price and delete routes update or remove a named apartment. The `/api/bookings`
collection supports listing and creation; `PATCH` changes an identified booking and
`DELETE` cancels it. Availability searches are expressed as query parameters on
`/api/availability`.

Operational endpoints are deliberately separate from business operations:
`/api/health` checks both the server and database, `/api/openapi.json` publishes the
OpenAPI 3.1 contract, and `/docs` renders the interactive explorer. The explorer
loads its examples directly from the contract, so the documentation and executable
requests remain aligned.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET`, `POST` | `/api/apartments` | List or create apartments |
| `PATCH` | `/api/apartments/<name>/price` | Update the nightly price |
| `DELETE` | `/api/apartments/<name>` | Remove an apartment and its bookings |
| `GET`, `POST` | `/api/bookings` | List or create bookings |
| `PATCH`, `DELETE` | `/api/bookings` | Change or cancel a booking |
| `GET` | `/api/availability` | Search by dates and party size |
| `GET` | `/api/health` | Check application and database readiness |

Successful responses use a `{"data": ...}` envelope. Validation, missing records
and conflicts return structured errors as
`{"error": {"code": "...", "message": "..."}}` with the appropriate HTTP status.

## Design and architecture

```text
HTTP client -> Flask routes --------+
                                   +-> BookingDatabase -> SQLite
Terminal ----> ApartmentBookingCLI -+
```

The application follows a simple layered design. `apartment_booking.database` is the
domain and persistence boundary: it owns validation, SQLite access and transactional
mutations. `apartment_booking.cli` handles terminal input and presentation, while
the `apartment_booking.web` package translates HTTP requests and responses without
containing SQL or reimplementing booking rules. It also holds the OpenAPI contract
(`apartment_booking.web.api_docs`) and the templates and static assets of the
browser explorer.

Flask creates a database wrapper for each request, and SQLite connections are never
shared between HTTP threads. Write operations use `BEGIN IMMEDIATE`, ensuring that
availability checks and their corresponding changes occur inside one transaction.
This keeps concurrent booking attempts consistent and allows failures to roll back
without leaving partial state.

The domain relationships are summarized in the
[concept map](docs/domain-concept-map.png).

## Project layout

```text
apartment-booking-cli/
├── apartment_booking/          # Application package
│   ├── __main__.py             # `python -m apartment_booking`
│   ├── cli.py                  # Terminal interface
│   ├── database.py             # Domain rules and SQLite persistence
│   └── web/                    # HTTP interface
│       ├── app.py              # Flask application factory and routes
│       ├── api_docs.py         # OpenAPI contract
│       ├── templates/          # API explorer markup
│       └── static/             # API explorer CSS and JavaScript
├── tests/
│   ├── test_*.py               # Unit and integration tests
│   ├── smoke/                  # Disposable Docker checks
│   └── performance/            # Locust user journey
├── requirements/
│   ├── web.txt                 # Flask, for the HTTP interface
│   ├── ci.txt                  # Test, coverage and lint tooling
│   └── load.txt                # Locust, for load testing
├── docs/                       # Architecture assets
├── ci/gitlab/                  # GitLab runner scripts and pipeline summary
├── .github/workflows/          # Test, coverage and load-test pipelines
├── .gitlab-ci.yml              # GitLab pipeline
├── Dockerfile
├── compose.yaml
├── main.py                     # Small compatibility launcher
└── pyproject.toml              # Coverage, pytest and Ruff configuration
```

The layout keeps runtime code, automated checks, performance scenarios and
documentation assets clearly separated. Generated data, virtual environments,
caches, reports and local databases are ignored so the repository contains only
source, tests and reproducible automation.

## Local development

Docker is recommended for normal use, but the project can also run directly with
Python 3.10 or newer. Create an isolated environment and install the web dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/web.txt
python main.py
```

The root launcher is retained for convenience. The equivalent package entry point is:

```bash
python -m apartment_booking
```

Start the API directly:

```bash
python -m flask --app apartment_booking.web:create_app --no-debug run \
  --host 127.0.0.1 --port 8000 --no-debugger --no-reload
```

On Windows, use `py -3` instead of `python3`, activate the environment with
`.venv\Scripts\activate`, and enter the Flask command on one line.

Direct Python runs store data in the ignored `apartment_booking.db` file by default.
Set `APARTMENT_BOOKING_DB_PATH` to use another location.

## Quality assurance

The automated suite covers the domain model, CLI workflows, HTTP contract, storage
configuration, concurrency, rollback behaviour and error handling. After installing
the web dependency, run all 46 unit and integration tests with:

```bash
python -m pip install -r requirements/web.txt
python -m unittest discover -s tests -v
```

Coverage, pytest and Ruff read their settings from `pyproject.toml`, so local runs
match CI. To reproduce the coverage gate and the lint check:

```bash
python -m pip install -r requirements/web.txt -r requirements/ci.txt
python -m coverage run -m unittest discover -s tests
python -m coverage report
python -m ruff check .
```

Docker smoke tests then verify properties that unit tests cannot: non-root execution,
image contents, shared persistent storage, backup/import behaviour, HTTP readiness
and persistence across service restarts.

```bash
docker compose config --quiet
docker build --target test --tag apartment-booking-cli:test .
docker compose build
python tests/smoke/docker_cli.py
python tests/smoke/docker_web.py
```

These scripts create random Compose projects with disposable volumes, so they never
read or modify the normal `booking-data` volume.

Every push and pull request to `main` runs three independent GitHub Actions
workflows. The primary test pipeline executes the full suite on Python 3.10 and 3.14
across Linux, macOS and Windows, then validates both Docker interfaces, persistence
and service restarts. A separate coverage workflow enforces an 85% branch-coverage
minimum, while the performance workflow runs the booking journey under load and
publishes downloadable HTML and CSV reports.

### Performance testing

The Locust scenario models a complete customer journey rather than isolated health
requests. A simulated user browses apartments, searches availability, creates and
lists a booking, changes it and finally cancels it. Each user owns uniquely named
fixtures and removes them on exit, preventing cross-user conflicts and persistent
test pollution.

```bash
python -m pip install -r requirements/load.txt
python -m locust --locustfile tests/performance/locustfile.py \
  --host http://127.0.0.1:8000
```

Open http://localhost:8089 for the Locust UI. CI uses 10 users for 30 seconds and
fails above 1% errors, 500 ms average response time or 1,000 ms p95.

### GitLab CI and the self-managed runner

The project is also hosted in the private university GitLab project
[`gitlab-ci-docker-lab`](https://gitlab.inf.unibz.it/Sebastiano.Druda/gitlab-ci-docker-lab).
GitHub remains the primary repository; GitLab receives the same commits by merging
GitHub `main`, so both contain identical files. The GitLab pipeline is defined in
`.gitlab-ci.yml` and runs only on a dedicated, project-scoped runner, because shared
runners are disabled for the project.

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
| validate | `lint` | Ruff correctness rules and bytecode compilation |
| test | `unit-tests:python3.10`, `unit-tests:python3.14` | Full suite with JUnit reports; branch coverage, Cobertura and HTML reports on 3.14 |
| performance | `load-test` | Locust booking journey against a Flask server inside the job |
| report | `pipeline-summary` | Markdown summary of tests, coverage and load results |

Because job containers are unprivileged, GitLab does not build Docker images; the
Docker build and Compose smoke checks run in the GitHub workflow.

The scripts in `ci/gitlab/` manage the runner. They require Docker Desktop and
`glab` authenticated against `gitlab.inf.unibz.it` with the `api` scope. Credentials
stay in the macOS Keychain and in `~/.gitlab-runner/config.toml`, never in the
repository.

```bash
./ci/gitlab/setup-runner.sh                         # register if needed, start the container
./ci/gitlab/verify-runner.sh                        # check container, executor and registration
UNINSTALL_CONFIRM=yes ./ci/gitlab/remove-runner.sh  # unregister and remove the container
```

If jobs remain pending, start Docker Desktop and run `./ci/gitlab/verify-runner.sh`;
`docker logs --tail 100 gitlab-runner` shows the runner log.

## Persistence and backups

Direct Python execution uses an ignored `apartment_booking.db` file. Docker stores
the same schema in the named `booking-data` volume, shared by the CLI and API. Local
database files are deliberately excluded from version control.

Before replacing, exporting or importing data, stop all writers and create a backup:

```bash
docker compose stop web
docker compose create booking
docker compose cp booking:/data/apartment_booking.db ./booking-backup.db
```

The command `docker compose down --volumes` deletes the normal Docker database and
should only be used when a complete reset is intentional. Removing an apartment from
the application also removes its bookings through the configured cascade.

## Troubleshooting

- If Docker commands cannot reach the daemon, start Docker Desktop and wait for the
  engine before retrying.
- Run application, Compose and test commands from the repository root.
- If a command is unavailable, enter `role` and select the role that owns it.
- For booking failures, verify the calendar dates, capacity and existing overlaps.
- If SQLite is locked or read-only, close other writers and check database directory
  permissions before retrying.
- Terminal completion is optional and uses GNU readline, macOS editline or the
  Windows console; full commands always remain available.
- If the configured database file is not a valid SQLite database, the CLI stops
  with an error instead of changing it; restore the file from a backup.

## Project scope

This repository is an educational local application rather than a production
booking platform. It intentionally omits authentication, payments, customer booking
ownership, schema migrations and multi-node persistence. Prices use SQLite `REAL`,
displayed totals follow the apartment's current price, and dates have no time-zone
component. The API should therefore remain bound to localhost.

## Releases

| Release | Focus |
| --- | --- |
| [Checkpoint 05](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-05) | GitLab CI with a self-managed Docker executor runner |
| [Checkpoint 04](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-04) | GitHub Actions pipeline with coverage and Locust load testing |
| [Checkpoint 03](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-03) | Flask REST API, OpenAPI contract and interactive API documentation |
| [Checkpoint 02](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-02) | Docker Compose, persistent storage and reliability fixes |
| [Checkpoint 01](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-01) | Terminal booking application with SQLite persistence |

## Authors and licensing

Created by **Sebastiano Druda, Tom Springer and Jacob Wieser**. No license file is
currently included; contact the authors before reuse or redistribution.
