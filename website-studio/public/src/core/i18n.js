/**
 * Internationalisation: Italian, English and German.
 *
 * Messages are nested objects addressed with dot keys. Plural entries use the
 * CLDR categories returned by Intl.PluralRules ({ one, other }). Missing keys
 * fall back to English, then to the key itself so gaps are visible in the UI.
 */
import { escapeHtml, raw } from './html.js';
import en from '../i18n/en.js';
import it from '../i18n/it.js';
import de from '../i18n/de.js';

export const LOCALES = {
  it: { label: 'Italiano', short: 'IT', intl: 'it-IT', messages: it },
  en: { label: 'English', short: 'EN', intl: 'en-GB', messages: en },
  de: { label: 'Deutsch', short: 'DE', intl: 'de-DE', messages: de },
};

export const DEFAULT_LOCALE = 'en';
let current = DEFAULT_LOCALE;

export function detectLocale(stored, languages = globalThis.navigator?.languages ?? []) {
  if (typeof stored === 'string' && stored in LOCALES) return stored;
  for (const language of languages) {
    const base = String(language).slice(0, 2).toLowerCase();
    if (base in LOCALES) return base;
  }
  return DEFAULT_LOCALE;
}

export function setLocale(code) {
  if (code in LOCALES) current = code;
  return current;
}

export const getLocale = () => current;
export const intlLocale = () => LOCALES[current].intl;

function lookup(messages, key) {
  return key.split('.').reduce((node, part) => (node == null ? undefined : node[part]), messages);
}

export function has(key) {
  return lookup(LOCALES[current].messages, key) !== undefined || lookup(en, key) !== undefined;
}

export function t(key, params = {}) {
  let entry = lookup(LOCALES[current].messages, key) ?? lookup(en, key);
  if (entry && typeof entry === 'object' && 'other' in entry) {
    const category = new Intl.PluralRules(intlLocale()).select(Number(params.count ?? 0));
    entry = entry[category] ?? entry.other;
  }
  if (typeof entry !== 'string') return key;
  return entry.replace(/\{(\w+)\}/g, (match, name) => (name in params ? String(params[name]) : match));
}

/** Like `t`, but returns safe markup where *text* becomes an <em> accent. */
export function tRich(key, params) {
  return raw(escapeHtml(t(key, params)).replace(/\*(.+?)\*/g, '<em>$1</em>'));
}
