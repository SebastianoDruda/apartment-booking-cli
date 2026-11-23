"""RabbitMQ publishing and consuming on top of pika's blocking adapter.

pika connections are not thread-safe, so each publisher and consumer owns its
own connection and is used from a single thread.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

import pika
from pika.adapters.blocking_connection import BlockingChannel

from dimora.common.events import (
    DEAD_LETTER_EXCHANGE, DEAD_LETTER_QUEUE, EXCHANGE, QUEUES, Event, InvalidEvent,
)


class Backoff:
    """Exponential retry delay: 0.5 s, 1 s, 2 s ... capped at ``maximum`` seconds."""

    def __init__(self, initial: float = 0.5, maximum: float = 15.0) -> None:
        self.initial = initial
        self.maximum = maximum
        self.current = initial

    def next(self) -> float:
        delay = self.current
        self.current = min(self.current * 2, self.maximum)
        return delay

    def reset(self) -> None:
        self.current = self.initial


def connection_parameters(url: str) -> pika.URLParameters:
    parameters = pika.URLParameters(url)
    parameters.heartbeat = 30
    parameters.blocked_connection_timeout = 30
    parameters.connection_attempts = 1
    parameters.socket_timeout = 5
    return parameters


def declare_topology(channel: BlockingChannel) -> None:
    """Declare the exchange, the durable queues and the dead-letter route.

    Declarations are idempotent, so every service runs them on connect. Messages
    published before a consumer starts wait in its durable queue.
    """
    channel.exchange_declare(EXCHANGE, exchange_type="topic", durable=True)
    channel.exchange_declare(DEAD_LETTER_EXCHANGE, exchange_type="fanout", durable=True)
    channel.queue_declare(DEAD_LETTER_QUEUE, durable=True)
    channel.queue_bind(DEAD_LETTER_QUEUE, DEAD_LETTER_EXCHANGE)
    for queue, routing_keys in QUEUES.items():
        channel.queue_declare(queue, durable=True,
                              arguments={"x-dead-letter-exchange": DEAD_LETTER_EXCHANGE})
        for routing_key in routing_keys:
            channel.queue_bind(queue, EXCHANGE, routing_key=routing_key)


class Publisher:
    """Publishes persistent events and waits for the broker to confirm each one."""

    def __init__(self, url: str, source: str) -> None:
        self.url = url
        self.source = source
        self._connection: pika.BlockingConnection | None = None
        self._channel: BlockingChannel | None = None

    def _ensure_channel(self) -> BlockingChannel:
        if self._channel is None or self._channel.is_closed:
            self.close()
            self._connection = pika.BlockingConnection(connection_parameters(self.url))
            self._channel = self._connection.channel()
            declare_topology(self._channel)
            self._channel.confirm_delivery()
        return self._channel

    def publish(self, event: Event) -> None:
        """Return only once RabbitMQ has stored the message in every bound queue.

        Raises a pika exception when the broker is unreachable, refuses the message
        or cannot route it; the caller keeps the row pending and retries later.
        """
        channel = self._ensure_channel()
        channel.basic_publish(
            exchange=EXCHANGE,
            routing_key=event.type,
            body=event.to_json(),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=pika.DeliveryMode.Persistent,
                message_id=event.event_id,
                type=event.type,
                app_id=self.source,
            ),
            mandatory=True,
        )

    def keep_alive(self) -> None:
        """Answer broker heartbeats while the publisher is idle."""
        if self._connection is not None and self._connection.is_open:
            self._connection.process_data_events(time_limit=0)

    def close(self) -> None:
        connection, self._connection, self._channel = self._connection, None, None
        if connection is not None and connection.is_open:
            try:
                connection.close()
            except Exception:  # noqa: BLE001 - the connection is being discarded anyway
                pass


def consume_forever(
    url: str,
    queue: str,
    handle: Callable[[Event], None],
    stop: threading.Event,
    log: logging.Logger,
    on_idle: Callable[[], None] | None = None,
    prefetch: int = 20,
) -> None:
    """Deliver each event of ``queue`` to ``handle`` until ``stop`` is set.

    A message is acknowledged only after ``handle`` returns, so nothing is lost if
    the service stops halfway. Messages that break the event contract go to the
    dead-letter queue. Any other failure (a database that is down, for example)
    closes the connection, which returns unacknowledged messages to the queue, and
    the consumer reconnects after a growing delay.
    """
    backoff = Backoff()
    while not stop.is_set():
        connection = None
        try:
            connection = pika.BlockingConnection(connection_parameters(url))
            channel = connection.channel()
            declare_topology(channel)
            channel.basic_qos(prefetch_count=prefetch)
            log.info("Consuming queue %s", queue)
            backoff.reset()
            for method, _properties, body in channel.consume(queue, inactivity_timeout=1):
                if on_idle is not None:
                    on_idle()
                if stop.is_set():
                    break
                if method is None:
                    continue
                try:
                    event = Event.from_json(body)
                    handle(event)
                except InvalidEvent as error:
                    log.error("Moving message %s to %s: %s", method.delivery_tag, DEAD_LETTER_QUEUE, error)
                    channel.basic_nack(method.delivery_tag, requeue=False)
                    continue
                channel.basic_ack(method.delivery_tag)
        except Exception as error:  # noqa: BLE001 - retry every infrastructure failure
            log.warning("Consumer of %s interrupted (%s: %s); retrying", queue, type(error).__name__, error)
        finally:
            if connection is not None and connection.is_open:
                try:
                    connection.close()
                except Exception:  # noqa: BLE001
                    pass
        stop.wait(backoff.next())
