import { expect, test } from '@playwright/test';

test.describe('landing page', () => {
  test('shows the promise, the live catalogue and the way in', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1, name: 'Anywhere feels like home.' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Casa Aurora' })).toBeVisible();

    await page.getByRole('main').getByRole('link', { name: 'Try our system' }).click();
    await expect(page).toHaveURL(/#\/login$/);
    await expect(page.getByRole('heading', { name: 'How are you joining?' })).toBeVisible();
  });

  test('the header draws in to a pill once the page scrolls', async ({ page }) => {
    await page.goto('/');
    const header = page.locator('[data-site-header]');
    await expect(header).not.toHaveClass(/is-scrolled/);
    await page.mouse.wheel(0, 900);
    await expect(header).toHaveClass(/is-scrolled/);
  });

  test('the footer is uncovered at the end and leads in', async ({ page }) => {
    await page.goto('/');
    const footer = page.getByRole('contentinfo');
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await expect(footer.getByText('Your next stay starts here.')).toBeInViewport();
    await expect(footer.getByRole('button', { name: 'How it works' })).toHaveCount(0);
    await footer.getByRole('link', { name: 'Try our system' }).click();
    await expect(page).toHaveURL(/#\/login$/);
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
