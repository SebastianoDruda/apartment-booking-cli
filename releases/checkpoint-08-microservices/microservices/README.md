# Dimora — microservices edition

This folder holds the checkpoint 08 edition of the Apartment Booking System. The
domain rules and the interfaces stay the same, but the system is split into two
services that each own their data, read and write it themselves, and stay in step
through events on [RabbitMQ](https://www.rabbitmq.com/). An nginx gateway in front
routes every request to the service that owns the resource.

It is the simpler sibling of the CQRS edition of checkpoint 07: there is no separate
read model, so the projector, the query service and MongoDB are gone. Six containers
instead of nine, and every read comes straight from the database that was written.
The trade-offs are on the project whiteboard and summarised in
[Compared with checkpoint 07](#compared-with-checkpoint-07).

The edition reuses the domain package (`apartment_booking`), the CLI and the Dimora
web client of the release folder, so input is validated with the same rules and
reported with the same messages.

## Architecture

```text
                Browser (Dimora)          CLI (python -m dimora.cli)
                           \                /
                      nginx gateway :8080  (web client + /api routing by path)
              /api/apartments  /docs  /api      /api/bookings  /api/availability
                     |                                   |
             Apartment service                  Reservation service
              reads + writes                reads + writes + availability
                     |                                   |
                PostgreSQL                          PostgreSQL
                apartments                bookings + apartment copy
                     \                                   ^
          apartment.* \                                  | apartment.*
                       v                                 |
                     RabbitMQ  exchange dimora.events  --+
```

| Container | Role | Owns | Publishes | Consumes |
| --- | --- | --- | --- | --- |
| `gateway` | nginx: serves the web client, routes `/api` by path | — | — | — |
| `apartment-service` | Lists, adds, reprices and removes apartments; API overview, OpenAPI, explorer | `apartments` (PostgreSQL) | `apartment.*` | nothing |
| `apartment-db` | PostgreSQL of the apartment service | | | |
| `reservation-service` | Lists, creates, changes and cancels bookings; availability search | `reservations` (PostgreSQL) | nothing | `apartment.*` |
| `reservation-db` | PostgreSQL of the reservation service | | | |
| `rabbitmq` | Topic exchange `dimora.events`, durable queue, dead-letter queue | — | — | — |

The apartment service knows nothing about bookings. The reservation service keeps a
small copy of each apartment (id, name, address, capacity, nightly price), fed by
apartment events. The copy lets it check capacity and overlaps, list bookings with
their apartment details, and answer availability, all from its own database and
without calling another service.

### Where the data lives

| Data | Checkpoint 06 | Checkpoint 07 (CQRS) | Checkpoint 08 |
| --- | --- | --- | --- |
| Apartments | One SQLite file | Apartment service's PostgreSQL | Apartment service's PostgreSQL |
| Bookings | Same SQLite file | Reservation service's PostgreSQL | Reservation service's PostgreSQL |
| Lists, availability, totals | JOIN on every read | Ready-made views in MongoDB | JOIN with the apartment copy, in the reservation database |
| Events | None | One per change, apartments and bookings | One per apartment change |

### Events

Every apartment change publishes one event that carries the row's **full current
state** and its **version**. The reservation service keeps the newest version it
has seen, so duplicates are harmless and an older version arriving late is ignored.
Booking changes need no event: nothing outside the reservation service reads them.

| Event | Publisher | Consumer |
| --- | --- | --- |
| `apartment.added` | apartment service | reservation service |
| `apartment.price_changed` | apartment service | reservation service |
| `apartment.removed` | apartment service | reservation service |

The examples in [`contracts/events/`](contracts/README.md) are the contract between
the two teams; both sides test against them.

## How it works

**Requests.** Every request from the web client or the CLI reaches nginx. It serves
the static client and routes the API by path: `/api/apartments` goes to the apartment
service, `/api/bookings` and `/api/availability` to the reservation service, and the
entry points (`/api`, `/api/health`, `/api/openapi.json`, `/docs`) to the apartment
service. The URLs and JSON bodies are those of the original API, so neither client
changed its calls. Each response carries `X-Served-By`, which names the service that
answered.

**Writing and reading.** Each service answers reads from the same database it writes,
so a client always sees its own change at once. Each write runs in one PostgreSQL
transaction, applies the same rules as `apartment_booking/database.py`, and increases
the row's `version`. A booking stores the nightly price it was made at, so a later
price change only affects new bookings. Removing an apartment or cancelling a booking
keeps the row (with `removed_at` or status `cancelled`). Apartment names stay unique,
case-insensitively, among apartments that are not removed. An exclusion constraint on
the booking dates guarantees that two active bookings of one apartment can never
overlap, even under concurrent writes.

**Publishing (outbox).** Each apartment row also stores `published_version`. A relay
thread in the apartment service publishes every row whose `published_version` is
behind its `version`, waits for RabbitMQ's publisher confirmation, and then records
the version it sent. A write therefore never depends on RabbitMQ being up: if the
broker is down, rows stay pending and go out on the next pass.

**Delivery.** Every service declares the topology when it connects: the topic
exchange `dimora.events`, the durable queue `reservation.apartment-events`
(`apartment.*`) and the dead-letter queue `dimora.dead-letter`. Messages are
persistent and acknowledged only after they have been applied. A message that
breaks the event contract goes to the dead-letter queue; any other failure returns
it to its queue, and the consumer retries after an increasing delay.

**The apartment copy.** The reservation service applies apartment events to its copy.
When an apartment is removed, it cancels that apartment's bookings in the same
transaction, with the same result as the original `ON DELETE CASCADE`. A booking for
an apartment created a moment earlier waits up to 5 s for the apartment to reach the
copy, so a client that creates an apartment and books it straight away keeps working.

**Reading your own writes across services.** Only the reservation service can be
behind, and only on apartments. Every write answers with
`X-Consistency-Token: apartment:3@2` (or `booking:…`). The web client and the CLI
send pending tokens back in `X-Wait-For` on their next reads. A service waits (up
to 3 s) until it holds that version, and answers with `X-Consistency: fresh`, or
`stale` after the timeout. Own tokens are fresh at once; an apartment token makes the
reservation service wait for the event to reach its copy.

**Restarts without failed requests.** Each service can run as several replicas
(`--scale`). nginx re-resolves the service names every 5 s, spreads requests over
the replicas, and moves a request it cannot deliver to the next one. On `SIGTERM`
(a restart, `docker stop`, a scale-down) a service refuses new connections, finishes
the requests in flight and then exits; Compose gives it 15 s to do so. nginx opens
one connection per request, so a stopping replica receives nothing new. With two
replicas, restarting one of them fails no request, POSTs included.

**First start and rebuilds.** Apartments imported from the original SQLite database
start with `published_version = 0`, so the first start publishes all of them and the
copy fills itself. `republish --rebuild-copy` empties the copy and publishes every
apartment again, which rebuilds it from the events alone.

## Compared with checkpoint 07

| | Checkpoint 07 (CQRS) | Checkpoint 08 |
| --- | --- | --- |
| Containers | 9 | 6 |
| `GET` requests | query service, routed by HTTP method | the service that owns the data, routed by path |
| Bookings with apartment details | ready-made view in MongoDB | JOIN with the apartment copy |
| Read your own writes | consistency token, waits up to 3 s | at once; only apartment changes may make the reservation service wait |
| Events | `apartment.*` and `booking.*` | `apartment.*` only |
| Restart of a service | requests fail while it restarts | no failed request with two replicas |
| Images | one image for every service | one image per service |
| Still CQRS? | yes: separate read model | no: event-driven microservices |

The [stress test](#tests) of both editions, with the same load (48 clients, 1,000
listings, 4,000 booking attempts, 90 s of mixed traffic) and RabbitMQ stopped for
20 s. Checkpoint 07 ran one replica per service and had its projector stopped and
its reservation service restarted; checkpoint 08 ran two replicas per service and
had one replica of each restarted. Measured on the same laptop, 2026-11-23:

| | Checkpoint 07 | Checkpoint 08 |
| --- | --- | --- |
| Requests that failed with a server error | 79 of 10,700 (502 while the reservation service restarted) | 0 of 13,713 |
| List apartments, p50 / p95 | 728 / 3,056 ms | 48 / 130 ms |
| List bookings, p50 / p95 | 849 / 3,198 ms | 840 / 1,646 ms |
| Availability, p50 / p95 | 738 / 3,001 ms | 480 / 1,205 ms |
| Double bookings, overlaps, over capacity | 0 | 0 |
| Write side and read side agree after the load | after 1 s | after 1 s |

## Getting started

Docker Desktop (or Docker Engine with Compose v2) is the only requirement. From this
folder:

```bash
docker compose up --build --detach --wait
# or, from the repository root:  python3 run.py 08 stack
```

| Address | What |
| --- | --- |
| http://127.0.0.1:8080 | Dimora web client |
| http://127.0.0.1:8080/docs | API explorer (requests go through the gateway) |
| http://127.0.0.1:8080/api | Route overview: which service owns which route |
| http://127.0.0.1:15672 | RabbitMQ management (user `dimora`, password `dimora-local`) |

Ports are published on `127.0.0.1` only, and the databases are reachable only
inside the Compose network. Set `DIMORA_PORT` or `DIMORA_RABBITMQ_UI_PORT` if a port
is taken; checkpoint 07 uses the same defaults, so run one of them at a time or move
one to another port.

Run two replicas of each service, so that restarting one fails no request:

```bash
docker compose up --build --detach --wait --scale apartment-service=2 --scale reservation-service=2
# or:  python3 run.py 08 stack --replicas 2
```

The terminal interface is the original CLI, connected to the gateway over HTTP:

```bash
docker compose run --rm cli                                                # inside the Compose network
DIMORA_API_URL=http://127.0.0.1:8080 PYTHONPATH=.. python3 -m dimora.cli   # from a checkout, no packages needed
```

Import the data of checkpoint 06 into a fresh stack (the importer refuses to write
into databases that already contain data):

```bash
# In releases/checkpoint-06-dimora-web: copy the database out of its volume (or use a backup)
docker compose create booking
docker compose cp booking:/data/apartment_booking.db ../checkpoint-08-microservices/microservices/apartment_booking.db

# In this folder: import it
docker compose run --rm -v "$PWD/apartment_booking.db:/import/apartment_booking.db:ro" importer
```

Rebuild the reservation service's apartment copy from the apartment database:

```bash
docker compose run --rm republish python -m dimora.tools.republish --rebuild-copy
```

Stop the stack with `docker compose stop`; `docker compose down --volumes` deletes
all three data volumes.

### Configuration

| Variable | Used by | Default |
| --- | --- | --- |
| `DIMORA_PORT` | gateway (host port) | `8080` |
| `DIMORA_RABBITMQ_UI_PORT` | RabbitMQ management (host port) | `15672` |
| `DIMORA_DB_PASSWORD`, `DIMORA_RABBITMQ_PASSWORD` | Compose | `dimora-local` |
| `DIMORA_APARTMENT_DSN`, `DIMORA_RESERVATION_DSN` | services, tools | set by Compose |
| `DIMORA_RABBITMQ_URL` | every Python service | `amqp://dimora:dimora-local@rabbitmq:5672/%2F` |
| `DIMORA_CONSISTENCY_TIMEOUT` | both services | `3` seconds |
| `DIMORA_COPY_GRACE` | reservation service | `5` seconds |
| `DIMORA_HTTP_THREADS` | both services | `16` |
| `DIMORA_API_URL` | CLI | `http://127.0.0.1:8080` |

## Tests

```bash
# Unit and contract tests (Python 3.11+), from this folder
python -m pip install -r requirements.txt
PYTHONPATH=.. python -m unittest discover -s tests/unit -v
PYTHONPATH=.. python -m unittest discover -s tests/contract -v

# The same tests inside the image
docker build --file Dockerfile --target test ..

# The whole stack in a disposable Compose project (about two minutes)
python3 tests/system/stack_smoke.py

# Stress test: 1,000 listings, 4,000 bookings, 90 s of mixed traffic with failures
python3 tests/system/stack_stress.py --report stress-report.json

# The Dimora end-to-end suite through the gateway, on a fresh stack
docker compose up --build --detach --wait
cd ../website-studio && E2E_GATEWAY_URL=http://127.0.0.1:8080 npm run test:e2e
```

The **unit tests** replace PostgreSQL and RabbitMQ with fakes. They cover the event
contract, the outbox (batches, failures, a change made while publishing,
republishing), the consistency tokens, the HTTP contract of both services, the
graceful shutdown, and the original CLI running on the gateway client. Each team's
tests are in their own files (`test_apartment_*`, `test_reservation_*`); shared
platform code is tested in `test_common_*`.

The **contract tests** check both sides of the event contract against the examples
in `contracts/events/`: the apartment service produces exactly that shape, and the
reservation service finds every field it reads.

The **system test** (`tests/system/stack_smoke.py`) builds the images and starts the
stack on random ports, then checks: the SQLite import; ownership routing, the web
client and the explorer; the original validation messages and status codes; prices,
changes, cancellations and availability; writes while RabbitMQ is stopped; events
queued for a reservation service that starts later; the removal cascade; the CLI
reading its own writes; the dead-letter queue; a rebuild of the apartment copy; a
restart of one of two replicas without a failed request; unprivileged containers;
and persistence across a restart. It removes its project and volumes at the end.

The **stress test** (`tests/system/stack_stress.py`) runs two replicas of each
service, creates 1,000 listings and 4,000 bookings (with 50 races of ten clients on
the same slot), then sends 90 s of mixed traffic while RabbitMQ is stopped for 20 s
and one replica of each service restarts. It fails if any request ends in a server
error, if a slot is booked twice, if a booking exceeds its capacity or survives its
apartment, or if the copy does not converge.

The pipelines that run them are described in the
[repository README](../../../README.md#continuous-integration) and in
[docs/devops.md](../../../docs/devops.md).

## Layout

```text
microservices/
├── compose.yaml            # the six containers, plus the cli, importer and republish tools
├── Dockerfile              # one image per service: apartment-service, reservation-service, tools, test
├── requirements.txt        # Flask, waitress, pika, psycopg
├── contracts/
│   └── events/             # one example per event type: the contract between the teams
├── gateway/
│   ├── Dockerfile          # nginx + the Dimora web client from ../website-studio/public
│   └── nginx.conf          # ownership routing, replicas, security headers
├── dimora/
│   ├── common/             # events, RabbitMQ, outbox, consistency tokens, HTTP, graceful shutdown
│   ├── apartment/          # apartment service (store, HTTP, entry point)
│   ├── reservation/        # reservation service (store, HTTP, apartment-event consumer)
│   ├── cli/                # gateway client for the original CLI
│   └── tools/              # SQLite import and republish
└── tests/
    ├── unit/               # no Docker needed; one file per service, test_common_* for shared code
    ├── contract/           # producer and consumer side of the event contract
    └── system/             # stack_smoke.py and stack_stress.py, Docker required
```

Both Dockerfiles build from the release folder (`releases/checkpoint-08-microservices`),
so the shared `apartment_booking` package and the web client are part of the images.
Their own `*.dockerignore` files limit the build context to what each image needs.

## Limits

This is an educational, local system like the original edition: no authentication,
no TLS, and default passwords meant for localhost. The reservation service's
apartment copy follows the apartment service by a few milliseconds; the consistency
token covers a client's own writes, not other people's. A price change reaches new
bookings once its event has arrived. Python 3.11 or newer is needed for the services
(the images use 3.14).
