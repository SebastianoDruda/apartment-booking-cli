"""Dimora microservices edition: two services, each owning its data, linked by RabbitMQ.

Packages:
    common       events, messaging, outbox relay, configuration and HTTP helpers
    apartment    apartment reads and writes (owns the apartments PostgreSQL database)
    reservation  booking reads, writes and availability (owns the reservations database,
                 with a copy of every apartment kept up to date from apartment events)
    cli          the original terminal interface, talking to the gateway over HTTP
    tools        data import and apartment republishing utilities

The domain rules (date parsing, price validation, totals) are reused from the
original ``apartment_booking`` package, so every edition validates input identically.
"""
