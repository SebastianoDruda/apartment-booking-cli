import { expect, test } from '@playwright/test';
import { api, enterAs, isoDays, openSection, uniqueName } from './helpers.js';

test.describe('host', () => {
  const listing = (page, name) => page.getByRole('article').filter({ has: page.getByRole('heading', { name }) });

  test('the overview summarises the portfolio', async ({ page }) => {
    await enterAs(page, 'host');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Good to see you, Sebastiano.');
    await expect(page.getByLabel('Key figures')).toContainText('Booked revenue');
    await expect(page.getByLabel('Key figures')).toContainText('Occupancy · 30 days');

    // Timeline: one row per listing, a bar per stay inside the next 30 days.
    await expect(page.getByRole('heading', { name: 'Next 30 days' })).toBeVisible();
    const aurora = page.getByRole('list', { name: 'Casa Aurora' });
    await expect(aurora.getByRole('listitem', { name: /^Anna Huber, / })).toBeVisible();
    await expect(page.getByRole('list', { name: 'Chalet Dolomiti' }).getByRole('listitem', { name: /, / })).toHaveCount(0);

    await expect(page.getByRole('heading', { name: 'Next arrivals' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Revenue by check-in month' })).toBeVisible();
    await expect(page.getByRole('list', { name: 'Revenue by check-in month' }).getByRole('listitem')).toHaveCount(6);
    await expect(page.getByRole('button', { name: 'New listing' })).toHaveCount(0); // lives in Listings only
  });

  test('publishes, reprices and removes a listing', async ({ page }, testInfo) => {
    const name = uniqueName('E2E Villa', testInfo);
    await enterAs(page, 'host');
    await openSection(page, 'Listings');

    await page.getByRole('button', { name: 'New listing' }).first().click();
    const form = page.getByRole('dialog', { name: 'New listing' });
    await form.getByRole('button', { name: 'Publish listing' }).click();
    await expect(form.getByText('Required.')).toHaveCount(4);

    await form.getByLabel('Listing name').fill(name);
    await form.getByLabel('Country').fill('Italia');
    await form.getByLabel('City').fill('Sorrento');
    await form.getByLabel('Street and number').fill('Via del Capo 3');
    await form.getByLabel('Price per night').fill('199');
    await form.getByRole('button', { name: 'Publish listing' }).click();
    await expect(listing(page, name)).toContainText('€199');

    await page.getByRole('button', { name: 'New listing' }).first().click();
    const duplicate = page.getByRole('dialog', { name: 'New listing' });
    await duplicate.getByLabel('Listing name').fill(name.toUpperCase());
    await duplicate.getByLabel('Country').fill('Italia');
    await duplicate.getByLabel('City').fill('Napoli');
    await duplicate.getByLabel('Street and number').fill('Via Toledo 1');
    await duplicate.getByLabel('Price per night').fill('99');
    await duplicate.getByRole('button', { name: 'Publish listing' }).click();
    await expect(duplicate.getByText('A listing with this name already exists.')).toBeVisible();
    await duplicate.getByRole('button', { name: 'Cancel' }).click();

    await listing(page, name).getByRole('button', { name: 'Price' }).click();
    const price = page.getByRole('dialog', { name: `Price for ${name}` });
    await price.getByLabel('New price per night').fill('229');
    await expect(price.getByText('+15%')).toBeVisible();
    await price.getByRole('button', { name: 'Update price' }).click();
    await expect(listing(page, name)).toContainText('€229');

    await listing(page, name).getByRole('button', { name: `Remove ${name}` }).click();
    await page.getByRole('dialog', { name: `Remove ${name}?` }).getByRole('button', { name: 'Remove listing' }).click();
    await expect(listing(page, name)).toHaveCount(0);
  });

  test('removing a listing with bookings asks for its name', async ({ page, request }, testInfo) => {
    const name = uniqueName('E2E Busy', testInfo);
    await api.addApartment(request, { name });
    await api.book(request, { apartment: name, start: isoDays(10), end: isoDays(12), guest: 'Lukas Weber' });
    await enterAs(page, 'host');
    await openSection(page, 'Listings');

    await listing(page, name).getByRole('button', { name: `Remove ${name}` }).click();
    const confirm = page.getByRole('dialog', { name: `Remove ${name}?` });
    await expect(confirm).toContainText('Its 1 booking will be cancelled too.');
    const remove = confirm.getByRole('button', { name: 'Remove listing' });
    await expect(remove).toBeDisabled();
    await confirm.getByLabel(`Type “${name}” to confirm`).fill(name);
    await remove.click();
    await expect(listing(page, name)).toHaveCount(0);
  });

  test('reservations are filtered from a single menu', async ({ page }) => {
    await enterAs(page, 'host');
    await openSection(page, 'Reservations');
    await expect(page.getByText(/\d+ reservations?/).first()).toBeVisible();
    const toggle = page.getByRole('button', { name: 'Filters' });
    const panel = page.getByRole('group', { name: 'Filters' });

    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await panel.getByRole('button', { name: 'Completed' }).click();
    await expect(page.getByRole('cell', { name: 'Tom Springer' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Anna Huber' })).toHaveCount(0);
    await page.keyboard.press('Escape');
    await expect(panel).toBeHidden();
    await expect(toggle).toContainText('1');

    await page.getByRole('button', { name: 'Remove filter: Completed' }).click();
    await toggle.click();
    await panel.getByLabel('Search guest').fill('anna');
    await panel.getByRole('button', { name: 'Done' }).click();
    await expect(page.getByRole('cell', { name: 'Anna Huber' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Tom Springer' })).toHaveCount(0);

    await toggle.click();
    await panel.getByRole('button', { name: 'Clear all' }).click();
    await expect(page.getByRole('cell', { name: 'Tom Springer' })).toBeVisible();
    await expect(page.getByRole('button', { name: /Remove filter/ })).toHaveCount(0);
  });
});
