"""Stress test of the microservices stack in a disposable Compose project.

Run from anywhere (Docker required):
    python3 microservices/tests/system/stack_stress.py [--report FILE] [--keep]

Phases (all through the nginx gateway, like the real clients), with two replicas
of each service:
  1. burst      1,000 listings created by 48 concurrent clients
  2. storm      4,000 booking attempts, 70 % on 100 "hot" listings, plus 50 races
                where 10 clients book the very same slot at the same instant
  3. mixed      90 s of mixed traffic (reads, bookings, changes, cancellations,
                price changes, removals with cascade) while chaos hits the stack:
                RabbitMQ down 20 s, then one replica of each service restarted
  4. converge   time until the reservation copy matches the apartment database,
                then a row-by-row comparison and the invariants
The script exits with status 1 if an invariant breaks or a request fails with a
server error. The project and its volumes are removed at the end unless --keep.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

COMPOSE_DIR = Path(__file__).resolve().parents[2]
KEEP = "--keep" in sys.argv
REPORT = Path(sys.argv[sys.argv.index("--report") + 1]) if "--report" in sys.argv else None
REPLICAS = 2
WORKERS = 48
rng = random.Random(1000)
rng_lock = threading.Lock()

# ------------------------------------------------------------------ stack


class Stack:
    def __init__(self) -> None:
        self.project = "dimora-stress-" + uuid.uuid4().hex[:8]
        self.env = dict(os.environ, DIMORA_PORT="0", DIMORA_RABBITMQ_UI_PORT="0")
        self.base = ""

    def compose(self, *args: str, timeout: int = 300) -> str:
        result = subprocess.run(["docker", "compose", "--project-name", self.project, *args],
                                cwd=COMPOSE_DIR, env=self.env, text=True,
                                capture_output=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(f"compose {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}")
        return result.stdout

    def sql(self, service: str, database: str, query: str) -> str:
        return self.compose("exec", "-T", service, "psql", "-U", "dimora", "-d", database,
                            "-tAc", query).strip()

    def queues(self) -> dict[str, int]:
        out = self.compose("exec", "-T", "rabbitmq", "rabbitmqctl", "list_queues", "-q", "name", "messages")
        rows = (line.split() for line in out.splitlines() if line.strip())
        return {row[0]: int(row[1]) for row in rows if len(row) == 2 and row[1].isdigit()}


stack = Stack()

# ------------------------------------------------------------------ http + metrics

lat: dict[str, list[float]] = defaultdict(list)       # op -> seconds
codes: dict[str, Counter] = defaultdict(Counter)      # phase -> Counter("op status")
served_by: Counter = Counter()
consistency: Counter = Counter()
server_error_log: list[str] = []  # when and where each server error happened
metrics_lock = threading.Lock()
started_at = time.monotonic()
phase = "setup"


def http(op: str, path: str, method: str = "GET", payload: dict | None = None,
         headers: dict | None = None, timeout: float = 30):
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request(stack.base + path, data=body, method=method,
                  headers={"Content-Type": "application/json", **(headers or {})})
    started = time.perf_counter()
    try:
        with urlopen(req, timeout=timeout) as resp:
            status, hdrs, raw = resp.status, dict(resp.headers), resp.read()
    except HTTPError as exc:
        status, hdrs, raw = exc.code, dict(exc.headers), exc.read()
    except (URLError, ConnectionError, TimeoutError, OSError, HTTPException) as exc:
        status, hdrs, raw = 0, {}, str(exc).encode()
    elapsed = time.perf_counter() - started
    with metrics_lock:
        lat[op].append(elapsed)
        codes[phase][f"{op} {status}"] += 1
        if "X-Served-By" in hdrs:
            served_by[hdrs["X-Served-By"]] += 1
        if "X-Consistency" in hdrs:
            consistency[hdrs["X-Consistency"]] += 1
        if status in (0, 500, 502, 503, 504):
            server_error_log.append(f"t={time.monotonic() - started_at:6.1f}s {phase} {method} {path[:40]} "
                                    f"{status} {raw[:80]!r}")
    try:
        data = json.loads(raw) if raw else None
    except ValueError:
        data = None
    return status, hdrs, data


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))]


# ------------------------------------------------------------------ data generators

CITIES = [("Italia", "Bolzano", ["Via dei Portici", "Via Museo", "Corso Libertà"]),
          ("Italia", "Merano", ["Via delle Corse", "Via Cavour"]),
          ("Italia", "Ortisei", ["Strada Rezia", "Strada Promenade"]),
          ("Italia", "Venezia", ["Fondamenta delle Zattere", "Calle Larga XXII Marzo"]),
          ("Italia", "Roma", ["Via Margutta", "Via dei Coronari"]),
          ("Österreich", "Innsbruck", ["Maria-Theresien-Straße", "Anichstraße"]),
          ("Österreich", "Wien", ["Mariahilfer Straße", "Praterstraße"]),
          ("Deutschland", "München", ["Leopoldstraße", "Türkenstraße"]),
          ("Schweiz", "Zermatt", ["Bahnhofstrasse", "Hofmattstrasse"])]
TYPES = ["Studio", "Apartment", "Loft", "Casa", "Chalet", "Penthouse", "Residence", "Ferienwohnung"]
WORDS = ["Edelweiss", "Rosengarten", "Laurin", "Bellavista", "Sole", "Panorama", "Alpenblick", "Dolomiti",
         "Al Duomo", "Sul Lago", "Belvedere", "Enzian", "Latemar", "Sciliar", "Margherita", "Aurora"]
FIRST = ["Anna", "Lukas", "Sofia", "Matteo", "Laura", "Thomas", "Giulia", "Florian", "Elena", "Jonas",
         "Emma", "Oliver", "Charlotte", "Pierre", "Camille", "Daan", "Marta", "Pablo", "Ingrid", "Erik"]
LAST = ["Huber", "Gruber", "Rossi", "Ferrari", "Mair", "Pichler", "Bianchi", "Hofer", "Moser", "Kofler",
        "Schmidt", "Müller", "Smith", "Taylor", "Dubois", "de Vries", "García", "Larsen", "Conti", "Thaler"]


def listing(i: int) -> dict:
    country, city, streets = CITIES[i % len(CITIES)]
    return {"name": f"{TYPES[i % len(TYPES)]} {WORDS[(i // 8) % len(WORDS)]} {i:04d}",
            "country": country, "city": city, "street_and_number": f"{streets[i % len(streets)]} {1 + i % 150}",
            "max_people": 1 + (i * 7) % 8, "price_per_night": float(60 + (i * 37) % 340)}


def guest() -> str:
    with rng_lock:
        return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


# shared client-side state
apartments: dict[str, dict] = {}      # name -> {"max_people"}
active: list[tuple[str, str, str, int]] = []   # (apt, start, end, people) we believe are active
state_lock = threading.Lock()


def random_slot(hot: bool) -> tuple[str, str, str, int]:
    with rng_lock:
        names = hot_names if hot else all_names
        apt = rng.choice(names)
        base = date(2027, 6, 1) if hot else date(2027, 1, 1)
        span = 92 if hot else 700
        start = base + timedelta(days=rng.randrange(span))
        nights = rng.choice([2, 3, 4, 5, 7])
        people = rng.randint(1, apartments[apt]["max_people"])
    return apt, start.isoformat(), (start + timedelta(days=nights)).isoformat(), people


def create_booking(slot) -> int:
    apt, start, end, people = slot
    status, hdrs, _ = http("booking.create", "/api/bookings", "POST",
                           {"apartment_name": apt, "start_date": start, "end_date": end,
                            "booker_name": guest(), "num_people": people})
    if status == 201:
        with state_lock:
            active.append(slot)
    return status


# ------------------------------------------------------------------ phases


def phase_burst() -> None:
    global phase
    phase = "1 burst"

    def make(i: int) -> None:
        body = listing(i)
        status, _, _ = http("apartment.create", "/api/apartments", "POST", body)
        if status == 201:
            with state_lock:
                apartments[body["name"]] = {"max_people": body["max_people"]}

    with ThreadPoolExecutor(WORKERS) as pool:
        list(pool.map(make, range(1000)))


def phase_storm() -> dict:
    global phase
    phase = "2 storm"
    with ThreadPoolExecutor(WORKERS) as pool:
        list(pool.map(lambda i: create_booking(random_slot(hot=rng.random() < 0.7)), range(4000)))

    # Races: 10 clients book the same slot at the same instant; exactly one must win.
    wins = []
    for _ in range(50):
        slot = random_slot(hot=False)
        barrier = threading.Barrier(10)

        def racer(_):
            barrier.wait()
            return create_booking(slot)

        with ThreadPoolExecutor(10) as pool:
            results = list(pool.map(racer, range(10)))
        wins.append(results.count(201))
    return {"races": len(wins), "one_winner": wins.count(1),
            "no_winner_slot_already_taken": wins.count(0),
            "two_or_more_winners": sum(1 for w in wins if w > 1)}


chaos_log: list[str] = []


def chaos(t0: float) -> None:
    def at(seconds: float, label: str, *args: str) -> None:
        while time.monotonic() - t0 < seconds:
            time.sleep(0.2)
        stack.compose(*args)
        chaos_log.append(f"t={time.monotonic() - started_at:6.1f}s  {label}")

    def restart(seconds: float, container: str) -> None:
        while time.monotonic() - t0 < seconds:
            time.sleep(0.2)
        subprocess.run(["docker", "restart", f"{stack.project}-{container}"],
                       check=True, capture_output=True, timeout=120)
        chaos_log.append(f"t={time.monotonic() - started_at:6.1f}s  {container} restarted")

    at(15, "RabbitMQ stopped", "stop", "rabbitmq")
    at(35, "RabbitMQ started", "start", "rabbitmq")
    restart(50, "reservation-service-1")
    restart(65, "apartment-service-1")


def phase_mixed(seconds: int = 90) -> None:
    global phase
    phase = "3 mixed+chaos"
    t0 = time.monotonic()
    chaos_thread = threading.Thread(target=chaos, args=(t0,), daemon=True)
    chaos_thread.start()
    removed = [0]

    def worker(_):
        while time.monotonic() - t0 < seconds:
            with rng_lock:
                r = rng.random()
            if r < 0.20:
                http("read.apartments", "/api/apartments")
            elif r < 0.35:
                http("read.bookings", "/api/bookings")
            elif r < 0.55:
                apt, start, end, people = random_slot(hot=False)
                http("read.availability", "/api/availability?" + urlencode(
                    {"start_date": start, "end_date": end, "num_people": people}))
            elif r < 0.72:
                slot = random_slot(hot=rng.random() < 0.5)
                apt, start, end, people = slot
                status, hdrs, _ = http("booking.create", "/api/bookings", "POST",
                                       {"apartment_name": apt, "start_date": start, "end_date": end,
                                        "booker_name": guest(), "num_people": people})
                if status == 201:
                    with state_lock:
                        active.append(slot)
                    token = hdrs.get("X-Consistency-Token")
                    if token:  # read-your-writes under load
                        http("read.own-write", "/api/bookings", headers={"X-Wait-For": token}, timeout=10)
            elif r < 0.82:
                with state_lock:
                    if not active:
                        continue
                    slot = active.pop(rng.randrange(len(active)))
                apt, start, end, people = slot
                new_start = date.fromisoformat(start) + timedelta(days=30)
                new_end = date.fromisoformat(end) + timedelta(days=30)
                status, _, _ = http("booking.change", "/api/bookings", "PATCH",
                                    {"apartment_name": apt, "start_date": start, "end_date": end,
                                     "new_start_date": new_start.isoformat(),
                                     "new_end_date": new_end.isoformat(), "num_people": people})
                with state_lock:
                    active.append((apt, new_start.isoformat(), new_end.isoformat(), people)
                                  if status == 200 else slot)
            elif r < 0.90:
                with state_lock:
                    if not active:
                        continue
                    slot = active.pop(rng.randrange(len(active)))
                apt, start, end, _ = slot
                http("booking.cancel", "/api/bookings", "DELETE",
                     {"apartment_name": apt, "start_date": start, "end_date": end})
            elif r < 0.98:
                with rng_lock:
                    apt = rng.choice(all_names)
                    price = float(rng.randrange(50, 450, 5))
                http("apartment.price", f"/api/apartments/{quote(apt, safe='')}/price", "PATCH",
                     {"price_per_night": price})
            else:
                with state_lock:
                    if removed[0] >= 40:
                        continue
                    removed[0] += 1
                with rng_lock:
                    apt = rng.choice([n for n in all_names if n not in hot_set])
                status, _, _ = http("apartment.remove", f"/api/apartments/{quote(apt, safe='')}", "DELETE")

    with ThreadPoolExecutor(WORKERS) as pool:
        list(pool.map(worker, range(WORKERS)))
    chaos_thread.join(timeout=120)


def copy_matches() -> tuple[bool, int, int]:
    """The reservation copy holds every apartment, with its price, as the apartment service."""
    owner = set(stack.sql("apartment-db", "apartments",
                          "SELECT id || '|' || price_per_night FROM apartments WHERE removed_at IS NULL"
                          ).splitlines())
    copy = set(stack.sql("reservation-db", "reservations",
                         "SELECT id || '|' || price_per_night FROM apartment_copies WHERE NOT removed"
                         ).splitlines())
    return owner == copy, len(owner), len(copy)


def api_matches() -> tuple[bool, int]:
    """What the gateway serves equals what the reservation database holds."""
    rows = set(stack.sql("reservation-db", "reservations",
                         "SELECT b.id FROM bookings b JOIN apartment_copies a ON a.id = b.apartment_id"
                         " WHERE b.status = 'active' AND NOT a.removed").splitlines())
    _, _, served = http("verify", "/api/bookings", timeout=60)
    return rows == {str(item["id"]) for item in served["data"]}, len(rows)


def phase_converge() -> dict:
    global phase
    phase = "4 converge"
    t0 = time.monotonic()
    while True:
        q = stack.queues()
        pending = int(stack.sql("apartment-db", "apartments",
                                "SELECT count(*) FROM apartments WHERE published_version < version"))
        same, owner, copy = copy_matches()
        if same and pending == 0 and all(v == 0 for k, v in q.items() if k != "dimora.dead-letter"):
            break
        if time.monotonic() - t0 > 300:
            break
        time.sleep(1)
    elapsed = time.monotonic() - t0
    served_ok, active = api_matches()
    removed = stack.sql("apartment-db", "apartments",
                        "SELECT coalesce(string_agg(id::text, ','), '0') FROM apartments WHERE removed_at IS NOT NULL")
    overlaps = stack.sql("reservation-db", "reservations",
                         "SELECT count(*) FROM bookings x JOIN bookings y ON x.apartment_id = y.apartment_id"
                         " AND x.id < y.id AND x.status = 'active' AND y.status = 'active'"
                         " AND daterange(x.start_date, x.end_date) && daterange(y.start_date, y.end_date)")
    over_capacity = stack.sql("reservation-db", "reservations",
                              "SELECT count(*) FROM bookings b JOIN apartment_copies a ON a.id = b.apartment_id"
                              " WHERE b.status = 'active' AND b.num_people > a.max_people")
    orphans = stack.sql("reservation-db", "reservations",
                        f"SELECT count(*) FROM bookings WHERE status = 'active' AND apartment_id IN ({removed})")
    totals = stack.sql("reservation-db", "reservations",
                       "SELECT count(*) FILTER (WHERE status = 'active'), count(*) FILTER (WHERE status = 'cancelled')"
                       " FROM bookings")
    return {"converged": same, "seconds_to_converge": round(elapsed, 1),
            "apartments_owner_vs_copy": [owner, copy],
            "gateway_serves_the_database": served_ok, "active_bookings": active,
            "outbox_pending": pending, "queues": q,
            "overlapping_active_bookings": int(overlaps), "bookings_over_capacity": int(over_capacity),
            "active_bookings_of_removed_apartments": int(orphans),
            "bookings_active|cancelled": totals}


# ------------------------------------------------------------------ main


def main() -> int:
    global all_names, hot_names, hot_set
    started = time.monotonic()
    report: dict = {"project": stack.project, "replicas": REPLICAS}
    failed = False
    try:
        print("Building and starting a disposable stack ...", flush=True)
        stack.compose("up", "--build", "--detach", "--wait",
                      "--scale", f"apartment-service={REPLICAS}",
                      "--scale", f"reservation-service={REPLICAS}", timeout=900)
        stack.base = "http://" + stack.compose("port", "gateway", "8080").strip()
        print(f"Gateway at {stack.base}", flush=True)

        t = time.monotonic()
        phase_burst()
        report["1_burst_s"] = round(time.monotonic() - t, 1)
        all_names = sorted(apartments)
        hot_names = all_names[:100]
        hot_set = set(hot_names)
        print(f"1 burst: {len(apartments)} listings in {report['1_burst_s']} s", flush=True)

        t = time.monotonic()
        report["2_races"] = phase_storm()
        report["2_storm_s"] = round(time.monotonic() - t, 1)
        print(f"2 storm: done in {report['2_storm_s']} s, races {report['2_races']}", flush=True)

        t = time.monotonic()
        phase_mixed()
        report["3_mixed_s"] = round(time.monotonic() - t, 1)
        report["3_chaos"] = chaos_log
        print("3 mixed+chaos:\n  " + "\n  ".join(chaos_log), flush=True)

        report["4_converge"] = result = phase_converge()
        print("4 converge:", json.dumps(result), flush=True)
        server_errors = {key: n for c in codes.values() for key, n in c.items()
                         if key.split()[-1] in ("0", "500", "502", "503", "504")}
        report["server_errors"] = server_errors
        report["server_error_log"] = server_error_log
        broken = [name for name in ("overlapping_active_bookings", "bookings_over_capacity",
                                    "active_bookings_of_removed_apartments") if result[name]]
        if not result["converged"] or not result["gateway_serves_the_database"]:
            broken.append("convergence")
        if report["2_races"]["two_or_more_winners"]:
            broken.append("double booking in a race")
        print(f"Server errors: {server_errors or 'none'}", flush=True)
        for line in server_error_log:
            print("  " + line, flush=True)
        if broken or server_errors:
            failed = True
            print(f"FAILED: {broken or ''} {server_errors or ''}", flush=True)
    finally:
        report["latency_ms"] = {op: {"n": len(v), "p50": round(pct(v, 50) * 1000), "p95": round(pct(v, 95) * 1000),
                                     "p99": round(pct(v, 99) * 1000), "max": round(max(v) * 1000)}
                                for op, v in sorted(lat.items()) if v}
        report["status_codes"] = {p: dict(sorted(c.items())) for p, c in codes.items()}
        report["served_by"] = dict(served_by)
        report["consistency_header"] = dict(consistency)
        report["total_s"] = round(time.monotonic() - started, 1)
        if REPORT:
            REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False))
            print(f"Report: {REPORT}", flush=True)
        else:
            print(json.dumps({k: report[k] for k in ("latency_ms", "status_codes")}, indent=1), flush=True)
        if KEEP:
            print(f"Stack kept: docker compose -p {stack.project} down -v", flush=True)
        else:
            stack.compose("down", "--volumes", "--remove-orphans", timeout=300)
            print("Disposable stack removed.", flush=True)
    return 1 if failed else 0


all_names: list[str] = []
hot_names: list[str] = []
hot_set: set[str] = set()

if __name__ == "__main__":
    raise SystemExit(main())
