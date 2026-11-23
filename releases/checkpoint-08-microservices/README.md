# Checkpoint 08 — Microservices without a read model

Release **checkpoint 08** of the Apartment Booking System: two services that each own
their data and answer both its reads and its writes, kept in step through apartment
events on RabbitMQ, behind an nginx gateway that routes by path. It drops the
projector, the query service and MongoDB of checkpoint 07: six containers instead of
nine. Each service has its own image, tests, event contract and pipeline, so separate
teams can work on them.

| Folder | What | Owner |
| --- | --- | --- |
| [`microservices/`](microservices/README.md) | The services, the gateway, the Compose stack and their tests: **start here** | apartment, reservation and platform teams |
| [`microservices/contracts/`](microservices/contracts/README.md) | The event contract between the apartment and reservation teams | both teams |
| `apartment_booking/` | The domain rules, CLI and API explorer the services reuse | domain team |
| `website-studio/` | The Dimora web client the gateway serves, and its end-to-end suite | frontend team |

The release runs on its own. From `microservices/`:

```bash
docker compose up --build --detach --wait      # http://127.0.0.1:8080
```

or, from the repository root, `python3 run.py 08 stack` (add `--replicas 2` for
restarts without failed requests; other modes: `cli`, `logs`, `down`, `test`,
`contract`, `smoke`). How the teams, `CODEOWNERS` and the pipelines fit together is
described in [docs/devops.md](../../docs/devops.md); the other releases are listed
in the [repository README](../../README.md).
