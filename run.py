"""Start any release of the Apartment Booking System, in any of the ways it supports.

    python3 run.py                      # list every release and how it can run
    python3 run.py 06 web               # checkpoint 06: REST API + Dimora on http://127.0.0.1:8080
    python3 run.py 08 stack             # checkpoint 08: the microservices stack in Docker
    python3 run.py 08 stack --replicas 2
    python3 run.py 03 test              # run the test suite of checkpoint 03

Every release lives in releases/checkpoint-NN-<title>/ and runs on its own: the
launcher only changes into that folder and runs the command its README gives.
Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RELEASES = ROOT / "releases"
PY = sys.executable


@dataclass(frozen=True)
class Release:
    title: str
    modes: dict[str, tuple[str, list[str]]] = field(default_factory=dict)
    folder: str = ""  # sub-folder that holds compose.yaml, when it is not the release root


def unit_tests(*extra: str) -> tuple[str, list[str]]:
    return "run the unit and integration tests", [PY, "-m", "unittest", "discover", "-s", "tests", *extra]


def monolith(title: str, flask_app: str, api: bool = True, docker: str | None = "web") -> Release:
    modes = {"cli": ("interactive terminal client", [PY, "main.py"]), "test": unit_tests()}
    if api:
        modes["api"] = ("REST API and explorer on http://127.0.0.1:8000",
                        [PY, "-m", "flask", "--app", flask_app, "--no-debug", "run",
                         "--host", "127.0.0.1", "--port", "8000", "--no-debugger", "--no-reload"])
    if docker == "web":
        modes["docker"] = ("API in Docker on http://127.0.0.1:8000 (Ctrl+C stops it)",
                           ["docker", "compose", "up", "--build", "web"])
        modes["docker-cli"] = ("terminal client in Docker, with persistent storage",
                               ["docker", "compose", "run", "--rm", "--build", "booking"])
    elif docker == "cli":
        modes["docker"] = ("terminal client in Docker, with persistent storage",
                           ["docker", "compose", "run", "--rm", "--build", "booking"])
    return Release(title, modes)


def microservices(title: str, tests: list[str]) -> Release:
    return Release(title, {
        "stack": ("start every container; Dimora on http://127.0.0.1:8080",
                  ["docker", "compose", "up", "--build", "--detach", "--wait"]),
        "cli": ("terminal client over HTTP, through the gateway",
                ["docker", "compose", "run", "--rm", "--build", "cli"]),
        "logs": ("follow the logs of every container", ["docker", "compose", "logs", "--follow"]),
        "down": ("stop the stack (add --volumes to delete its data)", ["docker", "compose", "down"]),
        "test": ("run the unit tests (needs microservices/requirements.txt)", tests),
        "smoke": ("full system test in a disposable stack (Docker)",
                  [PY, "tests/system/stack_smoke.py"]),
    }, folder="microservices")


CATALOGUE: dict[str, Release] = {
    "01": monolith("Terminal booking application with SQLite", "", api=False, docker=None),
    "02": monolith("Docker Compose, persistent storage and reliability", "", api=False, docker="cli"),
    "03": monolith("Flask REST API, OpenAPI contract and API explorer", "src.web:create_app"),
    "04": monolith("GitHub Actions: tests, coverage and Locust load test", "apartment_booking.web:create_app"),
    "05": monolith("GitLab CI with a self-managed runner", "apartment_booking.web:create_app"),
    "06": monolith("Dimora web client for guests and hosts", "apartment_booking.web:create_app"),
    "07": microservices("Event-driven CQRS microservices (9 containers)",
                        [PY, "-m", "unittest", "discover", "-s", "tests/unit"]),
    "08": microservices("Microservices without a read model (6 containers)",
                        [PY, "-m", "unittest", "discover", "-s", "tests/unit"]),
}
CATALOGUE["06"].modes["web"] = ("REST API + Dimora web client on http://127.0.0.1:8080", [])
CATALOGUE["08"].modes["contract"] = (
    "run the event contract tests", [PY, "-m", "unittest", "discover", "-s", "tests/contract"])


def folder_of(number: str) -> Path:
    """releases/checkpoint-NN-<title>/, found by its number."""
    return next(RELEASES.glob(f"checkpoint-{number}-*"))


def print_catalogue() -> None:
    print(__doc__.split("\n\n")[0], "\n")
    for number, release in CATALOGUE.items():
        print(f"  {number}  {release.title}    {folder_of(number).relative_to(ROOT)}/")
        for mode, (description, _) in release.modes.items():
            print(f"        {mode:<11} {description}")
    print("\nExample: python3 run.py 06 web")


def run(command: list[str], cwd: Path, env: dict[str, str]) -> int:
    if command[0] == "docker" and shutil.which("docker") is None:
        print("Docker is not installed or not on PATH.", file=sys.stderr)
        return 1
    print(f"$ cd {cwd.relative_to(ROOT)} && {' '.join(command)}", flush=True)
    try:
        return subprocess.call(command, cwd=cwd, env=env)
    except KeyboardInterrupt:
        return 130


def run_web(cwd: Path, env: dict[str, str]) -> int:
    """Checkpoint 06: the Flask API in the background and the Dimora dev server in front."""
    api = [PY, "-m", "flask", "--app", "apartment_booking.web:create_app", "--no-debug", "run",
           "--host", "127.0.0.1", "--port", "8000", "--no-debugger", "--no-reload"]
    print(f"$ cd {cwd.relative_to(ROOT)} && {' '.join(api)} &", flush=True)
    server = subprocess.Popen(api, cwd=cwd, env=env)
    try:
        return run([PY, "website-studio/serve.py"], cwd, env)
    finally:
        server.terminate()
        server.wait(timeout=10)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start a release of the Apartment Booking System.",
                                     epilog="Run without arguments to list every release.")
    parser.add_argument("release", nargs="?", help="checkpoint number, e.g. 06 or 8")
    parser.add_argument("mode", nargs="?", help="how to run it, e.g. cli, api, web, stack, test")
    parser.add_argument("--replicas", type=int, default=1,
                        help="08 stack: replicas of each service (2 allows restarts without errors)")
    parser.add_argument("--port", type=int, help="07/08 stack: gateway port on localhost (default 8080)")
    parser.add_argument("extra", nargs=argparse.REMAINDER, help="arguments passed on to the command")
    args = parser.parse_args(argv)

    if not args.release:
        print_catalogue()
        return 0
    number = args.release.zfill(2)
    release = CATALOGUE.get(number)
    if release is None:
        parser.error(f"unknown release {args.release!r}; choose one of {', '.join(CATALOGUE)}")
    if not args.mode or args.mode not in release.modes:
        modes = ", ".join(release.modes)
        if args.mode:
            parser.error(f"checkpoint {number} has no mode {args.mode!r}; choose one of {modes}")
        print(f"Checkpoint {number}: {release.title}\nModes: {modes}")
        return 0

    cwd = folder_of(number) / release.folder
    env = dict(os.environ)
    if args.port:
        env["DIMORA_PORT"] = str(args.port)
    if args.mode == "web":
        return run_web(cwd, env)

    command = list(release.modes[args.mode][1])
    if args.mode == "test" and release.folder:
        # The services import the domain package from the release root.
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(cwd.parent), env.get("PYTHONPATH")]))
    if args.mode == "contract":
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(cwd.parent), env.get("PYTHONPATH")]))
    if args.mode == "stack" and args.replicas > 1:
        if number != "08":
            parser.error("--replicas is supported by checkpoint 08 only")
        command += ["--scale", f"apartment-service={args.replicas}",
                    "--scale", f"reservation-service={args.replicas}"]
    return run(command + [arg for arg in args.extra if arg != "--"], cwd, env)


if __name__ == "__main__":
    raise SystemExit(main())
