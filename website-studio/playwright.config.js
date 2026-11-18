// End-to-end tests: the real Flask API and the studio server, driven in Chromium.
// Each run starts its own API on a fresh temporary database, on dedicated ports,
// so it never touches a running development server or the project's database.
import { defineConfig, devices } from '@playwright/test';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const API_PORT = Number(process.env.E2E_API_PORT ?? 8765);
const STUDIO_PORT = Number(process.env.E2E_STUDIO_PORT ?? 8766);
// Interpreter with Flask installed (requirements/web.txt), e.g. PYTHON=../.venv/bin/python
const PYTHON = JSON.stringify(process.env.PYTHON?.includes('/') ? resolve(process.env.PYTHON) : (process.env.PYTHON ?? 'python3'));

// E2E_GATEWAY_URL runs the same suite against a running event-driven stack
// (microservices/), whose nginx gateway serves both the client and the API.
const GATEWAY_URL = process.env.E2E_GATEWAY_URL?.replace(/\/$/, '');

if (GATEWAY_URL) {
  process.env.E2E_API_URL = GATEWAY_URL;
} else {
  process.env.E2E_API_URL = `http://127.0.0.1:${API_PORT}`;
  process.env.E2E_DB_PATH ??= join(tmpdir(), `dimora-e2e-${process.pid}-${Date.now()}.db`);
}

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.js',
  globalTeardown: './e2e/global-teardown.js',
  timeout: 30_000,
  expect: { timeout: 7_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : [['list']],
  use: {
    baseURL: GATEWAY_URL ?? `http://127.0.0.1:${STUDIO_PORT}`,
    locale: 'en-GB',
    timezoneId: 'Europe/Rome',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: GATEWAY_URL ? [] : [
    {
      command: `${PYTHON} -m flask --app apartment_booking.web:create_app --no-debug run --host 127.0.0.1 --port ${API_PORT} --no-reload`,
      cwd: '..',
      env: { APARTMENT_BOOKING_DB_PATH: process.env.E2E_DB_PATH },
      url: `${process.env.E2E_API_URL}/api/health`,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: `${PYTHON} serve.py --port ${STUDIO_PORT} --api ${process.env.E2E_API_URL}`,
      url: `http://127.0.0.1:${STUDIO_PORT}/`,
      reuseExistingServer: false,
      timeout: 15_000,
    },
  ],
});
