# Apartment Booking CLI — Product Requirements Document

**Document type:** Implementation-ready PRD for Codex  
**Version:** 1.0  
**Date:** 12 October 2026  
**Course:** Continuous Integration for Software Development  
**Target repository:** `SebastianoDruda/apartment-booking-cli` (private, unless the repository owner explicitly changes visibility)  
**Status:** Approved product direction; implement and validate against the acceptance criteria below.

---

## 0. Execution instructions for Codex

Build the **complete, working application** described in this document. Do not stop after scaffolding or generating examples. Implement source code, SQLite schema, interactive menus, demo JSON, tests, GitHub Actions workflow, complete README and this PRD in the repository. Follow the scope precisely; avoid adding unrelated features. Make reasonable implementation decisions where this PRD leaves room, favoring readability and minimal complexity.

Execute the project locally, run formatting, linting, tests and an interactive smoke test with scripted input. Resolve failures before delivery. Initialize Git if needed, commit all intended source files, and, **if authenticated and authorized**, create the private GitHub repository `SebastianoDruda/apartment-booking-cli`, set `main` as the default branch and push the verified implementation. Do **not** claim a remote repository, push, successful CI run or passing test unless confirmed. Never overwrite an existing repository or use a force push. If GitHub creation/push is blocked, leave a clean local commit and report the exact blocker and remaining command(s).

**Definition of done:** All mandatory functional and nonfunctional requirements, tests, documentation and local checks below have been implemented and verified; any remote-publication limitation is explicitly reported.

## 1. Product overview

Apartment Booking CLI is a **local, all-in-one apartment and reservation manager operated exclusively through an interactive terminal menu**. It serves one operator who manages a small set of apartments, searches availability and maintains reservations. It must be simple enough for a professor to install and run in a few commands and well structured enough to demonstrate software architecture and continuous integration practices.

It is a complete terminal product, **not a web application, graphical UI, API or command-based CLI framework**. The terminal is the only user interface. Internally, independent services own the business rules, and SQLite provides durable storage. A committed JSON fixture supplies deterministic demonstration data.

### 1.1 Primary goals

1. Meet the course requirements: add/update/remove/view apartments; create/view/change/cancel bookings; search availability by date range; prevent overlapping bookings.
2. Run locally without external infrastructure, accounts, servers, Docker or environment-specific secrets.
3. Provide a professional, usable and accessible terminal experience.
4. Persist data safely across application restarts, with transactional protection of booking invariants.
5. Demonstrate maintainability through modular architecture, automated tests and GitHub Actions CI.
6. Make evaluation straightforward through a one-command app launch, a guided demo loader and a professional English README.

### 1.2 Users and environment

- **User:** one local operator (student, evaluator/professor).
- **Operating systems:** macOS, Linux, Windows; use portable paths and UTF-8. Test in CI on Linux and, at minimum, one Windows smoke job if feasible.
- **Python:** 3.12 or newer, supporting an explicitly tested set of Python versions.
- **Usage:** keyboard-only, text terminal, no browser and no mouse requirement.
- **Deployment:** local checkout and isolated Python virtual environment.
- **Language:** all application text, sample data, comments where needed, docs and error messages in **clear English**.

### 1.3 Out of scope

Authentication, multiple users/roles, payments, invoices, email, calendar integration, notifications, online synchronization, REST API, browser interface, desktop GUI, Docker, ORM, web framework, image uploads, complex rate plans, reporting dashboards and custom plugin architecture. Do not implement these to appear more complete.

## 2. Technology decisions

| Concern | Decision | Reason |
|---|---|---|
| Language | Python 3.12+ | Familiar, readable, cross-platform |
| Terminal presentation | `rich` | Clean tables, panels, prompts and accessible text messages |
| Application style | Interactive numbered menus | No memorized commands; professor-friendly |
| Persistence | SQLite through Python `sqlite3` | One local database file, no services to install |
| Demo source | `data/demo.json` | Reviewable, deterministic dataset, committed to Git |
| Models | `dataclasses`, standard-library `datetime` | Minimal dependencies and explicit types |
| Packaging | `pyproject.toml`, `pip install -e '.[dev]'` | Standard editable developer setup |
| Testing | `pytest`, `pytest-cov` | Unit, integration and terminal smoke tests |
| Quality | Ruff check and format | Consistent code style |
| CI | GitHub Actions | Automatic checks on push and pull request |
| Repository | GitHub, `main` branch | Clear delivery and traceable commits |

Do **not** use Typer/Click for interaction: there are no user-facing CLI subcommands. Entry point is `python -m apartment_booking` after installation. The application must work using a normal terminal without requiring any network requests once dependencies have been installed.

## 3. Functional scope and menu map

The application starts with the following conceptual menu (exact spacing is flexible):

```text
APARTMENT BOOKING
Local apartment and reservation management

MAIN MENU
  1. Apartments
  2. Bookings
  3. Search availability
  4. Demo & data
  0. Exit

Select an option: _
```

**Apartments submenu**

```text
1. View apartments
2. Add apartment
3. Update apartment
4. Remove apartment (archive)
0. Back
```

**Bookings submenu**

```text
1. View bookings
2. Create booking
3. Change booking
4. Cancel booking
0. Back
```

**Demo & data submenu**

```text
1. Load sample data (empty database only)
2. Reset database to sample data
3. View storage information
0. Back
```

Use a single consistent selection mechanism. Offer numbered rows when selecting an apartment/booking so the operator does not need to copy internal UUIDs. Always include a clear way to return from a submenu. `Ctrl+C` and `Ctrl+D`/EOF must terminate gracefully with no traceback, closing connections. In an input sequence, `0` may cancel/back only where clearly advertised; never silently interpret `0` as a valid value.

## 4. Apartment management requirements

**Apartment data**

| Field | Type | Rules |
|---|---|---|
| `id` | UUID string, primary key | Generated by the app; fixture uses fixed, valid UUIDs |
| `name` | string | Required, trimmed, 1–80 characters |
| `city` | string | Required, trimmed, 1–80 characters |
| `capacity` | integer | 1–20 guests |
| `nightly_price_cents` | integer | Strictly positive; entered/displayed as EUR, stored as integer cents |
| `is_active` | boolean | Defaults to true; false means archived |
| `created_at` | UTC timestamp string | Generated automatically |

**FR-A01 — Add:** Prompt for required fields, validate each one, show a final summary, save only on confirmation. Prevent blank names, invalid prices and out-of-range capacities. No need for unique apartment names.

**FR-A02 — View:** Display a clean table with row number, apartment name, city, capacity, nightly price and status. Show active apartments by default, with an explicit choice to view all/archived. Empty states must suggest adding an apartment or loading demo data.

**FR-A03 — Update:** Choose an active apartment from a numbered list and edit name, city, capacity or nightly price. Blank input should preserve the existing field *only when the prompt says so*. Validate and confirm the change before saving. A reduced capacity must not invalidate any **confirmed future or ongoing** booking's guest count.

**FR-A04 — Remove:** Implement removal as **archiving (soft deletion)**, not SQL `DELETE`, to protect historical bookings. Hide archived apartments from new booking and availability flows. Reject archiving if the apartment has any confirmed booking whose `check_out` is after today's local date; explain which bookings prevent it. Allow archiving when no current/future confirmed bookings exist. Confirm before archiving. In the README explain that “remove” means “archive” and why.

The application does not need an unarchive feature for v1. An archived apartment remains visible in the “all/archived” view, along with any historical reservations.

## 5. Booking management requirements

**Booking data**

| Field | Type | Rules |
|---|---|---|
| `id` | UUID string, primary key | Generated by app; demo uses fixed UUIDs |
| `apartment_id` | UUID string, foreign key | Must reference an existing apartment |
| `guest_name` | string | Required, trimmed, 1–80 characters |
| `guest_count` | integer | Minimum 1; no greater than apartment capacity |
| `check_in` | ISO date string | `YYYY-MM-DD`, valid calendar date |
| `check_out` | ISO date string | Valid date strictly later than `check_in` |
| `status` | string | `CONFIRMED` or `CANCELLED` |
| `created_at` | UTC timestamp string | Generated automatically |
| `updated_at` | UTC timestamp string | Updated on changes/cancellation |

**FR-B01 — Create:** Select an active apartment, enter guest name/count and check-in/out, validate, check for conflicts, show a confirmation summary, then persist atomically. If an apartment has insufficient capacity or the period is unavailable, show a clear explanation, do not save and offer to try again or return.

**FR-B02 — View:** Show reservations in a readable table with apartment, guest, guest count, dates and status. All reservations (including cancelled) must remain accessible. Default to upcoming/ongoing confirmed bookings if that view is implemented, but always provide an obvious “all bookings” filter; the simplest acceptable v1 default is **all bookings** sorted by check-in date and apartment name.

**FR-B03 — Change:** Select an existing confirmed booking. Permit editing guest name, guest count, check-in and check-out. To keep scope small, **do not allow changing its apartment**: cancel and recreate instead. Revalidate dates, capacity and overlap. The overlap query must exclude the booking being edited. If validation fails, leave the booking unchanged. Cancelled bookings cannot be edited.

**FR-B04 — Cancel:** Select a confirmed booking, show details, ask for explicit confirmation and change its status to `CANCELLED`. Do not delete records. Its dates no longer block future bookings. Cancelling an already cancelled booking must return an informative message and cause no modification.

**Business constraints:** Bookings may use historical dates, for deterministic demos and tests; do not silently apply a future-only rule not required by the assignment. There is no checkout-hour or time-zone booking granularity: reservations are whole calendar dates only. No money is charged or computed for reservations in v1; nightly prices are descriptive apartment data.

## 6. Availability and overlap prevention

**FR-S01 — Search availability:** Prompt for requested check-in/check-out in `YYYY-MM-DD` and requested guests (default 1). Show only active apartments whose capacity meets the guest count and that have no overlapping **confirmed** booking. Display a clear result count and a useful no-results message.

**FR-S02 — Date boundaries:** Use half-open intervals: `[check_in, check_out)`. The checkout date is not occupied; a new booking may start on that date. Two intervals `[a,b)` and `[c,d)` overlap **if and only if** `a < d AND c < b`. For SQL, the equivalent on existing booking rows is:

```sql
existing.check_in < :requested_check_out
AND :requested_check_in < existing.check_out
```

Also filter `existing.status = 'CONFIRMED'`, restrict by apartment, and exclude the current booking ID during an update.

**FR-S03 — Enforce inside write transaction:** Both booking creation and date-changing updates must acquire the SQLite write reservation **before** checking conflicts, then perform the overlap check and insert/update in the **same transaction**. Use an explicit, compatible SQLite strategy, for example a connection opened with `isolation_level=None` and `BEGIN IMMEDIATE`, then SQL `COMMIT` or `ROLLBACK` in a `try/finally`-safe transaction helper. Do not mix this pattern with `autocommit=False`'s already-open transaction behavior. Set `PRAGMA foreign_keys=ON` for **every connection** and a finite busy timeout (for example 5000 ms). No unnecessary global lock or external locking service.

If a simultaneous write cannot acquire the lock within the timeout, show a controlled “database is busy, please retry” message rather than a traceback. SQLite serializes writers; after acquiring the write reservation, re-check conflicts with current committed data. Two competing bookings for overlapping dates must never both be saved.

**FR-S04 — Consistency:** Apply the same checks for create, change and availability search. Keep a single authoritative overlap rule in the service/repository collaboration, avoiding separate inconsistent implementations.

### Required overlap test cases

- Existing 10–15; requested 12–16 -> conflict.
- Existing 10–15; requested 8–12 -> conflict.
- Existing 10–15; requested 9–17 -> conflict.
- Existing 10–15; requested 10–15 -> conflict.
- Existing 10–15; requested 15–18 -> allowed.
- Existing 10–15; requested 8–10 -> allowed.
- Overlap with a **cancelled** booking -> allowed.
- Conflict in another apartment -> does not block current apartment.
- Change the dates of a booking without self-conflict -> allowed if no other overlap.
- Failed create/change -> zero partial writes, previous record unchanged.
- Simultaneous overlapping requests using separate database connections -> no double booking.

## 7. SQLite schema, constraints and initialization

Default database: `data/apartment_booking.db`, resolved relative to the **current working directory**, which is the repository root for the documented launch. The README must explicitly tell users to run commands from the project root. The DB location can optionally be overridden through `APARTMENT_BOOKING_DB` (a filesystem path); tests must always override it to a temporary path. Resolve and show the effective DB location in “Demo & data > View storage information”. Do not silently create multiple databases in arbitrary installation locations.

Use **exactly two main tables** (`apartments` and `bookings`) with SQLite column names corresponding to the data above. Use `TEXT PRIMARY KEY` for UUID IDs, `INTEGER` for money/capacity/guest counts/active status, and `TEXT` for ISO dates/status/timestamps. Enforce constraints using `NOT NULL`, `CHECK` and `FOREIGN KEY`; make application-layer validation produce friendly user messages. Recommended indexes: `bookings(apartment_id, status, check_in, check_out)`; optionally another only if justified by measured queries. Foreign key deletion behavior must prevent accidental cascading destruction (`ON DELETE RESTRICT`/`NO ACTION`). Use parameterized SQL exclusively.

Initialize the database on startup by creating `data/` if needed and using `CREATE TABLE IF NOT EXISTS`/a small schema initializer. The first normal startup creates an **empty** database (not automatically prepopulated). Subsequent launches preserve all user records. Do not initialize by dropping tables. Keep initialization and schema logic in the storage layer, isolated from menus. Be careful with `sqlite3.executescript()` because it can commit an open transaction; do not accidentally put it inside a seed/reset transaction and break atomicity.

Use SQLite transactions for all multi-step operations and ensure connections are closed. Keep implementation lightweight: no ORM, migration engine or database server. If future migrations are not implemented, document that schema evolution is out of scope for v1.

## 8. JSON sample data and demo workflows

Commit a **human-readable, valid UTF-8** file `data/demo.json` with deterministic, realistic data. It is a *fixture/import source*, **not** the live database. Its role is to help the professor quickly explore the full application and to support integration tests. Include:

- **5 apartments**, in multiple cities, with differing capacities and nightly prices.
- **6 bookings**, at least one cancelled and several confirmed.
- One occupied window with an overlapping requested interval that can be used to demonstrate rejection.
- At least one apartment/date interval that is available.
- No conflicts among confirmed bookings in the starting fixture.
- Fixed, syntactically valid UUIDs for apartment and booking IDs; bookings reference apartment UUIDs from the same JSON file.
- Static ISO dates (for example in 2027); tests and behavior must not rely on those dates being in the future.

### 8.1 Example JSON contract (illustrative excerpt)

```json
{
  "schema_version": 1,
  "apartments": [
    {
      "id": "10000000-0000-4000-8000-000000000001",
      "name": "Mountain View",
      "city": "Bolzano",
      "capacity": 4,
      "nightly_price_cents": 12500
    }
  ],
  "bookings": [
    {
      "id": "20000000-0000-4000-8000-000000000001",
      "apartment_id": "10000000-0000-4000-8000-000000000001",
      "guest_name": "Alex Morgan",
      "guest_count": 2,
      "check_in": "2027-06-10",
      "check_out": "2027-06-15",
      "status": "CONFIRMED"
    }
  ]
}
```

`created_at`, `updated_at` and `is_active` need not appear in JSON if the loader initializes them consistently. Validate the *entire fixture* and its references/overlaps before writing any row.

### 8.2 Demo menu behavior

**Load sample data:** Only allowed if both data tables are empty. Validate JSON, then import in one transaction. If there are already records, do nothing and explain that loading is only for an empty database. This makes repeated use safe and avoids accidental duplicate data.

**Reset database to sample data:** Provide a prominent warning that **all existing apartments and bookings will be replaced**. Require the user to type the exact confirmation string `RESET` (a simple Y/N is insufficient). Parse and validate the JSON **before** modifying the database. Within one transaction, delete booking rows first, then apartment rows, then insert the fixture; rollback on any failure so old data remains intact. This is a deliberate destructive demo convenience, not a general import feature. Never reset automatically at startup or during regular tests. Do not commit any generated `.db` file.

**View storage information:** Show absolute current DB path and counts of apartments and bookings, plus which demo fixture is available. No SQL console or file picker is required.

### 8.3 Test data isolation

Pytest fixtures create a fresh SQLite database under `tmp_path` and optionally load `data/demo.json` through the same import service. Tests must never write to `data/apartment_booking.db`, never reset a real operator's data and never depend on test execution order.

## 9. Terminal UX and HCI requirements

Use `rich` for clean tables, consistent headers and grouped messages. Prefer restrained visual hierarchy to decoration. No curses/TUI, external GUI, mouse interactions, animations, progress bars without meaningful work or terminal-size assumptions.

**UX-01 — Recognition over recall:** Numbered menus and selections; show relevant options and current values; never require typing a UUID.

**UX-02 — Status feedback:** Explicit success messages after add/update/archive/create/change/cancel/import/reset and clear no-op feedback after cancelled actions.

**UX-03 — Error prevention:** Validate formats immediately; display correct format/examples; confirm destructive steps; provide contextual explanation when capacity or dates conflict.

**UX-04 — Consistency:** ISO dates displayed everywhere; EUR formatted with two decimal digits, while stored in integer cents; same terminology (`apartment`, `booking`, `confirmed`, `cancelled`, `archived`). Consistent numbered menus, “0. Back”, and predictable flow.

**UX-05 — Accessibility:** Never rely on red/green alone; use words like `SUCCESS`, `ERROR`, `AVAILABLE`, `UNAVAILABLE`. Work with `NO_COLOR`/color-disabled terminals; preserve reasonable readability at narrow widths (avoid excessively wide tables). Keep text understandable without decorative symbols.

**UX-06 — Recovery:** Invalid entries reprompt instead of crashing. Catch expected domain/database errors at the CLI boundary and display a helpful message. Treat EOF/keyboard interrupt gracefully. Unexpected programming errors should not be silently swallowed: show a concise failure to the user and write technical detail to stderr or a debug-friendly diagnostic, without pretending success.

**UX-07 — Honest confirmations:** Show the exact apartment, guest and date range before finalizing bookings; after successful action, do not leave the user uncertain whether it was saved.

**Example response:**

```text
BOOKING NOT AVAILABLE
Apartment: Mountain View
Requested dates: 2027-06-12 to 2027-06-16
Reason: A confirmed booking overlaps the requested period.
No changes were saved.

0. Back   1. Try another date range
```

## 10. Architecture and code-quality standards

Adopt a **small layered architecture**, with three separations:

1. **CLI / Presentation:** menu navigation, prompts, formatting, confirmation, conversion from user input into service calls; no SQL and no overlap logic.
2. **Services / Business logic:** validate entities and operations, enforce booking/archiving rules, expose testable methods without terminal input/output.
3. **Storage / Persistence:** initialize schema, manage connections/transactions and execute parameterized queries. No Rich imports or terminal prompts.

`models.py` holds lightweight domain dataclasses/enums. Use type hints in public functions. Services accept collaborators explicitly (constructor parameters or function arguments), not hidden module-level mutable globals. Add small domain-specific exceptions such as `ValidationError`, `NotFoundError`, `BookingConflictError`, `OperationNotAllowedError` and `StorageBusyError`; map them to understandable CLI messages.

**Avoid:** circular imports, large monolithic `main.py`, repeated validation rules, `print()` buried in services, all-purpose `utils.py`, singleton globals, unnecessary abstract factories, excessive inheritance, a general DI framework, complex event systems, and speculative architecture. Dependency boundaries matter more than the number of files.

### Recommended repository structure

```text
apartment-booking-cli/
├── .github/
│   └── workflows/
│       └── ci.yml
├── data/
│   ├── demo.json
│   └── .gitkeep                 # optional; generated DB must be ignored
├── docs/
│   └── PRD.md
├── src/
│   └── apartment_booking/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── menu.py
│       │   ├── prompts.py
│       │   └── display.py
│       ├── models.py
│       ├── errors.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── apartments.py
│       │   ├── bookings.py
│       │   └── demo.py
│       └── storage/
│           ├── __init__.py
│           ├── database.py
│           ├── repositories.py
│           └── schema.sql
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── .gitignore
├── pyproject.toml
└── README.md
```

Adjust file boundaries modestly if that simplifies code; keep all three architectural responsibilities distinct and preserve predictable module names. No unnecessary empty packages or duplicated wrappers.

## 11. Reliability, security and edge cases

- Use parameterized SQL; never interpolate user input into query strings.
- Use ISO date parsing with `datetime.date.fromisoformat` plus explicit `YYYY-MM-DD` validation, rejecting ambiguous formatting. SQL string comparisons are valid only for normalized ISO dates.
- Use integer cents for prices; parse decimal user input safely with `Decimal`, not binary floating-point conversion. Reject zero, negative, NaN, excessive precision and malformed prices.
- Use `uuid.uuid4()` for real records; fixture UUIDs are fixed. Never rely on consecutive integer IDs as user-facing identifiers.
- Guard against empty apartment/booking collections; avoid uncaught selection-index exceptions.
- Handle missing or malformed `demo.json` without database mutation.
- Handle a database path that is unwritable or locked gracefully.
- Use a defined transaction boundary for creation/changes/cancellation/archive/import/reset.
- Do not delete or change actual data while running tests.
- Do not store passwords, tokens, credentials or personal secrets in source. All demo guest names must be fictitious.
- Avoid introducing unnecessary sensitive guest attributes (email, address, phone) beyond `guest_name`.
- Protect the Git repository from generated `.db`, `-wal`, `-shm`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.coverage`, virtualenv and OS files via `.gitignore`.
- Application runs fully offline after dependency installation; no telemetry or outbound requests.

## 12. Testing strategy and acceptance matrix

Use `pytest` for unit, integration and end-to-end/smoke tests. Tests must not be superficial; assert persisted state and rollback outcomes, not just displayed text. Use isolated temporary databases, reproducible dates and deterministic fixtures. Aim for at least **80% overall test coverage**, with strong attention to service-layer business rules; configure CI to fail below the agreed threshold.

| ID | Scenario | Expected result |
|---|---|---|
| T01 | Fresh launch without database | File and tables created; program opens; empty state shown |
| T02 | Add valid apartment | Persisted and visible after restart |
| T03 | Invalid apartment fields | Friendly error, no invalid row |
| T04 | Update apartment | Correct row updated; other fields retained |
| T05 | Reduce capacity below an upcoming booking's guest count | Rejected, no change |
| T06 | Archive with confirmed upcoming/ongoing booking | Rejected with reason |
| T07 | Archive without current/future confirmed booking | Archived; hidden from available inventory; history preserved |
| T08 | Valid booking | Saved and visible after restart |
| T09 | Invalid date, reversed dates, excessive guest count | Rejected without partial writes |
| T10 | Overlap cases from section 6 | Exact permitted/conflicting behavior |
| T11 | Change a booking | Own row excluded from overlap; valid changes saved |
| T12 | Failed booking change | Original row remains unchanged |
| T13 | Cancel booking | Status changes; same date range becomes available |
| T14 | Attempt to edit/cancel already cancelled booking | Informative no-op, stable state |
| T15 | Search available apartments | Active, capacity-sufficient and non-overlapping only |
| T16 | Import demo into empty DB | Exactly 5 apartments, 6 bookings, valid references |
| T17 | Reimport demo into nonempty DB | No duplicate data or modifications |
| T18 | Reject malformed/conflicting demo JSON | Atomic rollback; no partial data |
| T19 | Reset demo after typing incorrect confirmation | No changes |
| T20 | Confirm reset with `RESET` | Exact fixture replaces existing data |
| T21 | Interrupt/EOF at menu | Graceful termination; no traceback |
| T22 | Parallel conflicting writes on separate connections | Maximum one confirmed booking accepted |
| T23 | Run terminal scripted smoke journey | Menu traversal and at least one successful action work |
| T24 | `ruff check`, `ruff format --check`, coverage-enabled pytest | All pass locally and in CI |

Minimum scripted terminal journey: launch app on a temporary database; load demo via menu; display apartments; search one unavailable and one available interval; view bookings; cancel a demo booking; search again to confirm released availability; exit cleanly. Use `subprocess` with controlled stdin or an equivalent approach that tests the real entry point; no manual step may be required in automated CI.

## 13. Continuous integration and delivery

Create `.github/workflows/ci.yml` triggered on pushes to `main` and pull requests targeting `main`, with minimum `permissions: contents: read`. Use maintained versions of `actions/checkout` and `actions/setup-python` available at implementation time. Configure a Python matrix with 3.12 and 3.13 on Ubuntu; add a Windows smoke/test job if practical without excessive CI complexity.

**CI steps (must fail on errors):**

```bash
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest --cov=apartment_booking --cov-report=term-missing --cov-fail-under=80
```

Ensure test isolation means CI never commits, tracks or depends on generated SQLite files. Running CI locally before pushing should produce the same results. Do not set `continue-on-error` for required quality checks. No deployment step is necessary.

**Commit conventions:** meaningful message, e.g. `feat: build terminal apartment booking app with tests and CI`. It is acceptable to use several coherent commits if they improve traceability. Keep history clean and never commit generated data, secrets or broken unfinished scaffolding as the final delivery.

## 14. README.md requirements

Write a professional and complete **English** README aimed at a professor who has not seen the project. It must be self-contained and accurate; no placeholder text or claims unsupported by implementation. Include, in this order or similar:

1. Project title and 2–4 sentence overview.
2. Features and an explicit statement that this is terminal-only.
3. Requirements and supported Python versions.
4. Repository clone and OS-neutral setup; macOS/Linux and Windows venv activation when helpful.
5. Exact install and startup commands from the repository root:
   ```bash
   python -m venv .venv
   # Activate the virtual environment for your OS
   python -m pip install -e '.[dev]'
   python -m apartment_booking
   ```
6. First-run behavior (empty local SQLite DB created automatically).
7. Menu overview and a short walkthrough of adding an apartment, making a booking, searching, changing and cancelling.
8. Demo fixture instructions, example data and the exact consequences of `RESET`.
9. Date/availability rules with adjacency example and no-overlap formula in plain language.
10. Persistence details, DB path and `APARTMENT_BOOKING_DB` override.
11. Architecture diagram (plain-text is fine), module responsibilities and design rationale.
12. Tests and all quality commands including coverage.
13. GitHub Actions pipeline explanation.
14. Project tree.
15. Known limitations and out-of-scope features.
16. Troubleshooting for missing Python/dependencies, permissions, database busy/errors, and color-disabled terminals.
17. License statement only if an actual LICENSE file is supplied; otherwise do not invent one.

Use concise headings and real copyable commands. No excessive badges or marketing language. Include at least one readable terminal output example in a fenced text block. If the repository is private, the professor needs repository access; describe that clearly rather than pretending it is publicly clonable.

## 15. Implementation order for Codex

1. Set up package structure, `pyproject.toml`, `.gitignore` and test tooling.
2. Define domain models, errors and validations.
3. Implement SQLite schema, connection lifecycle and explicit transaction helper.
4. Implement repositories and service functions; test overlap, capacity and archive rules early.
5. Create and validate the full `data/demo.json` fixture and atomic demo services.
6. Build Rich menus, prompts, tables and error handling; route every action through services.
7. Write comprehensive unit, integration, concurrency and scripted terminal smoke tests.
8. Write professional README and commit this PRD as `docs/PRD.md`.
9. Implement GitHub Actions CI, run all checks and fix issues.
10. Run an end-to-end demo locally on a disposable DB; ensure persistent restart behavior.
11. Initialize/inspect Git; create a commit; create/push to the private GitHub repository if authorization and tools permit, without overwriting an existing repository.
12. Report the test results, final commit hash, repository URL if confirmed, and any remaining limitations or blockers.

## 16. Final delivery checklist

- [ ] App launches with `python -m apartment_booking` on a fresh machine after installing dependencies.
- [ ] Terminal-only numbered menu supports all required apartment and booking operations.
- [ ] Search returns only genuinely available active apartments for the requested dates and capacity.
- [ ] Adjacent checkout/check-in intervals are allowed; all true overlaps are blocked.
- [ ] Booking checks and writes share a safe SQLite transaction; concurrency test passes.
- [ ] Cancellation frees dates while preserving history.
- [ ] Removal archives apartments and preserves booking history.
- [ ] SQLite initializes automatically, persists restarts and requires no server.
- [ ] JSON demo file is validated, loadable on an empty database and safely resettable by explicit confirmation.
- [ ] Useful terminal formatting, empty states and friendly input-error messages are implemented.
- [ ] Unit, integration and scripted terminal tests cover edge cases and rollback behavior.
- [ ] Ruff checks pass; pytest and coverage threshold pass; GitHub Actions workflow is present.
- [ ] README is complete and installation/testing commands match the real project.
- [ ] `.gitignore` excludes generated databases, caches, virtualenv and secrets.
- [ ] Files are committed; GitHub repository and push are confirmed **only if actually completed**.

## 17. Final response expected from Codex

When implementation concludes, provide a compact factual delivery report containing: **implemented features**, **files and architecture**, **test commands and actual outcomes**, **demo and startup instructions**, **Git commit SHA**, **GitHub repository URL and push status** (if confirmed), and **remaining issues**. Do not replace execution evidence with assurances such as “error-free” or “production-ready”. If something cannot be verified, explicitly say so.
