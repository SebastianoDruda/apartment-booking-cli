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
    await page.getByLabel('Check-out').fill(end); // applies on its own once both dates are set
    await page.getByLabel('Where').fill(apartment);
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
    await page.getByLabel('Check-out').fill(isoDays(30));
    await expect(page.getByText('Add both check-in and check-out.')).toBeVisible();
    await page.getByLabel('Check-out').fill('');
    await expect(page.getByText('Add both check-in and check-out.')).toBeHidden();

    await page.getByLabel('Where').fill(apartment);
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
    await page.getByLabel('Where').fill(apartment);
    await card(page).getByRole('button', { name: 'Book' }).click();
    const booking = page.getByRole('dialog', { name: `Book ${apartment}` });
    await booking.getByLabel('Check-in').fill(isoDays(80));
    await booking.getByLabel('Check-out').fill(isoDays(82));
    await api.book(request, { apartment, start: isoDays(81), end: isoDays(84), guest: 'Someone Else' });
    await booking.getByRole('button', { name: 'Confirm booking' }).click();
    await expect(booking.getByRole('alert')).toHaveText('Those dates were just taken. Try different ones.');
  });

  test('filters apply live and clear in one click', async ({ page }) => {
    await enterAs(page, 'guest');
    const clear = page.getByRole('button', { name: 'Clear filters' });
    await expect(clear).toBeHidden();
    await page.getByLabel('Where').fill(apartment);
    await expect(page.getByRole('article')).toHaveCount(1);
    await page.getByRole('spinbutton', { name: 'Guests' }).fill('4');
    await page.getByRole('spinbutton', { name: 'Guests' }).press('Tab');
    await expect(page.getByRole('heading', { name: 'No match' })).toBeVisible(); // capacity 3 < 4 guests
    await clear.click();
    await expect(page.getByLabel('Where')).toHaveValue('');
    await expect(page.getByRole('spinbutton', { name: 'Guests' })).toHaveValue('1');
    await expect(clear).toBeHidden();
  });

  test('books under the name the guest entered with', async ({ page }) => {
    await enterAs(page, 'guest', { name: 'Mario Rossi' });
    await page.getByLabel('Where').fill(apartment);
    await card(page).getByRole('button', { name: 'Book' }).click();
    const booking = page.getByRole('dialog', { name: `Book ${apartment}` });
    await booking.getByLabel('Check-in').fill(isoDays(90));
    await booking.getByLabel('Check-out').fill(isoDays(92));
    await booking.getByRole('button', { name: 'Confirm booking' }).click();
    await expect(page.getByRole('article').filter({ hasText: apartment })).toBeVisible();

    await openSection(page, 'All bookings');
    await expect(page.getByRole('article').filter({ hasText: apartment })).toContainText('Booked by Mario Rossi');
  });

  test('all bookings lists every guest and changes or cancels any of them', async ({ page, request }) => {
    await api.book(request, { apartment, start: isoDays(100), end: isoDays(102), guest: 'Booked From The Terminal', people: 1 });
    await enterAs(page, 'guest');
    await openSection(page, 'My trips');
    await expect(page.getByRole('article').filter({ hasText: apartment })).toHaveCount(0);

    await openSection(page, 'All bookings');
    const stay = page.getByRole('article').filter({ hasText: apartment });
    await expect(stay).toContainText('Booked by Booked From The Terminal');
    await expect(stay).toContainText('2 nights · 1 guest');

    await stay.getByRole('button', { name: 'Change' }).click();
    const change = page.getByRole('dialog', { name: 'Change your stay' });
    await change.getByRole('button', { name: 'More' }).click();
    await change.getByRole('button', { name: 'Update booking' }).click();
    await expect(stay).toContainText('2 nights · 2 guests');

    await stay.getByRole('button', { name: 'Cancel' }).click();
    const confirm = page.getByRole('dialog', { name: 'Cancel this stay?' });
    await expect(confirm).toContainText('The stay of Booked From The Terminal');
    await confirm.getByRole('button', { name: 'Yes, cancel' }).click();
    await expect(stay).toHaveCount(0);
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
