# Event contracts

The events on the `dimora.events` exchange are the only interface between the
apartment team (producer) and the reservation team (consumer). Each file here is
a complete example of one event type, and both sides test against it:

| Event | Producer | Consumer |
| --- | --- | --- |
| [`apartment.added`](events/apartment.added.json) | apartment service | reservation service |
| [`apartment.price_changed`](events/apartment.price_changed.json) | apartment service | reservation service |
| [`apartment.removed`](events/apartment.removed.json) | apartment service | reservation service |

- **Producer test** (`tests/contract/test_apartment_producer.py`): the apartment
  service turns a row into an event with exactly these fields and types.
- **Consumer test** (`tests/contract/test_reservation_consumer.py`): the
  reservation service accepts every example and finds every field it reads.

## Changing a contract

1. Add fields only; never rename, remove or change the type of an existing field.
2. Update the example here in the same pull request as the producer change.
   CODEOWNERS asks both teams to approve anything in this folder.
3. A change that cannot be additive becomes a new event type (for example
   `apartment.added.v2`), published next to the old one until every consumer
   has moved.
