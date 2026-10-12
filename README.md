# Apartment Booking CLI

A local apartment and reservation manager operated through numbered terminal menus.
SQLite preserves apartments and booking history across restarts; Rich renders readable
tables and prompts. The application works offline after dependencies are installed.
Built for the Continuous Integration for Software Development course.

## Features

- Add, view, update and archive apartments with capacity and EUR nightly prices.
- Create, view, change and cancel reservations without deleting their history.
- Search availability by dates and guest count; prevent overlapping confirmed bookings.
- Load a deterministic demo or deliberately reset the database to that demo.
- Keyboard-only, **terminal-only** operation, with confirmations and recoverable errors.

There is no browser interface, server, API, account requirement or telemetry.

## Requirements and setup

Python **3.12, 3.13 or 3.14**, Git for cloning, and pip. The CI matrix runs the full
suite on Ubuntu for these Python versions and Windows with Python 3.13.
SQLite is included with standard Python installations.

The [GitHub repository](https://github.com/SebastianoDruda/apartment-booking-cli)
is private. The professor must be granted access before cloning. A local delivery
folder can also be used directly.

```bash
git clone https://github.com/SebastianoDruda/apartment-booking-cli.git
cd apartment-booking-cli
python -m venv .venv
```

On macOS/Linux, use `python3` if `python` is unavailable, then activate:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

On Windows Command Prompt, use `.venv\Scripts\activate.bat` instead.
If activation is restricted, call `.venv\Scripts\python.exe` directly on Windows,
or `.venv/bin/python` on macOS/Linux.

Install and launch **from the project root**:

```bash
python -m pip install -e '.[dev]'
python -m apartment_booking
```

For Windows Command Prompt use double quotes: `python -m pip install -e ".[dev]"`.
The first launch creates an **empty** `data/apartment_booking.db`. Subsequent
launches preserve records. No sample data is loaded automatically.

## Using the menus

```text
APARTMENT BOOKING
Local apartment and reservation management

MAIN MENU
  1. Apartments
  2. Bookings
  3. Search availability
  4. Demo & data
  0. Exit
```

1. Choose **Apartments → Add apartment**, enter a name, city, capacity (1–20) and
   price such as `125.50`. Review the summary and select **1. Confirm**.
2. Choose **Bookings → Create booking**. Select an apartment by row number, enter
   the guest and dates, review the details and confirm.
3. Choose **Search availability** and enter dates and guests (blank defaults to 1).
4. Use **Bookings → Change booking** to edit a confirmed reservation. A blank field
   keeps its displayed current value. The apartment cannot be changed: cancel the
   reservation and create another instead.
5. Use **Bookings → Cancel booking** to release its dates. All reservations,
   including cancelled ones, remain visible under **View bookings**.

Apartment views default to active records and offer explicit all/archived filters.
**Remove means archive**, preserving historical reservations and foreign keys. A
confirmed booking with check-out after today's local date prevents archiving; the
error identifies blocking guests and dates. Reducing capacity cannot invalidate
confirmed ongoing or future reservations. Archived apartments cannot be edited or
used for new/changed bookings, and never appear in availability results.

**0. Back** cancels forms where advertised. **0. Cancel** declines confirmation.
Invalid fields reprompt; failed operations offer retry/back. Ctrl+C and EOF
(Ctrl+D on macOS/Linux, Ctrl+Z then Enter on Windows) exit gracefully.

## Demonstration data

Choose **Demo & data → Load sample data** on an empty database. The UTF-8
`data/demo.json` contains 5 apartments in Bolzano, Venice, Trento, Riva del Garda and
Verona, plus 6 fictitious reservations, including one cancelled reservation.
Fixed UUIDs and static 2027 dates make the fixture reproducible at any time.

Try these cases after loading:

| Dates | Guests | Expected availability |
| --- | --- | --- |
| 2027-06-12 to 2027-06-14 | 1 | Garden Loft and Old Town Terrace |
| 2027-06-12 to 2027-06-14 | 6 | None: Lakeside Retreat is occupied |
| 2027-08-01 to 2027-08-03 | 1 | All 5 apartments |

Mountain View has a confirmed stay from June 10 to June 15 and another from June
15 to June 18. A request for June 12–16 is rejected. Cancelling Alex Morgan's
reservation releases June 10–15 without affecting the consecutive stay.

Loading twice is refused without modification. **Reset database to sample data**
warns that **all apartments and bookings will be replaced** and requires typing
exactly `RESET`. Any other response cancels. The entire fixture is validated in
disposable memory using the same schema, validators and conflict query before any
live data is changed. Replacement is one transaction and rolls back on failure.
Missing, malformed, invalid-reference, duplicate-ID or conflicting fixtures cannot
partially replace the live database. The fixture is an import source, not live data.

## Date and price rules

Dates must be real calendar dates in `YYYY-MM-DD` format. Check-out must be later
than check-in; historical bookings are allowed. Stays occupy **[check-in, check-out)**:
the check-out day is free. A June 10–15 stay permits another starting June 15.
Intervals overlap exactly when `existing.check_in < requested.check_out` **and**
`requested.check_in < existing.check_out`. Only confirmed bookings in the same
apartment block a request; editing excludes the reservation itself.

Nightly prices are positive EUR amounts with up to two decimal places, parsed with
`Decimal` and stored as integer cents. They describe the apartment; reservation
totals, payments and invoices are outside this version's scope.

## Persistence and concurrency

The default database is `data/apartment_booking.db`, relative to the **current
working directory**. Always launch from the project root, including after editable
installation. **Demo & data → View storage information** shows its absolute path,
record counts and the available fixture path.

To override the database on macOS/Linux:

```bash
APARTMENT_BOOKING_DB=/absolute/path/bookings.db python -m apartment_booking
```

On Windows PowerShell:

```powershell
$env:APARTMENT_BOOKING_DB = 'C:\data\bookings.db'
python -m apartment_booking
```

Every connection enables foreign keys and a finite 5-second busy timeout. Writes
use explicit `BEGIN IMMEDIATE` with `isolation_level=None`; capacity, archive and
overlap checks occur after acquiring the write reservation and before commit.
Competing writers therefore recheck committed data and cannot both book conflicting
dates through the application. Failures roll back, and connections close even on
interrupt. Availability is a read snapshot, not a reservation; saving rechecks it.

Only two tables are used, with an index on booking apartment/status/dates, CHECK
constraints and restricted foreign-key deletion. SQL values are parameterized.
Direct edits with external SQLite tools bypass service rules and are unsupported.
Generated databases, journals, caches and virtual environments are ignored by Git.

## Architecture

```text
python -m apartment_booking
           |
           v
cli: menus, prompts, tables, confirmations
           |
           v
services: apartments, bookings, demo import
           |
           v
storage: repositories, connections, transactions, schema
           |
           v
SQLite (local file)

models + validation + errors are shared domain building blocks.
```

Frozen dataclasses describe records. Services receive their database explicitly and
never perform terminal I/O. The storage layer has no Rich dependency. A single
repository conflict query is shared by creation, changes, search and fixture
validation. This keeps booking invariants testable without menus or a server.

## Tests and quality checks

Install the dev extra above, then run from the root:

```bash
ruff check .
ruff format --check .
pytest --cov=apartment_booking --cov-report=term-missing --cov-fail-under=80
```

Use `ruff format .` to apply formatting. Tests use temporary databases only and
override `APARTMENT_BOOKING_DB`; they never reset the operator's database. Coverage
includes branches and must reach 80%. Tests cover validation, half-open boundaries,
capacity and archive restrictions, cancellation, persistence, atomic fixture reset,
rollback on injected storage failures, busy handling and competing connections.
Subprocess smoke tests exercise the real module entry point with scripted input.

## Continuous integration

`.github/workflows/ci.yml` runs on pushes to `main` and pull requests targeting
`main`, with `contents: read` permission. Every job installs dependencies, checks
Ruff lint/format, and runs the coverage-enabled full test suite. The matrix covers
Python 3.12/3.13/3.14 on Ubuntu and 3.13 on Windows; no required step ignores errors.
There is no deployment step. A local pass does not imply a remote Actions run.
The workflow uses maintained [checkout](https://github.com/actions/checkout/releases)
and [setup-python](https://github.com/actions/setup-python/releases) v7 actions.

## Project tree

```text
.github/workflows/ci.yml
data/demo.json
docs/PRD.md
src/apartment_booking/
  __main__.py                 # startup and graceful shutdown
  models.py, errors.py, validation.py
  cli/                       # menu.py, prompts.py, display.py
  services/                  # apartments.py, bookings.py, demo.py
  storage/                   # database.py, repositories.py, schema.sql
tests/
  conftest.py
  unit/
  integration/
  e2e/
.gitignore
pyproject.toml
README.md
```

## Limitations

One local operator; no authentication, multiple roles, synchronization, web UI,
external infrastructure, reporting, payments, notifications or unarchive action.
No migration engine: schema evolution is outside v1. Fixtures are loaded from
`data/demo.json` under the project root; this is a checkout-based application, not
a standalone binary. SQLite write serialization protects application operations,
but the UI does not implement collaborative editing or optimistic version checks.

## Troubleshooting

- **Python not found or too old:** install Python 3.12–3.14 and check
  `python --version` (or `python3 --version` / `py --version`).
- **Module/dependency missing:** activate the same environment used for installation
  and rerun `python -m pip install -e '.[dev]'` from the project root.
- **Cannot open database / permissions:** check the displayed path, directory write
  permissions and available disk space. Use `APARTMENT_BOOKING_DB` for a writable
  location. Startup failures exit with status 1 and a helpful message.
- **Database is busy:** another process holds a transaction. Close that operation
  and retry. A timed-out write reports an error and saves no partial changes.
- **Damaged/incompatible database:** preserve a backup and choose a new database
  path. Startup never drops or silently rebuilds existing tables.
- **Demo fixture missing:** launch from the root containing `data/demo.json`.
- **Terminal colors or width:** set `NO_COLOR=1` to disable colors; status words
  remain visible. Tables wrap long content and group related fields vertically.
- **Unexpected failure:** technical diagnostics go to stderr and the program exits
  nonzero. Include that diagnostic when reporting the problem, without guest data.

The full implementation requirements are in [docs/PRD.md](docs/PRD.md).
