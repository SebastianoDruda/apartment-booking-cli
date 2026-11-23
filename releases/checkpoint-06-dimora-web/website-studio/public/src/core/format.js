/** Locale-aware formatting and calendar helpers. Dates are ISO strings (YYYY-MM-DD). */
import { intlLocale } from './i18n.js';

const DAY_MS = 86_400_000;

export function toIsoDate(date) {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

export const todayIso = (now = new Date()) => toIsoDate(now);

export function parseIso(iso) {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

export function addDays(iso, days) {
  const date = parseIso(iso);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function nightsBetween(start, end) {
  if (!start || !end) return 0;
  return Math.round((parseIso(end) - parseIso(start)) / DAY_MS);
}

/** Overlap in nights between [start, end) and [from, to). */
export function overlapNights(start, end, from, to) {
  const lower = start > from ? start : from;
  const upper = end < to ? end : to;
  return upper > lower ? nightsBetween(lower, upper) : 0;
}

export function stayStatus({ start, end }, today = todayIso()) {
  if (end <= today) return 'past';
  if (start <= today) return 'ongoing';
  return 'upcoming';
}

export const roundMoney = (value) => Math.round(value * 100) / 100;

export function formatMoney(value) {
  const whole = Number.isInteger(value);
  return new Intl.NumberFormat(intlLocale(), {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(value);
}

export function formatNumber(value) {
  return new Intl.NumberFormat(intlLocale()).format(value);
}

export function formatDate(iso, options = { day: 'numeric', month: 'short', year: 'numeric' }) {
  return new Intl.DateTimeFormat(intlLocale(), { ...options, timeZone: 'UTC' }).format(parseIso(iso));
}

export function formatRange(start, end) {
  const formatter = new Intl.DateTimeFormat(intlLocale(), {
    day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
  });
  if (typeof formatter.formatRange === 'function') {
    return formatter.formatRange(parseIso(start), parseIso(end));
  }
  return `${formatter.format(parseIso(start))} – ${formatter.format(parseIso(end))}`;
}

export function relativeDays(iso, today = todayIso()) {
  const diff = nightsBetween(today, iso);
  return new Intl.RelativeTimeFormat(intlLocale(), { numeric: 'auto' }).format(diff, 'day');
}

/** FNV-1a: stable hash used to give each apartment its own visual identity. */
export function hashString(value) {
  let hash = 2166136261;
  for (const char of String(value).toLowerCase()) {
    hash ^= char.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function initials(name = '') {
  return name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((word) => [...word][0]).join('').toUpperCase();
}

export const firstName = (name = '') => name.trim().split(/\s+/)[0] ?? '';

export const sameName = (a = '', b = '') =>
  a.trim().replace(/\s+/g, ' ').toLocaleLowerCase() === b.trim().replace(/\s+/g, ' ').toLocaleLowerCase();
