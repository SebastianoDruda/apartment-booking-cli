import { expect, test } from '@playwright/test';
import { enterAs, signOut } from './helpers.js';

test.describe('entry and access', () => {
  test('pointing at a door previews that role', async ({ page, isMobile }) => {
    test.skip(isMobile, 'The preview panel is a desktop feature.');
    await page.goto('/#/login');
    const entry = page.locator('.auth');
    await expect(entry).toHaveAttribute('data-role', 'guest');
    await page.getByRole('button', { name: /Enter as a host/ }).hover();
    await expect(entry).toHaveAttribute('data-role', 'host');
  });

  test('a guest enters their space and signs out', async ({ page }) => {
    await enterAs(page, 'guest');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Where to next, Tom?');
    await signOut(page);
    await page.goto('/#/guest/trips');
    await expect(page).toHaveURL(/#\/login\?role=guest/);
  });

  test('a guest is asked for their name, which is required and remembered', async ({ page }) => {
    await page.goto('/#/login');
    await page.getByRole('button', { name: /Enter as a guest/ }).click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('What’s your name?');
    await page.getByLabel('Your name').fill('   ');
    await page.getByRole('button', { name: 'Continue' }).click();
    await expect(page.getByRole('alert')).toHaveText('Enter your name to continue.');
    await page.getByRole('button', { name: 'Back' }).click();
    await expect(page.getByRole('button', { name: /Enter as a host/ })).toBeVisible();

    await enterAs(page, 'guest', { name: 'Anna Bianchi' });
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Where to next, Anna?');
    await signOut(page);
    await page.goto('/#/login');
    await page.getByRole('button', { name: /Enter as a guest/ }).click();
    await expect(page.getByLabel('Your name')).toHaveValue('Anna Bianchi');
  });

  test('each role stays inside its own space', async ({ page }) => {
    await enterAs(page, 'guest');
    await page.goto('/#/host/listings');
    await expect(page).toHaveURL(/#\/guest\/explore/);
    await page.goto('/#/login');
    await expect(page).toHaveURL(/#\/guest\/explore/);
  });

  test('the theme switch applies and remembers dark mode', async ({ page }) => {
    await enterAs(page, 'host');
    await page.getByRole('button', { name: 'Dark theme' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await expect(page.getByRole('button', { name: 'Dark theme' })).toHaveAttribute('aria-pressed', 'true');
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page.getByRole('button', { name: 'Light theme' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  });

  test('unknown pages answer with a way home', async ({ page }) => {
    await page.goto('/#/nowhere');
    await expect(page.getByRole('heading', { name: 'This door is closed.' })).toBeVisible();
    await page.getByRole('link', { name: 'Back home' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Anywhere feels like home.' })).toBeVisible();
  });
});
