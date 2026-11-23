"""Dimora event-driven edition: CQRS microservices connected through RabbitMQ.

Packages:
    common       events, messaging, outbox relay, configuration and HTTP helpers
    apartment    command side for apartments (owns the apartments PostgreSQL database)
    reservation  command side for bookings (owns the reservations PostgreSQL database)
    projector    consumes every event and builds the read model in MongoDB
    query        answers every GET request from the read model
    cli          the original terminal interface, talking to the gateway over HTTP
    tools        data import and read-model rebuild utilities

The domain rules (date parsing, price validation, totals) are reused from the
original ``apartment_booking`` package, so both editions validate input identically.
"""
