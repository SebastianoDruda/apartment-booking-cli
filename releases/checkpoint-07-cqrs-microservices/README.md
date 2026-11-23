# Checkpoint 07 — Event-driven CQRS microservices

Release **checkpoint 07** of the Apartment Booking System: the system split into
microservices that each own their data, connected through RabbitMQ, with reads and
writes separated (CQRS). A projector builds a read model in MongoDB, a query service
answers every read from it, and an nginx gateway routes requests by HTTP method.
Nine containers in total.

| Folder | What |
| --- | --- |
| [`microservices/`](microservices/README.md) | The services, the gateway, the Compose stack and their tests: **start here** |
| `apartment_booking/` | The domain rules, CLI and API explorer the services reuse (from checkpoint 06) |
| `website-studio/` | The Dimora web client the gateway serves, and its end-to-end suite |

The release runs on its own. From `microservices/`:

```bash
docker compose up --build --detach --wait      # http://127.0.0.1:8080
```

or, from the repository root, `python3 run.py 07 stack` (also `cli`, `logs`, `down`,
`test`, `smoke`). Checkpoint 08 is the same system without the read model; the other
releases are listed in the [repository README](../../README.md).
