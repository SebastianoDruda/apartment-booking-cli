import { expect, test } from '@playwright/test';

test.describe('landing page', () => {
  test('shows the promise, the live catalogue and both entry points', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1, name: 'Anywhere feels like home.' })).toBeVisible();
    await expect(page.getByText(/\d+ stays? available now/)).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Casa Aurora' })).toBeVisible();

    await page.getByRole('main').getByRole('link', { name: 'Find a stay' }).click();
    await expect(page).toHaveURL(/#\/login\?role=guest/);
    await expect(page.getByRole('heading', { name: 'How are you joining?' })).toBeVisible();
  });

  test('the header draws in to a pill once the page scrolls', async ({ page }) => {
    await page.goto('/');
    const header = page.locator('[data-site-header]');
    await expect(header).not.toHaveClass(/is-scrolled/);
    await page.mouse.wheel(0, 900);
    await expect(header).toHaveClass(/is-scrolled/);
  });

  test('the footer is uncovered at the end and links back to the sections', async ({ page }) => {
    await page.goto('/');
    const footer = page.getByRole('contentinfo');
    await footer.getByRole('button', { name: 'How it works' }).scrollIntoViewIfNeeded();
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await expect(footer.getByText('Your next stay starts here.')).toBeInViewport();
    await footer.getByRole('button', { name: 'How it works' }).click();
    await expect(page.getByRole('heading', { name: 'Two roles. One flow.' })).toBeInViewport();
  });

  test('the language choice lives once, in the footer, and is remembered', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'Deutsch' })).toHaveCount(1);
    await page.getByRole('button', { name: 'Deutsch' }).click();
    await expect(page.locator('html')).toHaveAttribute('lang', 'de');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Überall wie zu Hause.');
    await page.reload();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Überall wie zu Hause.');
    await page.getByRole('button', { name: 'Italiano' }).click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Ovunque, come a casa.');
  });
});
