// Seeds the fresh end-to-end database with a small, realistic catalogue.
import { request } from '@playwright/test';
import { api, isoDays } from './helpers.js';

const CATALOGUE = [
  { name: 'Casa Aurora', city: 'Amalfi', maxPeople: 4, price: 180 },
  { name: 'Loft Navigli', city: 'Milano', maxPeople: 2, price: 135 },
  { name: 'Chalet Dolomiti', city: 'Cortina', maxPeople: 6, price: 260 },
];

export default async function globalSetup() {
  const context = await request.newContext();
  for (const apartment of CATALOGUE) await api.addApartment(context, apartment);
  await api.book(context, { apartment: 'Casa Aurora', start: isoDays(20), end: isoDays(24), guest: 'Anna Huber', people: 3 });
  await api.book(context, { apartment: 'Loft Navigli', start: isoDays(-40), end: isoDays(-37), guest: 'Tom Springer' });
  await context.dispose();
}
