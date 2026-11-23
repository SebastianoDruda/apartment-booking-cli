# Apartment Booking

> **Release snapshot.** This folder is [checkpoint 04](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-04)
> exactly as it was tagged, kept so that it can still be run and tested on its own.
> Run every command below from this folder, or `python3 run.py 04 <mode>` from the
> repository root (`cli`, `api`, `docker`, `docker-cli`, `test`). Paths in this README are relative to this folder;
> its CI files (`.github/`) are kept for reference, while the pipelines that test it now run from the repository root. All releases are listed in the [repository README](../../README.md).


[![Tests](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/tests.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/tests.yml)
[![Coverage](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/coverage.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/coverage.yml)
[![Load test](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/load-test.yml/badge.svg)](https://github.com/SebastianoDruda/apartment-booking-cli/actions/workflows/load-test.yml)

A small apartment booking system with two interfaces over one domain layer:

- an interactive terminal application;
- a Flask REST API with a browser-based request explorer.

Both use the same SQLite database and enforce the same calendar, capacity, price,
overlap and transaction rules.

## Quick start

Docker is the simplest option. Start the API:

```bash
docker compose up --build --detach --wait web
```

Open:

- http://localhost:8000/docs — API explorer;
- http://localhost:8000/api/health — readiness check;
- http://localhost:8000/api/openapi.json — OpenAPI 3.1 contract.

Start the CLI in a separate terminal:

```bash
docker compose run --rm booking
```

Stop the web service without deleting bookings:

```bash
docker compose stop web
```

The CLI and API share the `booking-data` Docker volume. The HTTP port is published
only on `127.0.0.1`; the API has no authentication and must remain local.

## Main workflows

The CLI starts with a role selection:

| Role | Commands |
| --- | --- |
| Apartment Booker | `apartment view`, `apartment search`, `booking create`, `booking view`, `booking change`, `booking cancel` |
| System Manager | `apartment add`, `apartment view`, `apartment price`, `apartment remove`, `booking view` |

Use `help` for contextual help, `role` to switch roles and `exit` to close the
application. Dates accept `YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY` and `DD.MM.YYYY`.
Apartment names are case-insensitive. Check-out must be later than check-in, capacity
must fit, and bookings for the same apartment cannot overlap.

### REST API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Check API and database readiness |
| `GET` / `POST` | `/api/apartments` | List or create apartments |
| `PATCH` | `/api/apartments/{name}/price` | Change the nightly price |
| `DELETE` | `/api/apartments/{name}` | Delete an apartment and its bookings |
| `GET` / `POST` | `/api/bookings` | List or create bookings |
| `PATCH` / `DELETE` | `/api/bookings` | Change or cancel a booking |
| `GET` | `/api/availability` | Search by dates and party size |

Successful responses use `{"data": ...}`. Errors use
`{"error": {"code": "...", "message": "..."}}`. The interactive explorer at
`/docs` provides editable examples for every endpoint.

## Architecture

```text
HTTP client -> Flask routes --------+
                                   +-> BookingDatabase -> SQLite
Terminal ----> ApartmentBookingCLI -+
```

- `apartment_booking.database` owns persistence, validation and transactions.
- `apartment_booking.cli` owns terminal interaction and presentation.
- `apartment_booking.web` translates HTTP input/output and contains no SQL.
- `apartment_booking.api_docs` generates the OpenAPI contract used by the explorer.

Flask creates one database wrapper per request. SQLite connections are not shared
between threads. Mutations use `BEGIN IMMEDIATE`, so availability validation and the
following write happen in one transaction.

The domain relationships are summarized in the
[concept map](docs/domain-concept-map.png).

## Project layout

```text
apartment-booking-cli/
├── apartment_booking/          # Application package
│   ├── __main__.py             # `python -m apartment_booking`
│   ├── cli.py                  # Terminal interface
│   ├── database.py             # Domain rules and SQLite persistence
│   ├── web.py                  # Flask application factory and routes
│   ├── api_docs.py             # OpenAPI contract
│   ├── templates/              # API explorer markup
│   └── static/                 # API explorer CSS and JavaScript
├── tests/
│   ├── test_*.py               # Unit and integration tests
│   ├── smoke/                  # Disposable Docker checks
│   └── performance/            # Locust user journey
├── docs/                       # Architecture assets
├── .github/workflows/          # Test, coverage and load-test pipelines
├── Dockerfile
├── compose.yaml
├── main.py                     # Small compatibility launcher
├── requirements.txt            # Web dependency
└── requirements-load.txt       # Load-test dependency
```

Generated data, virtual environments, caches, reports and local databases are
ignored. The repository keeps source, tests and automation only.

## Run locally without Docker

Python 3.10 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

The equivalent package entry point is:

```bash
python -m apartment_booking
```

Start the API directly:

```bash
python -m flask --app apartment_booking.web:create_app --no-debug run \
  --host 127.0.0.1 --port 8000 --no-debugger --no-reload
```

On Windows, use `py -3` instead of `python3`, activate with
`.venv\Scripts\activate`, and use one line for the Flask command.

Direct Python runs store data in the ignored `apartment_booking.db` file by default.
Set `APARTMENT_BOOKING_DB_PATH` to use another location.

## Tests and CI

Install the web dependency, then run all 43 unit and integration tests:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Run the container checks:

```bash
docker compose config --quiet
docker build --target test --tag apartment-booking-cli:test .
docker compose build
python tests/smoke/docker_cli.py
python tests/smoke/docker_web.py
```

The smoke scripts create random Compose projects and disposable volumes. They never
use the normal `booking-data` volume.

GitHub Actions automatically runs:

- the full suite on Python 3.10 and 3.14 across Linux, macOS and Windows;
- CLI/API Docker build, persistence and restart checks;
- branch coverage with an 85% minimum;
- the API load test with downloadable HTML and CSV reports.

### Load test

The Locust scenario models the primary journey: browse apartments, search
availability, create a booking, list it, change it and cancel it. Each simulated
user owns and cleans up uniquely named data.

```bash
python -m pip install -r requirements-load.txt
python -m locust --locustfile tests/performance/locustfile.py \
  --host http://127.0.0.1:8000
```

Open http://localhost:8089 for the Locust UI. CI uses 10 users for 30 seconds and
fails above 1% errors, 500 ms average response time or 1,000 ms p95.

## Data and backups

Local `*.db` files are deliberately not tracked. Before replacing or importing data,
stop all writers:

```bash
docker compose stop web
docker compose create booking
docker compose cp booking:/data/apartment_booking.db ./booking-backup.db
```

Do not run `docker compose down --volumes` unless you intentionally want to delete
the normal Docker database. Removing an apartment also removes its bookings.

## Scope

This is a local course project, not a production service. It has no authentication,
payments, booking ownership, schema migrations or multi-node database. Prices use
SQLite `REAL`, totals use the apartment's current price, and dates have no time zone.
Keep the API bound to localhost.

## Releases and authors

- [Checkpoint 04](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-04) — complete CI pipeline, coverage and Locust load testing
- [Checkpoint 03](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-03) — Flask REST API, OpenAPI contract and local dashboard
- [Checkpoint 02](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-02)
- [Checkpoint 01](https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-01)

Created by **Sebastiano Druda, Tom Springer and Jacob Wieser**.
