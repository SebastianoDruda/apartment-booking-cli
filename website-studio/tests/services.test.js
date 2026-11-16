import { test } from 'node:test';
import assert from 'node:assert/strict';

import { STORAGE_KEYS } from '../public/src/config.js';
import { createStorage, memoryBackend } from '../public/src/core/storage.js';
import { ApiError, createApiClient } from '../public/src/services/api.js';
import { PERSONAS, createAuthService } from '../public/src/services/auth.js';
import { createBookingService } from '../public/src/services/booking-service.js';

test('a guest enters with their own name; the session expires and can be closed', () => {
  let clock = 0;
  const storage = createStorage(memoryBackend());
  const auth = createAuthService({ storage, now: () => clock });
  assert.equal(auth.getSession(), null);
  assert.equal(auth.lastGuestName(), '');
  const session = auth.enter('guest', '  Mario   Rossi ');
  assert.equal(session.name, 'Mario Rossi', 'trimmed like the API stores booker names');
  assert.deepEqual(storage.read(STORAGE_KEYS.session), session);
  assert.equal(auth.getSession().role, 'guest');
  assert.equal(auth.lastGuestName(), 'Mario Rossi', 'remembered to prefill the next entry');
  clock += 8 * 24 * 60 * 60 * 1000;
  assert.equal(auth.getSession(), null, 'expired');
  assert.equal(auth.enter('host').name, PERSONAS.host.name);
  auth.signOut();
  assert.equal(auth.getSession(), null);
  assert.throws(() => auth.enter('admin'));
  assert.throws(() => auth.enter('guest', '   '), 'a guest needs a name');
});

test('tampered sessions are discarded', () => {
  const storage = createStorage(memoryBackend());
  const auth = createAuthService({ storage, now: () => 0 });
  storage.write(STORAGE_KEYS.session, { role: 'root', name: 'x', expiresAt: 10 });
  assert.equal(auth.getSession(), null);
  assert.equal(storage.read(STORAGE_KEYS.session), null);
});

function fakeFetch(responses) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    const next = responses.shift();
    if (next instanceof Error) throw next;
    return { ok: next.status < 400, status: next.status, statusText: 'x', json: async () => next.body };
  };
  return { calls, fetchImpl };
}

test('API client unwraps data and maps errors', async () => {
  const { calls, fetchImpl } = fakeFetch([
    { status: 200, body: { data: [1] } },
    { status: 409, body: { error: { code: 'conflict', message: 'Taken.' } } },
    new TypeError('offline'),
  ]);
  const api = createApiClient({ baseUrl: '/api', fetchImpl });
  assert.deepEqual(await api.get('/availability', { query: { a: '1 2' } }), [1]);
  assert.equal(calls[0].url, '/api/availability?a=1+2');
  await assert.rejects(api.post('/bookings', { x: 1 }), (error) => error instanceof ApiError && error.code === 'conflict' && error.status === 409);
  assert.equal(calls[1].init.headers['Content-Type'], 'application/json');
  assert.equal(calls[1].init.body, '{"x":1}');
  await assert.rejects(api.get('/apartments'), { code: 'network' });
});

test('booking service speaks the REST contract', async () => {
  const { calls, fetchImpl } = fakeFetch([
    { status: 200, body: { data: { id: 1, name: 'Loft/2', address: 'IT, Roma, Via 1', max_people: 2, price_per_night: 99, old_price_per_night: 90 } } },
    { status: 200, body: { data: {} } },
  ]);
  const service = createBookingService(createApiClient({ baseUrl: '/api', fetchImpl }));
  const updated = await service.updatePrice('Loft/2', 99);
  assert.equal(calls[0].url, '/api/apartments/Loft%2F2/price');
  assert.equal(calls[0].init.method, 'PATCH');
  assert.equal(updated.previousPrice, 90);
  await service.cancelBooking({ apartmentName: 'Loft', start: '2026-12-01', end: '2026-12-03' });
  assert.equal(calls[1].init.method, 'DELETE');
  assert.deepEqual(JSON.parse(calls[1].init.body), { apartment_name: 'Loft', start_date: '2026-12-01', end_date: '2026-12-03' });
});
