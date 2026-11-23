import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

import en from '../public/src/i18n/en.js';
import it from '../public/src/i18n/it.js';
import de from '../public/src/i18n/de.js';
import { detectLocale, has, setLocale, t, tRich } from '../public/src/core/i18n.js';

const SRC = fileURLToPath(new URL('../public/src/', import.meta.url));

function leafKeys(node, prefix = '') {
  return Object.entries(node).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return value && typeof value === 'object' ? leafKeys(value, path) : [path];
  });
}

function sourceFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? sourceFiles(path) : path.endsWith('.js') ? [path] : [];
  });
}

test('Italian and German define exactly the English keys', () => {
  const reference = leafKeys(en).sort();
  assert.deepEqual(leafKeys(it).sort(), reference, 'it.js differs from en.js');
  assert.deepEqual(leafKeys(de).sort(), reference, 'de.js differs from en.js');
});

test('placeholders match across languages', () => {
  const placeholders = (text) => [...String(text).matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(',');
  const lookup = (messages, key) => key.split('.').reduce((node, part) => node[part], messages);
  for (const key of leafKeys(en)) {
    const expected = placeholders(lookup(en, key));
    assert.equal(placeholders(lookup(it, key)), expected, `it: ${key}`);
    assert.equal(placeholders(lookup(de, key)), expected, `de: ${key}`);
  }
});

test('every literal key used in the source exists', () => {
  const missing = [];
  for (const file of sourceFiles(SRC)) {
    const code = readFileSync(file, 'utf8');
    for (const match of code.matchAll(/\b(?:t|tRich)\('([a-zA-Z0-9_.]+)'/g)) {
      if (!has(match[1])) missing.push(`${match[1]} (${file.replace(SRC, '')})`);
    }
  }
  assert.deepEqual(missing, []);
});

test('dynamic keys used by views exist for every variant', () => {
  const keys = [
    ...['guest', 'host'].flatMap((role) => [
      `roles.${role}`, `auth.${role}.enter`, `auth.${role}.body`, `auth.${role}.visualTitle`,
      `landing.sides.${role}.title`, `landing.sides.${role}.cta`, `landing.sides.${role}.step3`,
    ]),
    ...['upcoming', 'ongoing', 'past'].map((status) => `status.${status}`),
    ...['priceAsc', 'priceDesc', 'capacity', 'name'].map((sort) => `explore.sorts.${sort}`),
    ...['revenue', 'upcoming', 'guests', 'occupancy'].map((kpi) => `host.overview.kpi.${kpi}`),
    ...['live', 'overlap', 'price', 'flex'].flatMap((key) => [`landing.features.${key}.title`, `landing.features.${key}.body`]),
    ...['how', 'features', 'stays'].map((id) => `nav.${id}`),
    ...['trips', 'bookings'].flatMap((scope) => [
      `${scope}.metaTitle`, `${scope}.title`, `${scope}.empty.title`, `${scope}.empty.body`,
      `${scope}.emptyPast.title`, `${scope}.emptyPast.body`,
    ]),
    ...['explore', 'trips', 'bookings', 'overview', 'listings', 'reservations'].map((item) => `shell.nav.${item}`),
  ];
  assert.deepEqual(keys.filter((key) => !has(key)), []);
});

test('plurals, interpolation and rich text', () => {
  setLocale('it');
  assert.equal(t('common.nights', { count: 1 }), '1 notte');
  assert.equal(t('common.nights', { count: 4 }), '4 notti');
  setLocale('de');
  assert.equal(t('common.guests', { count: 2 }), '2 Gäste');
  setLocale('en');
  assert.equal(t('explore.bookTitle', { name: 'Loft' }), 'Book Loft');
  assert.equal(t('does.not.exist'), 'does.not.exist');
  assert.equal(tRich('explore.title', { name: '<b>' }).value, 'Where to next, <em>&lt;b&gt;</em>?');
});

test('locale detection prefers storage, then browser languages, then English', () => {
  assert.equal(detectLocale('de', ['it-IT']), 'de');
  assert.equal(detectLocale(null, ['fr-FR', 'it-CH']), 'it');
  assert.equal(detectLocale('xx', ['fr-FR']), 'en');
});
