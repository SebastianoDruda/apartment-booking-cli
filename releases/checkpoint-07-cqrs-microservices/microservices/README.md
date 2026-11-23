# Dimora — event-driven edition

This folder holds a second edition of the Apartment Booking System. The domain rules
and the interfaces stay the same, but the system is split into microservices
that each own their data and talk to each other only through events on
[RabbitMQ](https://www.rabbitmq.com/). Reads and writes are separated (CQRS):
command services change data, while a query service answers every read from views
built out of those events.

The original edition in the repository root is untouched and keeps working.
This edition reuses its domain package (`apartment_booking`), its CLI and its Dimora
web client, so input is validated with the same rules and reported with the same
messages.

## Architecture

```text
                       Browser (Dimora)      CLI (python -m dimora.cli)
                                  \            /
                          nginx gateway :8080  (web client + /api routing)
               POST/PATCH/DELETE    |                         |   GET
          /api/apartments  /api/bookings                      |
                 |                  |                         |
       Apartment service   Reservation service          Query service
                 |                  |                         |
          PostgreSQL         PostgreSQL                    MongoDB
          apartments         bookings + apartment copy     read model
                 \                  |   ^                     ^
     apartment.*  \     booking.*   |   | apartment.*         | updates views
                   v                v   |                     |
                 RabbitMQ  exchange dimora.events  ----->  Projector
```

| Container | Role | Owns | Publishes | Consumes |
| --- | --- | --- | --- | --- |
| `gateway` | nginx: serves the web client, routes `/api` by HTTP method | — | — | — |
| `apartment-service` | Adds apartments, changes prices, removes apartments | `apartments` (PostgreSQL) | `apartment.*` | nothing |
| `reservation-service` | Creates, changes and cancels bookings | `reservations` (PostgreSQL) | `booking.*` | `apartment.*` |
| `projector` | Turns events into the read model | `dimora_read` (MongoDB) | — | everything |
| `query-service` | Answers every `GET /api/*`, serves the API explorer | reads `dimora_read` | — | — |
| `rabbitmq` | Topic exchange `dimora.events`, durable queues, dead-letter queue | — | — | — |

The apartment service knows nothing about bookings. The reservation service keeps a
small copy of each apartment (id, name, address, capacity, nightly price), fed by
apartment events, so it can check capacity and overlaps without calling another
service.

### Where the data lives

| Data | Original edition | Event-driven edition |
| --- | --- | --- |
| Apartments | One SQLite file in the `booking-data` volume | Apartment service's PostgreSQL |
| Bookings | Same SQLite file | Reservation service's PostgreSQL, next to its apartment copy |
| Lists, availability, totals | JOIN and calculation on every read | Ready-made views in MongoDB |
| Language, theme, session | Browser `localStorage` | Unchanged |
| Events | None | RabbitMQ, one per change |

### Events

Every change to a row publishes one event that carries the row's **full current
state** and its **version**. Consumers keep the newest version they have seen, so
duplicates are harmless and an older version arriving late is ignored.

| Event | Publisher | Consumers |
| --- | --- | --- |
| `apartment.added` | apartment service | reservation service, projector |
| `apartment.price_changed` | apartment service | reservation service, projector |
| `apartment.removed` | apartment service | reservation service, projector |
| `booking.created` | reservation service | projector |
| `booking.changed` | reservation service | projector |
| `booking.cancelled` | reservation service | projector |

```json
{
  "event_id": "booking:7:v2",
  "type": "booking.changed",
  "source": "reservation-service",
  "entity_id": 7,
  "version": 2,
  "occurred_at": "2026-11-18T10:15:00.000+00:00",
  "data": { "id": 7, "apartment_id": 3, "booker_name": "Anna Huber",
            "start_date": "2027-05-01", "end_date": "2027-05-04", "num_people": 2,
            "price_per_night": 100.0, "nights": 3, "total_price": 300.0, "status": "active" }
}
```

## How it works

**Requests.** Every request from the web client or the CLI reaches nginx. It
serves the static client and routes the API by method: `POST`, `PATCH` and `DELETE`
on `/api/apartments` go to the apartment service, the same methods on `/api/bookings`
go to the reservation service, and every `GET` goes to the query service. The URLs
and JSON bodies are those of the original API, so neither client had to change its
calls. Each API response carries `X-Served-By`, which names the service that
answered.

**Writing.** Each write runs in one PostgreSQL transaction, applies the same rules
as `apartment_booking/database.py`, and increases the row's `version`. A booking
stores the nightly price it was made at, so a later price change only affects new
bookings. Removing an apartment or cancelling a booking keeps the row (with
`removed_at` or status `cancelled`), so the removal is published like any other
change. Apartment names stay unique, case-insensitively, among apartments that are
not removed. An exclusion constraint on the booking dates guarantees that two
active bookings of one apartment can never overlap, even under concurrent writes.

**Publishing (outbox).** Each row also stores `published_version`. A relay thread
in each command service publishes every row whose `published_version` is behind
its `version`, waits for RabbitMQ's publisher confirmation, and then records the
version it sent. A write therefore never depends on RabbitMQ being up. If the broker
is down, rows stay pending and go out on the next pass. Recording the exact version
(instead of a true/false flag) matters: a change committed while an event is in
flight leaves the row pending, so it is published too.

**Delivery.** Every service declares the whole topology when it connects: the topic
exchange `dimora.events`, the durable queues `reservation.apartment-events`
(`apartment.*`) and `projector.events` (`apartment.*`, `booking.*`), and the
dead-letter queue `dimora.dead-letter`. The queues therefore exist before the first
publish, and a consumer that starts later still receives every event. Messages are
persistent and acknowledged only after they have been applied. A message that
breaks the event contract goes to the dead-letter queue. Any other failure, such as
a database that is down, returns the message to its queue, and the consumer retries
after an increasing delay.

**Consumers.** The reservation service applies apartment events to its copy. When an
apartment is removed, it cancels that apartment's bookings and publishes a
`booking.cancelled` event for each one, with the same result as the original `ON DELETE CASCADE`.
The projector builds two MongoDB collections: `apartments`, and `bookings` with
their apartment's name, address and capacity copied in and nights and totals
already calculated. Events from different services can arrive in any order, so a
booking may reach the projector before its apartment. The projector stores it
anyway and fills in the apartment details when they arrive; until then the booking
stays hidden. A removed apartment hides its bookings at once, before the
cancellations arrive.

**Reading your own writes.** Views update a moment after a write. Every write
answers with `X-Consistency-Token: booking:7@2` (or `apartment:…`). The web client
and the CLI send pending tokens back in `X-Wait-For` on their next reads. The query
service then waits (up to 3 s) until its views hold that version, and answers
with `X-Consistency: fresh`, or `stale` after the timeout. A booking for an
apartment created a moment earlier waits up to 2 s for the apartment to reach the
reservation service's copy, so API clients that create and book straight away keep
working.

**First start and rebuilds.** Rows imported from the original SQLite database start
with `published_version = 0`, so the first start publishes everything, and the
reservation copy and the read model fill themselves. Resetting `published_version`
to 0 republishes every row, which is how the read model is rebuilt from scratch.

## Getting started

Docker Desktop (or Docker Engine with Compose v2) is the only requirement. From this
folder:

```bash
docker compose up --build --detach --wait
```

| Address | What |
| --- | --- |
| http://127.0.0.1:8080 | Dimora web client |
| http://127.0.0.1:8080/docs | API explorer (requests go through the gateway) |
| http://127.0.0.1:8080/api | Route overview: which service owns which route |
| http://127.0.0.1:15672 | RabbitMQ management (user `dimora`, password `dimora-local`) |

Ports are published on `127.0.0.1` only, and the databases are reachable only
inside the Compose network. Set `DIMORA_PORT` or `DIMORA_RABBITMQ_UI_PORT` if a port
is taken. The original edition (port 8000) and this one can run side by side.

The terminal interface is the original CLI, connected to the gateway over HTTP:

```bash
docker compose run --rm cli                                   # inside the Compose network
DIMORA_API_URL=http://127.0.0.1:8080 PYTHONPATH=.. python3 -m dimora.cli   # from a checkout, no packages needed
```

Import the data of the original edition into a fresh stack (the importer refuses to
write into databases that already contain data):

```bash
# In releases/checkpoint-06-dimora-web: copy the original database out of its volume (or use a backup)
docker compose create booking
docker compose cp booking:/data/apartment_booking.db ../checkpoint-07-cqrs-microservices/microservices/apartment_booking.db

# In microservices/: import it
docker compose run --rm -v "$PWD/apartment_booking.db:/import/apartment_booking.db:ro" importer
```

Rebuild the read model from the command-side databases:

```bash
docker compose run --rm republish python -m dimora.tools.republish --drop-read-model
```

Stop the stack with `docker compose stop`; `docker compose down --volumes` deletes
all four data volumes.

### Configuration

| Variable | Used by | Default |
| --- | --- | --- |
| `DIMORA_PORT` | gateway (host port) | `8080` |
| `DIMORA_RABBITMQ_UI_PORT` | RabbitMQ management (host port) | `15672` |
| `DIMORA_DB_PASSWORD`, `DIMORA_RABBITMQ_PASSWORD` | Compose | `dimora-local` |
| `DIMORA_APARTMENT_DSN`, `DIMORA_RESERVATION_DSN` | command services, tools | set by Compose |
| `DIMORA_RABBITMQ_URL` | every Python service | `amqp://dimora:dimora-local@rabbitmq:5672/%2F` |
| `DIMORA_MONGO_URL`, `DIMORA_MONGO_DATABASE` | projector, query service | `mongodb://read-db:27017`, `dimora_read` |
| `DIMORA_CONSISTENCY_TIMEOUT` | query service | `3` seconds |
| `DIMORA_COPY_GRACE` | reservation service | `2` seconds |
| `DIMORA_API_URL` | CLI | `http://127.0.0.1:8080` |

## Tests

```bash
# Unit tests (Python 3.11+): event contract, projector, outbox, HTTP services, CLI client
python -m pip install -r requirements.txt
PYTHONPATH=.. python -m unittest discover -s tests/unit -v

# The same tests inside the service image
docker build --file Dockerfile --target test ..

# The whole stack in a disposable Compose project (about a minute)
python3 tests/system/stack_smoke.py

# The Dimora end-to-end suite through the gateway, on a fresh stack
docker compose up --build --detach --wait
cd ../website-studio && E2E_GATEWAY_URL=http://127.0.0.1:8080 npm run test:e2e
```

The **unit tests** replace PostgreSQL, MongoDB and RabbitMQ with in-memory fakes.
They cover the event contract, the projection rules (any order, duplicates,
interrupted projections), the outbox (batches, failures, a change made while
publishing, republishing), the HTTP contract and consistency headers of the three
services, and the original CLI running on the gateway client.

The **system test** (`tests/system/stack_smoke.py`) builds the images and starts
the stack on random ports, then checks: the SQLite import; the gateway's routing,
web client and explorer; the original validation messages and status codes; prices,
changes, cancellations and availability; writes while RabbitMQ is stopped; events
queued for a projector that starts later; the removal cascade; the CLI reading its
own writes; the dead-letter queue; a full read-model rebuild; unprivileged containers;
and persistence across a restart. It removes its project and volumes at the end.

On GitHub Actions the `Checkpoint 07 · CQRS microservices` workflow
(`.github/workflows/microservices.yml` at the repository root) runs the unit tests
on Python 3.11 and 3.14, the system test, and the Playwright suite of the web client
through the gateway. On GitLab the `checkpoint-07-unit-tests` job runs the unit tests
on the self-managed runner.

## Layout

```text
microservices/
├── compose.yaml            # the whole stack, plus the cli, importer and republish tools
├── Dockerfile              # one Python image for every service (runtime and test targets)
├── requirements.txt        # Flask, waitress, pika, psycopg, pymongo
├── gateway/
│   ├── Dockerfile          # nginx + the Dimora web client from ../website-studio/public
│   └── nginx.conf          # CQRS routing and security headers
├── dimora/
│   ├── common/             # events, RabbitMQ, outbox relay, consistency tokens, HTTP, config
│   ├── apartment/          # apartment service (store, HTTP, entry point)
│   ├── reservation/        # reservation service (store, HTTP, apartment-event consumer)
│   ├── projector/          # projection rules and the MongoDB store
│   ├── query/              # query service and read model
│   ├── cli/                # gateway client for the original CLI
│   └── tools/              # SQLite import and republish
└── tests/
    ├── unit/               # in-memory tests, no Docker needed
    └── system/             # stack_smoke.py, Docker required
```

Both Dockerfiles build from the release folder (`releases/checkpoint-07-cqrs-microservices`),
so the shared `apartment_booking` package and the web client are part of the image. Their own `*.dockerignore` files
limit the build context to what each image needs.

## Limits

This is an educational, local system like the original edition: no authentication,
no TLS, and default passwords meant for localhost. Reads are eventually consistent
(usually within milliseconds). The consistency token covers a client's own writes,
not other people's. Run one projector at a time: it applies one event after
another. Python 3.11 or newer is needed for the services (the images use 3.14),
because the MongoDB driver no longer supports 3.10.
