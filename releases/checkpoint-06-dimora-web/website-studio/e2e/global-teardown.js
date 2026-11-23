// Removes the temporary end-to-end database and its SQLite sidecar files.
import { rm } from 'node:fs/promises';

export default async function globalTeardown() {
  const path = process.env.E2E_DB_PATH;
  if (!path) return;
  await Promise.all(['', '-wal', '-shm', '-journal'].map((suffix) => rm(`${path}${suffix}`, { force: true })));
}
