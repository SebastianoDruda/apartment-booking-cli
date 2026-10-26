# Changelog

This file records named checkpoints of the project. Checkpoint names describe
project milestones and do not imply semantic versioning or production readiness.

## Unreleased

- Reject non-finite nightly prices and prices that round to zero in both the CLI
  and database layer; reject overflowing totals before creating/changing bookings.
- Keep validation and writes in one immediate SQLite transaction to prevent
  overlapping reservations from simultaneous application writers; roll back failures.
- Report expected SQLite operational/integrity failures at the command prompt;
  startup failures exit cleanly with status 1. Unexpected programming errors still propagate.
- Close the database when the application exits, including exceptional exits.
- Add 13 regression tests, bringing the suite to 22 tests; original workflow tests remain unchanged.
- Stop tracking the runtime database; keep its path/schema unchanged and preserve
  local data. New clones create an empty database on first run. Existing checkouts
  must back up the formerly tracked file before pulling this change (see README).
- Keep commands, prompts, roles, aliases, date rules and current-price booking totals
  unchanged. Checkpoint 01 remains the original release; no migration is required.

- Added explicit macOS and Windows launch, interpreter-check and test commands,
  including optional virtual-environment instructions and Windows fallback commands.
- Reviewed the repository layout and documented why the existing filenames,
  launchers and database location are retained; application functionality is unchanged.

## [Checkpoint 01] — 2026-10-26

Tag: `checkpoint-01`.

### Existing application captured

- Python CLI with System Manager and Apartment Booker roles, contextual help,
  command aliases, tab completion and dynamically sized tables.
- Apartment creation, nightly price updates, listing and removal.
- Booking creation, viewing, date/guest-count changes and cancellation.
- Availability search with capacity and overlap validation, plus direct booking
  from search results.
- SQLite persistence, calendar validation and EUR total-price calculations.
- Nine existing automated tests for database operations, CLI workflows and completion.

### Documentation and repository maintenance

- Expanded README with installation, first-use walkthrough, complete command/alias
  reference, input rules, source layout, schema, database backup/reset guidance,
  testing, troubleshooting and current limitations.
- Contributor guide and pull request template.
- GitHub Actions test matrix for Python 3.10 and 3.14 on Linux, macOS and Windows.
- Ignore rules for additional local database files and SQLite sidecars.

### Compatibility and scope

- Application code, test code, source layout, existing database and concept-map image
  are unchanged by the checkpoint preparation.
- No new runtime dependencies or database migration are required.
- The existing database remains tracked; local use can modify it.
- Roles are not authentication; displayed booking totals use current apartment prices.
- This checkpoint does not add a license or multi-user/concurrent-booking guarantees.

[Checkpoint 01]: https://github.com/SebastianoDruda/apartment-booking-cli/releases/tag/checkpoint-01
