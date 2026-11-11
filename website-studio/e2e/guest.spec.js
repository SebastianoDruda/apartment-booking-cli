import { expect, test } from '@playwright/test';
import { api, enterAs, isoDays, openSection, uniqueName } from './helpers.js';

test.describe('guest', () => {
  let apartment;

  test.beforeEach(async ({ request }, testInfo) => {
    apartment = uniqueName('E2E Loft', testInfo);
    await api.addApartment(request, { name: apartment, city: 'Bolzano', maxPeople: 3, price: 120 });
  });

  test.afterEach(async ({ request }) => {
    await api.removeApartment(request, apartment);
  });

  async function search(page, start, end) {
    await page.getByLabel('Check-in').fill(start);
    await page.getByLabel('Check-out').fill(end);
    await page.getByRole('button', { name: 'Search' }).click();
    await page.getByLabel('City or name').fill(apartment);
  }

  const card = (page) => page.getByRole('article').filter({ has: page.getByRole('heading', { name: apartment }) });

  test('books a stay, changes it and cancels it', async ({ page }) => {
    await enterAs(page, 'guest');
    await search(page, isoDays(60), isoDays(63));
    await expect(card(page)).toContainText('€360');
    await expect(card(page)).toContainText('3 nights');

    await card(page).getByRole('button', { name: 'Book' }).click();
    const booking = page.getByRole('dialog', { name: `Book ${apartment}` });
    await expect(booking.getByText('€120 × 3 nights')).toBeVisible();
    await booking.getByRole('button', { name: 'Confirm booking' }).click();

    await expect(page).toHaveURL(/#\/guest\/trips\?new=\d+/);
    const trip = page.getByRole('article').filter({ hasText: apartment });
    await expect(trip).toContainText('3 nights · 1 guest');
    await expect(trip).toContainText('€360');

    await trip.getByRole('button', { name: 'Change' }).click();
    const change = page.getByRole('dialog', { name: 'Change your stay' });
    await change.getByLabel('Check-out').fill(isoDays(65));
    await expect(change.getByText('+€240')).toBeVisible();
    await change.getByRole('button', { name: 'Update booking' }).click();
    await expect(trip).toContainText('5 nights');
    await expect(trip).toContainText('€600');

    await trip.getByRole('button', { name: 'Cancel' }).click();
    await page.getByRole('dialog', { name: 'Cancel this stay?' }).getByRole('button', { name: 'Yes, cancel' }).click();
    await expect(trip).toHaveCount(0);
  });

  test('prevents invalid dates and over-capacity bookings before calling the API', async ({ page }) => {
    await enterAs(page, 'guest');
    await page.getByLabel('Check-in').fill(isoDays(30));
    await page.getByRole('button', { name: 'Search' }).click();
    await expect(page.getByText('Add both check-in and check-out.')).toBeVisible();

    await page.getByLabel('City or name').fill(apartment);
    await card(page).getByRole('button', { name: 'Book' }).click();
    const booking = page.getByRole('dialog', { name: `Book ${apartment}` });
    await booking.getByLabel('Check-in').fill(isoDays(40));
    await booking.getByLabel('Check-out').fill(isoDays(38));
    await booking.getByRole('button', { name: 'Confirm booking' }).click();
    await expect(booking.getByRole('alert')).toHaveText(/Check-out must be after check-in|Choose check-in and check-out/);

    const guests = booking.getByRole('spinbutton', { name: 'Guests' });
    const more = booking.getByRole('button', { name: 'More' });
    await more.click();
    await more.click();
    await expect(guests).toHaveValue('3');
    await expect(more).toBeDisabled(); // aria-disabled at capacity; the button keeps focus
    await more.click({ force: true });
    await expect(guests).toHaveValue('3');
  });

  test('explains that dates were just taken', async ({ page, request }) => {
    await enterAs(page, 'guest');
    await page.getByLabel('City or name').fill(apartment);
    await card(page).getByRole('button', { name: 'Book' }).click();
    const booking = page.getByRole('dialog', { name: `Book ${apartment}` });
    await booking.getByLabel('Check-in').fill(isoDays(80));
    await booking.getByLabel('Check-out').fill(isoDays(82));
    await api.book(request, { apartment, start: isoDays(81), end: isoDays(84), guest: 'Someone Else' });
    await booking.getByRole('button', { name: 'Confirm booking' }).click();
    await expect(booking.getByRole('alert')).toHaveText('Those dates were just taken. Try different ones.');
  });

  test('past stays are listed apart, without actions', async ({ page }) => {
    await enterAs(page, 'guest');
    await openSection(page, 'My trips');
    await page.getByRole('button', { name: /Past/ }).click();
    const past = page.getByRole('article').filter({ hasText: 'Loft Navigli' });
    await expect(past).toBeVisible();
    await expect(past.getByRole('button')).toHaveCount(0);
  });
});
