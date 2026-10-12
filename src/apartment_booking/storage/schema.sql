CREATE TABLE IF NOT EXISTS apartments (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 80),
    city TEXT NOT NULL CHECK(length(trim(city)) BETWEEN 1 AND 80),
    capacity INTEGER NOT NULL CHECK(typeof(capacity) = 'integer' AND capacity BETWEEN 1 AND 20),
    nightly_price_cents INTEGER NOT NULL CHECK(typeof(nightly_price_cents) = 'integer' AND nightly_price_cents > 0),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY NOT NULL,
    apartment_id TEXT NOT NULL REFERENCES apartments(id) ON DELETE RESTRICT,
    guest_name TEXT NOT NULL CHECK(length(trim(guest_name)) BETWEEN 1 AND 80),
    guest_count INTEGER NOT NULL CHECK(typeof(guest_count) = 'integer' AND guest_count BETWEEN 1 AND 20),
    check_in TEXT NOT NULL CHECK(length(check_in) = 10 AND check_in GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    check_out TEXT NOT NULL CHECK(length(check_out) = 10 AND check_out GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    status TEXT NOT NULL CHECK(status IN ('CONFIRMED', 'CANCELLED')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(check_in < check_out)
);

CREATE INDEX IF NOT EXISTS bookings_availability
    ON bookings(apartment_id, status, check_in, check_out);
