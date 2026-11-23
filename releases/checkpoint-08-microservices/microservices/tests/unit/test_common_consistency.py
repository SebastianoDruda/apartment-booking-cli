import unittest

from dimora.common.consistency import format_token, parse_tokens, wait_until_visible


class ConsistencyTokenTests(unittest.TestCase):
    def test_format_and_parse(self):
        self.assertEqual(format_token("booking", 7, 2), "booking:7@2")
        self.assertEqual(parse_tokens("booking:7@2, apartment:12@3"),
                         [("booking", 7, 2), ("apartment", 12, 3)])
        self.assertEqual(parse_tokens(None), [])
        self.assertEqual(parse_tokens("  "), [])

    def test_malformed_headers_are_rejected(self):
        for header in ("booking:7", "guest:1@1", "booking:0@1", "booking:1@x", ",".join(["booking:1@1"] * 21)):
            with self.subTest(header=header), self.assertRaises(ValueError):
                parse_tokens(header)
        with self.assertRaises(ValueError):
            format_token("guest", 1, 1)

    def test_waits_until_the_copy_catches_up(self):
        clock = {"now": 0.0}
        versions = {("booking", 7): None}

        def sleep(seconds):
            clock["now"] += seconds
            if clock["now"] >= 0.1:
                versions[("booking", 7)] = 2

        fresh = wait_until_visible([("booking", 7, 2)], lambda a, i: versions[(a, i)], timeout=1,
                                   clock=lambda: clock["now"], sleep=sleep)
        self.assertTrue(fresh)
        self.assertLess(clock["now"], 0.2)

    def test_gives_up_after_the_timeout(self):
        clock = {"now": 0.0}

        def sleep(seconds):
            clock["now"] += seconds

        fresh = wait_until_visible([("apartment", 1, 5)], lambda a, i: 4, timeout=0.5,
                                   clock=lambda: clock["now"], sleep=sleep)
        self.assertFalse(fresh)
        self.assertGreaterEqual(clock["now"], 0.5)


if __name__ == "__main__":
    unittest.main()
