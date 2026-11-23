# Contributing

This project is maintained by Sebastiano Druda, Tom Springer and Jacob Wieser.
The CLI uses Python 3.10+ and the standard library. The HTTP interface and full
test suite also require the pinned Flask dependency in `requirements.txt`.

## Local setup

Follow the [README](README.md#requirements-and-installation), then run the existing
suite from the repository root before making changes. Create a virtual environment
and install `python -m pip install -r requirements.txt` using your chosen interpreter.

On MacBook / macOS:

```bash
python3 -m unittest discover -s tests -v
```

On Windows:

```powershell
py -3 -m unittest discover -s tests -v
```

If your selected interpreter is available as `python`, use that instead. See the
[platform-specific launch instructions](README.md#starting-the-application) for
running the app and using an optional virtual environment. No package installation
is required for the CLI alone.

## Docker checks

With Docker running, validate container changes using:

```bash
docker compose config --quiet
docker build --target test --tag apartment-booking-cli:test .
docker compose build
python3 tests/docker_smoke.py
python3 tests/docker_web_smoke.py
```

On Windows use `py -3` for the Python commands. The smoke check uses a random Compose
project and disposable volume, leaving normal user data alone. Do not run cleanup
commands with `--volumes` against the user's usual project. See the
[Docker guide](README.md#running-with-docker-and-compose) for interactive use and backups.

## Branch workflow

Start with a clean working tree. When upgrading an older checkout that tracked the
database, follow the [database backup/upgrade instructions](README.md#database-location-backup-and-reset)
**before pulling**; the update may remove the formerly tracked file.

```bash
git switch main
git pull --ff-only
git switch -c docs/describe-your-change
```

Choose a descriptive branch name appropriate to the work. Keep the change focused,
run the checks below, and review the diff before staging specific files:

```bash
git status --short
git diff --check
git diff
git add README.md
git diff --cached
git commit -m "docs: clarify setup instructions"
git push -u origin HEAD
```

The filename and message above are examples: stage only the files you intend to
include. Open a pull request against `main`, describe the behaviour or documentation
change, and record the checks actually performed.

## Repository conventions

- Keep the existing separation: launchers in `main.py` and `src/main.py`, terminal
  interaction in `src/cli.py`, persistence/business rules in `src/database.py`, and
  automated checks in `tests/` (`test_booking_system.py` for the original workflows,
  `test_robustness.py` for robustness regressions, and `test_database_path.py` for
  storage configuration). `test_web.py` covers HTTP behaviour; the two Docker smoke
  scripts run CLI and web container checks separately.
- Preserve existing commands and aliases unless a behaviour change is intentional
  and documented. Avoid unrelated renames, moves, formatting or refactors.
- Follow the surrounding Python style, type hints and docstrings.
- Use the standard library where practical. Discuss new runtime dependencies before
  introducing them; the current application has none.
- Add or update meaningful tests when changing behaviour. Documentation-only changes
  do not need new tests that merely repeat the documentation.
- Update the README when commands, validation, setup or persistence behaviour change.
  Record release-relevant changes in the changelog without rewriting past releases.

## Data handling

`apartment_booking.db` is local application data and is ignored by Git, along with
backup databases and SQLite sidecar files. New clones create an empty database on
first launch. Do not force-add database files. Older revisions, including Checkpoint 01,
still contain the formerly tracked database; back up existing data before updating
or switching to/from those revisions.

Use in-memory or temporary databases for tests, following the existing test suite.
Back up your database before manual experiments. Do not include personal bookings,
generated caches, credentials or unrelated database changes in a commit. Do not
discard a modified database until you have preserved any data you need.

## Validation before review

```bash
python -m unittest discover -s tests -v
git diff --check
```

For CLI behaviour changes, also manually check the affected commands and roles.
For terminal-input changes, check the relevant real terminals: simulated completion
tests cannot fully validate Windows `msvcrt` or macOS/Linux `readline` behaviour.
Keep availability checks and mutations inside the write transaction when changing
database operations. Retain concurrency and rollback tests; do not replace them
with mocks that skip SQLite's actual locking behaviour.
Document platform limitations or checks you could not run.

The GitHub Actions workflow installs Flask and runs the full suite on Python 3.10 and 3.14 across
Linux, macOS and Windows. Review its results before merging.

## Reporting issues

Include the operating system, Python version, command/input sequence, expected result,
actual output and whether a clean or existing database reproduces the problem.
Use fictitious names and addresses when sharing examples; a full database is usually
unnecessary. For private access or credential problems, contact the maintainers
without posting credentials.

## HTTP development

Use `create_app({"DATABASE_PATH": temporary_path, "TESTING": True})` with Flask's
client for API tests. Each test must own a temporary SQLite file. Do not use the
normal Docker project for write tests; the web smoke script assigns its own project
name, volume and temporary loopback port. Never reset the existing user volume.

Keep SQL and booking validation in `src/database.py`. HTTP routes only translate
input/output and errors. Domain errors remain `ValueError` subclasses so CLI callers
continue to work. No authentication or debugger is exposed; maintain loopback-only
host publishing. Work on `feature/flask-http-interface` and submit a PR against
`main`; do not merge automatically.

## Release convention

Checkpoint 02 is published as `checkpoint-02` with the title **Checkpoint 02**.
Checkpoint 01 remains available as `checkpoint-01`.
Release tags identify tested commits and should not be moved or overwritten.
For future releases, update the changelog, verify the selected commit's checks,
and publish notes describing changes and known limitations. Repository source
archives are generated by GitHub; no binary packaging is currently configured.
