import { test } from 'node:test';
import assert from 'node:assert/strict';

import { escapeHtml, html, raw } from '../public/src/core/html.js';
import {
  addDays, formatMoney, initials, nightsBetween, overlapNights, sameName, stayStatus,
} from '../public/src/core/format.js';
import { setLocale } from '../public/src/core/i18n.js';
import { buildHash, parseHash } from '../public/src/core/router.js';
import { createStorage, memoryBackend } from '../public/src/core/storage.js';
import { splitAddress, toApartment, toBooking } from '../public/src/services/booking-service.js';
import { portfolioStats } from '../public/src/views/host/overview.js';

test('html escapes interpolated values but keeps nested safe markup', () => {
  const name = '<img src=x onerror=alert(1)>';
  assert.equal(html`<p title="${name}">${name}</p>`.value,
    '<p title="&lt;img src=x onerror=alert(1)&gt;">&lt;img src=x onerror=alert(1)&gt;</p>');
  assert.equal(html`<ul>${['a', 'b'].map((item) => html`<li>${item}</li>`)}</ul>`.value, '<ul><li>a</li><li>b</li></ul>');
  assert.equal(html`${null}${false}${undefined}${0}`.value, '0');
  assert.equal(html`${raw('<b>ok</b>')}`.value, '<b>ok</b>');
  assert.equal(escapeHtml(`"'\``), '&quot;&#39;&#96;');
});

test('calendar helpers', () => {
  assert.equal(nightsBetween('2026-12-30', '2027-01-02'), 3);
  assert.equal(nightsBetween('2028-02-28', '2028-03-01'), 2, 'leap year');
  assert.equal(addDays('2026-12-31', 1), '2027-01-01');
  assert.equal(overlapNights('2026-11-05', '2026-11-12', '2026-11-10', '2026-12-10'), 2);
  assert.equal(overlapNights('2026-10-01', '2026-10-05', '2026-11-10', '2026-12-10'), 0);
  const today = '2026-11-11';
  assert.equal(stayStatus({ start: '2026-11-12', end: '2026-11-14' }, today), 'upcoming');
  assert.equal(stayStatus({ start: '2026-11-09', end: '2026-11-14' }, today), 'ongoing');
  assert.equal(stayStatus({ start: '2026-11-08', end: '2026-11-11' }, today), 'past', 'checkout day counts as completed');
});

test('formatting and names', () => {
  setLocale('de');
  assert.equal(formatMoney(1820).replace(/\s/g, ' '), '1.820 €');
  setLocale('en');
  assert.equal(formatMoney(85.5), '€85.50');
  assert.equal(initials('giulia  maria rossi'), 'GM');
  assert.ok(sameName(' Giulia   Rossi ', 'giulia rossi'));
  assert.ok(!sameName('Giulia Rossi', 'Giulia Rosso'));
});

test('hash routing round-trips paths and queries', () => {
  assert.deepEqual(parseHash('#/guest/explore?start=2026-12-01&guests=2'), {
    path: '/guest/explore', query: { start: '2026-12-01', guests: '2' },
  });
  assert.deepEqual(parseHash('#main'), { path: '/', query: {} });
  assert.deepEqual(parseHash('#/login/'), { path: '/login', query: {} });
  assert.equal(buildHash('/login', { role: 'host', mode: '' }), '#/login?role=host');
});

test('storage survives broken backends', () => {
  const broken = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); }, removeItem() { throw new Error('denied'); } };
  const storage = createStorage(broken);
  assert.equal(storage.read('x', 'fallback'), 'fallback');
  assert.equal(storage.write('x', 1), false);
  storage.remove('x');
  const memory = createStorage(memoryBackend());
  memory.write('k', { a: 1 });
  assert.deepEqual(memory.read('k'), { a: 1 });
});

test('API payloads map to view models', () => {
  assert.deepEqual(splitAddress('Italia, Roma, Via Appia, 12'), { country: 'Italia', city: 'Roma', street: 'Via Appia, 12' });
  const apartment = toApartment({ id: 1, name: 'Loft', address: 'Italia, Milano, Via X 1', max_people: 2, price_per_night: 135 });
  assert.equal(apartment.city, 'Milano');
  assert.equal(apartment.total, null);
  const booking = toBooking({
    id: 3, apartment_id: 1, apartment_name: 'Loft', apartment_address: 'Italia, Milano, Via X 1', apartment_max_people: 2,
    price_per_night: 135, booker_name: 'Giulia', start_date: '2026-12-01', end_date: '2026-12-03', nights: 2, num_people: 2, total_price: 270,
  });
  assert.equal(booking.guestName, 'Giulia');
  assert.equal(booking.people, 2);
  assert.equal(booking.total, 270);
});

test('host portfolio statistics', () => {
  const apartments = [{ id: 1, name: 'A' }, { id: 2, name: 'B' }];
  const bookings = [
    { apartmentId: 1, start: '2026-11-09', end: '2026-11-14', people: 2, total: 500 },
    { apartmentId: 1, start: '2026-12-20', end: '2026-12-22', people: 3, total: 200 },
    { apartmentId: 2, start: '2026-10-01', end: '2026-10-04', people: 1, total: 300 },
  ];
  const stats = portfolioStats(apartments, bookings, '2026-11-11');
  assert.equal(stats.listings, 2);
  assert.equal(stats.upcoming, 2);
  assert.equal(stats.guests, 5);
  assert.equal(stats.revenue, 1000);
  assert.deepEqual(stats.arrivals.map((b) => b.start), ['2026-12-20']);
  assert.equal(stats.occupancy, 5, 'A has 3 of 30 nights booked, B none: 3 / 60');
  const [first, second] = stats.timeline.rows;
  assert.deepEqual([first.name, first.percent, second.name, second.percent], ['A', 10, 'B', 0]);
  assert.equal(first.stays.length, 1, 'the December stay is beyond the 30-day window');
  assert.deepEqual(
    [first.stays[0].offset, first.stays[0].length, first.stays[0].cutStart, first.stays[0].cutEnd],
    [0, 3, true, false], 'an ongoing stay is clipped at today',
  );
  assert.deepEqual(stats.timeline.ticks.map((tick) => tick.iso), ['2026-11-11', '2026-11-18', '2026-11-25', '2026-12-02', '2026-12-09']);
  assert.deepEqual(stats.months.map((m) => [m.key, m.revenue]),
    [['2026-11', 500], ['2026-12', 200], ['2027-01', 0], ['2027-02', 0], ['2027-03', 0], ['2027-04', 0]]);
});
