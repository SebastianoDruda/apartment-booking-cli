"""Graceful shutdown of the HTTP services."""

import threading
import unittest

from dimora.common.http import GracefulShutdown


class SlowApp:
    """A WSGI app whose response is held until the test releases it."""

    def __init__(self):
        self.release = threading.Event()

    def __call__(self, environ, start_response):
        self.release.wait(5)
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"ok"]


class GracefulShutdownTests(unittest.TestCase):
    def setUp(self):
        self.app = SlowApp()
        self.exited = threading.Event()
        self.closed = []
        self.graceful = GracefulShutdown(self.app, grace=5, exit=lambda code: self.exited.set())

    def wait_for(self, condition, message):
        for _ in range(200):
            if condition():
                return
            threading.Event().wait(0.01)
        self.fail(message)

    def call(self):
        body = self.graceful({}, lambda status, headers, exc_info=None: None)
        list(body)
        body.close()

    def test_stops_accepting_at_once_and_exits_after_the_last_request(self):
        request = threading.Thread(target=self.call)
        request.start()
        while self.graceful.active == 0:  # the request is in flight
            threading.Event().wait(0.01)
        self.graceful.start_draining(lambda: self.closed.append(1))
        self.wait_for(lambda: self.closed == [1], "new connections are refused at once")
        self.assertFalse(self.exited.wait(0.3), "the process waits for the request")
        self.app.release.set()
        request.join()
        self.assertTrue(self.exited.wait(2), "and exits once it is done")
        self.assertEqual(self.graceful.active, 0)

    def test_a_second_signal_changes_nothing(self):
        self.app.release.set()
        self.graceful.start_draining(lambda: self.closed.append(1))
        self.graceful.start_draining(lambda: self.closed.append(2))
        self.assertTrue(self.exited.wait(2))
        self.assertEqual(self.closed, [1])

    def test_waits_for_connections_whose_request_is_still_queued(self):
        self.app.release.set()
        connections = [1]
        self.graceful.start_draining(lambda: None, busy_connections=lambda: connections[0])
        self.assertFalse(self.exited.wait(0.3), "a queued request keeps the process alive")
        connections[0] = 0
        self.assertTrue(self.exited.wait(2))

    def test_a_stuck_request_does_not_block_the_exit_forever(self):
        graceful = GracefulShutdown(self.app, grace=0.2, exit=lambda code: self.exited.set())
        request = threading.Thread(target=lambda: list(graceful({}, lambda *a: None)))
        request.start()
        while graceful.active == 0:
            threading.Event().wait(0.01)
        graceful.start_draining(lambda: None)
        self.assertTrue(self.exited.wait(2))
        self.app.release.set()
        request.join()


if __name__ == "__main__":
    unittest.main()
