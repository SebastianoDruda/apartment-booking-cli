// Shared helpers for the end-to-end suite.
import { expect } from '@playwright/test';

export const API_URL = () => process.env.E2E_API_URL;

/** ISO date `days` from today (local time). */
export function isoDays(days) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

/** A name no other test or project uses, so tests never share mutable data. */
export function uniqueName(prefix, testInfo) {
  return `${prefix} ${testInfo.project.name} ${Date.now().toString(36)}`;
}

async function call(request, method, path, data) {
  const response = await request.fetch(`${API_URL()}/api${path}`, { method, data });
  expect(response.ok(), `${method} ${path} → ${response.status()} ${await response.text()}`).toBeTruthy();
  return (await response.json()).data;
}

export const api = {
  addApartment: (request, { name, city = 'Torino', maxPeople = 4, price = 100 }) => call(request, 'POST', '/apartments', {
    name, country: 'Italia', city, street_and_number: 'Via Roma 1', max_people: maxPeople, price_per_night: price,
  }),
  removeApartment: (request, name) => request.fetch(`${API_URL()}/api/apartments/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  book: (request, { apartment, start, end, guest = 'Tom Springer', people = 2 }) => call(request, 'POST', '/bookings', {
    apartment_name: apartment, start_date: start, end_date: end, booker_name: guest, num_people: people,
  }),
};

/** Enter the app through the entry page, as a real visitor would; a guest types their name. */
export async function enterAs(page, role, { name = 'Tom Springer' } = {}) {
  await page.goto('/#/login');
  await page.getByRole('button', { name: role === 'host' ? /Enter as a host/ : /Enter as a guest/ }).click();
  if (role === 'guest') {
    await page.getByLabel('Your name').fill(name);
    await page.getByRole('button', { name: 'Continue' }).click();
  }
  await expect(page).toHaveURL(role === 'host' ? /#\/host\/overview/ : /#\/guest\/explore/);
}

/** Open a section from the sidebar (desktop) or the tab bar (mobile): only the visible one is in the accessibility tree. */
export async function openSection(page, name) {
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name }).click();
}

export async function signOut(page) {
  await page.getByRole('button', { name: 'Profile' }).click();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/#\/$/);
}
